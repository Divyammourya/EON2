"""EON's coding window.

A small built-in editor: the project's files down the left, the
selected file's contents on the right. Deliberately read-only on the
code side — EON writes the files, you watch them appear. Editing them
here as well would mean two writers and a save-conflict problem for no
real gain, since you already have an editor you like.

Design notes:
    - PySide6 is imported at module scope here, which is why
      ``service.py`` imports *this* module lazily. Nothing in EON
      touches PySide6 unless a coding window is actually wanted.
    - Only one ``QApplication`` may exist per process, and EON's
      hologram overlay creates it. So this window adopts the existing
      instance rather than making its own — see CodingWindowService.
    - Large or binary files are summarised instead of shown. Reading a
      50 MB file into a text box would freeze the window, and the
      point of the window is to see what EON is doing, not to be a
      file viewer.

Requires: PySide6 (already a dependency for the hologram overlay)
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPlainTextEdit,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
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
QTreeWidget {
    background: #0e141b; border: 1px solid #1d2b36; color: #c8d8e2;
}
QTreeWidget::item:selected { background: #14414a; color: #eafcff; }
QPlainTextEdit {
    background: #0e141b; border: 1px solid #1d2b36; color: #cfe9f5;
}
QSplitter::handle { background: #16222c; }
"""


class CodingWindow(QMainWindow):
    """The coding window: a file tree and a code view.

    Attributes:
        project_root: The project being shown, if any.
    """

    def __init__(self) -> None:
        super().__init__()

        self.project_root: Path | None = None

        self.setWindowTitle("EON — Coding")
        self.resize(1100, 700)
        self.setStyleSheet(_STYLESHEET)

        self._header = QLabel("No project open")
        self._header.setObjectName("header")

        self._hint = QLabel(
            "EON writes the files; they appear here as they are created."
        )
        self._hint.setObjectName("hint")

        self._tree = QTreeWidget()
        self._tree.setHeaderLabels(["File", "Size"])
        self._tree.setColumnWidth(0, 320)
        self._tree.itemSelectionChanged.connect(self._on_file_selected)

        self._code = QPlainTextEdit()
        self._code.setReadOnly(True)
        self._code.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)

        mono = QFont("Consolas")
        mono.setStyleHint(QFont.StyleHint.Monospace)
        mono.setPointSize(10)
        self._code.setFont(mono)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._tree)
        splitter.addWidget(self._code)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)

        top = QHBoxLayout()
        top.addWidget(self._header)
        top.addStretch(1)

        layout = QVBoxLayout()
        layout.addLayout(top)
        layout.addWidget(splitter)
        layout.addWidget(self._hint)

        central = QWidget()
        central.setLayout(layout)
        self.setCentralWidget(central)

    # --- showing ----------------------------------------------------------

    def show_project(self, project_root: Path, title: str) -> None:
        """Points the window at a project and refreshes it.

        Args:
            project_root: The folder to display.
            title: The project's name, for the header.
        """
        self.project_root = Path(project_root)

        self._header.setText(f"{title} — {self.project_root}")

        self.refresh()

        self.show()
        self.raise_()
        self.activateWindow()

    def refresh(self) -> None:
        """Re-reads the project's files into the tree.

        Keeps the selected file selected across a refresh, so a file
        you're watching doesn't jump away when EON writes another one.
        """
        if self.project_root is None:
            return

        selected = self._selected_relative_path()

        self._tree.clear()

        files = self._list_files()

        for relative, size in files:
            item = QTreeWidgetItem([relative, _human_size(size)])
            item.setData(0, Qt.ItemDataRole.UserRole, relative)
            self._tree.addTopLevelItem(item)

        if not files:
            self._code.setPlainText(
                "This project is empty so far.\n\n"
                "Ask EON to create a file, or to create a project."
            )
            self._hint.setText("No files yet.")
            return

        self._hint.setText(f"{len(files)} file(s).")

        self._reselect(selected)

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
        """Selects a file by relative path, or the first file."""
        target = relative

        if target is None:
            first = self._tree.topLevelItem(0)
            if first is not None:
                self._tree.setCurrentItem(first)
            return

        for index in range(self._tree.topLevelItemCount()):
            item = self._tree.topLevelItem(index)
            if item is not None and item.data(0, Qt.ItemDataRole.UserRole) == target:
                self._tree.setCurrentItem(item)
                return

        first = self._tree.topLevelItem(0)
        if first is not None:
            self._tree.setCurrentItem(first)

    # --- the code view ----------------------------------------------------

    def _on_file_selected(self) -> None:
        """Shows the selected file's contents."""
        relative = self._selected_relative_path()

        if relative is None or self.project_root is None:
            return

        path = self.project_root / relative

        self._code.setPlainText(_preview(path))


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
