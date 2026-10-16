"""
EON Application.
"""

from __future__ import annotations

from src.core.engine import Engine
from src.modules.briefing.morning import MorningBriefing
from src.modules.conversation.manager import ConversationManager
from src.modules.voice.service import VoiceService
from src.modules.proactive.service import ProactiveService
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
    ) -> None:

        self.engine = engine
        self.conversation = conversation
        self.voice = voice
        self.proactive = proactive
        self.hologram = hologram
        self.briefing = briefing
