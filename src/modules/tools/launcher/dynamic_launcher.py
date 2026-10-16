"""
Dynamic Application Launcher.

Launches any discovered application.
"""

from __future__ import annotations

import subprocess

from src.modules.tools.launcher.models import Application


class DynamicLauncher:

      def launch_application(self, application):
        try:
            subprocess.Popen([application.path])
            return True

        except Exception:
            return False
