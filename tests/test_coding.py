"""Tests for the coding skill.

The window itself isn't tested here — it needs a display, and what
matters about it (that it is asked to show the right project, and told
to refresh after a change) is tested through a stub. Everything else in
this feature is pure logic and is exercised directly.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.modules.workspace.workspaces.coding.mode import (
    CodingMode,
    is_leave_request,
    parse_coding_request,
)
from src.modules.workspace.workspaces.coding.nlp_parser import CodingCommandParser
from src.modules.workspace.workspaces.coding.planner.executor import (
    _step_failure,
)
from src.modules.workspace.workspaces.coding.session import (
    CodingSession,
    CodingSessionError,
    list_projects,
    sanitise_project_name,
)


# --- what a project may be called -------------------------------------------


@pytest.mark.parametrize(
    "name,expected",
    [
        ("calculator", "calculator"),
        ("todo-app", "todo-app"),
        ("my project", "my project"),
        ("snake_game", "snake_game"),
        ("  spaced  out  ", "spaced out"),
        ("v2.1", "v2.1"),
    ],
)
def test_usable_project_names(name, expected):
    assert sanitise_project_name(name) == expected


@pytest.mark.parametrize(
    "name",
    [
        "",            # nothing at all
        "   ",
        "...",
        "../escape",   # path traversal
        "..",
        "a/b",         # path separator
        "a\\b",        # windows separator
        ".hidden",     # would be a hidden folder
        "x" * 80,      # absurdly long
        "-leading-dash",
    ],
)
def test_names_that_are_rejected(name):
    with pytest.raises(CodingSessionError):
        sanitise_project_name(name)


# --- the session, and its boundary ------------------------------------------


def test_a_session_creates_its_folder_under_the_root(tmp_path):
    session = CodingSession(root=tmp_path, name="calculator")

    assert session.project_root == tmp_path / "calculator"
    assert session.project_root.is_dir()


def test_the_root_itself_is_created_if_missing(tmp_path):
    root = tmp_path / "does" / "not" / "exist"

    session = CodingSession(root=root, name="first")

    assert session.project_root.is_dir()


def test_writing_and_reading_a_file_round_trips(tmp_path):
    session = CodingSession(root=tmp_path, name="p")

    session.write_file("src/main.py", "print('hi')\n")

    assert session.read_file("src/main.py") == "print('hi')\n"
    assert (tmp_path / "p" / "src" / "main.py").is_file()


def test_writing_creates_missing_parent_folders(tmp_path):
    session = CodingSession(root=tmp_path, name="p")

    written = session.write_file("a/b/c/deep.py", "x")

    assert written.relative == "a/b/c/deep.py"


@pytest.mark.parametrize(
    "path",
    [
        "../outside.py",
        "../../further.py",
        "a/../../outside.py",
        "/etc/passwd",
        "~/secrets.txt",
    ],
)
def test_paths_that_escape_the_project_are_refused(tmp_path, path):
    session = CodingSession(root=tmp_path, name="p")

    with pytest.raises(CodingSessionError):
        session.write_file(path, "nope")

    with pytest.raises(CodingSessionError):
        session.read_file(path)


def test_an_escape_attempt_writes_nothing_anywhere(tmp_path):
    session = CodingSession(root=tmp_path, name="p")

    with pytest.raises(CodingSessionError):
        session.write_file("../../../escaped.py", "nope")

    assert not (tmp_path.parent / "escaped.py").exists()
    assert not Path("/escaped.py").exists()


def test_listing_files_is_relative_and_sorted(tmp_path):
    session = CodingSession(root=tmp_path, name="p")
    session.write_file("b.py", "")
    session.write_file("a/one.py", "")
    session.write_file("a/two.py", "")

    relative = [f.relative for f in session.list_files()]

    assert relative == ["a/one.py", "a/two.py", "b.py"]


def test_an_empty_project_lists_nothing(tmp_path):
    session = CodingSession(root=tmp_path, name="p")

    assert session.list_files() == []
    assert session.file_count() == 0


def test_deleting_a_project_removes_its_folder(tmp_path):
    session = CodingSession(root=tmp_path, name="p")
    session.write_file("x.py", "")

    session.delete()

    assert not (tmp_path / "p").exists()
    assert tmp_path.is_dir()


def test_deleting_refuses_to_remove_the_root(tmp_path):
    # A session whose project *is* the root would otherwise wipe the
    # whole workspace on a stray instruction.
    session = CodingSession(root=tmp_path, name="p")
    session.project_root = tmp_path

    with pytest.raises(CodingSessionError):
        session.delete()


def test_listing_projects(tmp_path):
    CodingSession(root=tmp_path, name="one")
    CodingSession(root=tmp_path, name="two")

    assert list_projects(tmp_path) == ["one", "two"]


def test_listing_projects_where_none_exist(tmp_path):
    assert list_projects(tmp_path / "nope") == []


# --- recognising the request ------------------------------------------------


@pytest.mark.parametrize(
    "said,project",
    [
        ("coding", ""),
        ("Coding", ""),
        ("code", ""),
        ("start coding", ""),
        ("let's code", ""),
        ("coding calculator", "calculator"),
        ("coding todo-app", "todo-app"),
        ("start coding my project", "my project"),
    ],
)
def test_coding_requests(said, project):
    request = parse_coding_request(said)

    assert request is not None
    assert request.project == project


@pytest.mark.parametrize(
    "said",
    ["", "hello", "play music", "open notepad", "what's the weather", "cod"],
)
def test_things_that_are_not_coding_requests(said):
    assert parse_coding_request(said) is None


@pytest.mark.parametrize(
    "said", ["done", "exit coding", "stop coding", "quit coding", "close coding"]
)
def test_leave_requests(said):
    assert is_leave_request(said)


def test_exit_alone_is_not_a_leave_request():
    # 'exit' quits EON, in either mode. 'done' leaves the mode.
    assert not is_leave_request("exit")


# --- the mode ---------------------------------------------------------------


class _StubWorkspace:
    """Stands in for the coding workspace, recording what it was asked."""

    def __init__(self, result=None) -> None:
        self.parser = CodingCommandParser()
        self.calls: list[str] = []
        self._result = result

    def handle_intent(self, intent):
        self.calls.append(intent.target)

        if self._result is not None:
            return self._result

        return {
            "success": True,
            "create_file": {
                "success": True,
                "path": "src/main.py",
                "bytes_written": 12,
            },
        }


class _StubWindow:
    """Stands in for the coding window."""

    def __init__(self) -> None:
        self.shown: list[tuple[str, str]] = []
        self.refreshes = 0
        self.closes = 0

    def show_project(self, project_root, title) -> None:
        self.shown.append((str(project_root), title))

    def refresh(self) -> None:
        self.refreshes += 1

    def close_window(self) -> None:
        self.closes += 1


def _mode(tmp_path, **kwargs):
    workspace = kwargs.pop("workspace", None) or _StubWorkspace()
    window = kwargs.pop("window", None) or _StubWindow()

    return (
        CodingMode(workspace=workspace, window=window, root=tmp_path, **kwargs),
        workspace,
        window,
    )


def test_entering_with_a_name_creates_the_project_and_opens_the_window(tmp_path):
    mode, workspace, window = _mode(tmp_path)

    reply = mode.enter("calculator")

    assert mode.active
    assert mode.session.name == "calculator"
    assert (tmp_path / "calculator").is_dir()
    assert window.shown == [(str(tmp_path / "calculator"), "calculator")]
    assert "calculator" in reply


def test_entering_opens_the_project_in_the_workspace(tmp_path):
    mode, workspace, _ = _mode(tmp_path)

    mode.enter("calculator")

    assert workspace.calls == [f"open project {tmp_path / 'calculator'}"]


def test_entering_with_no_name_and_no_projects_explains_what_to_do(tmp_path):
    mode, _, _ = _mode(tmp_path)

    reply = mode.enter("")

    assert not mode.active
    assert "coding <name>" in reply


def test_entering_with_no_name_resumes_the_only_project(tmp_path):
    CodingSession(root=tmp_path, name="only-one")
    mode, _, _ = _mode(tmp_path)

    mode.enter("")

    assert mode.session.name == "only-one"


def test_entering_with_no_name_and_several_projects_asks_which(tmp_path):
    CodingSession(root=tmp_path, name="one")
    CodingSession(root=tmp_path, name="two")
    mode, _, _ = _mode(tmp_path)

    reply = mode.enter("")

    assert not mode.active
    assert "one" in reply and "two" in reply


def test_a_bad_project_name_is_reported_not_raised(tmp_path):
    mode, _, _ = _mode(tmp_path)

    reply = mode.enter("../../evil")

    assert not mode.active
    assert "isn't a usable project name" in reply


def test_disabled_coding_says_how_to_turn_it_on(tmp_path):
    mode, _, _ = _mode(tmp_path, enabled=False)

    reply = mode.enter("anything")

    assert not mode.active
    assert "coding_enabled" in reply


# --- dispatching ------------------------------------------------------------


def test_a_write_is_dispatched_and_the_window_refreshed(tmp_path):
    mode, workspace, window = _mode(tmp_path)
    mode.enter("p")
    before = len(workspace.calls)

    reply = mode.handle("create file src/main.py")

    assert workspace.calls[before:] == ["create file src/main.py"]
    assert window.refreshes == 1
    assert "src/main.py" in reply


def test_a_command_asks_before_running(tmp_path):
    mode, workspace, _ = _mode(tmp_path)
    mode.enter("p")
    before = len(workspace.calls)

    reply = mode.handle("run command python main.py")

    assert "shall I?" in reply
    assert mode.pending_command == "python main.py"
    # Crucially: nothing was dispatched.
    assert workspace.calls[before:] == []


def test_saying_yes_runs_the_command(tmp_path):
    mode, workspace, _ = _mode(tmp_path)
    mode.enter("p")
    mode.handle("run command python main.py")
    before = len(workspace.calls)

    mode.handle("yes")

    assert workspace.calls[before:] == ["run command python main.py"]
    assert mode.pending_command is None


def test_saying_no_does_not_run_it(tmp_path):
    mode, workspace, _ = _mode(tmp_path)
    mode.enter("p")
    mode.handle("run command rm -rf /")
    before = len(workspace.calls)

    reply = mode.handle("no")

    assert workspace.calls[before:] == []
    assert mode.pending_command is None
    assert "won't run" in reply


def test_an_unclear_answer_re_asks_and_keeps_the_command_waiting(tmp_path):
    mode, workspace, _ = _mode(tmp_path)
    mode.enter("p")
    mode.handle("run command python main.py")
    before = len(workspace.calls)

    reply = mode.handle("maybe later?")

    assert "yes or no" in reply
    assert mode.pending_command == "python main.py"
    assert workspace.calls[before:] == []


def test_a_second_command_does_not_replace_a_waiting_one(tmp_path):
    mode, _, _ = _mode(tmp_path)
    mode.enter("p")
    mode.handle("run command python main.py")

    # Typed while a confirmation is open, so it is read as an answer
    # rather than as a new command.
    mode.handle("run command rm -rf /")

    assert mode.pending_command == "python main.py"


def test_switching_projects(tmp_path):
    mode, workspace, window = _mode(tmp_path)
    mode.enter("one")

    reply = mode.handle("project two")

    assert mode.session.name == "two"
    assert (tmp_path / "two").is_dir()
    assert "two" in reply
    assert len(window.shown) == 2


def test_listing_projects_from_inside_the_mode(tmp_path):
    mode, _, _ = _mode(tmp_path)
    mode.enter("one")
    mode.enter("two")

    reply = mode.handle("projects")

    assert "one" in reply and "two" in reply


def test_leaving_closes_the_window(tmp_path):
    mode, _, window = _mode(tmp_path)
    mode.enter("p")

    reply = mode.leave()

    assert not mode.active
    assert window.closes == 1
    assert "p" in reply


def test_leaving_when_not_in_the_mode(tmp_path):
    mode, _, _ = _mode(tmp_path)

    assert "not in coding mode" in mode.leave()


def test_done_leaves_the_mode(tmp_path):
    mode, _, _ = _mode(tmp_path)
    mode.enter("p")

    mode.handle("done")

    assert not mode.active


def test_an_empty_line_is_ignored(tmp_path):
    mode, workspace, _ = _mode(tmp_path)
    mode.enter("p")
    before = len(workspace.calls)

    assert mode.handle("   ") == ""
    assert workspace.calls[before:] == []


def test_a_workspace_that_raises_is_reported_not_propagated(tmp_path):
    class _Broken(_StubWorkspace):
        def handle_intent(self, intent):
            raise RuntimeError("workspace exploded")

    mode, _, _ = _mode(tmp_path, workspace=_Broken())
    mode.enter("p")

    reply = mode.handle("create file x.py")

    assert "didn't work" in reply
    assert "workspace exploded" in reply


def test_a_failed_step_is_reported_as_a_failure(tmp_path):
    failing = _StubWorkspace(
        result={"success": False, "error": "No project is currently open."}
    )
    mode, _, _ = _mode(tmp_path, workspace=failing)
    mode.enter("p")

    reply = mode.handle("create file x.py")

    assert "didn't work" in reply
    assert "No project is currently open." in reply


# --- the two fixes this feature needed --------------------------------------


def test_a_failed_step_stops_a_plan_being_reported_as_success():
    # This is the bug that would have made EON say "done" while writing
    # nothing at all.
    assert _step_failure({"success": False, "error": "boom"}) == "boom"
    assert _step_failure({"success": False, "message": "also boom"}) == "also boom"
    assert _step_failure({"success": False}) == "unknown error"


def test_a_successful_or_silent_step_is_not_a_failure():
    assert _step_failure({"success": True}) is None
    assert _step_failure({"path": "a.py"}) is None
    assert _step_failure(None) is None
    assert _step_failure(object()) is None


def test_a_result_object_with_success_false_is_a_failure():
    class _Result:
        success = False
        error = "nope"

    assert _step_failure(_Result()) == "nope"


def test_read_file_accepts_the_word_file():
    # "read file src/main.py" used to look for a file literally called
    # "file src/main.py", so every read of a named file failed.
    parser = CodingCommandParser()

    assert parser.parse("read file src/main.py").arguments == {
        "path": "src/main.py"
    }
    assert parser.parse("read src/main.py").arguments == {"path": "src/main.py"}
    assert parser.parse("open file notes.txt").arguments == {"path": "notes.txt"}
    assert parser.parse("show the file a/b.py").arguments == {"path": "a/b.py"}


def test_open_project_still_wins_over_read_file():
    # "open project X" is matched before the read branch, and the new
    # optional "file" must not shadow it.
    parser = CodingCommandParser()

    assert parser.parse("open project /tmp/thing").action == "open_project"
