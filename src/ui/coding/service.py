"""Owns EON's coding window and the Qt event loop it lives on.

The awkward part of this file is threading, and it's worth explaining
because getting it wrong produces a window that appears and then
freezes.

Qt requires two things: only one ``QApplication`` per process, and all
widget work on the thread that owns the event loop (the main thread).
EON's console loop is not always on the main thread — when the hologram
overlay is active, ``main()`` moves the console to a background thread
and blocks the main thread in Qt's event loop, because the overlay has
to paint there. So when you type ``coding``, the request comes from the
console thread, and creating or touching a widget from there would be a
crash waiting to happen.

The fix is Qt's own mechanism: a tiny ``QObject`` bridge whose signals
are emitted from the console thread. Qt delivers a cross-thread signal
as a queued call, so the connected slot runs on the main thread — which
is exactly where the widget work has to happen. Nothing here does
widget work directly; it only emits.

Design notes:
    - PySide6 is imported lazily, in ``initialize``. EON must start
      fine on a machine with no Qt at all, and the hologram overlay
      takes the same approach.
    - ``is_running`` means "the window system is up", not "a window is
      visible". ``main()`` has to decide how to arrange its threads at
      startup, long before anyone types ``coding``.
    - The window is created on first use, not at startup. A coding
      window you never open should cost nothing.

Requires: PySide6 (already a dependency for the hologram overlay)
"""

from __future__ import annotations

from pathlib import Path

from src.core.logger import get_logger

logger = get_logger("CodingWindow")


class CodingWindowService:
    """The coding window, and the Qt plumbing that keeps it alive.

    Attributes:
        _enabled: Whether a coding window is available at all.
        _app: The process-wide ``QApplication``, if one exists.
        _window: The window itself, created on first use.
        _bridge: The cross-thread signal bridge.
    """

    def __init__(self, *, enabled: bool = True) -> None:
        """Builds the service.

        Args:
            enabled: Whether the coding window can be used.
        """
        self._enabled = enabled
        self._app = None
        self._window = None
        self._bridge = None
        self._queries = None

    # --- lifecycle --------------------------------------------------------

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def is_running(self) -> bool:
        """Whether the Qt window system is up.

        True as soon as the service is initialized with Qt available,
        even before a window is shown — ``main()`` uses this at startup
        to decide whether the console loop can stay on the main thread.
        """
        return self._app is not None

    def initialize(self) -> None:
        """Ensures a ``QApplication`` exists.

        Safe to call when the hologram overlay has already made one —
        Qt allows only a single instance per process, so this adopts
        the existing one rather than trying to create a second.
        """
        if not self._enabled:
            logger.info("Coding window is disabled.")
            return

        try:
            from PySide6.QtWidgets import QApplication
        except ImportError:
            # Not fatal: EON runs without a coding window. It just
            # means typing 'coding' reports that it's unavailable.
            self._enabled = False
            logger.warning(
                "PySide6 isn't installed, so the coding window is "
                "unavailable. Everything else still works."
            )
            return

        existing = QApplication.instance()

        if existing is not None:
            self._app = existing
        else:
            self._app = QApplication(["EON"])

        # Imported here rather than at module scope for the same reason
        # PySide6 is: the assets module needs Qt, and EON has to start
        # on a machine that hasn't got it.
        from src.ui.assets import install_app_icon

        # On the application rather than on the window, so anything
        # EON opens later inherits it without having to remember.
        install_app_icon(self._app)

        self._bridge = self._make_bridge()

        logger.info("Coding window is ready.")

    def _make_bridge(self):
        """Builds the cross-thread signal bridge.

        Created after the ``QApplication`` so the signals have an event
        loop to be delivered through.
        """
        from PySide6.QtCore import QObject, Signal

        class _Bridge(QObject):
            show_requested = Signal(str, str)
            refresh_requested = Signal()
            close_requested = Signal()
            quit_requested = Signal()
            queries_changed = Signal()

        bridge = _Bridge()

        bridge.show_requested.connect(self._on_show)
        bridge.refresh_requested.connect(self._on_refresh)
        bridge.close_requested.connect(self._on_close)
        bridge.quit_requested.connect(self._on_quit)
        bridge.queries_changed.connect(self._on_queries_changed)

        return bridge

    def run_event_loop(self) -> int:
        """Blocks in Qt's event loop until the application quits.

        Only needed when the hologram overlay is *not* running; when it
        is, its own event loop already serves this window, and a second
        ``exec()`` on the same application is not allowed.
        """
        if self._app is None:
            return 0

        return int(self._app.exec())

    def stop(self) -> None:
        """Asks Qt to shut down, on the thread that owns it.

        Called at exit from the console thread, which is *not* the
        thread that owns Qt. This used to call ``_on_close()`` and
        ``self._app.quit()`` directly — widget work and an event-loop
        call from a thread Qt never granted them to. That is what made
        ``exit`` print "Goodbye!" and then never shut down.

        It now goes through the bridge like everything else, so the
        hiding and the quitting both happen on the main thread.
        """
        if self._app is None:
            return

        if self._bridge is None:
            # ``initialize`` never got as far as Qt, so there is no
            # event loop to quit.
            self._app = None
            return

        try:
            self._bridge.quit_requested.emit()
        except Exception as error:  # pragma: no cover - shutdown safety net
            logger.warning("Could not stop the coding window: %s", error)

    def shutdown(self) -> None:
        """Alias for ``stop``, for symmetry with the other services."""
        self.stop()

    # --- the API the mode uses (all thread-safe) --------------------------

    def bind_queries(self, queries) -> None:
        """Tells the sidebar how to answer its questions.

        Callable from any thread. The object is stored here and handed
        to the window on the main thread, because the window is only
        ever touched there — see ``_on_queries_changed``.

        Args:
            queries: Something with ``search``, ``outline`` and ``git``.
                ``WindowQueries`` is the real one; the tests pass a
                stub.
        """
        self._queries = queries

        if self._bridge is None:
            # No Qt yet, so no window to tell. ``_ensure_window`` will
            # pick the queries up when the window is finally built.
            return

        try:
            self._bridge.queries_changed.emit()
        except Exception as error:  # pragma: no cover - UI safety net
            logger.warning("Could not hand the window its queries: %s", error)

    def show_project(self, project_root: Path | str, title: str) -> None:
        """Shows the window on a project.

        Callable from any thread.

        Args:
            project_root: The folder to display.
            title: The project name, for the header.
        """
        if not self._enabled or self._bridge is None:
            return

        self._bridge.show_requested.emit(str(project_root), title)

    def refresh(self) -> None:
        """Re-reads the project's files. Callable from any thread."""
        if not self._enabled or self._bridge is None:
            return

        self._bridge.refresh_requested.emit()

    def close_window(self) -> None:
        """Hides the window without quitting Qt. Callable from any thread."""
        if not self._enabled or self._bridge is None:
            return

        self._bridge.close_requested.emit()

    # --- the slots (these run on the main thread) ------------------------

    def _ensure_window(self):
        """Creates the window on first use."""
        if self._window is not None:
            return self._window

        from src.ui.coding.window import CodingWindow

        self._window = CodingWindow(queries=self._queries)

        return self._window

    def _on_show(self, project_root: str, title: str) -> None:
        """Shows the window. Runs on the main thread."""
        try:
            self._ensure_window().show_project(Path(project_root), title)
        except Exception as error:  # pragma: no cover - UI safety net
            logger.warning("Could not show the coding window: %s", error)

    def _on_refresh(self) -> None:
        """Refreshes the window. Runs on the main thread."""
        if self._window is None:
            return

        try:
            self._window.refresh()
        except Exception as error:  # pragma: no cover - UI safety net
            logger.warning("Could not refresh the coding window: %s", error)

    def _on_queries_changed(self) -> None:
        """Hands the window the queries. Runs on the main thread."""
        if self._window is None:
            return

        try:
            self._window.set_queries(self._queries)
            self._window.refresh()
        except Exception as error:  # pragma: no cover - UI safety net
            logger.warning("Could not refresh the window's sidebar: %s", error)

    def _on_close(self) -> None:
        """Hides the window. Runs on the main thread."""
        if self._window is None:
            return

        try:
            self._window.hide()
        except Exception as error:  # pragma: no cover - UI safety net
            logger.warning("Could not hide the coding window: %s", error)

    def _on_quit(self) -> None:
        """Hides the window and quits Qt. Runs on the main thread."""
        self._on_close()

        if self._app is not None:
            self._app.quit()

        # Set here rather than in ``stop`` so it reflects what Qt has
        # actually done, not what another thread has asked for.
        self._app = None
