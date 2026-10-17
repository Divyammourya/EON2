"""
Service registration for EON.

Responsible for constructing and registering application services.
"""

from __future__ import annotations

from pathlib import Path

from src.core.container import ServiceContainer
from src.core.config import ConfigManager
from src.core.logger import get_logger

from src.modules.brain.manager import Brain
from src.modules.conversation.history import ConversationHistory
from src.modules.intent import IntentManager
from src.modules.planner import PlannerManager
from src.modules.actions import (
    ActionExecutor,
    ActionRouter,
)
from src.modules.tools.resource.service import ResourceService

from src.modules.memory.config import MemoryConfig
from src.modules.memory.service import MemoryService
from src.modules.memory.stores.sqlite import SQLiteMemoryStore

from src.modules.voice.config import VoiceServiceConfig
from src.modules.voice.manager import VoiceManager
from src.modules.voice.service import VoiceService
from src.modules.voice.session import VoiceSessionManager
from src.modules.voice.providers.faster_whisper import FasterWhisperProvider
from src.modules.voice.providers.piper import PiperProvider
from src.modules.voice.providers.sounddevice_microphone import SoundDeviceMicrophone
from src.modules.voice.providers.sounddevice_speaker import SoundDeviceSpeaker

from src.modules.proactive.config import ProactiveServiceConfig
from src.modules.proactive.service import ProactiveService

from src.modules.execution.executor import ExecutionExecutor
from src.modules.execution.manager import ExecutionManager

from src.modules.monitor import MonitorManager
from src.modules.monitor.config import AmbientMonitorConfig

from src.modules.reasoning import ReasoningManager
from src.modules.permissions.config import PermissionsServiceConfig
from src.modules.permissions.manager import PermissionManager

from src.modules.reflection import ReflectionManager

from src.modules.context import ContextManager

from src.modules.memory.models import DEFAULT_MIN_SCORE
from src.modules.recall import RecallManager

from src.modules.store import StoreManager

from src.modules.perception import PerceptionManager

from src.modules.vision.config import VisionConfig
from src.modules.vision.manager import VisionManager

from src.modules.identity.manager import IdentityManager
from src.modules.identity.personality import PERSONALITY_PRESETS

from src.modules.tools.knowledge.web_search import WebSearchClient
from src.modules.tools.media.music import MusicTool
from src.modules.tools.registry import ToolRegistry
from src.modules.tools.utility.lists import DEFAULT_LISTS_PATH, ListStore
from src.modules.tools.utility.skills import LocalSkills
from src.modules.tools.launcher.tool import LauncherTool
from src.modules.tools.system.vscode import VSCodeTool
from src.modules.tools.system.browser import BrowserTool
from src.modules.tools.system.terminal import TerminalTool

from src.modules.automation.clipboard import ClipboardTool
from src.modules.automation.volume import VolumeTool
from src.modules.automation.brightness import BrightnessTool
from src.modules.automation.window import WindowTool
from src.modules.automation.screenshot import ScreenshotTool
from src.modules.automation.file_organizer import FileOrganizerTool
from src.modules.automation.text_input import TypeTextTool
from src.modules.automation.ui_control import UIControlTool
from src.modules.automation.weather import WeatherTool

from src.modules.integrations.config import IntegrationsConfig
from src.modules.integrations.google_auth import GoogleAuthManager
from src.modules.integrations.calendar_tool import CalendarTool
from src.modules.integrations.email_tool import EmailTool
from src.modules.integrations.messaging_tool import MessagingTool

from src.ui.hologram.config import HologramConfig
from src.ui.hologram.service import DesktopCompanionService

from src.bootstrap.workspaces import (
    create_workspace_manager,
    create_workspace_router,
)

logger = get_logger("Bootstrap")

def register_services(
    container: ServiceContainer,
    config: ConfigManager | None = None,
) -> None:
    """
    Register all application services.
    """

    automation_enabled = bool(
        config.get("automation_enabled")
    ) if config is not None else False

    logger.info(
        "Automation is %s.",
        "enabled" if automation_enabled else "disabled (set automation_enabled=true in config/settings.json to turn it on)",
    )

    vision_config = VisionConfig()

    if config is not None:
        vision_enabled = config.get("vision_enabled")
        if vision_enabled is not None:
            vision_config.enabled = bool(vision_enabled)

        vision_model = config.get("vision_model")
        if vision_model is not None:
            vision_config.model = str(vision_model)

    logger.info(
        "Vision is %s.",
        "enabled" if vision_config.enabled else "disabled (set vision_enabled=true in config/settings.json to turn it on)",
    )

    history = ConversationHistory()

    # brain = Brain()
    identity = IdentityManager(
        personality=PERSONALITY_PRESETS["jarvis"],
    )

    web_grounding_enabled = True
    web_grounding_max_results = 3
    memory_max_messages = 40
    memory_keep_recent = 12

    if config is not None:
        grounding_enabled = config.get("web_grounding_enabled")
        if grounding_enabled is not None:
            web_grounding_enabled = bool(grounding_enabled)

        grounding_results = config.get("web_grounding_max_results")
        if grounding_results is not None:
            web_grounding_max_results = int(grounding_results)

        max_messages = config.get("conversation_memory_max_messages")
        if max_messages is not None:
            memory_max_messages = int(max_messages)

        keep_recent = config.get("conversation_memory_keep_recent")
        if keep_recent is not None:
            memory_keep_recent = int(keep_recent)

    skills_enabled = True
    skills_lists_path = DEFAULT_LISTS_PATH

    if config is not None:
        skills_setting = config.get("skills_enabled")
        if skills_setting is not None:
            skills_enabled = bool(skills_setting)

        lists_setting = config.get("skills_lists_path")
        if lists_setting:
            skills_lists_path = Path(str(lists_setting))

    logger.info(
        "Local skills are %s (calculator, unit conversion, lists at %s).",
        "enabled" if skills_enabled else "disabled (set skills_enabled=true in config/settings.json)",
        skills_lists_path,
    )

    logger.info(
        "Web grounding is %s.",
        "enabled (chat questions are looked up before answering)"
        if web_grounding_enabled
        else "disabled (set web_grounding_enabled=true in config/settings.json to turn it on)",
    )

    logger.info(
        "Conversation memory keeps the last %s messages and folds older ones "
        "into a summary past %s.",
        memory_keep_recent,
        memory_max_messages,
    )

    brain = Brain(
        identity=identity,
        knowledge=WebSearchClient(
            enabled=web_grounding_enabled,
            max_results=web_grounding_max_results,
        ),
        skills=LocalSkills(
            store=ListStore(skills_lists_path),
            enabled=skills_enabled,
        ),
        max_history_messages=memory_max_messages,
        keep_recent_messages=memory_keep_recent,
    )

    planner = PlannerManager()

    reasoning = ReasoningManager()

    permissions_config = PermissionsServiceConfig.from_env()

    if config is not None:
        permissions_enabled = config.get("permissions_enabled")
        if permissions_enabled is not None:
            permissions_config.enabled = bool(permissions_enabled)

    logger.info(
        "Permission confirmations are %s.",
        "enabled" if permissions_config.enabled else "disabled (every action runs immediately)",
    )

    if permissions_config.enabled:
        if permissions_config.authorization_passphrase:
            logger.info(
                "High-risk actions (run command, organize/delete "
                "files, send email/message) require the authorization "
                "passphrase."
            )
        else:
            logger.warning(
                "No AUTHORIZATION_PASSPHRASE is set in .env — "
                "high-risk actions (run command, organize/delete "
                "files, send email/message) are only gated by a plain "
                "yes/no. Anyone who can talk to EON can approve them. "
                "Set AUTHORIZATION_PASSPHRASE in .env to require more "
                "than that."
            )

    permissions = PermissionManager(config=permissions_config)

    router = ActionRouter()

    resources = ResourceService()

    tools = ToolRegistry()

    tools.register(
        LauncherTool()
    )

    tools.register(
        VSCodeTool()
    )

    tools.register(
        BrowserTool()
    )

    tools.register(
        TerminalTool()
    )

    tools.register(
        ClipboardTool()
    )

    tools.register(
        VolumeTool()
    )

    tools.register(
        BrightnessTool()
    )

    tools.register(
        WindowTool()
    )

    tools.register(
        ScreenshotTool()
    )

    tools.register(
        FileOrganizerTool()
    )

    tools.register(
        TypeTextTool()
    )

    tools.register(
        UIControlTool()
    )

    music_enabled = True
    music_folders: list[str] = []

    if config is not None:
        music_setting = config.get("music_enabled")
        if music_setting is not None:
            music_enabled = bool(music_setting)

        # An empty list is the default and means "look in ~/Music and
        # ~/Downloads", which is where a downloaded song normally is.
        folders_setting = config.get("music_folders")
        if isinstance(folders_setting, list):
            music_folders = [str(folder) for folder in folders_setting]

    logger.info(
        "Music playback is %s (looking in: %s).",
        "enabled" if music_enabled else "disabled (set music_enabled=true in config/settings.json)",
        ", ".join(music_folders) if music_folders else "~/Music, ~/Downloads",
    )

    tools.register(
        MusicTool(
            folders=music_folders,
            enabled=music_enabled,
        )
    )

    weather_location_name = config.get("weather_location_name") if config is not None else None
    weather_latitude = config.get("weather_latitude") if config is not None else None
    weather_longitude = config.get("weather_longitude") if config is not None else None

    weather_tool_kwargs = {}
    if weather_location_name:
        weather_tool_kwargs["default_location_name"] = str(weather_location_name)
    if weather_latitude is not None:
        weather_tool_kwargs["default_latitude"] = float(weather_latitude)
    if weather_longitude is not None:
        weather_tool_kwargs["default_longitude"] = float(weather_longitude)

    if config is not None:
        # With no place configured, the weather tool works out where it
        # is instead — see src/modules/automation/location.py. Absent
        # settings leave detection on, so this only ever switches it
        # off when the user has explicitly asked for that.
        weather_tool_kwargs["auto_detect_location"] = (
            config.get("location_auto_detect") is not False
        )
        weather_tool_kwargs["location_cache_hours"] = float(
            config.get("location_cache_hours") or 24
        )
        weather_tool_kwargs["location_cache_path"] = str(
            config.get("location_cache_path") or "data/location.json"
        )

    tools.register(
        WeatherTool(**weather_tool_kwargs)
    )

    integrations_config = IntegrationsConfig.from_env(
        calendar_enabled=bool(config.get("calendar_enabled")) if config is not None else True,
        email_enabled=bool(config.get("email_enabled")) if config is not None else True,
        messaging_enabled=bool(config.get("messaging_enabled")) if config is not None else True,
        messaging_provider=str(config.get("messaging_provider") or "telegram") if config is not None else "telegram",
    )

    logger.info(
        "Calendar is %s, Email is %s, Messaging is %s (provider: %s).",
        "enabled" if integrations_config.calendar_enabled else "disabled",
        "enabled" if integrations_config.email_enabled else "disabled",
        "enabled" if integrations_config.messaging_enabled else "disabled",
        integrations_config.messaging_provider,
    )

    # Calendar and Email share one Google OAuth manager (same account,
    # same consent flow, one cached token covers both) — see
    # integrations/google_auth.py.
    google_auth = GoogleAuthManager(
        credentials_path=integrations_config.google_credentials_path,
        token_path=integrations_config.google_token_path,
    )

    calendar_tool = CalendarTool(
        enabled=integrations_config.calendar_enabled,
        auth=google_auth,
    )

    tools.register(calendar_tool)

    tools.register(
        EmailTool(
            enabled=integrations_config.email_enabled,
            auth=google_auth,
        )
    )

    tools.register(
        MessagingTool(
            config=integrations_config,
        )
    )

    vision = VisionManager(
        config=vision_config,
    )

    executor = ActionExecutor(
        resources=resources,
        tools=tools,
        vision=vision,
        automation_enabled=automation_enabled,
    )

    memory_config = MemoryConfig()

    memory_store = SQLiteMemoryStore(
        config=memory_config,
    )

    memory_service = MemoryService(
        store=memory_store,
    )

    workspace_manager = create_workspace_manager()

    workspace_router = create_workspace_router(
        workspace_manager,
    )

    intent = IntentManager(
        memory=memory_service,
        router=workspace_router,
    )

    voice_config = VoiceServiceConfig()

    if config is not None:
        piper_hi_model_path = config.get("piper_hi_model_path")
        piper_hi_config_path = config.get("piper_hi_config_path")

        if piper_hi_model_path and piper_hi_config_path:
            voice_config.piper_hi = {
                "model_path": piper_hi_model_path,
                "config_path": piper_hi_config_path,
            }

        # Listening / conversation tuning. Every key is optional: the
        # defaults in VoiceServiceConfig apply when one is absent.
        for key, attr, caster in (
            ("voice_silence_end_seconds", "silence_end_seconds", float),
            ("voice_listen_max_seconds", "listen_max_seconds", float),
            (
                "voice_listen_start_timeout_seconds",
                "listen_start_timeout_seconds",
                float,
            ),
            ("conversation_mode_enabled", "conversation_mode_enabled", bool),
            (
                "conversation_idle_timeout_seconds",
                "conversation_idle_timeout_seconds",
                float,
            ),
            ("barge_in_enabled", "barge_in_enabled", bool),
            ("barge_in_energy_threshold", "barge_in_energy_threshold", float),
            ("barge_in_min_speech_seconds", "barge_in_min_speech_seconds", float),
            ("barge_in_window_seconds", "barge_in_window_seconds", float),
        ):
            value = config.get(key)
            if value is not None:
                setattr(voice_config, attr, caster(value))

    logger.info(
        "Hindi TTS voice is %s.",
        "configured" if voice_config.piper_hi else
        "not configured (set piper_hi_model_path/piper_hi_config_path in "
        "config/settings.json once a hi_IN Piper voice is downloaded — "
        "see src/modules/voice/config.py for where to get one). Hindi/"
        "Hinglish replies will use the default English voice until then.",
    )

    voice_stt_provider = FasterWhisperProvider(
        **voice_config.faster_whisper,
    )

    voice_tts_provider = PiperProvider(
        **voice_config.piper,
        **(
            {
                "model_path_hi": voice_config.piper_hi["model_path"],
                "config_path_hi": voice_config.piper_hi["config_path"],
            }
            if voice_config.piper_hi is not None
            else {}
        ),
    )

    voice_manager = VoiceManager(
        session_manager=VoiceSessionManager(),
        stt_provider=voice_stt_provider,
        tts_provider=voice_tts_provider,
    )

    # Optional audio device overrides. ``null`` (the default) means use
    # whatever the OS reports as the default; otherwise an index or a
    # case-insensitive part of the device name, e.g. "Realtek".
    voice_input_device = (
        config.get("voice_input_device") if config is not None else None
    )
    voice_output_device = (
        config.get("voice_output_device") if config is not None else None
    )

    # Log what the machine actually has, so a device can be picked from
    # here rather than guessed at. Purely diagnostic: a failure to
    # enumerate must not stop EON starting.
    for direction, lister in (
        ("in", SoundDeviceMicrophone),
        ("out", SoundDeviceSpeaker),
    ):
        try:
            for device in lister.enumerate_devices():
                logger.info(
                    "Audio %s [%s] %s (%s Hz)%s",
                    direction,
                    device.device_id,
                    device.name,
                    device.sample_rate_hz,
                    "  <- default" if device.is_default else "",
                )
        except Exception:
            logger.warning("Could not list the %s audio devices.", direction)

    microphone = SoundDeviceMicrophone(
        device_id=voice_input_device,
        sample_rate_hz=voice_config.sample_rate_hz,
    )

    speaker = SoundDeviceSpeaker(
        device_id=voice_output_device,
        sample_rate_hz=voice_config.sample_rate_hz,
    )

    logger.info(
        "Voice uses microphone '%s' and speaker '%s'.",
        microphone.device_info.name,
        speaker.device_info.name,
    )

    voice_service = VoiceService(
        manager=voice_manager,
        microphone=microphone,
        speaker=speaker,
        config=voice_config,
    )

    proactive_config = ProactiveServiceConfig()

    if config is not None:
        proactive_enabled = config.get("proactive_enabled")
        if proactive_enabled is not None:
            proactive_config.enabled = bool(proactive_enabled)

        idle_checkin_minutes = config.get("idle_checkin_minutes")
        if idle_checkin_minutes is not None:
            proactive_config.idle_checkin_minutes = float(idle_checkin_minutes)

    logger.info(
        "Proactive speech is %s.",
        "enabled" if proactive_config.enabled else "disabled (set proactive_enabled=true in config/settings.json to turn it on)",
    )

    execution_executor = ExecutionExecutor(
        executor=executor,
    )

    execution = ExecutionManager(
        executor=execution_executor,
    )

    ambient_config = AmbientMonitorConfig()

    if config is not None:
        ambient_enabled = config.get("ambient_awareness_enabled")
        if ambient_enabled is not None:
            ambient_config.enabled = bool(ambient_enabled)

        ambient_interval = config.get("ambient_check_interval_seconds")
        if ambient_interval is not None:
            ambient_config.check_interval_seconds = float(ambient_interval)

        ambient_downloads = config.get("ambient_downloads_enabled")
        if ambient_downloads is not None:
            ambient_config.downloads_enabled = bool(ambient_downloads)

        ambient_calendar = config.get("ambient_calendar_enabled")
        if ambient_calendar is not None:
            ambient_config.calendar_enabled = bool(ambient_calendar)

        ambient_hung_windows = config.get("ambient_hung_window_enabled")
        if ambient_hung_windows is not None:
            ambient_config.hung_window_enabled = bool(ambient_hung_windows)

        ambient_calendar_warning = config.get("ambient_calendar_warning_minutes")
        if ambient_calendar_warning is not None:
            ambient_config.calendar_warning_minutes = int(ambient_calendar_warning)

    logger.info(
        "Ambient awareness is %s.",
        "enabled" if ambient_config.enabled else "disabled (set ambient_awareness_enabled=true in config/settings.json to turn it on)",
    )

    monitor = MonitorManager(
        ambient_config=ambient_config,
        calendar_tool=calendar_tool,
    )

    proactive_service = ProactiveService(
        voice=voice_service,
        config=proactive_config,
        monitor=monitor,
    )

    hologram_config = HologramConfig()

    if config is not None:
        hologram_enabled = config.get("hologram_enabled")
        if hologram_enabled is not None:
            hologram_config.enabled = bool(hologram_enabled)

        hologram_size = config.get("hologram_size")
        if hologram_size is not None:
            hologram_config.size = HologramConfig.parse_size(hologram_size)

        hologram_theme = config.get("hologram_theme")
        if hologram_theme is not None:
            hologram_config.theme = HologramConfig.parse_theme(hologram_theme)

        hologram_particles_enabled = config.get("hologram_particles_enabled")
        if hologram_particles_enabled is not None:
            hologram_config.particles_enabled = bool(hologram_particles_enabled)

        hologram_glow_intensity = config.get("hologram_glow_intensity")
        if hologram_glow_intensity is not None:
            hologram_config.glow_intensity = max(0.0, min(1.0, float(hologram_glow_intensity)))

        hologram_animation_speed = config.get("hologram_animation_speed")
        if hologram_animation_speed is not None:
            hologram_config.animation_speed = max(0.0, float(hologram_animation_speed))

        hologram_transparency = config.get("hologram_transparency")
        if hologram_transparency is not None:
            hologram_config.transparency = max(0.05, min(1.0, float(hologram_transparency)))

        hologram_fps = config.get("hologram_fps")
        if hologram_fps is not None:
            hologram_config.fps = max(1, int(hologram_fps))

    logger.info(
        "Desktop companion hologram is %s (%s, %s theme).",
        "enabled" if hologram_config.enabled
        else "disabled (set hologram_enabled=true in config/settings.json to turn it on)",
        hologram_config.size.value,
        hologram_config.theme.value,
    )

    hologram_service = DesktopCompanionService(
        config=hologram_config,
    )

    reflection = ReflectionManager(memory=memory_service)

    context = ContextManager()

    perception = PerceptionManager()

    # How similar a memory must be to the current topic to be recalled.
    # This was hardcoded at 0.30 with 0.55 commented out above it, which
    # meant an unrelated memory came back on almost every turn and was
    # then fed into the prompt.
    recall_min_score = (
        config.get("memory_recall_min_score") if config is not None else None
    )

    recall = RecallManager(
        memory=memory_service,
        min_score=(
            DEFAULT_MIN_SCORE
            if recall_min_score is None
            else float(recall_min_score)
        ),
    )

    store = StoreManager(
        memory=memory_service,
    )



    container.register("history", history)
    container.register("brain", brain)
    container.register("identity", identity)
    container.register("intent", intent)
    container.register(
        "workspace_manager",
        workspace_manager,
    )

    container.register(
        "workspace_router",
        workspace_router,
    )
    container.register("planner", planner)
    container.register("reasoning", reasoning)
    container.register("permissions", permissions)
    container.register("router", router)
    container.register("resources", resources)
    container.register("executor", executor)
    container.register("memory", memory_service)
    container.register("voice", voice_service)
    container.register("proactive", proactive_service)
    container.register("hologram", hologram_service)
    container.register("execution", execution)
    container.register("monitor", monitor)
    container.register("reflection", reflection)
    container.register("perception", perception)
    container.register("vision", vision)
    container.register("context", context)
    container.register("recall", recall)
    container.register("store", store)
    container.register("tools", tools,)
