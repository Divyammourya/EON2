"""EON's coding window.

A small built-in editor, laid out the way an editor is normally laid
out: a sidebar down the left with sections you switch between, and the
project's files open as tabs on the right.

    ┌────────────┬──────────────────────────┐
    │ EXPLORER   │  main.py | README.md     │
    │  file tree │──────────────────────────│
    │ ─────────  │  the open file's text    │
    │ SEARCH     │                          │
    │ ─────────  │                          │
    │ OUTLINE    │                          │
    │ ─────────  │                          │
    │ GIT        │                          │
    ├────────────┴──────────────────────────┤
    │ main ● 2 changed │ src/main.py │ Ln 4 │
    └──────────────────────────────────────┘

The three sidebar sections beyond Explorer are not new features — EON
could already search a project, list a file's symbols, and read git
status. Those lived behind console commands and were never on screen.
Each section is wired to one of them.

Design notes:
    - PySide6 is imported at module scope here, which is why
      ``service.py`` imports *this* module lazily. Nothing in EON
      touches PySide6 unless a coding window is actually wanted.
    - Only one ``QApplication`` may exist per process, and EON's
      hologram overlay creates it. So this window adopts the existing
      instance rather than making its own — see CodingWindowService.
    - Every widget here is touched on the main thread only. The console
      runs on its own thread and reaches this window through the
      service's signal bridge, never directly.
    - The sidebar's queries go through ``queries``, an object supplied
      by the service, rather than importing the workspace. The window
      has no idea what a SearchManager is.

Requires: PySide6 (already a dependency for the hologram overlay)
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGu import QFont
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QPlainTextEdit,
    QSplitter,
    QTabWidget,
    QToolBox,
    QTreeWidget,
    ATreeWidgetItem,
    QVboxLayout,
    QWidget,
)

# Above this, show a summary rather than the contents.
MAX_PREVIEW_BYTES = 200_000

# Extensions worth showing as text. Anything else is reported as
# binary rather than rendered as mojibake.
TEXT_SUFFIXES = frozenset(
    {
        ".py", ".js", ".ts", ".tsx", ".jsx", ".json", ".md", ".txt", ".yml",
        ".yaml", ".toml", ".ini", ".cfg", ".html", ".htm", ".css", ".scss",
        ".xml", ".csv", ".sh", ".bat", ".ps1", ".sql", ".java", ".c", ".h",
        ".cpp", ".cs", ".go", ".rs", ".rb", ".php", ".env", ".gitignore",
    }
)

_STYLESHEET = """
QMainWindow, QWidget { background: #0b0f14; color: #d7e6ee; }
QLabel#header { color: #5eead4; font-weight: bold; padding: 6px 8px; }
QLabel#hint { color: #7c8b98; padding: 4px 8px; }
QLabel#section { color: #7c8b98; padding: 6px 8px 2px 8px; }
QTreeWidget, QListWidget {
    background: #0e141b; border: 1px solid #1d2b36; color: #c8d8e2;
}
QTreeWidget::item:selected, QListWidget::item:selected {
    background: #14414a; color: #eafcff;
}
QPlainTextEdit {
    background: #0e141b; border: 1px solid #1d2b36; color: #cfe9f5;
}
QLineEdit {
    background: #0e141b; border: 1px solid #1d2b36;
    color: #cfe9f5; padding: 4px 6px;
}
QSplitter::handle { background: #16222c; }
QToolBox::tab {
    background: #101a22; color: #8fa6b4; padding: 6px 8px;
    border-top: 1px solid #1d2b36;
}
QToolBox::tab:selected { color: #5eead4; background: #14414a; }
QTabBar::tab {
    background: #101a22; color: #8fa6b4; padding: 5px 10px;
    border: 1px solid #1d2b36;
}
QTabBar::tab:selected { background: #14414a; color: #eafcff; }
QStatusBar { background: #101a22; color: #8fa6b4; }
QStatusBar QLabel { color: #8fa6b4; padding: 0 8px; }
"""


class CodingWindow(QMainWindow):
    """The coding window: a sidebar, open files as tabs, and a status bar.

    Attributes:
        project_root: The project being shown, if any.
    """

    def __init__(self, queries=None) -> None:
        """Builds the window.

        Args:
            queries: Optional object answering the sidebar's questions.
                Anything with ``search``, ``outline`` and ``git`` will
                do; the tests pass a stub, and the service passes one
                backed by the real workspace. When it is ``None`` the
                sections simply stay empty.
        """
        super().__init__()

        self.project_root: Path | None = None
        self._queries = queries

        # Set while ``refresh`` rebuilds the tree. Without it, restoring
        # the selection would fire the same signal a click does, and a
        # file EON wrote in the background would yank you out of the
        # tab you were reading.
        self._refreshing = False

        self.setWindowTitle("EON — Coding")
        self.resize(1200, 760)
        self.setStyleSheet(_STYLESHEET)

        self._header = QLabel("No project open")
        self._header.setObjectName("header")

        self._sidebar = QToolBox()
        self._sidebar.addItem(self._build_explorer(), "Explorer")
        self._sidebar.addItem(self._build_search(), "Search")
        self._sidebar.addItem(self._build_outline(), "Outline")
        self._sidebar.addItem(self._build_git(), "Git")

        self._tabs = QTabWidget()
        self._tabs.setTabsClosable(True)
        self._tabs.setMovable(True)
        self._tabs.setDocumentMode(True)
        self._tabs.tabCloseRequested.connect(self.close_tab)
        self._tabs.currentChanged.connect(self._on_tab_changed)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._sidebar)
        splitter.addWidget(self._tabs)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([300, 900])

        top = QHBoxLayout()
        top.addWidget(self._header)
        top.addStretch(1)

        layout = QVBoxLayout()
        layout.addLayout(top)

        # The stretch has to be named, or the *header row* soaks up the
        # spare height instead of the splitter — which leaves the
        # title floating in a tall empty band above the sidebar.
        layout.addWidget(splitter, 1)

        central = QWidget()
        central.setLayout(layout)
        self.setCentralWidget(central)

        self._build_status_bar()

    # --- the sidebar pages ------------------------------------------------

    def _build_explorer(self) -> QWidget:
        """The file tree, which is what the window has always had."""
        self._tree = QTreeWidget()
        self._tree.setHeaderLabels(["File", "Size"])
        self._tree.setColumnWidth(0, 200)
        self._tree.itemSelectionChanged.connect(self._on_file_selected)

        self._hint = QLabel("No files yet.")
        self._hint.setObjectName("hint")

        page = QWidget()
        layout = QVboxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._tree)
        layout.addWidget(self._hint)
        page.setLayout(layout)

        return page

    def _build_search(self) -> QWidget:
        """Project-wide text search.

        The box is what the user types in; the list underneath holds
        the files that matched, with the line of the first match so a
        result is worth clicking.
        """
        self._search_box = QLineEdit()
        self._search_box.setPlaceholderText("Search the project…")
        self._search_box.returnPressed.connect(self._run_search)

        self._search_results = QListWidget()
        self._search_results.itemActivated.connect(self._on_search_activated)
        self._search_results.itemClicked.connect(self._on_search_activated)

        self._search_note = QLabel("")
        self._search_note.setObjectName("hint")

        page = QWidget()
        layout = QVboxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._search_box)
        layout.addWidget(self._search_results)
        layout.addWidget(self._search_note)
        page.setLayout(layout)

        return page

    def _build_outline(self) -> QWidget:
        """The symbols in the file currently open.

        Backed by the same symbol index EON uses for its own
        ``find symbol`` command — which, until now, only the console
        could reach.
        """
        self._outline = QListWidget()
        self._outline.itemActivated.connect(self._on_outline_activated)
        self._outline.itemClicked.connect(self._on_outline_activated)

        self._outline_note = QLabel("Open a file to see its symbols.")
        self._outline_note.setObjectName("hint")

        page = QWidget()
        layout = QVboxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._outline)
        layout.addWidget(self._outline_note)
        page.setLayout(layout)

        return page

    def _build_git(self) -> QWidget:
        """The branch and what has changed on it."""
        self._git_branch = QLabel("Not a git repository.")
        self._git_branch.setObjectName("section")

        self._git_files = QListWidget()
        self._git_files.itemActivated.connect(self._on_git_activated)
        self._git_files.itemClicked.connect(self._on_git_activated)

        page = QWidget()
        layout = QVboxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._git_branch)
        layout.addWidget(self._git_files)
        page.setLayout(layout)

        return page

    def _build_status_bar(self) -> None:
        """The strip along the bottom: branch, file, cursor."""
        self._status_branch = QLabel("")
        self._status_file = QLabel("")
        self._status_position = QLabel("")

        bar = self.statusBar()
        bar.addWidget(self._status_file)
        bar.addPermanentWidget(self._status_branch)
        bar.addPermanentWidget(self._status_position)

    # --- showing ----------------------------------------------------------

    def set_queries(self, queries) -> None:
        """Points the sidebar sections at something that can answer them.

        Called by the service when coding mode opens a project, which
        happens on the console thread — so this only stores the object,
        and ``refresh`` does the asking on the main thread.

        Args:
            queries: Something with ``search``, ``outline`` and ``git``.
        """
        self._queries = queries

    def show_project(self, project_root: Path, title: str) -> None:
        """Points the window at a project and refreshes it.

        Args:
            project_root: The folder to display.
            title: The project's name, for the header.
        """
        changed_project = self.project_root != Path(project_root)

        self.project_root = Path(project_root)

        self._header.setText(f"{title} — {self.project_root}")

        if changed_project:
            # Files from the last project would be confusing, and a tab
            # pointing at a file that is no longer on disk is worse.
            self._tabs.clear()
            self._search_results.clear()
            self._search_box.clear()
            self._search_note.setText("")

        self.refresh()

        self.show()
        self.raise_()
        self.activateWindow()

    def refresh(self) -> None:
        """Re-reads the project: the tree, the outline, and git.

        Keeps the open tabs open across a refresh, so a file EON has
        just written appears without you losing your place.
        """
        if self.project_root is None:
            return

        selected = self._selected_relative_path()

        self._refreshing = True
        try:
            self._tree.clear()

            files = self._list_files()

            for relative, size in files:
                item = QTreeWidgetItem([relative, _human_size(size)])
                item.setData(0, Qt.ItemDataRole.UserRole, relative)
                self._tree.addTopLevelItem(item)

            if not files:
                self._hint.setText("This project is empty so far.")
            else:
                self._hint.setText(f"{len(files)} file(s).")
                self._reselect(selected)
        finally:
            self._refreshing = False

        self._refresh_outline()
        self._refresh_git()

    # --- tabs ------------------------------------------------------------

    def open_file(self, relative: str, line: int | None = None) -> None:
        """Opens a file in a tab, or focuses it if it is already open.

        Args:
            relative: The file's path, relative to the project root.
            line: A 1-based line to scroll to and highlight.
        """
        if self.project_root is None:
            return

        relative = relative.replace("\\", "/")

        for index in range(self._tabs.count()):
            if self._tabs.tabToolTip(index) == relative:
                self._tabs.setCurrentIndex(index)
                self._go_to_line(self._tabs.widget(index), line)
                return

        path = self.project_root / relative

        editor = QPlainTextEdit()
        editor.setReadOnly(True)
        editor.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)

        mono = QFont("Consolas")
        mono.setStyleHint(QFont.StyleHint.Monospace)
        mono.setPointSize(10)
        editor.setFont(mono)

        editor.setPlainText(_preview(path))

        index = self._tabs.addTab(editor, _tab_label(relative))
        self._tabs.setTabToolTip(index, relative)
        self._tabs.setCurrentIndex(index)

        # ``addTab`` makes the first tab current, and that fires
        # ``currentChanged`` *before* the tooltip above exists — so the
        # outline would look up a file with no name. Refreshing here as
        # well means the sidebar follows regardless of which signal did
        # or didn't fire.
        self._refresh_outline()
        self._update_status()

        self._go_to_line(editor, line)

    def close_tab(self, index: int) -> None:
        """Closes the tab at ``index``."""
        if 0 <= index < self._tabs.count():
            widget = self._tabs.widget(index)
            self._tabs.removeTab(index)
            if widget is not None:
                widget.deleteLater()

        self._refresh_outline()
        self._update_status()

    def current_relative_path(self) -> str | None:
        """The relative path of the file in the active tab, if any."""
        index = self._tabs.currentIndex()

        if index < 0:
            return None

        return self._tabs.tabToolTip(index) or None

    def _on_tab_changed(self, index: int) -> None:
        """Follows the active tab: outline and status follow it too."""
        self._refresh_outline()
        self._update_status()

    def _go_to_line(self, editor, line: int | None) -> None:
        """Scrolls an editor to a line and puts the cursor there."""
        if editor is None or line is None:
            return

        try:
            block = editor.document().findBlockByNumber(max(0, line - 1))
        except Exception:  # pragma: no cover - document safety net
            return

        if not block.isValid():
            return

        cursor = editor.textCursor()
        cursor.setPosition(block.position())
        editor.setTextCursor(cursor)
        editor.centerCursor()

    # --- the explorer ----------------------------------------------------

    def _list_files(self) -> list[tuple[str, int]]:
        """Every file in the project, as (relative path, size)."""
        assert self.project_root is not None

        found: list[tuple[str, int]] = []

        try:
            candidates = sorted(self.project_root.rglob("*"))
        except OSError:
            return []

        for path in candidates:
            try:
                if not path.is_file():
                    continue
                size = path.stat().st_size
            except OSError:
                continue

            relative = str(path.relative_to(self.project_root)).replace("\\", "/")
            found.append((relative, size))

        return found

    def _selected_relative_path(self) -> str | None:
        """The relative path of the currently selected file, if any."""
        items = self._tree.selectedItems()

        if not items:
            return None

        return items[0].data(0, Qt.ItemDataRole.UserRole)

    def _reselect(self, relative: str | None) -> None:
        """Restores the tree selection, if there was one.

        Deliberately does *nothing* when there was no previous
        selection: pre-selecting the first file looks helpful but means
        the first click on it does nothing, because the selection has
        not changed and so no signal fires.
        """
        target = relative

        if target is None:
            return

        for index in range(self._tree.topLevelItemCount()):
            item = self._tree.topLevelItem(index)
            if item is not None and item.data(0, Qt.ItemDataRole.UserRole) == target:
                self._tree.setCurrentItem(item)
                return

        first = self._tree.topLevelItem(0)
        if first is not None:
            self._tree.setCurrentItem(first)

    def _on_file_selected(self) -> None:
        """Opens the selected file in a tab.

        Only when the user did the selecting — a refresh restores the
        previous selection, and that must not move the active tab.
        """
        if self._refreshing:
            return

        relative = self._selected_relative_path()

        if relative is not None:
            self.open_file(relative)

    # --- search -----------------------------------------------------------

    def _run_search(self) -> None:
        """Asks the backend what contains the query, and lists it."""
        query = self._search_box.text().strip()

        self._search_results.clear()

        if not query:
            self._search_note.setText("")
            return

        results = self._ask_search(query)

        for relative, line in results:
            item = QListWidgetItem(f"{relative}:{line}" if line else relative)
            item.setData(Qt.ItemDataRole.UserRole, (relative, line))
            self._search_results.addItem(item)

        if not results:
            self._search_note.setText(f"Nothing contains “{query}”.")
        elif len(results) == 1:
            self._search_note.setText("1 file.")
        else:
            self._search_note.setText(f"{len(results)} files.")

    def _ask_search(self, query: str) -> list[tuple[str, int]]:
        """The search results, or none if nothing is wired up."""
        if self._queries is None:
            return []

        try:
            return list(self._queries.search(query))
        except Exception:  # pragma: no cover - backend safety net
            return []

    def _on_search_activated(self, item: QListWidgetItem) -> None:
        """Opens the file a search result points at."""
        payload = item.data(Qt.ItemDataRole.UserRole)

        if not payload:
            return

        relative, line = payload
        self.open_file(relative, line)

    # --- outline ----------------------------------------------------------

    def _refresh_outline(self) -> None:
        """Lists the symbols in whichever file is open."""
        self._outline.clear()

        relative = self.current_relative_path()

        if relative is None:
            self._outline_note.setText("Open a file to see its symbols.")
            return

        symbols = self._ask_outline(relative)

        for name, kind, line in symbols:
            item = QListWidgetItem(f"{name}  ({kind})  :{line}")
            item.setData(Qt.ItemDataRole.UserRole, line)
            self._outline.addItem(item)

        if not symbols:
            self._outline_note.setText("No symbols found in this file.")
        else:
            self._outline_note.setText(f"{len(symbols)} symbol(s).")

    def _ask_outline(self, relative: str) -> list[tuple[str, str, int]]:
        """The symbols in a file, or none if nothing is wired up."""
        if self._queries is None:
            return []

        try:
            return list(self._queries.outline(relative))
        except Exception:  # pragma: no cover - backend safety net
            return []

    def _on_outline_activated(self, item: QListWidgetItem) -> None:
        """Jumps to the symbol's line in the open file."""
        line = item.data(Qt.ItemDataRole.UserRole)

        if line is None:
            return

        self._go_to_line(self._tabs.currentWidget(), int(line))

    # --- git --------------------------------------------------------------

    def _refresh_git(self) -> None:
        """Shows the branch and the files that changed on it."""
        self._git_files.clear()

        branch, changed = self._ask_git()

        if branch is None:
            self._git_branch.setText("Not a git repository.")
        else:
            self._git_branch.setText(f"On branch {branch}")
            self._status_branch.setText(branch)

        for relative, status in changed:
            item = QListWidgetItem(f"{status}  {relative}")
            item.setData(Qt.ItemDataRole.UserRole, relative)
            self._git_files.addItem(item)

        if branch is not None and not changed:
            self._git_files.addItem(QListWidgetItem("Nothing changed."))

        self._update_status(changed=len(changed))

    def _ask_git(self) -> tuple[str | None, list[tuple[str, str]]]:
        """The branch and changed files, or nothing if unwired."""
        if self._queries is None:
            return None, []

        try:
            return self._queries.git()
        except Exception:  # pragma: no cover - backend safety net
            return None, []

    def _on_git_activated(self, item: QListWidgetItem) -> None:
        """Opens a changed file."""
        relative = item.data(Qt.ItemDataRole.UserRole)

        if relative:
            self.open_file(str(relative))

    # --- the status bar ---------------------------------------------------

    def _update_status(self, changed: int | None = None) -> None:
        """Refreshes the bottom strip."""
        relative = self.current_relative_path()
        self._status_file.setText(relative or "No file open")

        if changed is not None:
            self._changed_count = changed

        self._status_position.setText("")

    def update_position(self, line: int, column: int) -> None:
        """Reports where the cursor is. Called by the editor, later."""
        self._status_position.setText(f"Ln {line}, Col {column}")


def _tab_label(relative: str) -> str:
    """A short tab title: the file's name, not its whole path."""
    return relative.rsplit("/", 1)[-1]


def _preview(path: Path) -> str:
    """Reads a file for display, or explains why it won't.

    Args:
        path: The file to show.

    Returns:
        The file's text, or a short note about why it isn't shown.
    """
    try:
        size = path.stat().st_size
    except OSError as error:
        return f"Could not read {path.name}: {error}"

    if size > MAX_PREVIEW_BYTES:
        return (
            f"{path.name} is {_human_size(size)} — too large to show here.\n"
            "Open it in your editor to read it."
        )

    if path.suffix.lower() not in TEXT_SUFFIXES:
        return f"{path.name} ({_human_size(size)}) isn't a text file."

    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError as error:
        return f"Could not read {path.name}: {error}"


def _human_size(size: int) -> str:
    """A byte count as something short and readable."""
    if size < 1024:
        return f"{size} B"

    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"

    return f"{size / (1024 * 1024):.1f} MB"
