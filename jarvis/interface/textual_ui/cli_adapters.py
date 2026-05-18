"""Real implementations for CLI adapter classes using JARVIS core components."""

import json
from contextlib import contextmanager
from dataclasses import dataclass, field
from enum import Enum
from logging import getLogger
from pathlib import Path
from typing import Any

from pydantic import AliasChoices, BaseModel, Field, model_validator

from jarvis.core.agents.profiles import AgentSafety as CoreAgentSafety
from jarvis.core.skills.manager import SkillManager as CoreSkillManager
from jarvis.core.tools.permissions import RequiredPermission as CoreRequiredPermission

# Use core types
AgentSafety = CoreAgentSafety
RequiredPermission = CoreRequiredPermission

logger = getLogger(__name__)

# Try to import Completion for completers
try:
    from prompt_toolkit.completion import Completion
except ImportError:
    Completion = None  # type: ignore


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


@dataclass
class Command:
    """Represents a slash command."""
    aliases: tuple[str, ...]  # e.g., ("/help", "/h")
    description: str = ""
    usage: str = ""
    handler: str = ""  # method name on the app
    exits: bool = False  # whether command exits the app
    hidden: bool = False  # whether to hide from completion


class CommandRegistry:
    """Registry for available commands."""

    def __init__(self, availability_context: CommandAvailabilityContext | None = None):
        self.availability_context = availability_context
        self.commands: dict[str, Command] = {}
        self._built = False
        self._build_commands()

    def _build_commands(self) -> None:
        """Build the available commands."""
        if self._built:
            return
        self._built = True

        # Register core commands
        self._register_core_commands()

    def _register_core_commands(self) -> None:
        """Register built-in commands."""
        # Help command
        self.commands["help"] = Command(
            aliases=("/help", "/h"),
            description="Show available commands",
            usage="",
            handler="_show_help",
        )

        # Status command
        self.commands["status"] = Command(
            aliases=("/status", "/st"),
            description="Show system status",
            usage="",
            handler="_show_status",
        )

        # Clear command
        self.commands["clear"] = Command(
            aliases=("/clear",),
            description="Clear the screen",
            usage="",
            handler="_clear_history",
        )

        # Exit command
        self.commands["exit"] = Command(
            aliases=("/exit", "/quit"),
            description="Exit JARVIS",
            usage="",
            handler="_exit_app",
            exits=True,
        )

        # Profile command
        self.commands["profile"] = Command(
            aliases=("/profile",),
            description="Switch or list agent profiles",
            usage="[<profile>]",
            handler="_switch_to_profile_app",
        )

        # Tools command
        self.commands["tools"] = Command(
            aliases=("/tools",),
            description="List available tools",
            usage="",
            handler="_show_tools",
        )

        # Skills command
        self.commands["skills"] = Command(
            aliases=("/skills",),
            description="List and manage skills",
            usage="[activate <name>]",
            handler="_show_skills",
        )

        # Themes command
        self.commands["themes"] = Command(
            aliases=("/themes",),
            description="List and manage UI themes",
            usage="",
            handler="_show_themes",
        )

        # Rewind command (similar to mistral-vibe)
        self.commands["rewind"] = Command(
            aliases=("/rewind", "/rw"),
            description="Rewind conversation to a previous message (Alt+↑/↓ to navigate)",
            usage="",
            handler="_start_rewind_mode",
        )

        # Config command (like Vibe)
        self.commands["config"] = Command(
            aliases=("/config", "/settings"),
            description="Edit config settings",
            usage="",
            handler="_show_config",
        )

        # MCP command (like Vibe)
        self.commands["mcp"] = Command(
            aliases=("/mcp",),
            description="Display available MCP servers",
            usage="[server_name]",
            handler="_show_mcp",
        )

        # Copy command
        self.commands["copy"] = Command(
            aliases=("/copy",),
            description="Copy last assistant answer to clipboard",
            usage="",
            handler="_copy_last_answer",
        )

        # Clear command - start new session
        self.commands["clear"] = Command(
            aliases=("/clear",),
            description="Start a new session with fresh history",
            usage="",
            handler="_start_new_session",
        )

    def refresh(self, availability_context: CommandAvailabilityContext) -> None:
        """Refresh command availability based on context."""
        self.availability_context = availability_context

    def has_command(self, command_name: str) -> bool:
        """Check if a command exists."""
        return command_name in self.commands or any(
            command_name in cmd.aliases for cmd in self.commands.values()
        )

    def resolve_alias(self, alias: str) -> tuple[str, Command] | None:
        """Resolve a slash-command alias to its canonical command."""
        for cmd_name, cmd in self.commands.items():
            if alias in cmd.aliases:
                return cmd_name, cmd
        return None

    def parse_command(self, user_input: str) -> tuple[str, Command, str] | None:
        """Parse command from user input."""
        user_input = user_input.strip()

        # Direct check for /rewind and /rw commands
        if user_input == '/rewind' or user_input.startswith('/rewind '):
            if 'rewind' in self.commands:
                cmd = self.commands['rewind']
                args = user_input[len('/rewind'):].strip()
                return ('rewind', cmd, args)
        if user_input == '/rw' or user_input.startswith('/rw '):
            if 'rewind' in self.commands:
                cmd = self.commands['rewind']
                args = user_input[len('/rw'):].strip()
                return ('rewind', cmd, args)

        # Normal processing for other commands
        for cmd_name, cmd in self.commands.items():
            for alias in cmd.aliases:
                if user_input == alias or user_input.startswith(alias + ' '):
                    args = user_input[len(alias):].strip()
                    return cmd_name, cmd, args

        return None

    def get_help_text(self) -> str:
        """Get help text for all commands."""
        lines = ["Available commands:"]
        for cmd_name, cmd in sorted(self.commands.items()):
            aliases = "/".join(cmd.aliases)
            usage = f" {cmd.usage}" if cmd.usage else ""
            lines.append(f"  {aliases}{usage} - {cmd.description}")
        return "\n".join(lines)


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
        self._suggestions: list[tuple[str, str, str]] = []
        self._selected_index = 0
        self._popup_visible = False

    def can_handle(self, text: str, cursor_index: int) -> bool:
        # Handle @ paths or ~ paths
        if cursor_index == 0:
            return False
        before_cursor = text[:cursor_index]
        # Check if the current word starts with @, ~, /, or .
        parts = before_cursor.split()
        if not parts:
            return False
        last_word = parts[-1]
        return last_word.startswith(("@", "~", "/", "."))

    def on_text_changed(self, text: str, cursor_index: int) -> None:
        if not self.can_handle(text, cursor_index):
            self.reset()
            return

        # Get the word being completed
        before_cursor = text[:cursor_index]
        parts = before_cursor.split()
        if not parts:
            self.reset()
            return

        word = parts[-1]

        # Get suggestions from completer
        self._suggestions = self.completer.get_completions(word, self.parent) if hasattr(self.completer, 'get_completions') else []
        self._selected_index = 0
        self._popup_visible = bool(self._suggestions)

        if self._suggestions and self.parent:
            self.parent.render_completion_suggestions(self._suggestions, 0)
        elif self.parent:
            self.parent.clear_completion_suggestions()

    def on_key(self, event: Any, text: str, cursor_index: int) -> CompletionResult:
        if not self._popup_visible or not self._suggestions:
            return CompletionResult.IGNORED

        if event.key == "tab":
            if 0 <= self._selected_index < len(self._suggestions):
                replacement = self._suggestions[self._selected_index][2]
                if self.parent and hasattr(self.parent, 'replace_completion_range'):
                    self.parent.replace_completion_range(cursor_index - len(self._get_word_before_cursor(text, cursor_index)),
                                                          cursor_index, replacement)
                return CompletionResult.HANDLED
        elif event.key == "enter":
            if 0 <= self._selected_index < len(self._suggestions):
                current_word = self._get_word_before_cursor(text, cursor_index)
                # If the current text exactly matches a suggestion's replacement, let it submit instead of completing
                if current_word in [suggestion[2] for suggestion in self._suggestions]:
                    return CompletionResult.IGNORED
                replacement = self._suggestions[self._selected_index][2]
                if self.parent and hasattr(self.parent, 'replace_completion_range'):
                    self.parent.replace_completion_range(cursor_index - len(self._get_word_before_cursor(text, cursor_index)),
                                                          cursor_index, replacement)
                return CompletionResult.HANDLED
        elif event.key == "escape":
            self.reset()
            return CompletionResult.HANDLED
        elif event.key == "up":
            self._selected_index = max(0, self._selected_index - 1)
            if self.parent:
                self.parent.render_completion_suggestions(self._suggestions, self._selected_index)
            return CompletionResult.HANDLED
        elif event.key == "down":
            self._selected_index = min(len(self._suggestions) - 1, self._selected_index + 1)
            if self.parent:
                self.parent.render_completion_suggestions(self._suggestions, self._selected_index)
            return CompletionResult.HANDLED

        return CompletionResult.IGNORED

    def _get_word_before_cursor(self, text: str, cursor_index: int) -> str:
        before_cursor = text[:cursor_index]
        parts = before_cursor.split()
        return parts[-1] if parts else ""

    def reset(self) -> None:
        self._suggestions = []
        self._selected_index = 0
        self._popup_visible = False
        if self.parent:
            self.parent.clear_completion_suggestions()


class SlashCommandController:
    """Controller for slash command completion."""
    def __init__(self, completer: Any, parent: Any):
        self.completer = completer
        self.parent = parent
        # (label, description, replacement)
        self._suggestions: list[tuple[str, str, str]] = []
        self._selected_index = 0
        self._popup_visible = False

    def can_handle(self, text: str, cursor_index: int) -> bool:
        # Handle slash commands - check if we're in a slash command context
        text_before_cursor = text[:cursor_index]
        # Check if we're at the start of a slash command or typing it
        return text_before_cursor.lstrip().startswith("/") or \
               (cursor_index > 0 and text[cursor_index - 1] == "/" and not text[:cursor_index - 1].strip().endswith(" "))

    def on_text_changed(self, text: str, cursor_index: int) -> None:
        if not self.can_handle(text, cursor_index):
            self.reset()
            return

        text_before_cursor = text[:cursor_index]
        stripped_before_cursor = text_before_cursor.lstrip()
        parts = stripped_before_cursor.split()

        if not parts or not parts[0].startswith("/"):
            self.reset()
            return

        cmd_alias = parts[0]
        current_word = self._get_current_word(text, cursor_index)

        # Completing the command token itself.
        if len(parts) == 1 and not stripped_before_cursor.endswith(" "):
            entries = (
                self.completer.entries_getter()
                if hasattr(self.completer, "entries_getter")
                else []
            )
            # (label, description, replacement)
            self._suggestions = [
                (label, desc, self._format_command_replacement(label))
                for label, desc in entries
                if label.lower().startswith(cmd_alias.lower())
            ]
        else:
            arg_entries = (
                self.completer.get_argument_entries(cmd_alias, stripped_before_cursor)
                if hasattr(self.completer, "get_argument_entries")
                else []
            )
            prefix = "" if text_before_cursor.endswith(" ") else current_word
            # (label, description, replacement)
            self._suggestions = [
                (label, desc, self._format_argument_replacement(label, text, cursor_index))
                for label, desc in arg_entries
                if label.lower().startswith(prefix.lower())
            ]

        self._selected_index = 0
        self._popup_visible = bool(self._suggestions)
        if self._suggestions and self.parent:
            self.parent.render_completion_suggestions(self._suggestions, 0)
        elif self.parent:
            self.parent.clear_completion_suggestions()

    def on_key(self, event: Any, text: str, cursor_index: int) -> CompletionResult:
        if not self._popup_visible or not self._suggestions:
            return CompletionResult.IGNORED

        if event.key == "tab":
            if 0 <= self._selected_index < len(self._suggestions):
                replacement = self._format_replacement(
                    text,
                    cursor_index,
                    self._suggestions[self._selected_index][2],
                )
                if self.parent and hasattr(self.parent, 'replace_completion_range'):
                    self.parent.replace_completion_range(
                        cursor_index - len(self._get_current_word(text, cursor_index)),
                        cursor_index,
                        replacement,
                    )
            return CompletionResult.HANDLED
        elif event.key == "enter":
            # Only handle enter if popup is visible and we have a selection
            if 0 <= self._selected_index < len(self._suggestions):
                current_word = self._get_current_word(text, cursor_index)
                # If the current text exactly matches a command, let it submit instead of completing
                if current_word in [suggestion[0] for suggestion in self._suggestions]:
                    return CompletionResult.IGNORED
                replacement = self._format_replacement(
                    text,
                    cursor_index,
                    self._suggestions[self._selected_index][2],
                )
                if self.parent and hasattr(self.parent, 'replace_completion_range'):
                    self.parent.replace_completion_range(
                        cursor_index - len(self._get_current_word(text, cursor_index)),
                        cursor_index,
                        replacement,
                    )
                return CompletionResult.HANDLED
            return CompletionResult.IGNORED
        elif event.key == "escape":
            self.reset()
            return CompletionResult.HANDLED
        elif event.key == "up":
            self._selected_index = max(0, self._selected_index - 1)
            if self.parent:
                self.parent.render_completion_suggestions(self._suggestions, self._selected_index)
            return CompletionResult.HANDLED
        elif event.key == "down":
            self._selected_index = min(len(self._suggestions) - 1, self._selected_index + 1)
            if self.parent:
                self.parent.render_completion_suggestions(self._suggestions, self._selected_index)
            return CompletionResult.HANDLED

        return CompletionResult.IGNORED

    def _get_current_word(self, text: str, cursor_index: int) -> str:
        # Get the last word before cursor
        before_cursor = text[:cursor_index]
        parts = before_cursor.split()
        return parts[-1] if parts else ""

    def _format_replacement(
        self, text: str, cursor_index: int, replacement: str
    ) -> str:
        suffix = text[cursor_index:]
        if replacement.startswith("/"):
            return replacement + (" " if not suffix or not suffix[0].isspace() else "")
        return replacement + (" " if not suffix or not suffix[0].isspace() else "")

    def _format_command_replacement(self, label: str) -> str:
        """Format a slash command for replacement."""
        return label

    def _format_argument_replacement(self, label: str, text: str, cursor_index: int) -> str:
        """Format an argument for replacement."""
        return label

    def reset(self) -> None:
        self._suggestions = []
        self._selected_index = 0
        self._popup_visible = False
        if self.parent:
            self.parent.clear_completion_suggestions()


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

    def __init__(self, entries_getter: Any, argument_entries_getter: Any = None):
        self.entries_getter = entries_getter
        self.argument_entries_getter = argument_entries_getter

    def get_completions(self, document, complete_event):
        # Handle both document objects and strings (for backward compatibility)
        if isinstance(document, str):
            text = document
        else:
            text = document.get_word_before_cursor()

        if text.startswith('/'):
            entries = self.entries_getter() if self.entries_getter else []
            for label, _ in entries:
                if label.lower().startswith(text.lower()):
                    if Completion:
                        yield Completion(label, start_position=-len(text))

    def get_argument_entries(
        self, command_alias: str, text_before_cursor: str
    ) -> list[tuple[str, str]]:
        if not self.argument_entries_getter:
            return []
        return self.argument_entries_getter(command_alias, text_before_cursor)


class PathCompleter:
    """Completer for file paths and @ search."""

    def __init__(self, watcher_enabled_getter: Any = None):
        self.watcher_enabled_getter = watcher_enabled_getter
        from jarvis.core.utils.indexer import ProjectIndexer
        self.indexer = ProjectIndexer()

    def get_completions(self, document, complete_event) -> list[tuple[str, str, str]]:
        # Handle both document objects and strings
        if isinstance(document, str):
            text = document
        elif hasattr(document, 'get_word_before_cursor'):
            text = document.get_word_before_cursor()
        else:
            text = str(document)

        if text.startswith('@'):
            # Use ProjectIndexer for project-wide search
            return self.indexer.search(text)

        if text.startswith('/') or text.startswith('~') or text.startswith('.'):
            import os
            import sys
            base_path = text
            if '/' in text or ('\\' in text and sys.platform == 'win32'):
                # Use split to handle both separators
                if '/' in text:
                    base_path = text[:text.rfind('/') + 1]
                    prefix = text[text.rfind('/') + 1:]
                elif '\\' in text:
                    base_path = text[:text.rfind('\\') + 1]
                    prefix = text[text.rfind('\\') + 1:]
                else:
                    base_path = './'
                    prefix = text
            else:
                base_path = './'
                prefix = text

            suggestions = []
            try:
                # Expand user for ~ paths
                expanded_base = os.path.expanduser(base_path)
                for item in os.listdir(expanded_base):
                    if item.lower().startswith(prefix.lower()):
                        full_path = os.path.join(expanded_base, item)
                        is_dir = os.path.isdir(full_path)
                        label = item + ("/" if is_dir else "")
                        desc = base_path
                        # For local paths, replacement is just the label without icon
                        replacement = item + ("/" if is_dir else "")
                        suggestions.append((label, desc, replacement))
            except (FileNotFoundError, PermissionError):
                pass
            return suggestions

        return []


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
    url: str = ""  # For HTTP/SSE transport
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
    api_timeout: float = 1800.0  # 30 minutes for long-running tool operations
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
    query: str = Field(validation_alias=AliasChoices("query", "pattern"))
    path: str = "."
    max_matches: int | None = Field(None, validation_alias=AliasChoices("max_matches", "maxMatches"))
    is_regexp: bool | None = Field(False, validation_alias=AliasChoices("is_regexp", "isRegexp"))
    include_pattern: str | None = Field(None, validation_alias=AliasChoices("include_pattern", "includePattern"))


class LSArgs(BaseModel):
    path: str = Field(".", validation_alias=AliasChoices("path", "directory"))


class FindArgs(BaseModel):
    pattern: str
    path: str = ""
    max_results: int | None = Field(None, validation_alias=AliasChoices("max_results", "maxResults"))


class ReadFileArgs(BaseModel):
    # Matches the read_file tool schema which uses 'files' array with 'file_path'
    # The files array contains dicts with file_path, offset, and limit
    files: list = []
    encoding: str = "utf-8"

    @model_validator(mode="before")
    @classmethod
    def normalize_files(cls, data: Any) -> Any:
        if isinstance(data, dict):
            # If called with single path instead of files list
            path = data.get("path") or data.get("filePath") or data.get("file_path")
            if path and not data.get("files"):
                data["files"] = [{"file_path": path}]
        return data


class TodoArgs(BaseModel):
    action: str
    todos: list = []


class WriteFileArgs(BaseModel):
    file_path: str = Field(validation_alias=AliasChoices("file_path", "filePath", "path"))
    content: str


class SearchReplaceArgs(BaseModel):
    filePath: str
    content: str


class EditArgs(BaseModel):
    """Arguments for the edit tool."""
    replacements: list[dict] = Field(default_factory=list)


# ============================================================================
# QUESTION SYSTEM
# ============================================================================

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


class AskUserQuestionArgs(BaseModel):
    """Arguments for asking the user questions."""
    questions: list[Question] = Field(default_factory=list)
    cancelled: bool = False
    content_preview: str = ""


class AskUserQuestionResult(BaseModel):
    answers: list["Answer"] = []
    cancelled: bool = False


class Answer(BaseModel):
    question: str = ""
    answer: str = ""
    is_other: bool = False


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
        args = getattr(event, "tool_args", {}) or {}

        # Specialized summaries for better UX
        if tool_name == "grep":
            query = args.get("query", args.get("pattern", ""))
            path = args.get("path", args.get("includePattern", "."))
            path_suffix = f" in {path}" if path != "." else ""
            return Display(summary=f"GREP \"{query}\"{path_suffix}")

        if tool_name == "agents":
            agent_name = args.get("agentName", "agent")
            prompt = args.get("prompt", "")
            prompt_preview = prompt[:30] + "..." if len(prompt) > 30 else prompt
            return Display(summary=f"AGENT {agent_name}: {prompt_preview}")

        if tool_name in ("read", "read_file"):
            def get_rel_path(p_str):
                if not p_str: return "unknown"
                try:
                    p = Path(p_str).resolve()
                    cwd = Path.cwd().resolve()
                    if p == cwd: return "."
                    if p.is_relative_to(cwd):
                        rel = p.relative_to(cwd)
                        res = str(rel).replace('\\', '/')
                        return res if res else "."
                    return p_str
                except Exception:
                    return p_str

            paths = args.get("files", [])
            if paths and isinstance(paths, list) and len(paths) > 0:
                first = paths[0]
                if isinstance(first, dict):
                    raw_path = first.get("file_path") or first.get("filePath") or "unknown"
                    path = get_rel_path(raw_path)
                    offset = first.get("offset")
                    limit = first.get("limit")
                    params = []
                    if offset is not None:
                        params.append(f"offset={offset}")
                    if limit is not None:
                        params.append(f"limit={limit}")

                    param_str = f" ({', '.join(params)})" if params else ""
                    summary = f"READ {path}{param_str}"
                    if len(paths) > 1:
                        summary += f" (+{len(paths)-1} more files)"
                    return Display(summary=summary)

            # Single file mode
            raw_path = args.get("filePath") or args.get("path") or args.get("file_path")
            if raw_path:
                path = get_rel_path(raw_path)
                offset = args.get("offset")
                limit = args.get("limit")
                params = []
                if offset is not None:
                    params.append(f"offset={offset}")
                if limit is not None:
                    params.append(f"limit={limit}")

                param_str = f" ({', '.join(params)})" if params else ""
                return Display(summary=f"READ {path}{param_str}")

            return Display(summary="READ unknown")

        if tool_name in ("write", "write_file"):
            def get_rel_path(p_str):
                if not p_str: return "unknown"
                try:
                    p = Path(p_str).resolve()
                    cwd = Path.cwd().resolve()
                    if p == cwd: return "."
                    if p.is_relative_to(cwd):
                        rel = p.relative_to(cwd)
                        res = str(rel).replace('\\', '/')
                        return res if res else "."
                    return p_str
                except Exception:
                    return p_str

            raw_path = args.get("path", args.get("filePath", args.get("file_path", "unknown")))
            path = get_rel_path(raw_path)
            return Display(summary=f"{tool_name.upper()} {path}")

        if tool_name == "edit":
            def get_rel_path(p_str):
                if not p_str: return "unknown"
                try:
                    p = Path(p_str).resolve()
                    cwd = Path.cwd().resolve()
                    if p == cwd: return "."
                    if p.is_relative_to(cwd):
                        rel = p.relative_to(cwd)
                        res = str(rel).replace('\\', '/')
                        return res if res else "."
                    return p_str
                except Exception:
                    return p_str

            replacements = args.get("replacements", [])
            if replacements and isinstance(replacements, list):
                first = replacements[0]
                if isinstance(first, dict):
                    raw_path = first.get("filePath") or first.get("file_path") or "unknown"
                else:
                    raw_path = "unknown"
            else:
                raw_path = "unknown"
            path = get_rel_path(raw_path)
            count = len(replacements) if isinstance(replacements, list) else 0
            suffix = f" ({count} edits)" if count > 1 else ""
            return Display(summary=f"EDIT {path}{suffix}")

        if tool_name == "bash":
            command = args.get("command", "")
            summary = command.split("\n")[0]
            if len(summary) > 50:
                summary = summary[:47] + "..."
            return Display(summary=f"BASH \"{summary}\"")

        if tool_name == "ls":
            path_str = args.get("path", ".")
            try:
                p = Path(path_str).resolve()
                cwd = Path.cwd().resolve()
                if p == cwd:
                    display_path = "."
                elif p.is_relative_to(cwd):
                    rel = p.relative_to(cwd)
                    display_path = str(rel).replace("\\", "/")
                    if not display_path:
                        display_path = "."
                else:
                    display_path = path_str
                return Display(summary=f"LIST {display_path}")
            except Exception:
                return Display(summary=f"List {path_str}")

        if tool_name == "find":
            pattern = args.get("pattern", "")
            path_str = args.get("path", "")
            if not path_str:
                path_str = "."
            try:
                p = Path(path_str).resolve()
                cwd = Path.cwd().resolve()
                if p == cwd:
                    display_path = str(cwd).replace('\\', '/')
                elif p.is_relative_to(cwd):
                    rel = p.relative_to(cwd)
                    display_path = (str(cwd).replace("\\", "/") + "/" + str(rel).replace("\\", "/")).rstrip("/")
                else:
                    display_path = path_str.replace('\\', '/')
                return Display(summary=f"FIND \"{pattern}\" in {display_path}")
            except Exception:
                return Display(summary=f"FIND \"{pattern}\" in {path_str}")

        args_text = self._format_args(args)
        if args_text:
            return Display(summary=f"{tool_name.upper()} {args_text}")
        return Display(summary=f"{tool_name.upper()}")

    def get_result_display(self, event: Any) -> Any:
        @dataclass
        class Display:
            success: bool = True
            message: str = ""
            warnings: list[Any] | None = None

        tool_name = getattr(event, "tool_name", "") or self.tool_class or "tool"

        # Check for explicit error in event
        if hasattr(event, 'error') and event.error:
            return Display(success=False, message=f"{tool_name}: error", warnings=[])

        # Check for skipped or cancelled
        if getattr(event, "skipped", False) or getattr(event, "cancelled", False):
            return Display(success=False, message=f"{tool_name}: interrupted", warnings=[])

        # Check the result object for success indicators
        result = getattr(event, "result", None)
        success = True

        if result is not None:
            # Bash tool: check returncode
            if hasattr(result, "returncode"):
                success = result.returncode == 0
            # Generic success flag
            elif hasattr(result, "success"):
                success = bool(result.success)
            elif isinstance(result, dict) and "success" in result:
                success = bool(result["success"])
            # Some tools return error messages in the result
            elif isinstance(result, dict) and "error" in result and result["error"]:
                success = False

        return Display(success=success, message=f"{tool_name}: completed", warnings=[])


def make_transcribe_client(provider: str, model: str) -> Any:
    return None


# ============================================================================
# PROXY SYSTEM
# ============================================================================

SUPPORTED_PROXY_VARS: dict[str, str] = {}


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
