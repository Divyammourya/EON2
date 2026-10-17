"""
EON Launcher.
"""

import threading
import time
from uuid import UUID

from src.bootstrap import ApplicationBuilder
from src.modules.voice.exceptions import VoiceError
from src.modules.voice.service import VoiceService
from src.modules.workspace.workspaces.coding.mode import parse_coding_request

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


def _speak_morning_briefing(app, voice_session_id: UUID | None) -> None:
    """Speaks the first-of-the-day weather briefing, if one is due.

    Does nothing outside the configured morning window, on a second
    launch the same day, or when the weather service can't be reached â€”
    ``MorningBriefing.greeting`` decides all of that and returns
    ``None`` when there is nothing to say.

    Args:
        app: The running application.
        voice_session_id: The open voice session to speak through.
    """
    try:
        briefing = app.briefing.greeting()
    except Exception as exc:
        # A briefing is a nicety. It must never be what stops EON
        # starting up.
        print(f"[briefing skipped: {exc}]")
        return

    if not briefing:
        return

    print()
    print(f"EON: {briefing}")

    try:
        speak_interruptibly(app.voice, voice_session_id, briefing)
    except VoiceError as exc:
        print(f"[briefing failed: {exc}]")


def stream_conversation_reply(
    app,
    voice_session_id: UUID | None,
    voice_available: bool,
    user_message: str,
    reply_language_code: str | None = None,
) -> None:
    """Streams EON's reply instead of waiting for the full text.

    Prints each sentence to the console as soon as it's generated,
    and (if voice is available) speaks it right away too â€” so on a
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
            typed input â€” there's no spoken language to detect from
            typed text, so typed messages always get the default
            voice regardless of whether they're in Hindi/Hinglish.

    Barge-in still works the same way it did with a single blocking
    ``say`` call: one interrupt-watcher thread runs for the entire
    streamed reply, and as soon as any spoken sentence gets
    interrupted (keypress, or a repeated wake word handled by
    ``on_wake_word``), this stops feeding further sentences to the
    speaker instead of ploughing on through the rest of the reply.

    All of EON's usual history/memory-store side effects still happen
    exactly as they did before â€” they're handled inside
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
                # A barge-in cut this sentence off â€” stop here instead
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

    if app.hologram.is_running or app.coding_window.is_running:
        # Qt's event loop needs to run on the process's actual main
        # thread for the overlay to reliably paint (see the docstring
        # in DesktopCompanionService for why) â€” so when the hologram is
        # active, the console/voice loop moves to its own background
        # thread instead, and this thread blocks in Qt's event loop
        # until that thread finishes (typing 'exit' triggers
        # engine.shutdown(), which quits the Qt app, which is what
        # makes run_event_loop() below return).
        #
        # The coding window needs the same arrangement, for the same
        # reason, even when the overlay is off: a blocking input() on
        # the thread owning Qt would freeze the window while you type.
        console_thread = threading.Thread(
            target=_run_console,
            args=(app,),
            name="EON-Console",
            daemon=True,
        )
        console_thread.start()

        if app.hologram.is_running:
            # One QApplication, one event loop â€” this serves the
            # coding window too when both are up.
            app.hologram.run_event_loop()
        else:
            app.coding_window.run_event_loop()

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
        it fires while the user is mid-typing at the ``input()`` prompt.

        Args:
            is_owner: Whether the audio that triggered the wake word
                also matched the enrolled owner's voiceprint (see
                ``VoiceService.enroll_speaker``)¤=8ÍÑ¥±°…¹ÍÝ•ÉÌ(€€€€€€€€€€€€€€€•¥Ñ¡•ÈÝ…äƒŠPÑ¡¥Ì½¹±ä…Ñ•ÌÑ¡”Á•ÉÍ½¹…±¥é•(€€€€€€€€€€€€€€€€‰]•±½µ”‰…¬ˆÉ••Ñ¥¹œ°¹½ÐÝ¡•Ñ¡•È¥ÐÉ•ÍÁ½¹‘Ì¸(€€€€€€€€ˆˆˆ(€€€€€€€¥˜…ÁÀ¹Ù½¥”¹¥Í}ÍÁ•…­¥¹œè(€€€€€€€€€€€€Œ	…É”µ¥¸èÑ¡”ÕÍ•ÈÍ…¥€‰=8ˆ……¥¸Ý¡¥±”„ÁÉ•Ù¥½ÕÌ(€€€€€€€€€€€€ŒÉ•ÍÁ½¹Í”Ý…ÌÍÑ¥±°Á±…å¥¹œ¸ÕÐ¥Ð½™˜¥µµ•‘¥…Ñ•±ä(€€€€€€€€€€€€Œ¥¹ÍÑ•…½˜±•ÑÑ¥¹œ¥Ð™¥¹¥Í ½ÈÑ…±­¥¹œ½Ù•È¥Ð¸(€€€€€€€€€€€ÁÉ¥¹Ð ¤(€€€€€€€€€€€ÁÉ¥¹Ð ‰mÝ…­”Ý½É‘t%¹Ñ•ÉÉÕÁÑ¥¹œ¸¸¸ˆ¤(€€€€€€€€€€€…ÁÀ¹Ù½¥”¹¥¹Ñ•ÉÉÕÁÑ}ÍÁ•…­¥¹œ ¤((€€€€€€€ÁÉ¥¹Ð ¤((€€€€€€€¥˜¥Í}½Ý¹•Èè(€€€€€€€€€€€ÁÉ¥¹Ð ‰mÝ…­”Ý½É‘t=Ý¹•ÈÌÙ½¥”É•½¹¥é•¸ˆ¤(€€€€€€€€€€€ÑÉäè(€€€€€€€€€€€€€€€…ÁÀ¹Ù½¥”¹Í…ä¡Ù½¥•}Í•ÍÍ¥½¹}¥°€‰]•±½µ”‰…¬°Í¥È¸ˆ¤(€€€€€€€€€€€•á•ÁÐY½¥•ÉÉ½È…Ì•áŒè(€€€€€€€€€€€€€€€ÁÉ¥¹Ð¡˜‰mÉ••Ñ¥¹œ™…¥±•èí•áõtˆ¤((€€€€€€€ÁÉ¥¹Ð ‰mÝ…­”Ý½É‘t1¥ÍÑ•¹¥¹œ¸¸¸ˆ¤((€€€€€€€‘•˜½¹}ÕÑÑ•É…¹”¡Ñ•áÐèÍÑÈ°±…¹Õ…•}½‘”èÍÑÈð9½¹”¤€´ø9½¹”è(€€€€€€€€€€€ÁÉ¥¹Ð¡˜‰e½ÔÍ…¥èíÑ•áÑôˆ¤((€€€€€€€€€€€ÍÑÉ•…µ}½¹Ù•ÉÍ…Ñ¥½¹}É•Á±ä (€€€€€€€€€€€€€€€…ÁÀ°Ù½¥•}Í•ÍÍ¥½¹}¥°Ù½¥•}…Ù…¥±…‰±”°Ñ•áÐ°(€€€€€€€€€€€€€€€É•Á±å}±…¹Õ…•}½‘”õ±…¹Õ…•}½‘”°(€€€€€€€€€€€€¤((€€€€€€€€€€€…ÁÀ¹ÁÉ½…Ñ¥Ù”¹¹½Ñ¥™å}¥¹Ñ•É…Ñ¥½¸ ¤((€€€€€€€ÑÉäè(€€€€€€€€€€€ÑÕÉ¹Ì€ô…ÁÀ¹Ù½¥”¹ÉÕ¹}½¹Ù•ÉÍ…Ñ¥½¸¡Ù½¥•}Í•ÍÍ¥½¹}¥°½¹}ÕÑÑ•É…¹”¤(€€€€€€€•á•ÁÐY½¥•ÉÉ½È…Ì•áŒè(€€€€€€€€€€€ÁÉ¥¹Ð¡˜‰m±¥ÍÑ•¸™…¥±•èí•áõtˆ¤(€€€€€€€€€€€É•ÑÕÉ¸((€€€€€€€¥˜ÑÕÉ¹Ì€ôô€Àè(€€€€€€€€€€€ÁÉ¥¹Ð ‰mÝ…­”Ý½É‘t¥‘¸Ð…Ñ …¹åÑ¡¥¹œ°½¥¹œ‰…¬Ñ¼Í±••À¸ˆ¤((€€€ÑÉäè(€€€€€€€Í•ÍÍ¥½¸€ô…ÁÀ¹Ù½¥”¹ÍÑ…ÉÑ}Í•ÍÍ¥½¸ ¤(€€€€€€€Ù½¥•}Í•ÍÍ¥½¹}¥€ôÍ•ÍÍ¥½¸¹Í•ÍÍ¥½¹}¥(€€€€€€€Ù½¥•}…Ù…¥±…‰±”€ôQÉÕ”(€€€•á•ÁÐá•ÁÑ¥½¸…Ì•áŒè(€€€€€€€ÁÉ¥¹Ð¡˜‰mÙ½¥”Õ¹…Ù…¥±…‰±”°½¹Ñ¥¹Õ¥¹œ¥¸Ñ•áÐµ½¹±äµ½‘”èí•áõtˆ¤((€€€¥˜Ù½¥•}…Ù…¥±…‰±”è(€€€€€€€ÑÉäè(€€€€€€€€€€€…ÁÀ¹Ù½¥”¹ÍÑ…ÉÑ}Ý…­•}Ý½É‘}±¥ÍÑ•¹¥¹œ¡½¹}‘•Ñ•Ñ•õ½¹}Ý…­•}Ý½É¤(€€€€€€€€€€€Ý…­•}Ý½É‘}…Ù…¥±…‰±”€ôQÉÕ”(€€€€€€€•á•ÁÐá•ÁÑ¥½¸…Ì•áŒè(€€€€€€€€€€€ÁÉ¥¹Ð¡˜‰mÝ…­”Ý½É±¥ÍÑ•¹¥¹œÕ¹…Ù…¥±…‰±”èí•áõtˆ¤((€€€ÁÉ¥¹Ð ¤(€€€ÁÉ¥¹Ð ˆôôôôôôôôôôôôôôôôôôôôôôôôôôôôôôôôôôôˆ¤(€€€ÁÉ¥¹Ð ˆ€€€€€=8%¹Ñ•É…Ñ¥Ù”½¹Í½±”ˆ¤(€€€ÁÉ¥¹Ð ‰QåÁ”€•á¥ÐœÑ¼ÅÕ¥Ð¸ˆ¤((€€€¥˜Ù½¥•}…Ù…¥±…‰±”è(€€€€€€€ÁÉ¥¹Ð ‰QåÁ”€±¥ÍÑ•¸œÑ¼ÍÁ•…¬å½ÕÈµ•ÍÍ…”Ù¥„µ¥É½Á¡½¹”¥¹ÍÑ•…½˜ÑåÁ¥¹œ¸ˆ¤((€€€¥˜Ý…­•}Ý½É‘}…Ù…¥±…‰±”è(€€€€€€€ÁÉ¥¹Ð ‰M…ä€=8œ…Ð…¹äÑ¥µ”Ñ¼…Ñ¥Ù…Ñ”¡…¹‘Ìµ™É•”±¥ÍÑ•¹¥¹œ¸ˆ¤(€€€€€€€ÁÉ¥¹Ð ‰M…ä€=8œ……¥¸Ý¡¥±”=8¥ÌÍÁ•…­¥¹œÑ¼¥¹Ñ•ÉÉÕÁÐ¥Ð¸ˆ¤((€€€¥˜Ù½¥•}…Ù…¥±…‰±”è(€€€€€€€ÁÉ¥¹Ð ‰QåÁ”€•¹É½±°Ù½¥”œÑ¼Ñ•… =8Ñ¼É•½¹¥é”å½ÕÈÙ½¥”¸ˆ¤((€€€¥˜Ù½¥•}…Ù…¥±…‰±”…¹µÍÙÉÐ¥Ì¹½Ð9½¹”è(€€€€€€€ÁÉ¥¹Ð ‰AÉ•ÍÌ¹Ñ•ÈÝ¡¥±”=8¥ÌÍÁ•…­¥¹œÑ¼¥¹Ñ•ÉÉÕÁÐ¥Ð¸ˆ¤((€€€ÁÉ¥¹Ð ‰QåÁ”€É•µ¥¹€ñµ¥¹ÕÑ•Ìø€ñµ•ÍÍ…”øœÑ¼Í¡•‘Õ±”„ÍÁ½­•¸É•µ¥¹‘•È¸ˆ¤((€€€¥˜…ÁÀ¹ÁÉ½…Ñ¥Ù”¹¡•…±Ñ¡}¡•¬ ¤è(€€€€€€€ÁÉ¥¹Ð ‰=8µ…ä…±Í¼ÍÁ•…¬ÕÀ½¸¥ÑÌ½Ý¸…™Ñ•È„ÅÕ¥•ÐÍÑÉ•Ñ ¸ˆ¤((€€€¥˜…ÁÀ¹¡½±½É…´¹¥Í}ÉÕ¹¹¥¹œè(€€€€€€€ÁÉ¥¹Ð ‰Q¡”¡½±½É…´½Ù•É±…ä¥Ì…Ñ¥Ù”¥¸Ñ¡”½É¹•È½˜å½ÕÈÍÉ••¸¸ˆ¤((€€€ÁÉ¥¹Ð ˆôôôôôôôôôôôôôôôôôôôôôôôôôôôôôôôôôôôˆ¤((€€€¥˜Ù½¥•}…Ù…¥±…‰±”è(€€€€€€€}ÍÁ•…­}µ½É¹¥¹}‰É¥•™¥¹œ¡…ÁÀ°Ù½¥•}Í•ÍÍ¥½¹}¥¤((€€€ÑÉäè(€€€€€€€Ý¡¥±”QÉÕ”è((€€€€€€€€€€€ÁÉ¥¹Ð ¤((€€€€€€€€€€€¥˜…ÁÀ¹½‘¥¹œ¹…Ñ¥Ù”è(€€€€€€€€€€€€€€€Í•ÍÍ¥½¸€ô…ÁÀ¹½‘¥¹œ¹Í•ÍÍ¥½¸(€€€€€€€€€€€€€€€¹…µ”€ôÍ•ÍÍ¥½¸¹¹…µ”¥˜Í•ÍÍ¥½¸¥Ì¹½Ð9½¹”•±Í”€ˆüˆ(€€€€€€€€€€€€€€€ÁÉ½µÁÐ€ô˜‰½‘¥¹mí¹…µ•õtø€ˆ(€€€€€€€€€€€•±Í”è(€€€€€€€€€€€€€€€ÁÉ½µÁÐ€ô€‰e½Ô€¡½È€±¥ÍÑ•¸œ¤è€ˆ¥˜Ù½¥•}…Ù…¥±…‰±”•±Í”€‰e½Ôè€ˆ((€€€€€€€€€€€É…Ü€ô¥¹ÁÕÐ¡ÁÉ½µÁÐ¤¹ÍÑÉ¥À ¤((€€€€€€€€€€€¥˜¹½ÐÉ…Üè(€€€€€€€€€€€€€€€½¹Ñ¥¹Õ”((€€€€€€€€€€€€Œ€•á¥Ðœ¼ÅÕ¥Ðœµ•…¸ÅÕ¥Ð=8¥¸•¥Ñ¡•Èµ½‘”ƒŠP±•…Ù¥¹œ(€€€€€€€€€€€€Œ½‘¥¹œµ½‘”¥Ì€‘½¹”œ¸(€€€€€€€€€€€¥˜É…Ü¹±½Ý•È ¤¥¸€ ‰•á¥Ðˆ°€‰ÅÕ¥Ðˆ¤è(€€€€€€€€€€€€€€€ÁÉ¥¹Ð ‰=8è½½‘‰å”„ˆ¤(€€€€€€€€€€€€€€€‰É•…¬((€€€€€€€€€€€¥˜…ÁÀ¹½‘¥¹œ¹…Ñ¥Ù”è(€€€€€€€€€€€€€€€€ŒÙ•ÉåÑ¡¥¹œÑåÁ•¥¸½‘¥¹œµ½‘”½•ÌÑ¼Ñ¡”½‘¥¹œ(€€€€€€€€€€€€€€€€ŒÝ½É­ÍÁ…”°¹½ÐÑ¼Ñ¡”¡…Ð‰É…¥¸¸M•”½‘¥¹5½‘”™½È(€€€€€€€€€€€€€€€€ŒÝ¡ä½µµ…¹‘Ì…É”…Ñ•…¹™¥±”ÝÉ¥Ñ•Ì…É”¹½Ð¸(€€€€€€€€€€€€€€€É•Á±ä€ô…ÁÀ¹½‘¥¹œ¹¡…¹‘±”¡É…Ü¤((€€€€€€€€€€€€€€€¥˜É•Á±äè(€€€€€€€€€€€€€€€€€€€ÁÉ¥¹Ð ¤(€€€€€€€€€€€€€€€€€€€ÁÉ¥¹Ð¡˜‰=8èíÉ•Á±åôˆ¤((€€€€€€€€€€€€€€€½¹Ñ¥¹Õ”((€€€€€€€€€€€½‘¥¹}É•ÅÕ•ÍÐ€ôÁ…ÉÍ•}½‘¥¹}É•ÅÕ•ÍÐ¡É…Ü¤((€€€€€€€€€€€¥˜½‘¥¹}É•ÅÕ•ÍÐ¥Ì¹½Ð9½¹”è(€€€€€€€€€€€€€€€É•Á±ä€ô…ÁÀ¹½‘¥¹œ¹•¹Ñ•È¡½‘¥¹}É•ÅÕ•ÍÐ¹ÁÉ½©•Ð¤((€€€€€€€€€€€€€€€ÁÉ¥¹Ð ¤(€€€€€€€€€€€€€€€ÁÉ¥¹Ð¡˜‰=8èíÉ•Á±åôˆ¤((€€€€€€€€€€€€€€€½¹Ñ¥¹Õ”((€€€€€€€€€€€¥˜É…Ü¹±½Ý•È ¤¹ÍÑ…ÉÑÍÝ¥Ñ  ‰É•µ¥¹€ˆ¤è(€€€€€€€€€€€€€€€€Œ•µ¼¡½½¬™½ÈAÉ½…Ñ¥Ù”MÁ•• è€‰É•µ¥¹€À¸ÔÍÑÉ•Ñ å½ÕÈ±•Ìˆ(€€€€€€€€€€€€€€€|°|°É•ÍÐ€ôÉ…Ü¹Á…ÉÑ¥Ñ¥½¸ ˆ€ˆ¤(€€€€€€€€€€€€€€€µ¥¹ÕÑ•Í}ÍÑÈ°|°µ•ÍÍ…”€ôÉ•ÍÐ¹Á…ÉÑ¥Ñ¥½¸ ˆ€ˆ¤((€€€€€€€€€€€€€€€ÑÉäè(€€€€€€€€€€€€€€€€€€€µ¥¹ÕÑ•Ì€ô™±½…Ð¡µ¥¹ÕÑ•Í}ÍÑÈ¤(€€€€€€€€€€€€€€€•á•ÁÐY…±Õ•ÉÉ½Èè(€€€€€€€€€€€€€€€€€€€ÁÉ¥¹Ð ‰mÕÍ…”èÉ•µ¥¹€ñµ¥¹ÕÑ•Ìø€ñµ•ÍÍ…”ùtˆ¤(€€€€€€€€€€€€€€€€€€€½¹Ñ¥¹Õ”((€€€€€€€€€€€€€€€¥˜¹½Ðµ•ÍÍ…”è(€€€€€€€€€€€€€€€€€€€ÁÉ¥¹Ð ‰mÕÍ…”èÉ•µ¥¹€ñµ¥¹ÕÑ•Ìø€ñµ•ÍÍ…”ùtˆ¤(€€€€€€€€€€€€€€€€€€€½¹Ñ¥¹Õ”((€€€€€€€€€€€€€€€…ÁÀ¹ÁÉ½…Ñ¥Ù”¹É•µ¥¹‘}¥¸¡µ•ÍÍ…”°µ¥¹ÕÑ•Ì¤(€€€€€€€€€€€€€€€ÁÉ¥¹Ð¡˜‰mÉ•µ¥¹‘•ÈÍ•Ð™½Èíµ¥¹ÕÑ•Íôµ¥¹ÕÑ”¡Ì¤™É½´¹½Ýtˆ¤(€€€€€€€€€€€€€€€½¹Ñ¥¹Õ”((€€€€€€€€€€€¥˜Ù½¥•}…Ù…¥±…‰±”…¹É…Ü¹±½Ý•È ¤¥¸€ ‰•¹É½±°Ù½¥”ˆ°€‰•¹É½±°ˆ¤è(€€€€€€€€€€€€€€€ÁÉ¥¹Ð (€€€€€€€€€€€€€€€€€€€˜‰M…ä„Í•¹Ñ•¹”½ÈÑÝ¼½ÕÐ±½ÕƒŠPÉ•½É‘¥¹œ™½È€ˆ(€€€€€€€€€€€€€€€€€€€˜‰í…ÁÀ¹Ù½¥”¹ÍÁ•…­•É}•¹É½±±}Í•½¹‘Ìè¸Á™ôÍ•½¹‘Ì¸¸¸ˆ(€€€€€€€€€€€€€€€€¤(€€€€€€€€€€€€€€€ÑÉäè(€€€€€€€€€€€€€€€€€€€…ÁÀ¹Ù½¥”¹•¹É½±±}ÍÁ•…­•È ¤(€€€€€€€€€€€€€€€•á•ÁÐY½¥•ÉÉ½È…Ì•áŒè(€€€€€€€€€€€€€€€€€€€ÁÉ¥¹Ð¡˜‰m•¹É½±±µ•¹Ð™…¥±•èí•áõtˆ¤(€€€€€€€€€€€€€€€•á•ÁÐY…±Õ•ÉÉ½È…Ì•áŒè(€€€€€€€€€€€€€€€€€€€ÁÉ¥¹Ð¡˜‰m•¹É½±±µ•¹Ð™…¥±•èí•áõtQÉä……¥¸Ý¥Ñ ±•…É•ÈÍÁ•• ¸ˆ¤(€€€€€€€€€€€€€€€•±Í”è(€€€€€€€€€€€€€€€€€€€ÁÉ¥¹Ð ‰mÙ½¥”•¹É½±±•ƒŠPÍ…ä€=8œ…¹$±°É•½¹¥é”å½Ô¹•áÐÑ¥µ•tˆ¤(€€€€€€€€€€€€€€€½¹Ñ¥¹Õ”((€€€€€€€€€€€ÍÁ½­•¹}±…¹Õ…•}½‘”€ô9½¹”((€€€€€€€€€€€¥˜Ù½¥•}…Ù…¥±…‰±”…¹É…Ü¹±½Ý•È ¤€ôô€‰±¥ÍÑ•¸ˆè(€€€€€€€€€€€€€€€ÁÉ¥¹Ð ‰1¥ÍÑ•¹¥¹œ¸¸¸ˆ¤((€€€€€€€€€€€€€€€ÑÉäè(€€€€€€€€€€€€€€€€€€€É•ÍÕ±Ð€ô…ÁÀ¹Ù½¥”¹±¥ÍÑ•¹}½¹”¡Ù½¥•}Í•ÍÍ¥½¹}¥¤(€€€€€€€€€€€€€€€€€€€ÕÍ•É}µ•ÍÍ…”€ôÉ•ÍÕ±Ð¹ÑÉ…¹ÍÉ¥ÁÐ(€€€€€€€€€€€€€€€€€€€ÍÁ½­•¹}±…¹Õ…•}½‘”€ôÉ•ÍÕ±Ð¹±…¹Õ…•}½‘”(€€€€€€€€€€€€€€€€€€€ÁÉ¥¹Ð¡˜‰e½ÔÍ…¥èíÕÍ•É}µ•ÍÍ…•ôˆ¤(€€€€€€€€€€€€€€€•á•ÁÐY½¥•ÉÉ½È…Ì•áŒè(€€€€€€€€€€€€€€€€€€€ÁÉ¥¹Ð¡˜‰m±¥ÍÑ•¸™…¥±•èí•áõtˆ¤(€€€€€€€€€€€€€€€€€€€½¹Ñ¥¹Õ”((€€€€€€€€€€€•±Í”è(€€€€€€€€€€€€€€€ÕÍ•É}µ•ÍÍ…”€ôÉ…Ü((€€€€€€€€€€€¥˜¹½ÐÕÍ•É}µ•ÍÍ…”è(€€€€€€€€€€€€€€€½¹Ñ¥¹Õ”((€€€€€€€€€€€ÍÑÉ•…µ}½¹Ù•ÉÍ…Ñ¥½¹}É•Á±ä (€€€€€€€€€€€€€€€…ÁÀ°Ù½¥•}Í•ÍÍ¥½¹}¥°Ù½¥•}…Ù…¥±…‰±”°ÕÍ•É}µ•ÍÍ…”°(€€€€€€€€€€€€€€€É•Á±å}±…¹Õ…•}½‘”õÍÁ½­•¹}±…¹Õ…•}½‘”°(€€€€€€€€€€€€¤((€€€€€€€€€€€…ÁÀ¹ÁÉ½…Ñ¥Ù”¹¹½Ñ¥™å}¥¹Ñ•É…Ñ¥½¸ ¤((€€€™¥¹…±±äè(€€€€€€€¥˜Ý…­•}Ý½É‘}…Ù…¥±…‰±”è(€€€€€€€€€€€ÑÉäè(€€€€€€€€€€€€€€€…ÁÀ¹Ù½¥”¹ÍÑ½Á}Ý…­•}Ý½É‘}±¥ÍÑ•¹¥¹œ ¤(€€€€€€€€€€€•á•ÁÐá•ÁÑ¥½¸è(€€€€€€€€€€€€€€€Á…ÍÌ((€€€€€€€¥˜Ù½¥•}…Ù…¥±…‰±”…¹Ù½¥•}Í•ÍÍ¥½¹}¥¥Ì¹½Ð9½¹”è(€€€€€€€€€€€ÑÉäè(€€€€€€€€€€€€€€€…ÁÀ¹Ù½¥”¹ÍÑ½Á}Í•ÍÍ¥½¸¡Ù½¥•}Í•ÍÍ¥½¹}¥¤(€€€€€€€€€€€•á•ÁÐá•ÁÑ¥½¸è(€€€€€€€€€€€€€€€Á…ÍÌ((€€€€€€€€Œ=É‘•Èµ…ÑÑ•ÉÌ¡•É”°…¹¥Ð¥ÌÝ¡…Ðµ…‘”•á¥Ñ€¡…¹œ‰•™½É”¸(€€€€€€€€Œ(€€€€€€€€ŒQ¡”½¹Í½±”¥Ì¹½ÐÑ¡”Ñ¡É•…Ñ¡…Ð½Ý¹ÌEÐ°Í¼•Ù•Éä½¹”½˜(€€€€€€€€ŒÑ¡•Í”¡…ÌÑ¼¼Ñ¡É½Õ Ñ¡”Ý¥¹‘½ÜÌÍ¥¹…°‰É¥‘”É…Ñ¡•È(€€€€€€€€ŒÑ¡…¸Ñ½Õ¡¥¹œ„Ý¥‘•Ð½ÈÑ¡”•Ù•¹Ð±½½À‘¥É•Ñ±ä¸¹EÐ¡…Ì(€€€€€€€€ŒÑ¼‰”ÅÕ¥Ð€©±…ÍÐ¨èÍ¡ÕÑÑ¥¹œÑ¡”•¹¥¹”‘½Ý¸¥¹±Õ‘•ÌÑ¡”(€€€€€€€€Œ¡½±½É…´½Ù•É±…ä°Ý¡½Í”½Ý¸Ñ•…É‘½Ý¸ÍÑ¥±°¹••‘Ì„±¥Ù”•Ù•¹Ð(€€€€€€€€Œ±½½ÀÑ¼‰”‘•±¥Ù•É•Ñ¡É½Õ ¸EÕ¥ÑÑ¥¹œ™¥ÉÍÐ±•™ÐÑ¡…ÐÝ½É¬(€€€€€€€€ŒÅÕ•Õ•Ý¥Ñ ¹½Ñ¡¥¹œ±•™ÐÑ¼ÉÕ¸¥Ð¸(€€€€€€€…ÁÀ¹½‘¥¹}Ý¥¹‘½Ü¹±½Í•}Ý¥¹‘½Ü ¤((€€€€€€€…ÁÀ¹•¹¥¹”¹Í¡ÕÑ‘½Ý¸ ¤((€€€€€€€€ŒEÕ¥ÑÌEÐ°Í¼Ñ¡”•Ù•¹Ð±½½À…‰½Ù”É•ÑÕÉ¹Ì¸!…Éµ±•ÍÌÝ¡•¸Ñ¡”(€€€€€€€€Œ½Ù•É±…ä¡…Ì…±É•…‘äÅÕ¥Ð¥Ð¸(€€€€€€€…ÁÀ¹½‘¥¹}Ý¥¹‘½Ü¹ÍÑ½À ¤(()¥˜}}¹…µ•}|€ôô€‰}}µ…¥¹}|ˆè(€€€µ…¥¸ ¤(