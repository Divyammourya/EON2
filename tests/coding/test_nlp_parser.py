"""
Tests for CodingCommandParser.

Covers the existing routes (updated to the dict-based `arguments`
convention) plus the new create_file / create_directory /
create_project routes added for project generation.
"""

from __future__ import annotations

from src.modules.workspace.workspaces.coding.nlp_parser import (
    CodingCommandParser,
)


class TestExistingRoutes:
    def test_open_project(self) -> None:
        parser = CodingCommandParser()

        parsed = parser.parse("open project /some/path")

        assert parsed.action == "open_project"
        assert parsed.arguments == {"path": "/some/path"}

    def test_read_file(self) -> None:
        parser = CodingCommandParser()

        parsed = parser.parse("read sample.py")

        assert parsed.action == "read_file"
        assert parsed.arguments == {"path": "sample.py"}

    def test_search(self) -> None:
        parser = CodingCommandParser()

        parsed = parser.parse("search greet")

        assert parsed.action == "search"
        assert parsed.arguments == {"query": "greet"}

    def test_find_symbol(self) -> None:
        parser = CodingCommandParser()

        parsed = parser.parse("where is greet defined")

        assert parsed.action == "find_symbol"
        assert parsed.arguments == {"name": "greet"}

    def test_index(self) -> None:
        parser = CodingCommandParser()

        parsed = parser.parse("index project")

        assert parsed.action == "index"
        assert parsed.arguments == {}

    def test_unparseable_returns_none(self) -> None:
        parser = CodingCommandParser()

        assert parser.parse("what is the meaning of life") is None


class TestFileCreationRoutes:
    def test_create_file(self) -> None:
        parser = CodingCommandParser()

        parsed = parser.parse("create file src/app.py")

        assert parsed.action == "create_file"
        assert parsed.arguments == {"path": "src/app.py"}

    def test_create_file_with_article(self) -> None:
        parser = CodingCommandParser()

        parsed = parser.parse("create a file README.md")

        assert parsed.action == "create_file"
        assert parsed.arguments == {"path": "README.md"}

    def test_create_directory(self) -> None:
        parser = CodingCommandParser()

        parsed = parser.parse("create directory src/app")

        assert parsed.action == "create_directory"
        assert parsed.arguments == {"path": "src/app"}

    def test_create_folder_alias(self) -> None:
        parser = CodingCommandParser()

        parsed = parser.parse("create a folder tests")

        assert parsed.action == "create_directory"
        assert parsed.arguments == {"path": "tests"}


class TestCreateProjectRoute:
    def test_create_project_routes_full_description(self) -> None:
        parser = CodingCommandParser()

        text = (
            "Create a Python FastAPI project with a health check "
            "endpoint and a README"
        )

        parsed = parser.parse(text)

        assert parsed.action == "create_project"
        assert parsed.arguments == {"description": text}

    def test_generate_project_verb_variant(self) -> None:
        parser = CodingCommandParser()

        parsed = parser.parse("generate a new Flask project")

        assert parsed.action == "create_project"

    def test_create_project_wins_over_create_file_when_project_named(
        self,
    ) -> None:
        parser = CodingCommandParser()

        # Mentions "file" in passing, but is clearly a project
        # description, not a request to create one literal file.
        parsed = parser.parse(
            "create a project with a config file and a README",
        )

        assert parsed.action == "create_project"

    def test_create_file_still_wins_without_project_keyword(
        self,
    ) -> None:
        parser = CodingCommandParser()

        parsed = parser.parse("create file config.json")

        assert parsed.action == "create_file"
