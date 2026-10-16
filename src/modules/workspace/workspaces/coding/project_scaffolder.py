"""
AI-driven project scaffolding for the Coding Workspace.

Deliberately narrow, matching `AICodeEditor`'s role: this class's only
job is prompting the model for a file list and parsing the reply. It
knows nothing about the filesystem, the planner, or how those files
actually get written — that stays with CodingAgent, FileManager, and
the Planner/PlanExecutor pipeline, which is exercised identically
whether the file list came from here or was supplied literally.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

from src.modules.ai.manager import AIManager

_CODE_FENCE = re.compile(
    r"```(?:[a-zA-Z0-9_+-]*)\s*\n(.*?)```",
    re.DOTALL,
)

_SYSTEM_PROMPT = (
    "You are a project scaffolding engine embedded inside a "
    "developer tool. You are given a natural-language description "
    "of a project to create. Respond with ONLY a JSON array - no "
    "explanation, no markdown code fences, no surrounding prose. "
    "Each element of the array must be an object with exactly two "
    "string fields: \"path\" (a file path relative to the project "
    "root, using forward slashes, e.g. \"app/main.py\") and "
    "\"content\" (the complete literal file content). Do not include "
    "directory-only entries; every entry must be a file. Produce a "
    "small, working set of files - only what the description asks "
    "for, with correct, runnable content, not a placeholder."
)


@dataclass(slots=True)
class ScaffoldFile:
    """A single file the model wants created, with its content."""

    path: str
    content: str


@dataclass(slots=True)
class ScaffoldResult:
    """Result of asking the model to scaffold a project."""

    success: bool
    files: list[ScaffoldFile]
    message: str = ""


class ProjectScaffolder:
    """
    Turns a natural-language project description into a list of
    files-to-create, using a chat-capable AI provider.
    """

    def __init__(
        self,
        ai: AIManager | None = None,
    ) -> None:
        self._ai = ai or AIManager()

    def generate(self, description: str) -> ScaffoldResult:
        """
        Ask the model to design a project matching `description` and
        return the files it wants created.

        Never raises for a malformed or empty model reply - that is
        an expected failure mode (the model didn't cooperate), not an
        exceptional one, so it comes back as a `ScaffoldResult` with
        `success=False` for the caller to report plainly.
        """

        messages = [
            {
                "role": "system",
                "content": _SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": description,
            },
        ]

        reply = self._ai.chat(messages)

        try:
            entries = self._parse(reply)
        except ValueError as exc:
            return ScaffoldResult(
                success=False,
                files=[],
                message=f"Could not parse project plan: {exc}",
            )

        files = [
            ScaffoldFile(
                path=entry["path"],
                content=entry.get("content", ""),
            )
            for entry in entries
            if isinstance(entry, dict)
            and isinstance(entry.get("path"), str)
            and entry["path"].strip()
        ]

        if not files:
            return ScaffoldResult(
                success=False,
                files=[],
                message="The model did not return any files to create.",
            )

        return ScaffoldResult(
            success=True,
            files=files,
        )

    def _parse(self, reply: str) -> list[dict]:
        """
        Extract the JSON file list from a model reply, tolerating a
        stray markdown code fence despite the system prompt asking
        for none (mirrors `AICodeEditor._extract_code`).
        """

        text = self._strip_fence(reply)

        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSON ({exc})") from exc

        if isinstance(data, dict) and "files" in data:
            data = data["files"]

        if not isinstance(data, list):
            raise ValueError("expected a JSON array of files")

        return data

    def _strip_fence(self, reply: str) -> str:

        match = _CODE_FENCE.search(reply)

        if match:
            return match.group(1).strip()

        return reply.strip()
