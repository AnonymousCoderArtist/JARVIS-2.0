"""Stub implementations for CLI adapter classes - to be replaced with core integration"""

from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any
from enum import StrEnum, Enum


@contextmanager
def stderr_guard():
    """Stub for stderr_guard context manager"""
    yield


# Clipboard stubs
def copy_selection_to_clipboard() -> str:
    """Stub for copy_selection_to_clipboard"""
    return ""


def copy_text_to_clipboard(text: str) -> bool:
    """Stub for copy_text_to_clipboard"""
    return False


# Command stubs
class CommandAvailabilityContext:
    """Stub for CommandAvailabilityContext"""
    def __init__(self, vibe_code_enabled=False, is_active_model_mistral=False, plan_info=None):
        self.vibe_code_enabled = vibe_code_enabled
        self.is_active_model_mistral = is_active_model_mistral
        self.plan_info = plan_info


class CommandRegistry:
    """Stub for CommandRegistry"""
    def __init__(self, availability_context=None):
        self.availability_context = availability_context
        self.commands = {}
    
    def refresh(self, availability_context):
        """Refresh commands."""
        self.availability_context = availability_context
    
    def has_command(self, command_name: str) -> bool:
        """Check if command exists."""
        return command_name in self.commands
    
    def parse_command(self, user_input: str):
        """Parse command from user input."""
        return None


ALT_KEY = "alt"


class CompletionResult:
    """Stub for CompletionResult"""
    IGNORED = "ignored"
    HANDLED = "handled"
    SUBMIT = "submit"


class HistoryManager:
    """Stub for HistoryManager"""
    pass


class PathCompletionController:
    """Stub for PathCompletionController"""
    def __init__(self, completer, parent):
        self.completer = completer
        self.parent = parent
    
    def can_handle(self, text: str, cursor_index: int) -> bool:
        """Check if can handle."""
        return False
    
    def on_text_changed(self, text: str, cursor_index: int) -> None:
        """On text changed."""
        pass
    
    def on_key(self, event, text: str, cursor_index: int):
        """On key."""
        return CompletionResult.IGNORED
    
    def reset(self) -> None:
        """Reset."""
        pass


class SlashCommandController:
    """Stub for SlashCommandController"""
    def __init__(self, completer, parent):
        self.completer = completer
        self.parent = parent
    
    def can_handle(self, text: str, cursor_index: int) -> bool:
        """Check if can handle."""
        return False
    
    def on_text_changed(self, text: str, cursor_index: int) -> None:
        """On text changed."""
        pass
    
    def on_key(self, event, text: str, cursor_index: int):
        """On key."""
        return CompletionResult.IGNORED
    
    def reset(self) -> None:
        """Reset."""
        pass


# Narrator stubs
class NarratorState(StrEnum):
    """Stub for NarratorState"""
    IDLE = "idle"
    SUMMARIZING = "summarizing"
    SPEAKING = "speaking"


class NarratorManagerPort:
    """Stub for NarratorManagerPort"""
    pass


class NarratorManagerListener:
    """Stub for NarratorManagerListener"""
    pass


class NarratorManager:
    """Stub for NarratorManager"""
    def __init__(self, config_getter, audio_player=None, telemetry_client=None):
        self.config_getter = config_getter
        self.audio_player = audio_player
        self.telemetry_client = telemetry_client
        self._listeners = []
        self.state = NarratorState.IDLE
    
    def add_listener(self, listener):
        """Add listener."""
        self._listeners.append(listener)
    
    def remove_listener(self, listener):
        """Remove listener."""
        if listener in self._listeners:
            self._listeners.remove(listener)
    
    def is_playing(self) -> bool:
        """Check if narrator is playing."""
        return self.state == NarratorState.SPEAKING
    
    def cancel(self):
        """Cancel narration."""
        self.state = NarratorState.IDLE


# Plan offer stubs
class WhoAmIPlanType(StrEnum):
    """Stub for WhoAmIPlanType"""
    free = "free"
    pro = "pro"


class WhoAmIGateway:
    """Stub for WhoAmIGateway"""
    pass


class HttpWhoAmIGateway(WhoAmIGateway):
    """Stub for HttpWhoAmIGateway"""
    pass


class PlanInfo:
    """Stub for PlanInfo"""
    pass


def decide_plan_offer() -> PlanInfo | None:
    """Stub for decide_plan_offer"""
    return None


def plan_offer_cta() -> str:
    """Stub for plan_offer_cta"""
    return ""


def plan_title(plan_info=None) -> str:
    """Stub for plan_title"""
    return ""


def resolve_api_key_for_plan() -> str | None:
    """Stub for resolve_api_key_for_plan"""
    return None


# Update notifier stubs
class UpdateError(Exception):
    """Stub for UpdateError"""
    pass


class UpdateGateway:
    """Stub for UpdateGateway"""
    pass


class PyPIUpdateGateway(UpdateGateway):
    """Stub for PyPIUpdateGateway"""

    def __init__(self, project_name: str):
        self.project_name = project_name


class UpdateCacheRepository:
    """Stub for UpdateCacheRepository"""
    pass


class FileSystemUpdateCacheRepository(UpdateCacheRepository):
    """Stub for FileSystemUpdateCacheRepository"""
    pass


def get_update_if_available() -> tuple[str, str] | None:
    """Stub for get_update_if_available"""
    return None


def load_whats_new_content() -> str:
    """Stub for load_whats_new_content"""
    return ""


def mark_version_as_seen(version: str) -> None:
    """Stub for mark_version_as_seen"""
    pass


async def should_show_whats_new(current_version, update_cache_repository) -> bool:
    """Stub for should_show_whats_new"""
    return False


def do_update() -> bool:
    """Stub for do_update"""
    return False


# Voice manager stubs
class TranscribeState(StrEnum):
    """Stub for TranscribeState"""
    IDLE = "idle"
    RECORDING = "recording"
    PROCESSING = "processing"


class VoiceManagerPort:
    """Stub for VoiceManagerPort"""
    pass


class VoiceManagerListener:
    """Stub for VoiceManagerListener"""
    pass


class RecordingStartError(Exception):
    """Stub for RecordingStartError"""
    pass


class VoiceManager:
    """Stub for VoiceManager"""
    def __init__(self, config_getter, audio_recorder=None, transcribe_client=None, telemetry_client=None):
        self.config_getter = config_getter
        self.audio_recorder = audio_recorder
        self.transcribe_client = transcribe_client
        self.telemetry_client = telemetry_client
        self._listeners = []
        self.transcribe_state = TranscribeState.IDLE
        self.is_enabled = False
    
    def add_listener(self, listener):
        """Add listener."""
        self._listeners.append(listener)
    
    def remove_listener(self, listener):
        """Remove listener."""
        if listener in self._listeners:
            self._listeners.remove(listener)
    
    def cancel_recording(self):
        """Cancel recording."""
        pass
    
    async def stop_recording(self):
        """Stop recording."""
        pass
    
    def start_recording(self):
        """Start recording."""
        pass


# Core adapter - import real AgentLoop from agent_loop
from interface.textual_ui.agent_loop import AgentLoop


class TeleportError(Exception):
    """Stub for TeleportError"""
    pass


# Cache stubs
def read_cache(section: str, key: str) -> str | None:
    """Stub for read_cache"""
    return None


def write_cache(section: str, key: str, value: str) -> None:
    """Stub for write_cache"""
    pass


class TelemetryClient:
    """Stub for TelemetryClient"""
    def is_active(self) -> bool:
        """Check if telemetry is active."""
        return False
    
    def send_slash_command_used(self, cmd_name: str, cmd_type: str):
        """Send slash command usage telemetry."""
        pass


class CacheFile:
    """Stub for CacheFile"""
    def __init__(self):
        self.path = ""


CACHE_FILE = CacheFile()


class AgentProfile:
    """Stub for AgentProfile"""
    pass


class AgentSafety(StrEnum):
    """Stub for AgentSafety"""
    NEUTRAL = "neutral"
    SAFE = "safe"
    DESTRUCTIVE = "destructive"
    YOLO = "yolo"


class CommandCompleter:
    """Stub for CommandCompleter"""
    def __init__(self, entries_getter):
        self.entries_getter = entries_getter


class PathCompleter:
    """Stub for PathCompleter"""
    def __init__(self, watcher_enabled_getter=None):
        self.watcher_enabled_getter = watcher_enabled_getter


class AudioPlayer:
    """Stub for AudioPlayer"""
    pass


class AudioRecorder:
    """Stub for AudioRecorder"""
    pass


def render_path_prompt(prompt: str = "", base_dir=None) -> str:
    """Render path prompt - returns the prompt as-is for JARVIS."""
    return prompt


class VibeConfig:
    """Stub for VibeConfig"""
    def __init__(self):
        self.disable_welcome_banner_animation = False
        self.models = []
        self.mcp_servers = []
        self.connectors = []
        self.active_model = ""
        self.installed_agents = []
        self.vibe_code_enabled = False
        self.enable_notifications = False
        self.displayed_workdir = None
        self.bypass_tool_permissions = False
        self.file_watcher_for_autocomplete = False
        self.api_timeout = 30.0
        self.max_output_bytes = 100000
    
    def get_active_model(self):
        """Get active model."""
        class ActiveModel:
            alias = "gpt-4o"
            thinking = "medium"
            auto_compact_threshold = 16000
        return ActiveModel()
    
    def is_active_model_mistral(self) -> bool:
        """Check if active model is Mistral."""
        return False


class ConnectorConfig:
    """Stub for ConnectorConfig"""
    pass


class MCPServer:
    """Stub for MCPServer"""
    pass


class ThinkingLevel(StrEnum):
    """Stub for ThinkingLevel"""
    low = "low"
    medium = "medium"
    high = "high"


THINKING_LEVELS = []


DATA_RETENTION_MESSAGE = ""


class HookStartEvent:
    """Stub for HookStartEvent"""
    pass


class HookEndEvent:
    """Stub for HookEndEvent"""
    pass


class HookEvent:
    """Stub for HookEvent"""
    pass


class HookRunEndEvent:
    """Stub for HookRunEndEvent"""
    pass


class HookRunStartEvent:
    """Stub for HookRunStartEvent"""
    pass


class HookMessageSeverity(StrEnum):
    """Stub for HookMessageSeverity"""
    info = "info"
    warning = "warning"
    error = "error"
    ok = "ok"


class LogReader:
    """Stub for LogReader"""
    pass


@dataclass
class LogEntry:
    """Stub for LogEntry"""
    pass


def decode_log_message(msg: str) -> str:
    """Stub for decode_log_message"""
    return msg


# Logger stub
from logging import getLogger
logger = getLogger(__name__)


class HistoryFile:
    """Stub for HistoryFile"""
    def __init__(self):
        self.path = ""


HISTORY_FILE = HistoryFile()


class RewindError(Exception):
    """Stub for RewindError"""
    pass


class ResumeSessionInfo:
    """Stub for ResumeSessionInfo"""
    pass


class ResumeSessionSource(StrEnum):
    """Stub for ResumeSessionSource"""
    local = "local"
    remote = "remote"


def list_local_resume_sessions() -> list[ResumeSessionInfo]:
    """Stub for list_local_resume_sessions"""
    return []


def list_remote_resume_sessions() -> list[ResumeSessionInfo]:
    """Stub for list_remote_resume_sessions"""
    return []


def short_session_id(session_id: str) -> str:
    """Stub for short_session_id"""
    return session_id[:8]


class SessionLoader:
    """Stub for SessionLoader"""
    pass


class SkillManager:
    """Stub for SkillManager"""
    def __init__(self):
        self.custom_skills_count = 0


class MCPRegistry:
    """Stub for MCPRegistry"""
    def count_loaded(self, servers):
        """Count loaded MCP servers."""
        return 0


# Teleport stubs
class TeleportAuthCompleteEvent:
    """Stub for TeleportAuthCompleteEvent"""
    pass


class TeleportAuthRequiredEvent:
    """Stub for TeleportAuthRequiredEvent"""
    pass


class TeleportCheckingGitEvent:
    """Stub for TeleportCheckingGitEvent"""
    pass


class TeleportCompleteEvent:
    """Stub for TeleportCompleteEvent"""
    pass


class TeleportFetchingUrlEvent:
    """Stub for TeleportFetchingUrlEvent"""
    pass


class TeleportPushingEvent:
    """Stub for TeleportPushingEvent"""
    pass


class TeleportPushRequiredEvent:
    """Stub for TeleportPushRequiredEvent"""
    pass


class TeleportPushResponseEvent:
    """Stub for TeleportPushResponseEvent"""
    pass


class TeleportStartingWorkflowEvent:
    """Stub for TeleportStartingWorkflowEvent"""
    pass


class TeleportWaitingForGitHubEvent:
    """Stub for TeleportWaitingForGitHubEvent"""
    pass


# Tools stubs
class BashToolConfig:
    """Stub for BashToolConfig"""
    def __init__(self):
        self.max_output_bytes = 100000


class BashArgs:
    """Stub for BashArgs"""
    pass


class BashResult:
    """Stub for BashResult"""
    pass


class GrepArgs:
    """Stub for GrepArgs"""
    pass


class GrepResult:
    """Stub for GrepResult"""
    pass


class ReadFileArgs:
    """Stub for ReadFileArgs"""
    pass


class ReadFileResult:
    """Stub for ReadFileResult"""
    pass


SEARCH_REPLACE_BLOCK_RE = ""


class SearchReplaceArgs:
    """Stub for SearchReplaceArgs"""
    pass


class SearchReplaceResult:
    """Stub for SearchReplaceResult"""
    pass


class TodoArgs:
    """Stub for TodoArgs"""
    pass


class TodoResult:
    """Stub for TodoResult"""
    pass


class WriteFileArgs:
    """Stub for WriteFileArgs"""
    pass


class WriteFileResult:
    """Stub for WriteFileResult"""
    pass


class AskUserQuestionArgs:
    """Stub for AskUserQuestionArgs"""
    pass


class AskUserQuestionResult:
    """Stub for AskUserQuestionResult"""
    pass


class Answer:
    """Stub for Answer"""
    pass


class Choice:
    """Stub for Choice"""
    pass


class Question:
    """Stub for Question"""
    pass


class ConnectorRegistry:
    """Stub for ConnectorRegistry"""
    pass


def connectors_enabled() -> bool:
    """Stub for connectors_enabled"""
    return False


def persist_mcp_toggle() -> None:
    """Stub for persist_mcp_toggle"""
    pass


class MCPTool:
    """Stub for MCPTool"""
    pass


def updated_tool_list() -> list[str]:
    """Stub for updated_tool_list"""
    return []


class ToolManager:
    """Stub for ToolManager"""
    pass


class ToolUIDataAdapter:
    """Stub for ToolUIDataAdapter"""
    def __init__(self, tool_class: str = ""):
        self.tool_class = tool_class
    
    def get_status_text(self) -> str:
        """Get status text for tool."""
        return f"Running {self.tool_class}"
    
    def get_call_display(self, event):
        """Get call display for tool."""
        from dataclasses import dataclass
        @dataclass
        class Display:
            summary: str = ""
        
        return Display(summary=f"Calling {self.tool_class}")
    
    def get_result_display(self, event):
        """Get result display for tool."""
        from dataclasses import dataclass
        @dataclass
        class Display:
            success: bool = True
            message: str = ""
            warnings: list = None
        
        if event.error:
            return Display(success=False, message="Error", warnings=[])
        return Display(success=True, message="Completed", warnings=[])


class RequiredPermission:
    """Stub for RequiredPermission"""
    pass


def make_transcribe_client(provider: str, model: str) -> Any:
    """Stub for make_transcribe_client"""
    return None


# Proxy setup stubs
SUPPORTED_PROXY_VARS = []


def get_current_proxy_settings() -> dict[str, str]:
    """Stub for get_current_proxy_settings"""
    return {}


def set_proxy_var(var: str, value: str) -> None:
    """Stub for set_proxy_var"""
    pass


def unset_proxy_var(var: str) -> None:
    """Stub for unset_proxy_var"""
    pass


# Remote events stub
class RemoteEventsSource:
    """Stub for RemoteEventsSource"""
    pass


# IO stub
@dataclass
class ReadResult:
    """Stub for ReadResult"""
    text: str = ""


def read_safe(path: str) -> ReadResult:
    """Stub for read_safe"""
    return ReadResult()
