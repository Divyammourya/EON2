

"""
Application Builder.

Builds an ApplicationRegistry by discovering
installed desktop applications.
"""

from __future__ import annotations

from src.modules.tools.launcher.models import Application
from src.modules.tools.launcher.registry import ApplicationRegistry
from src.modules.tools.launcher.scanner import ApplicationScanner
from src.modules.tools.launcher.shortcuts import ShortcutScanner
from src.modules.tools.launcher.resolver import ShortcutResolver

from src.modules.tools.launcher.cache import ApplicationCache


class ApplicationBuilder:

    def __init__(self) -> None:
        self.application_scanner = ApplicationScanner()
        self.shortcut_scanner = ShortcutScanner()
        self.shortcut_resolver = ShortcutResolver()
        self.cache = ApplicationCache()

    def build(self) -> ApplicationRegistry:

        if self.cache.exists():
            return self.cache.load()

        registry = ApplicationRegistry()

        for application in self.application_scanner.scan():

            try:
                registry.register(application)

            except Exception:
                pass

        for shortcut in self.shortcut_scanner.scan():

            target = self.shortcut_resolver.resolve(shortcut)

            if target is None:
                continue

            name = shortcut.stem.lower()

            aliases = []

            if name == "visual studio code":
                aliases = ["vscode", "vs code", "code"]

            elif name == "google chrome":
                aliases = ["chrome"]

            elif name == "mozilla firefox":
                aliases = ["firefox"]

            application = Application(
                name=name,
                path=str(target),
                aliases=aliases,
            )

            try:
                registry.register(application)

            except Exception:
                pass

        self.cache.save(registry)

        return registry
