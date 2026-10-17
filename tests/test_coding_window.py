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

    # A file now opens as a tab rather than replacing a single
    # preview, so this drives the tab and reads it back. Opening is a
    # widget call, so it belongs on this thread — the service's
    # thread-safe entry points are show_project, refresh and
    # close_window, which go through the bridge.
    window._window.open_file("README.md")

    assert window._window._tabs.count() == 1

    editor = window._window._tabs.widget(0)

    assert "# Demo" in editor.toPlainText()


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


# --- the sidebar -----------------------------------------------------------


class _StubQueries:
    """Stands in for the workspace, so the layout can be tested alone."""

    def __init__(self, *, search=(), outline=(), git=(None, [])) -> None:
        self._search = list(search)
        self._outline = list(outline)
        self._git = git
        self.searches: list[str] = []

    def search(self, text: str):
        self.searches.append(text)
        return list(self._search)

    def outline(self, relative: str):
        return list(self._outline)

    def git(self):
        return self._git


def test_the_sidebar_has_the_four_sections(qt_app):
    from src.ui.coding.window import CodingWindow

    window = CodingWindow()

    labels = [
        window._sidebar.itemText(i) for i in range(window._sidebar.count())
    ]

    assert labels == ["Explorer", "Search", "Outline", "Git"]


def test_opening_a_project_lists_its_files(qt_app, project):
    from src.ui.coding.window import CodingWindow

    window = CodingWindow()
    window.show_project(project, "demo")

    tree = window._tree

    assert tree.topLevelItemCount() == 3
    assert window._hint.text() == "3 file(s)."


def test_the_empty_state_says_it_once(qt_app, tmp_path):
    from src.ui.coding.window import CodingWindow

    window = CodingWindow()
    window.show_project(tmp_path, "empty")

    assert window._tree.topLevelItemCount() == 0
    assert window._hint.text() == "This project is empty so far."


def test_clicking_a_file_opens_it_in_a_tab(qt_app, project):
    from src.ui.coding.window import CodingWindow

    window = CodingWindow()
    window.show_project(project, "demo")

    assert window._tabs.count() == 0

    window._tree.setCurrentItem(window._tree.topLevelItem(2))  # src/main.py

    assert window._tabs.count() == 1
    assert window._tabs.tabToolTip(0) == "src/main.py"
    assert "print('hello')" in window._tabs.widget(0).toPlainText()


def test_a_refresh_does_not_yank_you_out_of_your_tab(qt_app, project):
    """EON writing a file must not move the tab you are reading."""
    from src.ui.coding.window import CodingWindow

    window = CodingWindow()
    window.show_project(project, "demo")

    window._tree.setCurrentItem(window._tree.topLevelItem(0))  # README.md
    assert window.current_relative_path() == "README.md"

    (project / "src" / "extra.py").write_text("x = 1\n", encoding="utf-8")
    window.refresh()

    assert window._tabs.count() == 1
    assert window.current_relative_path() == "README.md"


def test_the_search_section_lists_what_the_backend_found(qt_app, project):
    from src.ui.coding.window import CodingWindow

    queries = _StubQueries(
        search=[("src/main.py", 1), ("docs/notes.md", 4)],
    )
    window = CodingWindow(queries=queries)
    window.show_project(project, "demo")

    window._search_box.setText("hello")
    window._run_search()

    assert queries.searches == ["hello"]
    assert window._search_results.count() == 2
    assert window._search_results.item(0).text() == "src/main.py:1"
    assert window._search_note.text() == "2 files."


def test_a_search_result_opens_the_file_at_its_line(qt_app, project):
    from src.ui.coding.window import CodingWindow

    (project / "src" / "main.py").write_text(
        "one\ntwo\nthree\nfour\n", encoding="utf-8"
    )

    queries = _StubQueries(search=[("src/main.py", 3)])
    window = CodingWindow(queries=queries)
    window.show_project(project, "demo")

    window._search_box.setText("three")
    window._run_search()
    window._on_search_activated(window._search_results.item(0))

    assert window.current_relative_path() == "src/main.py"
    assert window._tabs.widget(0).textCursor().blockNumber() == 2


def test_a_search_with_nothing_wired_up_is_just_empty(qt_app, project):
    from src.ui.coding.window import CodingWindow

    window = CodingWindow()  # no queries at all
    window.show_project(project, "demo")

    window._search_box.setText("hello")
    window._run_search()

    assert window._search_results.count() == 0
    assert "Nothing contains" in window._search_note.text()


def test_the_outline_follows_the_open_file(qt_app, project):
    from src.ui.coding.window import CodingWindow

    queries = _StubQueries(
        outline=[("main", "function", 1), ("Greeter", "class", 8)],
    )
    window = CodingWindow(queries=queries)
    window.show_project(project, "demo")

    assert window._outline.count() == 0

    window.open_file("src/main.py")

    assert window._outline.count() == 2
    assert "Greeter" in window._outline.item(1).text()
    assert window._outline_note.text() == "2 symbol(s)."


def test_an_outline_entry_jumps_to_its_line(qt_app, project):
    from src.ui.coding.window import CodingWindow

    (project / "src" / "main.py").write_text(
        "\n".join(f"line {n}" for n in range(1, 21)) + "\n",
        encoding="utf-8",
    )

    queries = _StubQueries(outline=[("main", "function", 12)])
    window = CodingWindow(queries=queries)
    window.show_project(project, "demo")

    window.open_file("src/main.py")
    window._on_outline_activated(window._outline.item(0))

    assert window._tabs.widget(0).textCursor().blockNumber() == 11


def test_the_git_section_shows_the_branch_and_the_changes(qt_app, project):
    from src.ui.coding.window import CodingWindow

    queries = _StubQueries(git=("main", [("src/main.py", "M")]))
    window = CodingWindow(queries=queries)
    window.show_project(project, "demo")

    assert window._git_branch.text() == "On branch main"
    assert window._git_files.count() == 1
    assert window._git_files.item(0).text() == "M  src/main.py"
    assert window._status_branch.text() == "main"


def test_outside_a_repository_the_git_section_says_so(qt_app, project):
    from src.ui.coding.window import CodingWindow

    window = CodingWindow(queries=_StubQueries(git=(None, [])))
    window.show_project(project, "demo")

    assert window._git_branch.text() == "Not a git repository."


def test_the_status_bar_names_the_open_file(qt_app, project):
    from src.ui.coding.window import CodingWindow

    window = CodingWindow()
    window.show_project(project, "demo")

    assert window._status_file.text() == "No file open"

    window.open_file("src/main.py")

    assert window._status_file.text() == "src/main.py"


def test_closing_a_tab_removes_it(qt_app, project):
    from src.ui.coding.window import CodingWindow

    window = CodingWindow()
    window.show_project(project, "demo")

    window.open_file("src/main.py")
    window.open_file("README.md")
    assert window._tabs.count() == 2

    window.close_tab(0)

    assert window._tabs.count() == 1
    assert window._tabs.tabToolTip(0) == "README.md"


def test_the_same_file_opens_once(qt_app, project):
    from src.ui.coding.window import CodingWindow

    window = CodingWindow()
    window.show_project(project, "demo")

    window.open_file("src/main.py")
    window.open_file("src/main.py")

    assert window._tabs.count() == 1


def test_the_queries_reach_the_window_through_the_service(qt_app, project):
    """The whole chain: service stores them, the window gets them."""
    from src.ui.coding.window import CodingWindow

    service = CodingWindowService(enabled=True)
    service.initialize()

    queries = _StubQueries(git=("main", [("src/main.py", "M")]))
    _from_console_thread(lambda: service.bind_queries(queries))
    _from_console_thread(lambda: service.show_project(project, "demo"))

    assert _settle(qt_app, lambda: service._window is not None)
    assert _settle(qt_app, lambda: service._window._git_branch.text() != "")

    window: CodingWindow = service._window
    assert window._git_branch.text() == "On branch main"
    assert window._queries is queries
