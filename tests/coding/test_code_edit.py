"""
Tests for the code_edit package: SourceEditor.replace_node,
CodeEditEngine.edit_symbol, and DiffGenerator.

Covers two real bugs found while wiring the coding pipeline:

    * code_edit/editor.py had its entire contents duplicated,
      producing a SyntaxError and a missing `replace_node` method
      that `CodeEditEngine.edit_symbol` depends on.

    * code_edit/diff.py defined `changed_line_count` nested inside
      `has_changes`, making it permanently unreachable.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.modules.workspace.workspaces.coding.code_edit import (
    CodeEditEngine,
    EditRequest,
)
from src.modules.workspace.workspaces.coding.code_edit.diff import (
    DiffGenerator,
)
from src.modules.workspace.workspaces.coding.code_edit.editor import (
    SourceEditor,
)


SAMPLE_SOURCE = (
    "def greet(name):\n"
    "    return \"hello \" + name\n"
    "\n"
    "\n"
    "class Greeter:\n"
    "    def hello(self):\n"
    "        return \"hi\"\n"
)


@pytest.fixture
def sample_file(tmp_path: Path) -> Path:
    file = tmp_path / "sample.py"
    file.write_text(SAMPLE_SOURCE, encoding="utf-8")
    return file


class TestSourceEditorReplaceNode:
    def test_replace_node_does_not_write_to_disk(
        self, sample_file: Path,
    ) -> None:
        import ast

        editor = SourceEditor()
        tree = ast.parse(sample_file.read_text(encoding="utf-8"))
        func_node = tree.body[0]

        original, updated = editor.replace_node(
            file=sample_file,
            node=func_node,
            replacement='def greet(name):\n    return f"hi {name}"',
        )

        assert original == SAMPLE_SOURCE
        assert 'f"hi {name}"' in updated
        # Nothing should be written to disk by replace_node itself.
        assert sample_file.read_text(encoding="utf-8") == SAMPLE_SOURCE

    def test_replace_lines_still_writes_to_disk(
        self, sample_file: Path,
    ) -> None:
        editor = SourceEditor()

        editor.replace_lines(
            sample_file,
            1,
            2,
            "def greet(name):\n    return 'hey ' + name",
        )

        assert "hey" in sample_file.read_text(encoding="utf-8")


class TestCodeEditEngine:
    def test_edit_symbol_success(self, sample_file: Path) -> None:
        engine = CodeEditEngine()

        result = engine.edit_symbol(
            EditRequest(
                file=sample_file,
                symbol="greet",
                instruction=(
                    'def greet(name):\n    return f"hey {name}"'
                ),
            ),
        )

        assert result.success is True
        assert "hey" in result.updated
        # edit_symbol must not write to disk on its own — that is
        # PatchEngine's job, only after validation.
        assert sample_file.read_text(encoding="utf-8") == SAMPLE_SOURCE

    def test_edit_symbol_missing_symbol(self, sample_file: Path) -> None:
        engine = CodeEditEngine()

        result = engine.edit_symbol(
            EditRequest(
                file=sample_file,
                symbol="does_not_exist",
                instruction="pass",
            ),
        )

        assert result.success is False
        assert "not found" in result.message


class TestDiffGenerator:
    def test_changed_line_count_is_reachable(self) -> None:
        diff = DiffGenerator()

        count = diff.changed_line_count(
            "a\nb\nc\n",
            "a\nx\nc\n",
        )

        assert count == 2

    def test_has_changes(self) -> None:
        diff = DiffGenerator()

        assert diff.has_changes("a", "b") is True
        assert diff.has_changes("a", "a") is False
