"""
Volume Tool.

Controls the Windows default audio output device's volume and mute
state via pycaw, a thin ctypes wrapper around the Windows Core Audio
APIs. Requires the `pycaw` and `comtypes` packages (see
requirements.txt).
"""

from __future__ import annotations

import re

from src.modules.tools.base import Tool
from src.modules.tools.models import ToolResult

_PERCENT_PATTERN = re.compile(r"(\d{1,3})\s*%?")
_VOLUME_STEP = 0.10


class VolumeTool(Tool):
    """Tool to get/set the system output volume and mute state."""

    @property
    def name(self) -> str:
        return "volume"

    def _get_endpoint(self):
        """Returns the IAudioEndpointVolume interface for the default
        playback device. Imported lazily so importing this module
        doesn't require pycaw/comtypes to already be installed."""
        from ctypes import POINTER, cast

        from comtypes import CLSCTX_ALL
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

        speakers = AudioUtilities.GetSpeakers()

        if not hasattr(speakers, "Activate"):
            # On some pycaw builds, AudioUtilities.GetSpeakers() returns
            # a plain wrapper object (the `AudioDevice` dataclass meant
            # for device *enumeration*) instead of the raw COM device
            # pointer that `.Activate` requires. When that happens, ask
            # Windows for the default render endpoint directly instead,
            # bypassing pycaw's own wrapping entirely.
            speakers = self._get_default_render_endpoint()

        interface = speakers.Activate(
            IAudioEndpointVolume._iid_,
            CLSCTX_ALL,
            None,
        )
        return cast(interface, POINTER(IAudioEndpointVolume))

    @staticmethod
    def _get_default_render_endpoint():
        """Gets the default playback IMMDevice straight from the
        Windows Core Audio device enumerator, independent of whatever
        object shape pycaw's own `GetSpeakers()` helper returns on this
        particular pycaw version."""
        from comtypes import CLSCTX_ALL, GUID, CoCreateInstance

        try:
            from pycaw.pycaw import (
                CLSID_MMDeviceEnumerator,
                EDataFlow,
                ERole,
                IMMDeviceEnumerator,
            )
            clsid = CLSID_MMDeviceEnumerator
        except ImportError:
            from pycaw.pycaw import EDataFlow, ERole, IMMDeviceEnumerator

            # Well-known, stable Windows CLSID for MMDeviceEnumerator
            # (documented by Microsoft). Used as a fallback so this
            # doesn't depend on pycaw exposing that exact constant name.
            clsid = GUID("{BCDE0395-E52F-467C-8E3D-C4579291692E}")

        enumerator = CoCreateInstance(
            clsid,
            IMMDeviceEnumerator,
            CLSCTX_ALL,
        )

        return enumerator.GetDefaultAudioEndpoint(
            EDataFlow.eRender.value,
            ERole.eMultimedia.value,
        )

    def execute(self, command: str = "") -> ToolResult:
        """Interprets a natural-language volume command and applies it.

        Understands: status queries, mute/unmute, "set volume to N%",
        and relative up/down adjustments.
        """
        try:
            endpoint = self._get_endpoint()
            text = (command or "").strip().lower()

            if not text or "status" in text or "what" in text:
                current = round(endpoint.GetMasterVolumeLevelScalar() * 100)
                muted = bool(endpoint.GetMute())
                suffix = " and currently muted" if muted else ""
                return ToolResult(
                    success=True,
                    message=f"Volume is at {current}%{suffix}.",
                )

            if re.search(r"\bunmute\b", text):
                endpoint.SetMute(0, None)
                return ToolResult(success=True, message="Unmuted.")

            if re.search(r"\bmute\b", text):
                endpoint.SetMute(1, None)
                return ToolResult(success=True, message="Muted.")

            match = _PERCENT_PATTERN.search(text)

            if match and ("set" in text or "%" in text or text.strip(" %").isdigit()):
                level = max(0, min(100, int(match.group(1))))
                endpoint.SetMasterVolumeLevelScalar(level / 100.0, None)
                endpoint.SetMute(0, None)
                return ToolResult(success=True, message=f"Volume set to {level}%.")

            current = endpoint.GetMasterVolumeLevelScalar()

            if any(word in text for word in ("up", "increase", "raise")):
                new_level = min(1.0, current + _VOLUME_STEP)
                endpoint.SetMasterVolumeLevelScalar(new_level, None)
                return ToolResult(
                    success=True,
                    message=f"Volume increased to {round(new_level * 100)}%.",
                )

            if any(word in text for word in ("down", "decrease", "lower")):
                new_level = max(0.0, current - _VOLUME_STEP)
                endpoint.SetMasterVolumeLevelScalar(new_level, None)
                return ToolResult(
                    success=True,
                    message=f"Volume decreased to {round(new_level * 100)}%.",
                )

            return ToolResult(
                success=False,
                message=f"I didn't understand the volume command: '{command}'.",
            )

        except Exception as error:
            return ToolResult(
                success=False,
                message=self._describe_failure(error),
            )

    @staticmethod
    def _describe_failure(error: Exception) -> str:
        """Only blame missing packages when that's actually what
        happened — an AttributeError or COM error after a successful
        import is a different problem, and the old message claiming
        packages were missing in that case was actively misleading."""
        if isinstance(error, ImportError):
            return (
                "Volume control requires the 'pycaw' and 'comtypes' "
                f"packages (pip install pycaw comtypes). Error: {error}"
            )

        return (
            "Volume control failed on this machine. "
            f"Error: {type(error).__name__}: {error}"
        )
