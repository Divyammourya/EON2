from __future__ import annotations

from pathlib import Path


class ValidationStrategy:
    """
    Determines how a project should be validated.

    The strategy layer only detects the appropriate command.
    It does not execute anything.
    """

    def detect(self, project_root: Path) -> list[str] | None:
        """
        Return the best validation command for the project.

        Returns:
            A command suitable for subprocess execution,
            or None when no known validation strategy exists.
        """

        # Python projects
        if (
            (project_root / "pytest.ini").exists()
            or (project_root / "pyproject.toml").exists()
            or (project_root / "setup.cfg").exists()
        ):
            return ["python", "-m", "pytest"]

        if (project_root / "requirements.txt").exists():
            return ["python", "-m", "pytest"]

        # Node / JavaScript / TypeScript projects
        package_json = project_root / "package.json"

        if package_json.exists():
            return self._detect_node_command(package_json)

        # Rust
        if (project_root / "Cargo.toml").exists():
            return ["cargo", "test"]

        # Go
        if (project_root / "go.mod").exists():
            return ["go", "test", "./..."]

        # Java Maven
        if (project_root / "pom.xml").exists():
            return ["mvn", "test"]

        # Java Gradle
        if (project_root / "build.gradle").exists():
            return ["gradle", "test"]

        if (project_root / "build.gradle.kts").exists():
            return ["gradle", "test"]

        return None

    def _detect_node_command(
        self,
        package_json: Path,
    ) -> list[str] | None:
        """
        Detect a validation command from package.json.

        This method intentionally performs only lightweight
        inspection. Dependency installation is never performed here.
        """

        try:
            import json

            data = json.loads(
                package_json.read_text(
                    encoding="utf-8",
                )
            )

        except (
            OSError,
            UnicodeDecodeError,
            json.JSONDecodeError,
        ):
            return None

        scripts = data.get("scripts", {})

        if not isinstance(scripts, dict):
            return None

        if "test" in scripts:
            return ["npm", "test"]

        if "lint" in scripts:
            return ["npm", "run", "lint"]

        if "build" in scripts:
            return ["npm", "run", "build"]

        return None
