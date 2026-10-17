"""
EON Application.
"""

from __future__ import annotations

from src.core.engine import Engine
from src.modules.briefing.morning import MorningBriefing
from src.modules.conversation.manager import ConversationManager
from src.modules.voice.service import VoiceService
from src.modules.proactive.service import ProactiveService
from src.modules.workspace.workspaces.coding.mode import CodingMode
from src.ui.coding.service import CodingWindowService
from src.ui.hologram.service import DesktopCompanionService


class Application:

    def __init__(
        self,
        engine: Engine,
        conversation: ConversationManager,
        voice: VoiceService,
        proactive: ProactiveService,
        hologram: DesktopCompanionService,
        briefing: MorningBriefing,
        coding_window: CodingWindowService,
        coding: CodingMode,
    ) -> None:

        self.engine = engine
        self.conversation = conversation
        self.voice = voice
        self.proactive = proactive
        self.hologram = hologram
        self.briefing = briefing
        self.coding_window = coding_window
        self.coding = coding
