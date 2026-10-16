from __future__ import annotations

import re

from dataclasses import dataclass, field


@dataclass(slots=True)
class ParsedCommand:
    """
    Represents a parsed coding command.

    `arguments` is a named-value map (e.g. {"path": "a.py"}) rather
    than a single string, so a command needing more than one piece
    of data (a description, a path plus content) has somewhere to
    put it. See PlanStep in planner/step.py for the matching change
    on the planner side.
    """

    action: str
    arguments: dict[str, str] = field(default_factory=dict)


class CodingCommandParser:
    """
    Converts natural language into Coding Workspace commands.
    """

    def parse(self, text: str) -> ParsedCommand | None:

        message = text.strip()

        lower = message.lower()

        # --------------------------
        # Open Project
        # --------------------------

        if lower.startswith("open project "):
            return ParsedCommand(
                "open_project",
                {"path": message[len("open project "):].strip()},
            )

        # --------------------------
        # Create Project (AI-driven scaffold)
        # --------------------------
        # Checked before the "create file"/"create directory" and
        # "open"/"read" patterns below, since a project description
        # can freely mention words like "file" ("...with a config
        # file...") without meaning the narrower create_file command.

        if (
            re.match(r"^(create|scaffold|generate|build)\b", message, re.IGNORECASE)
            and re.search(r"\bproject\b", lower)
        ):
            return ParsedCommand(
                "create_project",
                {"description": message},
            )

        # --------------------------
        # Create File
        # --------------------------

        match = re.match(
            r"^create\s+(?:a\s+|an\s+)?file\s+(.+)$",
            message,
            re.IGNORECASE,
        )

        if match:
            return ParsedCommand(
                "create_file",
                {"path": match.group(1).strip()},
            )

        # --------------------------
        # Create Directory
        # --------------------------

        match = re.match(
            r"^create\s+(?:a\s+|an\s+)?(?:directory|folder)\s+(.+)$",
            message,
            re.IGNORECASE,
        )

        if match:
            return ParsedCommand(
                "create_directory",
                {"path": match.group(1).strip()},
            )

        # --------------------------
        # Read/Open File
        # --------------------------

        match = re.match(
            r"^(read|open|show)\s+(.+)$",
            message,
            re.IGNORECASE,
        )

        if match:
            return ParsedCommand(
                "read_file",
                {"path": match.group(2).strip()},
            )

        # --------------------------
        # Search
        # --------------------------

        match = re.match(
            r"^(search|find)\s+(.+)$",
            message,
            re.IGNORECASE,
        )

        if match:
            return ParsedCommand(
                "search",
                {"query": match.group(2).strip()},
            )

        # --------------------------
        # Find Symbol
        # --------------------------

        match = re.match(
            r"where\s+is\s+(.+?)\s+defined\??",
            lower,
        )

        if match:
            return ParsedCommand(
                "find_symbol",
                {"name": match.group(1).strip()},
            )

        # --------------------------
        # Index
        # --------------------------

        if lower in {
            "index",
            "index project",
            "index repository",
        }:
            return ParsedCommand(
                "index",
                {},
            )


        # --------------------------
        # Run command
        # --------------------------

        match = re.match(
            r"^(run|execute)\s+(.+)$",
            message,
            re.IGNORECASE,
        )

        if match:
            return ParsedCommand(
                "run_command",
                {"command": match.group(2).strip()},
            )

        return None
