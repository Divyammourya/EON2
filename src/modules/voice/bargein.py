"""Voice barge-in: let the user interrupt EON just by starting to talk.

Design notes:
    - EON already has two ways to cut off a reply: pressing a key, and
      saying the wake word again. This adds a third, more natural one —
      the user simply starts speaking and EON stops and listens.
    - Detection is energy-based (RMS over short windows), not a full
      speech-to-text pass. Running STT continuously during playback
      would be expensive and would mostly transcribe EON's own output.
    - IMPORTANT: this is *not* echo-cancelled. EON's voice comes out of
      the speakers and the microphone hears it, so with a loud speaker
      or a sensitive mic EON may interrupt itself. Raise
      ``barge_in_energy_threshold`` until that stops, or set
      ``barge_in_enabled`` to False. The proper fix is acoustic echo
      cancellation, which is out of scope here.
    - Runs on its own daemon thread for the duration of one playback
      call, reading the shared microphone under the same lock the other
      readers use. The caller is responsible for pausing the wake-word
      listener so only one reader drives the microphone at a time.

Requires: Python 3.12+
"""

from __future__ import annotations

import threading
from collections.abc import Callable

from src.core.logger import get_logger
from src.modules.voice.exceptions import VoiceError
from src.modules.voice.microphone import Microphone
from src.utils.audio import BYTES_PER_SAMPLE, rms_pcm

logger = get_logger("BargeIn")

# How long to wait before retrying after a transient microphone failure.
_RETRY_INTERVAL_SECONDS = 0.05


class BargeInDetector:
    """Pure decision logic: has the user spoken long enough to interrupt?

    Feed it one observation per captured frame; it returns ``True`` the
    first time enough speech has been seen, and ``False`` on every other
    call.

    Short dips do *not* reset the run, because real speech has gaps
    between words — requiring strictly unbroken energy above the threshold
    made interruption far harder to trigger than it should be. A pause
    longer than ``silence_grace_seconds`` does reset it, so a single
    transient noise spike still cannot fire on its own.
    """

    def __init__(
        self,
        min_speech_seconds: float,
        silence_grace_seconds: float = 0.3,
    ) -> None:
        self._min_speech_seconds = min_speech_seconds
        self._silence_grace_seconds = silence_grace_seconds
        self._speech_run_seconds = 0.0
        self._silence_run_seconds = 0.0
        self._fired = False

    @property
    def fired(self) -> bool:
        """Whether a barge-in has already been reported."""
        return self._fired

    def update(self, frame_seconds: float, is_speech: bool) -> bool:
        """Advance by one frame.

        Args:
            frame_seconds: Duration of this frame in seconds.
            is_speech: Whether the frame's energy cleared the threshold.

        Returns:
            ``True`` exactly once, when sustained speech first reaches
            ``min_speech_seconds``.
        """
        if self._fired:
            return False

        if is_speech:
            self._silence_run_seconds = 0.0
            self._speech_run_seconds += frame_seconds
            if self._speech_run_seconds >= self._min_speech_seconds:
                self._fired = True
                return True
            return False

        # Silence: tolerate a short dip, give up on a real pause.
        self._silence_run_seconds += frame_seconds
        if self._silence_run_seconds > self._silence_grace_seconds:
            self._speech_run_seconds = 0.0

        return False


class BargeInListener:
    """Listens on a background thread and fires once on sustained speech.

    Attributes:
        _microphone: Shared microphone device to capture audio from.
        _mic_lock: Lock serialising microphone start/stop/read calls
            against the other consumers of the same device.
        _sample_rate_hz: Sample rate, in hertz, audio is captured at.
        _window_seconds: Duration of each audio window checked.
        _energy_threshold: Minimum RMS a window must reach to count as
            speech. This should be well above the ambient level *and*
            above what EON's own playback leaks into the mic.
        _min_speech_seconds: How long speech must persist before an
            interruption is declared.
        _on_barge_in: Callback invoked (on this listener's thread) the
            moment an interruption is detected.
    """

    def __init__(
        self,
        microphone: Microphone,
        mic_lock: threading.Lock,
        sample_rate_hz: int,
        window_seconds: float,
        energy_threshold: float,
        min_speech_seconds: float,
        on_barge_in: Callable[[], object],
        silence_grace_seconds: float = 0.3,
    ) -> None:
        self._microphone = microphone
        self._mic_lock = mic_lock
        self._sample_rate_hz = sample_rate_hz
        self._window_seconds = window_seconds
        self._energy_threshold = energy_threshold
        self._min_speech_seconds = min_speech_seconds
        self._silence_grace_seconds = silence_grace_seconds
        self._on_barge_in = on_barge_in
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    @property
    def is_running(self) -> bool:
        """Whether the background listening thread is currently active."""
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        """Starts the background barge-in listening thread."""
        if self.is_running:
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run,
            name="EON-BargeIn",
            daemon=True,
        )
        self._thread.start()
        logger.info(
            "Barge-in armed for this reply (needs %.1fs of speech above %.0f RMS).",
            self._min_speech_seconds,
            self._energy_threshold,
        )

    def stop(self) -> None:
        """Stops the background thread, blocking briefly for it to exit."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
        self._thread = None

    def _run(self) -> None:
        """Main loop for the background listening thread."""
        detector = BargeInDetector(
            self._min_speech_seconds,
            silence_grace_seconds=self._silence_grace_seconds,
        )
        peak_energy = 0.0

        while not self._stop_event.is_set():
            audio = self._capture_window()

            if audio is None:
                # A transient failure — most often the microphone
                # refusing to start because another reader had just
                # released it. Giving up here (as this used to) meant a
                # single hiccup silently disabled interruption for the
                # whole reply, which is indistinguishable from the user
                # simply never speaking.
                if self._stop_event.wait(_RETRY_INTERVAL_SECONDS):
                    break
                continue

            frame_seconds = len(audio) / (BYTES_PER_SAMPLE * self._sample_rate_hz)
            energy = rms_pcm(audio)
            peak_energy = max(peak_energy, energy)

            if detector.update(frame_seconds, energy >= self._energy_threshold):
                logger.info(
                    "Barge-in: user started speaking (%.0f RMS); interrupting EON.",
                    energy,
                )
                try:
                    self._on_barge_in()
                except Exception:
                    logger.exception("Barge-in callback raised an exception.")
                return

        if peak_energy and not detector.fired:
            # One line per playback, so the threshold can be set from
            # evidence instead of guesswork: if the peak here is below
            # barge_in_energy_threshold, that is why nothing interrupted.
            logger.info(
                "Barge-in: no interruption; loudest window was %.0f RMS "
                "(threshold is %.0f).",
                peak_energy,
                self._energy_threshold,
            )

    def _capture_window(self) -> bytes | None:
        """Records one short window of audio from the microphone.

        Returns:
            The captured PCM audio, or ``None`` if the microphone isn't
            open or a stop was requested mid-capture.
        """
        target_bytes = int(
            self._sample_rate_hz * BYTES_PER_SAMPLE * self._window_seconds
        )
        frames: list[bytes] = []
        collected = 0

        with self._mic_lock:
            if not self._microphone.is_open or self._stop_event.is_set():
                return None
            try:
                self._microphone.start_recording()
            except VoiceError:
                return None
            try:
                while collected < target_bytes and not self._stop_event.is_set():
                    try:
                        frame = self._microphone.read_frame()
                    except VoiceError:
                        break
                    frames.append(frame)
                    collected += len(frame)
            finally:
                try:
                    self._microphone.stop_recording()
                except VoiceError:
                    pass

        return b"".join(frames) if frames else None
