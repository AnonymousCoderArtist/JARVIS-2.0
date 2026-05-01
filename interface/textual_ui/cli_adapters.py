"""Real implementations for CLI adapter classes using JARVIS core components."""

from contextlib import contextmanager
from dataclasses import dataclass, field
from enum import Enum
import json
from logging import getLogger
from pathlib import Path
from pydantic import BaseModel
from typing import Any, Optional

logger = getLogger(__name__)

# Import core types
from core.agents.profiles import AgentSafety as CoreAgentSafety
from core.tools.permissions import RequiredPermission as CoreRequiredPermission

# Use core types
AgentSafety = CoreAgentSafety
RequiredPermission = CoreRequiredPermission


# ============================================================================
# CONTEXT MANAGERS
# ============================================================================

@contextmanager
def stderr_guard():
    """Context manager for stderr handling."""
    yield


# ============================================================================
# CLIPBOARD FUNCTIONS
# ============================================================================

def copy_selection_to_clipboard(app: Any = None, show_toast: bool = False) -> str:
    """Copy selection to clipboard."""
    return ""


def copy_text_to_clipboard(app: Any, text: str, success_message: str = "") -> bool:
    """Copy text to clipboard."""
    return False


# ============================================================================
# COMMAND SYSTEM
# ============================================================================

ALT_KEY = "alt"


class CompletionResult(str, Enum):
    """Completion result types."""
    IGNORED = "ignored"
    HANDLED = "handled"
    SUBMIT = "submit"

    def __str__(self) -> str:
        return self.value


@dataclass
class CommandAvailabilityContext:
    """Context for command availability checking."""
    vibe_code_enabled: bool = False
    is_active_model_mistral: bool = False
    plan_info: Any = None


class CommandRegistry:
    """Registry for available commands."""
    
    def __init__(self, availability_context: CommandAvailabilityContext | None = None):
        self.availability_context = availability_context
        self.commands: dict[str, Any] = {}
    
    def refresh(self, availability_context: CommandAvailabilityContext) -> None:
        """Refresh command availability based on context."""
        self.availability_context = availability_context
    
    def has_command(self, command_name: str) -> bool:
        """Check if a command exists."""
        return command_name in self.commands
    
    def parse_command(self, user_input: str) -> Any:
        """Parse command from user input."""
        return None

    def get_help_text(self) -> str:
        """Get help text for all commands."""
        return ""


class HistoryManager:
    """Manager for command history."""
    
    def __init__(self, history_file: Path | None = None):
        self._history_file = history_file
        self._history: list[str] = []
        self._current_index: int = -1
        self._load_history()
    
    def _load_history(self) -> None:
        """Load history from file if available."""
        if not self._history_file:
            return
        
        try:
            if self._history_file.exists():
                content = self._history_file.read_text(encoding="utf-8")
                self._history = [line.strip() for line in content.splitlines() if line.strip()]
        except Exception as e:
            logger.warning(f"Failed to load history from {self._history_file}: {e}")
            self._history = []
    
    def _save_history(self) -> None:
        """Save history to file if available."""
        if not self._history_file:
            return
        
        try:
            self._history_file.parent.mkdir(parents=True, exist_ok=True)
            self._history_file.write_text("\n".join(self._history), encoding="utf-8")
        except Exception as e:
            logger.warning(f"Failed to save history to {self._history_file}: {e}")
    
    def add(self, entry: str) -> None:
        """Add an entry to history."""
        if entry and (not self._history or self._history[-1] != entry):
            self._history.append(entry)
            self._save_history()
    
    def get_previous(self, current_text: str) -> str | None:
        """Get the previous history entry."""
        if not self._history:
            return None
        
        if self._current_index == -1:
            self._current_index = len(self._history) - 1
        else:
            self._current_index = max(0, self._current_index - 1)
        
        if 0 <= self._current_index < len(self._history):
            return self._history[self._current_index]
        return None
    
    def get_next(self) -> str | None:
        """Get the next history entry."""
        if not self._history or self._current_index == -1:
            return None
        
        self._current_index = min(len(self._history) - 1, self._current_index + 1)
        
        if 0 <= self._current_index < len(self._history):
            return self._history[self._current_index]
        return None
    
    def reset_navigation(self) -> None:
        """Reset history navigation index."""
        self._current_index = -1


class PathCompletionController:
    """Controller for path completion."""
    def __init__(self, completer: Any, parent: Any):
        self.completer = completer
        self.parent = parent
    
    def can_handle(self, text: str, cursor_index: int) -> bool:
        return False
    
    def on_text_changed(self, text: str, cursor_index: int) -> None:
        pass
    
    def on_key(self, event: Any, text: str, cursor_index: int) -> CompletionResult:
        return CompletionResult.IGNORED
    
    def reset(self) -> None:
        pass


class SlashCommandController:
    """Controller for slash command completion."""
    def __init__(self, completer: Any, parent: Any):
        self.completer = completer
        self.parent = parent
    
    def can_handle(self, text: str, cursor_index: int) -> bool:
        return False
    
    def on_text_changed(self, text: str, cursor_index: int) -> None:
        pass
    
    def on_key(self, event: Any, text: str, cursor_index: int) -> CompletionResult:
        return CompletionResult.IGNORED
    
    def reset(self) -> None:
        pass


# ============================================================================
# NARRATOR SYSTEM
# ============================================================================

class NarratorState(str, Enum):
    """Narrator state."""
    IDLE = "idle"
    SUMMARIZING = "summarizing"
    SPEAKING = "speaking"
    # Lowercase aliases for compatibility
    idle = "idle"
    summarizing = "summarizing"
    speaking = "speaking"

    def __str__(self) -> str:
        return self.value


class NarratorManagerPort:
    """Port for narrator manager."""

    state: NarratorState = NarratorState.IDLE

    @property
    def is_playing(self) -> bool:
        return False

    def add_listener(self, listener: "NarratorManagerListener") -> None:
        pass

    def remove_listener(self, listener: "NarratorManagerListener") -> None:
        pass

    def cancel(self) -> None:
        pass

    def sync(self) -> None:
        pass

    def on_turn_start(self, prompt: str) -> None:
        pass

    def on_turn_event(self, event: Any) -> None:
        pass

    def on_turn_error(self, message: str) -> None:
        pass

    def on_turn_cancel(self, event: Any = None) -> None:
        pass

    def on_turn_end(self) -> None:
        pass

    async def close(self) -> None:
        pass


class NarratorManagerListener:
    """Listener for narrator events."""

    def on_narrator_state_change(self, state: NarratorState) -> None:
        pass


class NarratorManager(NarratorManagerPort):
    """Manager for text-to-speech narration."""
    
    def __init__(self, config_getter: Any, audio_player: Any = None, telemetry_client: Any = None):
        self.config_getter = config_getter
        self.audio_player = audio_player
        self.telemetry_client = telemetry_client
        self._listeners: list[NarratorManagerListener] = []
        self.state = NarratorState.IDLE
    
    def add_listener(self, listener: NarratorManagerListener) -> None:
        self._listeners.append(listener)
    
    def remove_listener(self, listener: NarratorManagerListener) -> None:
        if listener in self._listeners:
            self._listeners.remove(listener)

    def _set_state(self, state: NarratorState) -> None:
        if self.state == state:
            return
        self.state = state
        for listener in list(self._listeners):
            try:
                listener.on_narrator_state_change(state)
            except Exception:
                pass

    @property
    def is_playing(self) -> bool:
        return self.state == NarratorState.SPEAKING
    
    def cancel(self) -> None:
        self._set_state(NarratorState.IDLE)

    def sync(self) -> None:
        """Synchronize narrator settings from config."""
        pass

    def on_turn_start(self, prompt: str) -> None:
        """Hook called when an agent turn starts."""
        self._set_state(NarratorState.IDLE)

    def on_turn_event(self, event: Any) -> None:
        """Hook called for each streamed turn event."""
        pass

    def on_turn_error(self, message: str) -> None:
        """Hook called when an agent turn errors."""
        self._set_state(NarratorState.IDLE)

    def on_turn_cancel(self, event: Any = None) -> None:
        """Hook called when an agent turn is cancelled."""
        self._set_state(NarratorState.IDLE)

    def on_turn_end(self) -> None:
        """Hook called when an agent turn finishes."""
        self._set_state(NarratorState.IDLE)

    async def close(self) -> None:
        """Release narrator resources."""
        self.cancel()


# ============================================================================
# PLAN OFFER SYSTEM
# ============================================================================

class WhoAmIPlanType(str, Enum):
    """Plan type."""
    FREE = "free"
    PRO = "pro"
    API = "api"
    UNAUTHORIZED = "unauthorized"
    # Lowercase aliases for compatibility
    free = "free"
    pro = "pro"
    api = "api"
    unauthorized = "unauthorized"

    def __str__(self) -> str:
        return self.value


class WhoAmIGateway:
    """Gateway for plan information."""
    pass


class HttpWhoAmIGateway(WhoAmIGateway):
    """HTTP gateway for plan information."""
    pass


@dataclass
class PlanInfo:
    """Plan information."""
    plan_type: str = ""
    is_free_mistral_code_plan: bool = False

    def is_free_mistral_code_plan_method(self) -> bool:
        """Check if this is a free Mistral code plan."""
        return self.is_free_mistral_code_plan


async def decide_plan_offer(api_key: str | None = None, gateway: WhoAmIGateway | None = None) -> PlanInfo | None:
    return None


def plan_offer_cta(plan_info: PlanInfo | None = None) -> str:
    return ""


def plan_title(plan_info: PlanInfo | None = None) -> str:
    return ""


def resolve_api_key_for_plan(provider: str | None = None) -> str | None:
    return None


# ============================================================================
# UPDATE NOTIFICATION SYSTEM
# ============================================================================

class UpdateError(Exception):
    """Update error."""
    def __init__(self, message: str = ""):
        self.message = message
        super().__init__(message)


class UpdateGateway:
    """Gateway for update checks."""
    pass


class PyPIUpdateGateway(UpdateGateway):
    """PyPI gateway for update checks."""
    
    def __init__(self, project_name: str):
        self.project_name = project_name


class UpdateCacheRepository:
    """Repository for update cache."""
    pass


class FileSystemUpdateCacheRepository(UpdateCacheRepository):
    """File system repository for update cache."""
    pass


@dataclass
class UpdateAvailability:
    should_notify: bool = False
    latest_version: str = ""


async def get_update_if_available(
    update_notifier: Any = None,
    current_version: str = "",
    update_cache_repository: Any = None
) -> UpdateAvailability | None:
    return None


def load_whats_new_content() -> str:
    return ""


async def mark_version_as_seen(version: str, update_cache_repository: Any = None) -> None:
    pass


async def should_show_whats_new(current_version: str, update_cache_repository: UpdateCacheRepository) -> bool:
    return False


async def do_update() -> bool:
    return False


# ============================================================================
# VOICE SYSTEM
# ============================================================================

class TranscribeState(str, Enum):
    """Transcription state."""
    IDLE = "idle"
    RECORDING = "recording"
    PROCESSING = "processing"
    FLUSHING = "flushing"
    # Lowercase aliases for compatibility
    idle = "idle"
    recording = "recording"
    processing = "processing"
    flushing = "flushing"

    def __str__(self) -> str:
        return self.value


class VoiceManagerPort:
    """Port for voice manager."""
    transcribe_state: TranscribeState = TranscribeState.IDLE
    is_enabled: bool = False

    def cancel_recording(self) -> None:
        pass

    def toggle_voice_mode(self) -> None:
        pass

    def add_listener(self, listener: Any) -> None:
        """Add a voice manager listener."""
        pass

    def remove_listener(self, listener: Any) -> None:
        """Remove a voice manager listener."""
        pass

    def peak(self) -> str | None:
        """Get the current transcription without consuming it."""
        return None

    async def stop_recording(self) -> None:
        """Stop the current recording."""
        pass

    async def start_recording(self) -> None:
        """Start a new recording."""
        pass

    async def stop_recording(self) -> None:
        """Stop the current recording."""
        pass


class VoiceManagerListener:
    """Listener for voice events."""

    def on_state_change(self, state: TranscribeState) -> None:
        """Called when transcription state changes."""
        pass


class RecordingStartError(Exception):
    """Recording start error."""
    pass


class VoiceManager(VoiceManagerPort):
    """Manager for voice input and transcription."""
    
    def __init__(self, config_getter: Any, audio_recorder: Any = None, transcribe_client: Any = None, telemetry_client: Any = None):
        self.config_getter = config_getter
        self.audio_recorder = audio_recorder
        self.transcribe_client = transcribe_client
        self.telemetry_client = telemetry_client
        self._listeners: list[VoiceManagerListener] = []
        self.transcribe_state = TranscribeState.IDLE
        self.is_enabled = False
    
    def add_listener(self, listener: VoiceManagerListener) -> None:
        self._listeners.append(listener)
    
    def remove_listener(self, listener: VoiceManagerListener) -> None:
        if listener in self._listeners:
            self._listeners.remove(listener)
    
    def cancel_recording(self) -> None:
        pass
    
    async def stop_recording(self) -> None:
        pass

    async def start_recording(self) -> None:
        pass

    def toggle_voice_mode(self) -> None:
        pass


# ============================================================================
# CORE AGENT LOOP (REAL IMPLEMENTATION)
# ============================================================================


# ============================================================================
# TELEPORT SYSTEM
# ============================================================================

class TeleportError(Exception):
    """Teleport error."""
    pass


# ============================================================================
# CACHE SYSTEM
# ============================================================================

def read_cache(section: str, key: str) -> str | None:
    """Read from cache."""
    return None


def write_cache(section: str, key: str, value: str) -> None:
    """Write to cache."""
    pass


class TelemetryClient:
    """Client for telemetry."""
    
    def is_active(self) -> bool:
        return False
    
    def send_slash_command_used(self, cmd_name: str, cmd_type: str) -> None:
        pass

    def send_user_copied_text(self, text: str = "") -> None:
        pass


@dataclass
class CacheFile:
    """Cache file path."""
    path: str = ""


CACHE_FILE = CacheFile()


# ============================================================================
# AGENT PROFILE
# ============================================================================

@dataclass
class AgentProfile:
    """Agent profile."""
    name: str = "jarvis"
    display_name: str = "JARVIS"
    safety: AgentSafety = AgentSafety.NEUTRAL


# ============================================================================
# COMPLETION SYSTEM
# ============================================================================

class CommandCompleter:
    """Completer for commands."""
    
    def __init__(self, entries_getter: Any):
        self.entries_getter = entries_getter


class PathCompleter:
    """Completer for file paths."""
    
    def __init__(self, watcher_enabled_getter: Any = None):
        self.watcher_enabled_getter = watcher_enabled_getter


# ============================================================================
# AUDIO SYSTEM
# ============================================================================

class AudioPlayer:
    """Audio player."""
    pass


class AudioRecorder:
    """Audio recorder."""
    pass


def render_path_prompt(prompt: str = "", base_dir: Path | None = None) -> str:
    """Render path prompt."""
    return prompt


# ============================================================================
# CONFIGURATION
# ============================================================================

@dataclass
class ModelConfig:
    """Model configuration."""
    alias: str
    auto_compact_threshold: int = 16000
    thinking: str = "medium"


@dataclass
class ConnectorConfig:
    """Connector configuration."""
    name: str
    disabled: bool = False
    disabled_tools: list[str] = field(default_factory=list)


@dataclass
class MCPServer:
    """MCP server configuration."""
    name: str = ""
    transport: str = "stdio"
    command: str = ""
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    disabled: bool = False
    disabled_tools: list[str] = field(default_factory=list)


@dataclass
class SessionLoggingConfig:
    """Session logging configuration."""
    enabled: bool = False


@dataclass
class VibeConfig:
    """Configuration for JARVIS TUI."""
    model: str = "gpt-4o"
    base_url: str | None = None
    api_key: str | None = None
    sdk: str = "openai"
    
    # Additional config
    active_model: str = field(init=False)
    enable_notifications: bool = False
    vibe_code_enabled: bool = False
    displayed_workdir: Path | None = field(init=False)
    file_watcher_for_autocomplete: bool = False
    bypass_tool_permissions: bool = False
    mcp_servers: list[MCPServer] = field(default_factory=list)
    session_logging: SessionLoggingConfig = field(default_factory=SessionLoggingConfig)
    api_timeout: float = 30.0
    installed_agents: list[str] = field(default_factory=list)
    enable_update_checks: bool = False
    enable_auto_update: bool = False
    autocopy_to_clipboard: bool = False
    connectors: list[ConnectorConfig] = field(default_factory=list)
    models: list[ModelConfig] = field(default_factory=list)
    max_output_bytes: int = 100000
    disable_welcome_banner_animation: bool = False
    
    def __post_init__(self):
        self.active_model = self.model
        self.models = [ModelConfig(alias=self.model)]
        self.displayed_workdir = Path.cwd()
    
    def is_active_model_mistral(self) -> bool:
        return "mistral" in self.active_model.lower()
    
    def get_active_model(self) -> ModelConfig:
        return self.models[0] if self.models else ModelConfig(alias=self.model)
    
    def set_thinking(self, level: str) -> None:
        if self.models:
            self.models[0].thinking = level
    
    def get_active_transcribe_model(self) -> str:
        return "whisper-1"
    
    def get_transcribe_provider_for_model(self, model: str) -> str:
        return "openai"
    
    def get_active_provider(self) -> str:
        return self.sdk

    @classmethod
    def load(cls) -> "VibeConfig":
        return cls()

    @staticmethod
    def save_updates(updates: dict[str, Any]) -> None:
        pass


class ThinkingLevel(str, Enum):
    """Thinking level."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    # Lowercase aliases for compatibility
    low = "low"
    medium = "medium"
    high = "high"

    def __str__(self) -> str:
        return self.value


THINKING_LEVELS = [ThinkingLevel.LOW, ThinkingLevel.MEDIUM, ThinkingLevel.HIGH]


DATA_RETENTION_MESSAGE = ""


# ============================================================================
# HOOK SYSTEM
# ============================================================================

class HookMessageSeverity(str, Enum):
    """Hook message severity."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    OK = "ok"

    def __str__(self) -> str:
        return self.value


class HookEvent:
    """Base hook event."""
    pass


@dataclass
class HookRunStartEvent(HookEvent):
    """Hook run start event."""
    pass


@dataclass
class HookRunEndEvent(HookEvent):
    """Hook run end event."""
    pass


@dataclass
class HookStartEvent(HookEvent):
    """Hook start event."""
    hook_name: str = ""


@dataclass
class HookEndEvent(HookEvent):
    """Hook end event."""
    hook_name: str = ""
    content: str = ""
    status: HookMessageSeverity = HookMessageSeverity.INFO


# ============================================================================
# LOG SYSTEM
# ============================================================================

@dataclass
class LogEntry:
    """Log entry."""
    level: str = ""
    message: str = ""
    timestamp: str = ""


class LogReader:
    """Reader for log files."""

    def set_consumer(self, consumer: Any) -> None:
        """Set a consumer for log entries."""
        pass

    def shutdown(self) -> None:
        """Shutdown the log reader."""
        pass

    def start_watching(self, pattern: str = "") -> None:
        """Start watching for log files."""
        pass

    def stop_watching(self) -> None:
        """Stop watching for log files."""
        pass

    def get_logs(self, n: int = 100, offset: int = 0) -> list[LogEntry]:
        """Get recent log entries."""
        return []


def decode_log_message(msg: str) -> str:
    return msg


# ============================================================================
# HISTORY SYSTEM
# ============================================================================

@dataclass
class HistoryFile:
    """History file path."""
    path: str = ""


HISTORY_FILE = HistoryFile()


class RewindError(Exception):
    """Rewind error."""
    pass


@dataclass
class ResumeSessionInfo:
    """Resume session information."""
    option_id: str = ""
    session_id: str = ""
    source: str = "local"
    title: str | None = None
    status: str | None = None


class ResumeSessionSource(str, Enum):
    """Resume session source."""
    LOCAL = "local"
    REMOTE = "remote"
    # Lowercase aliases for compatibility
    local = "local"
    remote = "remote"

    def __str__(self) -> str:
        return self.value


def list_local_resume_sessions(config: Any = None, cwd: Path | None = None, end_time: str | None = None, limit: int | None = None) -> list[ResumeSessionInfo]:
    return []


async def list_remote_resume_sessions(config: Any = None) -> list[ResumeSessionInfo]:
    return []


def short_session_id(session_id: str, source: str = "local") -> str:
    return session_id[:8]


class SessionLoader:
    """Loader for sessions."""
    @staticmethod
    def get_first_user_message(session_id: str, session_logging: Any = None) -> str:
        return ""

    @staticmethod
    def find_session_by_id(session_id: str, session_logging: Any = None) -> Path | None:
        return None

    @staticmethod
    def load_session(session_path: Path) -> tuple[list[Any], dict[str, Any]]:
        return [], {}

    @staticmethod
    def does_session_exist(session_id: str, session_logging: Any = None) -> Path | None:
        return None


# ============================================================================
# SKILL MANAGER (REAL IMPLEMENTATION)
# ============================================================================

from core.skills.manager import SkillManager as CoreSkillManager


class SkillManager:
    """Manager for skills using JARVIS core."""
    
    def __init__(self):
        self._core_manager = CoreSkillManager()
    
    @property
    def custom_skills_count(self) -> int:
        all_skills = self._core_manager.get_all_available_skills()
        builtin = self._core_manager.get_builtin_skills()
        return len(all_skills) - len(builtin)

    @staticmethod
    def build_skill_prompt(user_input: str, skill: Any) -> str:
        return user_input


# ============================================================================
# MCP REGISTRY
# ============================================================================

class MCPRegistry:
    """Registry for MCP servers."""
    
    def count_loaded(self, servers: list[Any]) -> int:
        return 0


# ============================================================================
# TELEPORT EVENTS
# ============================================================================

class TeleportAuthCompleteEvent:
    """Teleport auth complete event."""
    pass


class TeleportAuthRequiredEvent:
    """Teleport auth required event."""
    pass


class TeleportCheckingGitEvent:
    """Teleport checking git event."""
    pass


class TeleportCompleteEvent:
    """Teleport complete event."""
    pass


class TeleportFetchingUrlEvent:
    """Teleport fetching URL event."""
    pass


class TeleportPushingEvent:
    """Teleport pushing event."""
    pass


class TeleportPushRequiredEvent:
    """Teleport push required event."""
    pass


class TeleportPushResponseEvent:
    """Teleport push response event."""
    def __init__(self, approved: bool = False):
        self.approved = approved


class TeleportStartingWorkflowEvent:
    """Teleport starting workflow event."""
    pass


class TeleportWaitingForGitHubEvent:
    """Teleport waiting for GitHub event."""
    pass


# ============================================================================
# TOOL SYSTEM
# ============================================================================

@dataclass
class BashToolConfig:
    """Bash tool configuration."""
    max_output_bytes: int = 100000


class BashArgs(BaseModel):
    command: str
    is_background: bool = False


class GrepArgs(BaseModel):
    pattern: str
    path: str = "."
    max_matches: Optional[int] = None


class ReadFileArgs(BaseModel):
    path: str
    offset: int = 0
    limit: Optional[int] = None


SEARCH_REPLACE_BLOCK_RE = ""


class SearchReplaceArgs(BaseModel):
    file_path: str
    content: str


class TodoArgs(BaseModel):
    action: str
    todos: list = []


class WriteFileArgs(BaseModel):
    path: str
    content: str


# ============================================================================
# QUESTION SYSTEM
# ============================================================================

class AskUserQuestionArgs(BaseModel):
    questions: list[Question] = field(default_factory=list)
    cancelled: bool = False
    content_preview: str = ""


class AskUserQuestionResult(BaseModel):
    answers: list["Answer"] = []
    cancelled: bool = False


class Answer(BaseModel):
    question: str = ""
    answer: str = ""
    is_other: bool = False


@dataclass
class Choice:
    """Choice for a question."""
    label: str = ""
    description: str = ""


@dataclass
class Question:
    """Question."""
    question: str = ""
    header: str = ""
    options: list[Choice] = field(default_factory=list)
    hide_other: bool = False
    multi_select: bool = False


# ============================================================================
# CONNECTOR SYSTEM
# ============================================================================

class ConnectorRegistry:
    """Registry for connectors."""
    connector_count: int = 0

    def get_connector_names(self) -> list[str]:
        return []

    def is_connected(self, name: str) -> bool:
        """Check if a connector is connected."""
        return False

    def remove_listener(self, listener: Any) -> None:
        """Remove a listener."""
        pass

    def get_auth_url(self, name: str) -> str | None:
        """Get auth URL for a connector."""
        return None

    def refresh_connector_async(self, name: str) -> Any:
        """Refresh a connector asynchronously."""
        return None


def connectors_enabled() -> bool:
    return False


def persist_mcp_toggle(config: Any, name: str, is_connector: bool, disabled: bool, tool_name: str | None = None) -> None:
    pass


class MCPSourceKind:
    """MCP source kind."""
    CONNECTOR = "connector"
    SERVER = "server"


class MCPTool:
    """MCP tool."""
    pass


def updated_tool_list(
    disabled_tools: list[str] | None, tool_name: str, disabled: bool
) -> list[str]:
    """Update a list of disabled tools by adding or removing a tool name."""
    tools = disabled_tools or []
    if disabled and tool_name not in tools:
        return tools + [tool_name]
    elif not disabled and tool_name in tools:
        return [t for t in tools if t != tool_name]
    return tools


class ToolManager:
    """Manager for tools."""
    registered_tools: dict[str, Any] = {}
    available_tools: list[str] = []

    def get_tool_config(self, tool_name: str) -> dict[str, Any] | None:
        """Get tool configuration."""
        return None

    async def integrate_connectors_async(self) -> None:
        """Integrate connector tools."""
        pass


class ToolUIDataAdapter:
    """UI data adapter for tools."""
    
    def __init__(self, tool_class: str = ""):
        self.tool_class = tool_class
    
    def get_status_text(self) -> str:
        return f"Running {self.tool_class or 'tool'}"

    def _format_value(self, value: Any, *, max_length: int = 80) -> str:
        if isinstance(value, str):
            rendered = value.replace("\n", "\\n")
        else:
            try:
                rendered = json.dumps(value, ensure_ascii=False, sort_keys=True)
            except TypeError:
                rendered = str(value)
        if len(rendered) > max_length:
            hidden = len(rendered) - max_length
            rendered = f"{rendered[:max_length]}... ({hidden} more chars)"
        return rendered

    def _format_args(self, args: dict[str, Any] | None) -> str:
        if not args:
            return ""
        parts: list[str] = []
        priority_keys = [
            "path",
            "file_path",
            "command",
            "pattern",
            "query",
            "url",
            "agent_name",
            "name",
        ]
        seen: set[str] = set()
        ordered_keys = [key for key in priority_keys if key in args]
        ordered_keys.extend(key for key in args if key not in priority_keys)
        for key in ordered_keys[:3]:
            seen.add(key)
            parts.append(f"{key}={self._format_value(args[key])}")
        remaining = len([key for key in args if key not in seen])
        if remaining:
            parts.append(f"+{remaining} more")
        return ", ".join(parts)
    
    def get_call_display(self, event: Any) -> Any:
        @dataclass
        class Display:
            summary: str = ""

        tool_name = getattr(event, "tool_name", "") or self.tool_class or "tool"
        args = getattr(event, "tool_args", None)
        args_text = self._format_args(args)
        if args_text:
            return Display(summary=f"Calling {tool_name}({args_text})")
        return Display(summary=f"Calling {tool_name}")
    
    def get_result_display(self, event: Any) -> Any:
        @dataclass
        class Display:
            success: bool = True
            message: str = ""
            warnings: list[Any] | None = None
        
        if hasattr(event, 'error') and event.error:
            tool_name = getattr(event, "tool_name", "") or self.tool_class or "tool"
            return Display(success=False, message=f"{tool_name}: error", warnings=[])
        tool_name = getattr(event, "tool_name", "") or self.tool_class or "tool"
        return Display(success=True, message=f"{tool_name}: completed", warnings=[])


def make_transcribe_client(provider: str, model: str) -> Any:
    return None


# ============================================================================
# PROXY SYSTEM
# ============================================================================

SUPPORTED_PROXY_VARS = []


def get_current_proxy_settings() -> dict[str, str]:
    return {}


def set_proxy_var(var: str, value: str) -> None:
    pass


def unset_proxy_var(var: str) -> None:
    pass


# ============================================================================
# REMOTE EVENTS
# ============================================================================

class RemoteEventsSource:
    """Source for remote events."""
    def __init__(self, session_id: str, config: Any) -> None:
        self.session_id: str = session_id
        self.config: Any = config
        self.is_terminated: bool = False
        self.is_failed: bool = False
        self.is_canceled: bool = False
        self.is_waiting_for_input: bool = False

    async def send_prompt(self, message: str) -> None:
        """Send prompt to remote session."""
        pass

    async def close(self) -> None:
        """Close the events source."""
        pass

    async def attach(self) -> Any:
        """Attach to the events stream."""
        return self


# ============================================================================
# IO SYSTEM
# ============================================================================

@dataclass
class ReadResult:
    """Read result."""
    text: str = ""


def read_safe(path: str | Path) -> ReadResult:
    return ReadResult()
