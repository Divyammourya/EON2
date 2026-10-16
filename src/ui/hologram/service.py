"""
Desktop Companion Service.

Owns the Qt application and hologram overlay window's lifecycle.
"""

from __future__ import annotations

import signal

from src.core.logger import get_logger
from src.ui.hologram.config import HologramConfig

logger = get_logger("Hologram")


class DesktopCompanionService:
    """
    Public interface for the JARVIS-style hologram overlay.

    Qt's real requirement — stricter than "just don't touch widgets
    from two threads at once" — is that on Windows and macOS, a
    QApplication's event loop should run on the process's actual main
    thread for windows to reliably paint. This is especially true for
    frameless, translucent, layered windows like this overlay: an
    earlier version of this class ran ``QApplication.exec()`` on its
    own background thread, which started up without any error and
    reported itself healthy, but silently painted nothing — no crash,
    just an invisible window, because Windows' compositor never
    treated it as a real GUI thread's window.

    So the split here is:
      - ``start()`` creates the QApplication and the overlay widget and
        shows it, but does **not** block — it's meant to be called
        during EON's normal module startup, on whatever thread that
        happens to be.
      - ``run_event_loop()`` is the blocking call (``QApplication.exec()``)
        and *must* be called from the same thread that called
        ``start()``. The caller (``main.py``) is responsible for making
        that thread the process's actual main thread, and for moving
        everything else (the console/voice loop) onto a background
        thread instead — the reverse of how most of EON's other
        background services work, because Qt is the one component here
        with a genuine "must be the main thread" requirement.
      - ``stop()`` is safe to call from any thread (including the
        console thread, during ``engine.shutdown()``) — it asks Qt to
        quit via a thread-safe queued call, which is what makes
        ``run_event_loop()`` return on the main thread.

    One consequence of QApplication being a genuine process-wide
    singleton (Qt's constraint, not this class'): only one
    DesktopCompanionService should ever run per process. That matches
    how EON actually uses it — one instance, started once, stopped
    once right before the process exits — so it's a non-issue in
    practice, but a second concurrent instance is not supported.
    """

    def __init__(self, config: HologramConfig) -> None:
        self._config = config
        self._app = None
        self._overlay = None
        self._wake_timer = None
        self._start_error: BaseException | None = None

    def initialize(self) -> None:
        """No setup needed here — everything happens in ``start()``,
        which is where the Qt objects actually get created."""

    @property
    def is_running(self) -> bool:
        """Whether the overlay is currently up and showing."""
        return self._app is not None and self._overlay is not None

    def start(self) -> None:
        """
        Creates the QApplication and overlay and shows it.

        Non-blocking — does not run Qt's event loop. Call
        ``run_event_loop()`` afterward, from this same thread, to
        actually pump events (and make the window responsive/visible
        long-term; without an event loop running, a just-shown window
        typically still isn't painted).
        """
        if not self._config.enabled:
            logger.info(
                "Desktop companion hologram is disabled (set "
                "hologram_enabled=true in config/settings.json to turn it on)."
            )
            return

        if self.is_running:
            return

        try:
            from PySide6.QtWidgets import QApplication

            from src.ui.hologram.overlay import HologramOverlay

            self._app = QApplication.instance() or QApplication(["EON"])
            # The hologram is a background effect, not the app's main
            # window — closing it (or it failing to open) must never
            # be interpreted by Qt as "the application should exit".
            self._app.setQuitOnLastWindowClosed(False)

            self._overlay = HologramOverlay(self._config)
            self._overlay.show()

            logger.info(
                "Hologram overlay started (%s, %s theme).",
                self._config.size.value,
                self._config.theme.value,
            )

        except ImportError as exc:
            self._start_error = exc
            self._app = None
            self._overlay = None
            logger.error(
                "Hologram overlay needs PySide6, which isn't installed. "
                "Run 'pip install PySide6' to enable it, or set "
                "hologram_enabled=false in config/settings.json. (%s)",
                exc,
            )

        except Exception as exc:  # noqa: BLE001 - never let this abort EON's boot
            self._start_error = exc
            self._app = None
            self._overlay = None
            logger.exception("Hologram overlay failed to start.")

    def run_event_loop(self) -> int:
        """
        Runs Qt's event loop, blocking until ``stop()`` is called (from
        any thread) or the process receives SIGINT (Ctrl+C).

        Must be called from the same thread that called ``start()`` —
        in EON's case, that thread should be the process's actual main
        thread; see the class docstring for why.

        Returns:
            Qt's event loop exit code, or ``0`` immediately if the
            overlay isn't running (disabled, or failed to start).
        """
        if not self.is_running:
            return 0

        from PySide6.QtCore import QTimer

        # A pure Qt/C++ event loop doesn't reliably hand control back
        # to the Python interpreter often enough for a Python signal
        # handler to actually run — so Ctrl+C can appear to do nothing
        # while this is blocking. A trivial, frequently-firing QTimer
        # gives Python a chance to notice the signal and act on it.
        self._wake_timer = QTimer()
        self._wake_timer.timeout.connect(lambda: None)
        self._wake_timer.start(200)

        previous_handler = signal.getsignal(signal.SIGINT)
        signal.signal(signal.SIGINT, lambda *_: self._app.quit())

        try:
            return self._app.exec()
        finally:
            signal.signal(signal.SIGINT, previous_handler)
            self._teardown()

    def _teardown(self) -> None:
        """Destroys every Qt object this service owns. Must run on the
        same thread that created them (i.e. right after ``exec()``
        returns, still inside ``run_event_loop()``) — destroying Qt
        widgets from a different thread than the one that created them
        crashes the process rather than raising a catchable error."""
        if self._wake_timer is not None:
            try:
                self._wake_timer.stop()
            except Exception:
                pass
            self._wake_timer = None

        if self._overlay is not None:
            try:
                self._overlay.close()
            except Exception:
                pass
            self._overlay = None

        self._app = None

    def stop(self) -> None:
        """
        Asks the overlay to close and the Qt event loop to quit.

        Safe to call from any thread. If ``run_event_loop()`` is
        currently blocking on the thread that called ``start()``, this
        is what makes it return.
        """
        app = self._app

        if app is None:
            return

        try:
            from PySide6.QtCore import QMetaObject
            from PySide6.QtCore import Qt as QtNamespace

            QMetaObject.invokeMethod(app, "quit", QtNamespace.QueuedConnection)
        except ImportError:
            pass

        logger.info("Hologram overlay stop requested.")

    def shutdown(self) -> None:
        self.stop()

    def health_check(self) -> bool:
        if not self._config.enabled:
            return True
        return self.is_running

    # ---- live config updates, safe to call from any thread --------------
    #
    # Each just re-emits onto the overlay's own Qt signal; Qt marshals
    # the call onto the Qt thread automatically since the emitting
    # thread and the overlay's thread differ. A no-op if the overlay
    # isn't running (e.g. hologram_enabled=false) or is mid-teardown
    # from a concurrent stop() — RuntimeError there means the C++ side
    # of the widget was just deleted; the emit is simply dropped rather
    # than raised, since "stop was requested a moment before this
    # update" isn't a caller error.

    def set_theme(self, theme: str) -> None:
        self._safe_emit(lambda overlay: overlay.themeChanged.emit(theme))

    def set_size(self, size: str) -> None:
        self._safe_emit(lambda overlay: overlay.sizeChanged.emit(size))

    def set_particles_enabled(self, enabled: bool) -> None:
        self._safe_emit(lambda overlay: overlay.particlesToggled.emit(enabled))

    def set_glow_intensity(self, value: float) -> None:
        self._safe_emit(lambda overlay: overlay.glowChanged.emit(value))

    def set_animation_speed(self, value: float) -> None:
        self._safe_emit(lambda overlay: overlay.speedChanged.emit(value))

    def set_transparency(self, value: float) -> None:
        self._safe_emit(lambda overlay: overlay.transparencyChanged.emit(value))

    def set_speaking(self, speaking: bool) -> None:
        """
        Tells the overlay whether EON is currently speaking, so it can
        grow and brighten slightly while active and ease back down to
        its resting size when idle. Meant to be bracketed around each
        spoken reply — ``set_speaking(True)`` right before,
        ``set_speaking(False)`` in a ``finally`` right after (see
        ``stream_conversation_reply`` in main.py).
        """
        self._safe_emit(lambda overlay: overlay.speakingChanged.emit(speaking))

    def _safe_emit(self, emit_call) -> None:
        overlay = self._overlay
        if overlay is None:
            return
        try:
            emit_call(overlay)
        except RuntimeError:
            pass
