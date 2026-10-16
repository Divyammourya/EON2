"""Small PCM audio helpers shared across the voice subsystem.

Pure, dependency-free (stdlib only) so they can be used and unit
tested without a microphone, a provider, or any third-party package.

All helpers assume 16-bit mono PCM, which is the format EON captures
and feeds to its speech-to-text providers.
"""

from __future__ import annotations

import array

#: Bytes per sample for 16-bit PCM.
BYTES_PER_SAMPLE = 2


def rms_pcm(pcm_bytes: bytes) -> float:
    """Root-mean-square energy of 16-bit mono PCM audio.

    Used as a cheap voice-activity gate: audio whose RMS is below a
    threshold is treated as silence/near-silence and skipped, rather
    than being sent to the (much more expensive) speech-to-text model.

    Args:
        pcm_bytes: Raw little-endian 16-bit mono PCM samples.

    Returns:
        The RMS amplitude (0.0 for empty or unusable input).
    """
    usable_length = len(pcm_bytes) - (len(pcm_bytes) % BYTES_PER_SAMPLE)
    if usable_length <= 0:
        return 0.0

    samples = array.array("h")
    samples.frombytes(pcm_bytes[:usable_length])
    if not samples:
        return 0.0

    sum_squares = sum(sample * sample for sample in samples)
    return (sum_squares / len(samples)) ** 0.5


def pcm_frame_seconds(frame_bytes: int, sample_rate_hz: int) -> float:
    """Duration, in seconds, of a chunk of 16-bit mono PCM audio.

    Args:
        frame_bytes: Number of bytes in the chunk.
        sample_rate_hz: Sample rate the audio was captured at.

    Returns:
        The duration of the chunk in seconds.
    """
    if sample_rate_hz <= 0:
        return 0.0
    return frame_bytes / (BYTES_PER_SAMPLE * sample_rate_hz)
