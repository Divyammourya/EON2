"""Endpointing: decide when a spoken utterance has finished.

Pure decision logic only — no audio, no microphone, no I/O — so it can
be unit tested without any hardware. ``VoiceService`` feeds it one
observation per captured audio frame ("was this frame speech or
silence?") and acts on the :class:`EndpointDecision` it returns.

Why this exists: the previous behaviour recorded for a fixed number of
seconds (``listen_seconds``, default 5.0). That is wrong in both
directions — it cuts people off mid-sentence on a long question, and
it makes them wait out the full window after a one-word answer. Real
assistants stop when the speaker *stops talking*; that is what this
tracks.
"""

from __future__ import annotations

from enum import Enum


class EndpointDecision(Enum):
    """The result of feeding one frame to :class:`UtteranceEndpoint`."""

    #: Keep recording — the utterance is still in progress.
    CONTINUE = "continue"

    #: The speaker has been silent long enough; the utterance is done.
    STOP_SPEECH_ENDED = "stop_speech_ended"

    #: The hard duration cap was reached while the speaker was talking.
    STOP_MAX_DURATION = "stop_max_duration"

    #: Nothing (or too little) was ever said — treat as "no utterance".
    STOP_NO_SPEECH = "stop_no_speech"


class UtteranceEndpoint:
    """Tracks a single utterance and decides when to stop recording it.

    Feed it frames in order with :meth:`update`. Once it returns
    anything other than :attr:`EndpointDecision.CONTINUE`, recording
    should stop.

    Args:
        silence_end_seconds: How long the speaker must be continuously
            silent, *after* having started speaking, before the
            utterance is considered finished.
        max_seconds: Hard cap on total recording time, so a stuck
            microphone or constant background noise can't record
            forever.
        min_speech_seconds: Minimum amount of actual speech required for
            the recording to count as a real utterance. A window that is
            all silence, or a single cough, falls below this and yields
            :attr:`EndpointDecision.STOP_NO_SPEECH`.
        start_timeout_seconds: How long to wait for speech to *begin*
            before giving up. In conversation mode this is the idle
            timeout that ends the conversation.
    """

    def __init__(
        self,
        *,
        silence_end_seconds: float,
        max_seconds: float,
        min_speech_seconds: float,
        start_timeout_seconds: float,
    ) -> None:
        self._silence_end_seconds = silence_end_seconds
        self._max_seconds = max_seconds
        self._min_speech_seconds = min_speech_seconds
        self._start_timeout_seconds = start_timeout_seconds

        self._elapsed_seconds = 0.0
        self._speech_seconds = 0.0
        self._silence_run_seconds = 0.0
        self._speech_started = False

    @property
    def speech_started(self) -> bool:
        """Whether any speech frame has been observed yet."""
        return self._speech_started

    @property
    def elapsed_seconds(self) -> float:
        """Total audio time observed so far."""
        return self._elapsed_seconds

    @property
    def speech_seconds(self) -> float:
        """Total speech time observed so far."""
        return self._speech_seconds

    def update(self, frame_seconds: float, is_speech: bool) -> EndpointDecision:
        """Advance the state machine by one frame.

        Args:
            frame_seconds: Duration of this frame in seconds.
            is_speech: Whether the frame's energy cleared the
                voice-activity threshold.

        Returns:
            What the caller should do next.
        """
        self._elapsed_seconds += frame_seconds

        if is_speech:
            self._speech_started = True
            self._speech_seconds += frame_seconds
            self._silence_run_seconds = 0.0
        else:
            self._silence_run_seconds += frame_seconds

        # Hard cap: always respected, whatever else is happening.
        if self._elapsed_seconds >= self._max_seconds:
            if self._speech_seconds < self._min_speech_seconds:
                return EndpointDecision.STOP_NO_SPEECH
            return EndpointDecision.STOP_MAX_DURATION

        # Before the speaker has started: only the start timeout applies.
        if not self._speech_started:
            if self._elapsed_seconds >= self._start_timeout_seconds:
                return EndpointDecision.STOP_NO_SPEECH
            return EndpointDecision.CONTINUE

        # Speaker started and has now gone quiet for long enough.
        if self._silence_run_seconds >= self._silence_end_seconds:
            if self._speech_seconds < self._min_speech_seconds:
                return EndpointDecision.STOP_NO_SPEECH
            return EndpointDecision.STOP_SPEECH_ENDED

        return EndpointDecision.CONTINUE
