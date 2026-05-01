"""Real implementations for CLI adapter classes using JARVIS core components."""

from contextlib import contextmanager
from dataclasses import dataclass, field
from enum import StrEnum
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

def copy_selection_to_clipboard() -> str:
    """Copy selection to clipboard (placeholder for TUI integration)."""
    return ""


def copy_text_to_clipboard(text: str) -> bool:
    """Copy text to clipboard (placeholder for TUI integration)."""
    return False


# ============================================================================
# COMMAND SYSTEM
# ============================================================================

ALT_KEY = "alt"


class CompletionResult(StrEnum):
    """Completion result types."""
    IGNORED = "ignored"
    HANDLED = "handled"
    SUBMIT = "submit"


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


class HistoryManager:
    """Manager for command history."""
    pass


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

class NarratorState(StrEnum):
    """Narrator state."""
    IDLE = "idle"
    SUMMARIZING = "summarizing"
    SPEAKING = "speaking"
    # Lowercase aliases for compatibility
    idle = "idle"
    summarizing = "summarizing"
    speaking = "speaking"


class NarratorManagerPort:
    """Port for narrator manager."""

    state: NarratorState

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

    def on_turn_cancel(self) -> None:
        pass

    def on_turn_end(self) -> None:
        pass

    async def close(self) -> None:
        pass


class NarratorManagerListener:
    """Listener for narrator events."""

    def on_narrator_state_change(self, state: NarratorState) -> None:
        pass


class NarratorManager:
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

    def on_turn_cancel(self) -> None:
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

class WhoAmIPlanType(StrEnum):
    """Plan type."""
    FREE = "free"
    PRO = "pro"
    # Lowercase aliases for compatibility
    free = "free"
    pro = "pro"


class WhoAmIGateway:
    """Gateway for plan information."""
    pass


class HttpWhoAmIGateway(WhoAmIGateway):
    """HTTP gateway for plan information."""
    pass


@dataclass
class PlanInfo:
    """Plan information."""
    pass


def decide_plan_offer() -> PlanInfo | None:
    return None


def plan_offer_cta() -> str:
    return ""


def plan_title(plan_info: PlanInfo | None = None) -> str:
    return ""


def resolve_api_key_for_plan() -> str | None:
    return None


# ============================================================================
# UPDATE NOTIFICATION SYSTEM
# ============================================================================

class UpdateError(Exception):
    """Update error."""
    pass


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


def get_update_if_available() -> tuple[str, str] | None:
    return None


def load_whats_new_content() -> str:
    return ""


def mark_version_as_seen(version: str) -> None:
    pass


async def should_show_whats_new(current_version: str, update_cache_repository: UpdateCacheRepository) -> bool:
    return False


def do_update() -> bool:
    return False


# ============================================================================
# VOICE SYSTEM
# ============================================================================

class TranscribeState(StrEnum):
    """Transcription state."""
    IDLE = "idle"
    RECORDING = "recording"
    PROCESSING = "processing"
    # Lowercase aliases for compatibility
    idle = "idle"
    recording = "recording"
    processing = "processing"


class VoiceManagerPort:
    """Port for voice manager."""
    pass


class VoiceManagerListener:
    """Listener for voice events."""
    pass


class RecordingStartError(Exception):
    """Recording start error."""
    pass


class VoiceManager:
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
    
    def start_recording(self) -> None:
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
    safety: str = "standard"


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


@dataclass
class MCPServer:
    """MCP server configuration."""
    pass


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
    session_logging_enabled: bool = False
    api_timeout: float = 30.0
    installed_agents: list[AgentProfile] = field(default_factory=list)
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


class ThinkingLevel(StrEnum):
    """Thinking level."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    # Lowercase aliases for compatibility
    low = "low"
    medium = "medium"
    high = "high"


THINKING_LEVELS = [ThinkingLevel.LOW, ThinkingLevel.MEDIUM, ThinkingLevel.HIGH]


DATA_RETENTION_MESSAGE = ""


# ============================================================================
# HOOK SYSTEM
# ============================================================================

class HookStartEvent:
    """Hook start event."""
    pass


class HookEndEvent:
    """Hook end event."""
    pass


class HookEvent:
    """Hook event."""
    pass


class HookRunEndEvent:
    """Hook run end event."""
    pass


class HookRunStartEvent:
    """Hook run start event."""
    pass


class HookMessageSeverity(StrEnum):
    """Hook message severity."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    OK = "ok"
    # Lowercase aliases for compatibility
    info = "info"
    warning = "warning"
    error = "error"
    ok = "ok"


# ============================================================================
# LOG SYSTEM
# ============================================================================

class LogReader:
    """Reader for log files."""
    
    def shutdown(self) -> None:
        """Shutdown the log reader."""
        pass


@dataclass
class LogEntry:
    """Log entry."""
    pass


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
    pass


class ResumeSessionSource(StrEnum):
    """Resume session source."""
    LOCAL = "local"
    REMOTE = "remote"
    # Lowercase aliases for compatibility
    local = "local"
    remote = "remote"


def list_local_resume_sessions() -> list[ResumeSessionInfo]:
    return []


def list_remote_resume_sessions() -> list[ResumeSessionInfo]:
    return []


def short_session_id(session_id: str) -> str:
    return session_id[:8]


class SessionLoader:
    """Loader for sessions."""
    pass


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
    pass


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
    question: str
    choices: list[str] = []
    allow_other: bool = False


class AskUserQuestionResult(BaseModel):
    answers: list["Answer"] = []


class Answer(BaseModel):
    question: str = ""
    answer: str = ""
    is_other: bool = False


@dataclass
class Choice:
    """Choice for a question."""
    pass


@dataclass
class Question:
    """Question."""
    pass


# ============================================================================
# CONNECTOR SYSTEM
# ============================================================================

class ConnectorRegistry:
    """Registry for connectors."""
    pass


def connectors_enabled() -> bool:
    return False


def persist_mcp_toggle() -> None:
    pass


class MCPTool:
    """MCP tool."""
    pass


def updated_tool_list() -> list[str]:
    return []


class ToolManager:
    """Manager for tools."""
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
            warnings: list = None
        
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
    pass


# ============================================================================
# IO SYSTEM
# ============================================================================

@dataclass
class ReadResult:
    """Read result."""
    text: str = ""


def read_safe(path: str) -> ReadResult:
    return ReadResult()
