"""The adapter behind the coding window's sidebar.

``WindowQueries`` turns the workspace's managers into the three plain
answers the window asks for — what contains some text, what symbols a
file defines, and what git says. Keeping it separate from the window is
what lets the window stay ignorant of the workspace, and it means these
can be tested without Qt at all.

The rule every method follows: a sidebar section that cannot answer is
an empty sidebar section, never a window that fails to open.
"""

from __future__ import annotations

from pathlib import Path

from src.modules.workspace.workspaces.coding.models import GitFileStatus
from src.modules.workspace.workspaces.coding.window_queries import WindowQueries


# --- stubs ------------------------------------------------------------------


class _Kind:
    def __init__(self, value: str) -> None:
        self.value = value


class _Symbol:
    def __init__(self, name: str, kind: str, line: int) -> None:
        self.name = name
        self.kind = _Kind(kind)
        self.line = line


class _Search:
    def __init__(self, matches=(), error=None) -> None:
        self._matches = list(matches)
        self._error = error

    def search_text(self, text: str):
        if self._error:
            raise self._error
        return list(self._matches)


class _Symbols:
    def __init__(self, symbols=(), error=None) -> None:
        self._symbols = list(symbols)
        self._error = error
        self.asked: list[Path] = []

    def symbols_in_file(self, relative_path: Path):
        self.asked.append(relative_path)
        if self._error:
            raise self._error
        return list(self._symbols)


class _Git:
    def __init__(self, *, repo=True, branch="main", changed=(), error=None) -> None:
        self._repo = repo
        self._branch = branch
        self._changed = list(changed)
        self._error = error

    def is_repository(self) -> bool:
        return self._repo

    def current_branch(self):
        if self._error:
            raise self._error
        return self._branch

    def changed_files(self):
        return list(self._changed)


class _Project:
    def __init__(self, root: Path) -> None:
        self.project_root = root


class _Workspace:
    def __init__(self, root: Path, *, search=None, symbols=None, git=None) -> None:
        self.project_manager = _Project(root)
        if search is not None:
            self.search = search
        if symbols is not None:
            self.symbol_indexer = symbols
        if git is not None:
            self.git = git


# --- search -----------------------------------------------------------------


def test_search_reports_the_file_and_the_first_matching_line(tmp_path):
    (tmp_path / "src").mkdir()
    target = tmp_path / "src" / "main.py"
    target.write_text("one\ntwo\nneedle here\nfour\n", encoding="utf-8")

    queries = WindowQueries(_Workspace(tmp_path, search=_Search([target])))

    assert queries.search("needle") == [("src/main.py", 3)]


def test_search_gives_paths_relative_to_the_project(tmp_path):
    nested = tmp_path / "a" / "b"
    nested.mkdir(parents=True)
    target = nested / "c.py"
    target.write_text("hit\n", encoding="utf-8")

    queries = WindowQueries(_Workspace(tmp_path, search=_Search([target])))

    assert queries.search("hit") == [("a/b/c.py", 1)]


def test_search_says_zero_when_it_cannot_point_at_a_line(tmp_path):
    """A file that matched but whose line we could not find."""
    target = tmp_path / "blob.bin"
    target.write_bytes(b"\xff\xfe\x00binary")

    queries = WindowQueries(_Workspace(tmp_path, search=_Search([target])))

    assert queries.search("anything") == [("blob.bin", 0)]


def test_search_is_empty_for_an_empty_query(tmp_path):
    queries = WindowQueries(_Workspace(tmp_path, search=_Search([tmp_path / "x"])))

    assert queries.search("   ") == []


def test_search_survives_the_backend_failing(tmp_path):
    queries = WindowQueries(
        _Workspace(tmp_path, search=_Search(error=RuntimeError("boom")))
    )

    assert queries.search("anything") == []


def test_search_without_a_search_manager_is_empty(tmp_path):
    queries = WindowQueries(_Workspace(tmp_path))

    assert queries.search("anything") == []


# --- outline ----------------------------------------------------------------


def test_outline_reports_name_kind_and_line(tmp_path):
    symbols = _Symbols(
        [_Symbol("Greeter", "class", 3), _Symbol("greet", "function", 9)]
    )
    queries = WindowQueries(_Workspace(tmp_path, symbols=symbols))

    assert queries.outline("src/main.py") == [
        ("Greeter", "class", 3),
        ("greet", "function", 9),
    ]
    assert symbols.asked == [Path("src/main.py")]


def test_outline_survives_the_backend_failing(tmp_path):
    queries = WindowQueries(
        _Workspace(tmp_path, symbols=_Symbols(error=RuntimeError("boom")))
    )

    assert queries.outline("src/main.py") == []


def test_outline_without_an_indexer_is_empty(tmp_path):
    queries = WindowQueries(_Workspace(tmp_path))

    assert queries.outline("src/main.py") == []


# --- git --------------------------------------------------------------------


def test_git_reports_the_branch_and_the_changed_files(tmp_path):
    git = _Git(
        branch="feature/x",
        changed=[GitFileStatus(Path("src/main.py"), " ", "M")],
    )
    queries = WindowQueries(_Workspace(tmp_path, git=git))

    assert queries.git() == ("feature/x", [("src/main.py", "M")])


def test_git_outside_a_repository_is_nothing(tmp_path):
    queries = WindowQueries(_Workspace(tmp_path, git=_Git(repo=False)))

    assert queries.git() == (None, [])


def test_git_prefers_the_working_tree_status(tmp_path):
    """Git reports two columns; the window has room for one.

    What you can see in the editor is the working tree, so that wins.
    """
    git = _Git(
        changed=[
            GitFileStatus(Path("a.py"), "M", " "),   # staged only
            GitFileStatus(Path("b.py"), "M", "D"),   # staged, then deleted
        ]
    )
    queries = WindowQueries(_Workspace(tmp_path, git=git))

    _, changed = queries.git()

    assert changed == [("a.py", "M"), ("b.py", "D")]


def test_git_shows_untracked_as_a_question_mark(tmp_path):
    git = _Git(changed=[GitFileStatus(Path("new.py"), "?", "?")])
    queries = WindowQueries(_Workspace(tmp_path, git=git))

    _, changed = queries.git()

    assert changed == [("new.py", "?")]


def test_git_accepts_absolute_paths_too(tmp_path):
    git = _Git(changed=[GitFileStatus(tmp_path / "src" / "a.py", " ", "M")])
    queries = WindowQueries(_Workspace(tmp_path, git=git))

    _, changed = queries.git()

    assert changed == [("src/a.py", "M")]


def test_git_survives_the_backend_failing(tmp_path):
    queries = WindowQueries(
        _Workspace(tmp_path, git=_Git(error=RuntimeError("boom")))
    )

    assert queries.git() == (None, [])


def test_git_without_a_manager_is_nothing(tmp_path):
    queries = WindowQueries(_Workspace(tmp_path))

    assert queries.git() == (None, [])
