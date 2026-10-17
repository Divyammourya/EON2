"""Tests for the coding window and its cross-thread bridge.

This is the one part of the coding feature that needs a display, so it
runs against Qt's ``offscreen`` platform plugin and is skipped wherever
PySide6 isn't installed. What it exercises is the part most likely to
break silently: the window is driven from the *console* thread — which
is not the thread that owns Qt's event loop — through a signal bridge,
and a queued cross-thread signal is only delivered when the receiving
thread's event loop runs.

``show_project``, ``refresh`` and ``close_window`` therefore have to be
called from another thread here, with the event loop pumped on this
one, or the test would be testing the easy case that never happens in
practice.
"""

from __future__ import annotations

import os
import threading
import time
from pathlib import Path

import pytest

# Must be set before Qt is imported, or it tries to open a real display.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from src.ui.coding.service import CodingWindowService  # noqa: E402

# How long to let a queued signal travel before giving up on it.
_SETTLE_SECONDS = 1.0
_POLL_SECONDS = 0.01


@pytest.fixture(scope="module")
def qt_app():
    """A process-wide QApplication, as EON has in practice.

    Skips rather than fails if Qt can't start at all: that is an
    environment problem, not a bug in the window.
    """
    try:
        app = QApplication.instance() or QApplication(["EON-tests"])
    except Exception as error:  # pragma: no cover - environment dependent
        pytest.skip(f"Qt could not start here: {error}")

    yield app


def _settle(app, until=None) -> bool:
    """Pumps the event loop until ``until`` is true, or time runs out.

    Args:
        app: The QApplication to pump.
        until: A predicate that must become true.

    Returns:
        Whether the predicate became true.
    """
    deadline = time.monotonic() + _SETTLE_SECONDS

    while time.monotonic() < deadline:
        app.processEvents()

        if until is None or until():
            return True

        time.sleep(_POLL_SECONDS)

    return until is None or until()


def _from_console_thread(call) -> None:
    """Runs ``call`` on a different thread, as the console does."""
    thread = threading.Thread(target=call)
    thread.start()
    thread.join()


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """A small project to show in the window."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("print('hello')\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("# Demo\n", encoding="utf-8")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "notes.md").write_text("notes\n", encoding="utf-8")
    return tmp_path


def test_the_window_shows_the_project_it_was_given(qt_app, project):
    window = CodingWindowService(enabled=True)
    window.initialize()

    assert window.is_running

    _from_console_thread(lambda: window.show_project(project, "demo"))

    assert _settle(qt_app, lambda: window._window is not None)

    shown = window._window

    assert _settle(qt_app, lambda: shown.isVisible())
    assert shown.isVisible()
    assert "demo" in shown._header.text()
    assert str(project) in shown._header.text()


def test_the_tree_lists_the_files(qt_app, project):
    window = CodingWindowService(enabled=True)
    window.initialize()

    _from_console_thread(lambda: window.show_project(project, "demo"))
    assert _settle(qt_app, lambda: window._window is not None)

    tree = window._window._tree

    assert _settle(qt_app, lambda: tree.topLevelItemCount() == 3)

    listed = {
        tree.topLevelItem(i).text(0) for i in range(tree.topLevelItemCount())
    }

    assert listed == {"README.md", "docs/notes.md", "src/main.py"}


def test_the_code_view_shows_the_selected_file(qt_app, project):
    window = CodingWindowService(enabled=True)
    window.initialize()

    _from_console_thread(lambda: window.show_project(project, "demo"))
    assert _settle(qt_app, lambda: window._window is not None)

    code = window._window._code

    # README.md sorts first, so it is selected on load.
    assert _settle(qt_app, lambda: bool(code.toPlainText()))
    assert "# Demo" in code.toPlainText()


def test_refresh_picks_up_a_new_file(qt_app, project):
    window = CodingWindowService(enabled=True)
    window.initialize()

    _from_console_thread(lambda: window.show_project(project, "demo"))
    assert _settle(qt_app, lambda: window._window is not None)

    tree = window._window._tree
    assert _settle(qt_app, lambda: tree.topLevelItemCount() == 3)

    # A file appears, as it does when EON writes one.
    (project / "src" / "extra.py").write_text("x = 1\n", encoding="utf-8")

    _from_console_thread(window.refresh)

    assert _settle(qt_app, lambda: tree.topLevelItemCount() == 4)


def test_closing_hides_the_window(qt_app, project):
    window = CodingWindowService(enabled=True)
    window.initialize()

    _from_console_thread(lambda: window.show_project(project, "demo"))
    assert _settle(qt_app, lambda: window._window is not None)
    assert _settle(qt_app, lambda: window._window.isVisible())

    _from_console_thread(window.close_window)

    assert _settle(qt_app, lambda: not window._window.isVisible())
    assert not window._window.isVisible()


def test_a_disabled_service_does_nothing(qt_app, project):
    window = CodingWindowService(enabled=False)
    window.initialize()

    assert not window.is_running

    # None of these should raise, and none should create a window.
    window.show_project(project, "demo")
    window.refresh()
    window.close_window()

    assert window._window is None


# --- stopping, which is where ``exit`` hung --------------------------------


def test_stop_does_not_touch_the_window_on_the_calling_thread(qt_app, project):
    """The bug behind "exit is not working".

    ``stop`` is called from the console thread at exit. It used to call
    ``_on_close()`` and ``self._app.quit()`` directly from there —
    hiding a widget and calling into the event loop on a thread Qt
    never granted either to. EON printed "Goodbye!" and then never shut
    down.

    The tell is that nothing happens *synchronously* any more: after
    ``stop`` returns, the window is still up and Qt is still ours,
    because the request is sitting in the main thread's queue.
    """
    window = CodingWindowService(enabled=True)
    window.initialize()

    _from_console_thread(lambda: window.show_project(project, "demo"))
    assert _settle(
        qt_app,
        lambda: window._window is not None and window._window.isVisible(),
    )

    _from_console_thread(window.stop)

    # Nothing yet: the work has been asked for, not done.
    assert window._window.isVisible()
    assert window._app is not None


def test_stop_then_hides_the_window_and_releases_qt(qt_app, project):
    window = CodingWindowService(enabled=True)
    window.initialize()

    _from_console_thread(lambda: window.show_project(project, "demo"))
    assert _settle(
        qt_app,
        lambda: window._window is not None and window._window.isVisible(),
    )

    _from_console_thread(window.stop)

    # Once the main thread gets to it, both happen there.
    assert _settle(qt_app, lambda: not window._window.isVisible())
    assert not window._window.isVisible()
    assert window._app is None


def test_stop_is_harmless_when_nothing_was_shown(qt_app):
    window = CodingWindowService(enabled=True)
    window.initialize()

    _from_console_thread(window.stop)

    assert _settle(qt_app, lambda: window._app is None)


def test_stop_on_a_disabled_service_does_nothing(qt_app):
    window = CodingWindowService(enabled=False)
    window.initialize()

    window.stop()

    assert window._app is None
    assert window._window is None
