"""
EON Launcher.
"""

import threading
import time
from uuid import UUID

from src.bootstrap import ApplicationBuilder
from src.modules.voice.exceptions import VoiceError
from src.modules.voice.service import VoiceService

# msvcrt (Windows-only) lets us poll for a keypress without blocking,
# which is what makes "press Enter to interrupt" possible while EON is
# speaking. On non-Windows platforms this simply isn't available, so
# the keypress trigger is skipped there; barge-in via a repeated wake
# word still works everywhere.
try:
    import msvcrt
except ImportError:
    msvcrt = None


def _watch_for_interrupt_keypress(
    voice: VoiceService,
    stop_event: threading.Event,
) -> None:
    """Watches for a keypress and interrupts speech the moment one arrives.

    Runs on its own daemon thread for the duration of a single ``say``
    call. Exits as soon as either a key is pressed or ``stop_event`` is
    set (meaning playback already finished on its own).
    """
    while not stop_event.is_set():
        if msvcrt.kbhit():
            msvcrt.getch()  # consume the keystroke so it doesn't leak
            voice.interrupt_speaking()
            return
        time.sleep(0.05)


def speak_interruptibly(voice: VoiceService, session_id: UUID, text: str) -> None:
    """Speaks ``text``, allowing the user to cut it off early.

    Two ways to interrupt while EON is talking:
      - Press Enter (or any key), if running on Windows.
      - Say the wake word again (handled in ``on_wake_word`` below).
    """
    stop_event = threading.Event()
    watcher: threading.Thread | None = None

    if msvcrt is not None:
        watcher = threading.Thread(
            target=_watch_for_interrupt_keypress,
            args=(voice, stop_event),
            name="EON-InterruptWatcher",
            daemon=True,
        )
        watcher.start()

    try:
        voice.say(session_id, text)
    finally:
        stop_event.set()


def stream_conversation_reply(
    app,
    voice_session_id: UUID | None,
    voice_available: bool,
    user_message: str,
    reply_language_code: str | None = None,
) -> None:
    """Streams EON's reply instead of waiting for the full text.

    Prints each sentence to the console as soon as it's generated,
    and (if voice is available) speaks it right away too — so on a
    long reply, EON starts talking after the first sentence instead
    of sitting silent until the whole thing has been generated.

    Args:
        reply_language_code: The language Whisper detected for the
            user's *spoken* input this turn (from
            ``SpeechRecognitionResult.language_code``), if the message
            came in via ``listen``/wake word. Passed straight through
            to ``voice.say()``, which is what lets ``PiperProvider``
            pick the Hindi voice for a Hindi-dominant turn instead of
            always using the default English one. Left ``None`` for
            typed input — there's no spoken language to detect from
            typed text, so typed messages always get the default
            voice regardless of whether they're in Hindi/Hinglish.

    Barge-in still works the same way it did with a single blocking
    ``say`` call: one interrupt-watcher thread runs for the entire
    streamed reply, and as soon as any spoken sentence gets
    interrupted (keypress, or a repeated wake word handled by
    ``on_wake_word``), this stops feeding further sentences to the
    speaker instead of ploughing on through the rest of the reply.

    All of EON's usual history/memory-store side effects still happen
    exactly as they did before — they're handled inside
    ``ConversationManager.ask_stream`` once the full reply is known,
    not by this function.
    """
    from src.utils.text import detect_reply_language, iter_sentences

    print()
    print("EON:", end=" ", flush=True)

    stop_event = threading.Event()
    watcher: threading.Thread | None = None

    if voice_available and msvcrt is not None:
        watcher = threading.Thread(
            target=_watch_for_interrupt_keypress,
            args=(app.voice, stop_event),
            name="EON-InterruptWatcher",
            daemon=True,
        )
        watcher.start()

    if voice_available:
        app.hologram.set_speaking(True)

    try:
        for sentence in iter_sentences(app.conversation.ask_stream(user_message)):
            print(sentence, end=" ", flush=True)

            if not voice_available:
                continue

            try:
                sentence_language = detect_reply_language(sentence) or reply_language_code
                app.voice.say(voice_session_id, sentence, language_code=sentence_language)
            except VoiceError as exc:
                print(f"\n[speak failed: {exc}]")
                break

            if app.voice.was_interrupted():
                # A barge-in cut this sentence off — stop here instead
                # of continuing to speak the rest of the reply right
                # after the user deliberately interrupted it.
                break
    finally:
        if voice_available:
            app.hologram.set_speaking(False)
        stop_event.set()
        print()


def main() -> None:
    builder = ApplicationBuilder()
    app = builder.build()

    if app.hologram.is_running:
        # Qt's event loop needs to run on the process's actual main
        # thread for the overlay to reliably paint (see the docstring
        # in DesktopCompanionService for why) — so when the hologram is
        # active, the console/voice loop moves to its own background
        # thread instead, and this thread blocks in Qt's event loop
        # until that thread finishes (typing 'exit' triggers
        # engine.shutdown(), which quits the Qt app, which is what
        # makes run_event_loop() below return).
        console_thread = threading.Thread(
            target=_run_console,
            args=(app,),
            name="EON-Console",
            daemon=True,
        )
        console_thread.start()
        app.hologram.run_event_loop()
        console_thread.join(timeout=5.0)
    else:
        _run_console(app)


def _run_console(app) -> None:
    voice_session_id = None
    voice_available = False
    wake_word_available = False

    def on_wake_word(is_owner: bool) -> None:
        """Runs a hands-free conversation after the wake word.

        Enters conversation mode: EON listens, replies, and keeps
        listening for follow-up turns without the wake word again,
        until the user goes quiet for the configured idle timeout or
        says an exit phrase (see ``VoiceService.run_conversation``).

        Called on the wake-word listener's background thread, so this
        may print output that interleaves with the console prompt if
        it fires while the user is mid-type at the ``input()`` prompt.

        Args:
            is_owner: Whether the audio that triggered the wake word
                also matched the enrolled owner's voiceprint (see
                ``VoiceService.enroll_speaker``). EON still answers
                either way — this only gates the personalized
                "Welcome back" greeting, not whether it responds.
        """
        if app.voice.is_speaking:
            # Barge-in: the user said "EON" again while a previous
            # response was still playing. Cut it off immediately
            # instead of letting it finish or talking over it.
            print()
            print("[wake word] Interrupting...")
            app.voice.interrupt_speaking()

        print()

        if is_owner:
            print("[wake word] Owner's voice recognized.")
            try:
                app.voice.say(voice_session_id, "Welcome back, sir.")
            except VoiceError as exc:
                print(f"[greeting failed: {exc}]")

        print("[wake word] Listening...")

        def on_utterance(text: str, language_code: str | None) -> None:
            print(f"You said: {text}")

            stream_conversation_reply(
                app, voice_session_id, voice_available, text,
                reply_language_code=language_code,
            )

            app.proactive.notify_interaction()

        try:
            turns = app.voice.run_conversation(voice_session_id, on_utterance)
        except VoiceError as exc:
            print(f"[listen failed: {exc}]")
            return

        if turns == 0:
            print("[wake word] Didn't catch anything, going back to sleep.")

    try:
        session = app.voice.start_session()
        voice_session_id = session.session_id
        voice_available = True
    except Exception as exc:
        print(f"[voice unavailable, continuing in text-only mode: {exc}]")

    if voice_available:
        try:
            app.voice.start_wake_word_listening(on_detected=on_wake_word)
            wake_word_available = True
        except Exception as exc:
            print(f"[wake word listening unavailable: {exc}]")

    print()
    print("===================================")
    print("      EON Interactive Console")
    print("Type 'exit' to quit.")

    if voice_available:
        print("Type 'listen' to speak your message via microphone instead of typing.")

    if wake_word_available:
        print("Say 'EON' at any time to activate hands-free listening.")
        print("Say 'EON' again while EON is speaking to interrupt it.")

    if voice_available:
        print("Type 'enroll voice' to teach EON to recognize your voice.")

    if voice_available and msvcrt is not None:
        print("Press Enter while EON is speaking to interrupt it.")

    print("Type 'remind <minutes> <message>' to schedule a spoken reminder.")

    if app.proactive.health_check():
        print("EON may also speak up on its own after a quiet stretch.")

    if app.hologram.is_running:
        print("The hologram overlay is active in the corner of your screen.")

    print("===================================")

    try:
        while True:

            print()

            prompt = "You (or 'listen'): " if voice_available else "You: "
            raw = input(prompt).strip()

            if not raw:
                continue

            if raw.lower() in ("exit", "quit"):
                print("EON: Goodbye!")
                break

            if raw.lower().startswith("remind "):
                # Demo hook for Proactive Speech: "remind 0.5 stretch your legs"
                _, _, rest = raw.partition(" ")
                minutes_str, _, message = rest.partition(" ")

                try:
                    minutes = float(minutes_str)
                except ValueError:
                    print("[usage: remind <minutes> <message>]")
                    continue

                if not message:
                    print("[usage: remind <minutes> <message>]")
                    continue

                app.proactive.remind_in(message, minutes)
                print(f"[reminder set for {minutes} minute(s) from now]")
                continue

            if voice_available and raw.lower() in ("enroll voice", "enroll"):
                print(
                    f"Say a sentence or two out loud — recording for "
                    f"{app.voice.speaker_enroll_seconds:.0f} seconds..."
                )
                try:
                    app.voice.enroll_speaker()
                except VoiceError as exc:
                    print(f"[enrollment failed: {exc}]")
                except ValueError as exc:
                    print(f"[enrollment failed: {exc}] Try again with clearer speech.")
                else:
                    print("[voice enrolled — say 'EON' and I'll recognize you next time]")
                continue

            spoken_language_code = None

            if voice_available and raw.lower() == "listen":
                print("Listening...")

                try:
                    result = app.voice.listen_once(voice_session_id)
                    user_message = result.transcript
                    spoken_language_code = result.language_code
                    print(f"You said: {user_message}")
                except VoiceError as exc:
                    print(f"[listen failed: {exc}]")
                    continue

            else:
                user_message = raw

            if not user_message:
                continue

            stream_conversation_reply(
                app, voice_session_id, voice_available, user_message,
                reply_language_code=spoken_language_code,
            )

            app.proactive.notify_interaction()

    finally:
        if wake_word_available:
            try:
                app.voice.stop_wake_word_listening()
            except Exception:
                pass

        if voice_available and voice_session_id is not None:
            try:
                app.voice.stop_session(voice_session_id)
            except Exception:
                pass

        app.engine.shutdown()


if __name__ == "__main__":
    main()
