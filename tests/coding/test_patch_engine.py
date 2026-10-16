"""
Tests for the patch_engine package.

Covers real bugs found while wiring the coding pipeline:

    * patch_engine/patch.py and patch_engine/rollback.py were empty
      files, even though PatchBuilder and Rollback are imported and
      used elsewhere (agent.py, patch_engine/__init__.py).

    * PatchEngine.apply() checked `if validation is not None`, but
      PatchValidator.validate() returns a list[str] — never None —
      so every patch was unconditionally rejected as invalid.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.modules.workspace.workspaces.coding.patch_engine import (
    PatchBuilder,
    PatchEngine,
    Rollback,
)


@pytest.fixture
def sample_file(tmp_path: Path) -> Path:
    file = tmp_path / "sample.py"
    file.write_text("value = 1\n", encoding="utf-8")
    return file


class TestPatchBuilder:
    def test_build_single_operation(self, sample_file: Path) -> None:
        builder = PatchBuilder()

        operation = builder.build(
            file=sample_file,
            original="value = 1\n",
            updated="value = 2\n",
        )

        assert operation.file == sample_file
        assert operation.original == "value = 1\n"
        assert operation.updated == "value = 2\n"

    def test_build_many(self, tmp_path: Path) -> None:
        file_a = tmp_path / "a.py"
        file_b = tmp_path / "b.py"
        file_a.write_text("a = 1\n", encoding="utf-8")
        file_b.write_text("b = 1\n", encoding="utf-8")

        builder = PatchBuilder()

        operations = builder.build_many(
            [
                (file_a, "a = 1\n", "a = 2\n"),
                (file_b, "b = 1\n", "b = 2\n"),
            ],
        )

        assert len(operations) == 2
        assert operations[0].file == file_a
        assert operations[1].file == file_b


class TestPatchEngineApply:
    def test_valid_patch_is_applied(self, sample_file: Path) -> None:
        engine = PatchEngine()
        builder = PatchBuilder()

        operation = builder.build(
            file=sample_file,
            original="value = 1\n",
            updated="value = 2\n",
        )

        result = engine.apply([operation])

        assert result.success is True
        assert result.changed_files == 1
        assert sample_file.read_text(encoding="utf-8") == "value = 2\n"

    def test_patch_with_no_changes_is_rejected(
        self, sample_file: Path,
    ) -> None:
        engine = PatchEngine()
        builder = PatchBuilder()

        # original == updated -> PatchValidator should reject this.
        operation = builder.build(
            file=sample_file,
            original="value = 1\n",
            updated="value = 1\n",
        )

        result = engine.apply([operation])

        assert result.success is False
        # File must be untouched since validation failed.
        assert sample_file.read_text(encoding="utf-8") == "value = 1\n"

    def test_patch_for_missing_file_is_rejected(
        self, tmp_path: Path,
    ) -> None:
        engine = PatchEngine()
        builder = PatchBuilder()

        missing = tmp_path / "does_not_exist.py"

        operation = builder.build(
            file=missing,
            original="a = 1\n",
            updated="a = 2\n",
        )

        result = engine.apply([operation])

        assert result.success is False


class TestRollback:
    def test_successful_patch_can_be_rolled_back(
        self, sample_file: Path,
    ) -> None:
        engine = PatchEngine()
        builder = PatchBuilder()

        operation = builder.build(
            file=sample_file,
            original="value = 1\n",
            updated="value = 2\n",
        )

        apply_result = engine.apply([operation])
        assert apply_result.success is True
        assert sample_file.read_text(encoding="utf-8") == "value = 2\n"

        rollback_result = engine.rollback.rollback_last()

        assert rollback_result is not None
        assert rollback_result.success is True
        assert sample_file.read_text(encoding="utf-8") == "value = 1\n"

    def test_rollback_with_no_history_returns_none(self) -> None:
        rollback = Rollback()

        assert rollback.rollback_last() is None
        assert rollback.has_history() is False

    def test_failed_patch_is_not_recorded_for_rollback(
        self, sample_file: Path,
    ) -> None:
        engine = PatchEngine()
        builder = PatchBuilder()

        # No-op edit -> validation failure -> should not be recorded.
        operation = builder.build(
            file=sample_file,
            original="value = 1\n",
            updated="value = 1\n",
        )

        engine.apply([operation])

        assert engine.rollback.has_history() is False
