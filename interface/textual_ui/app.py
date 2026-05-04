from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from contextlib import aclosing
from dataclasses import dataclass
from enum import Enum, auto
import gc
import os
from pathlib import Path
import signal
import subprocess
import time
from typing import Any, ClassVar, cast, TYPE_CHECKING
from weakref import WeakKeyDictionary
import webbrowser

if TYPE_CHECKING:
    from typing_extensions import assert_never
else:
    def assert_never(value: Any) -> None:
        raise AssertionError(f"Unhandled value: {value}")


from pydantic import BaseModel
from rich import print as rprint
from textual.app import WINDOWS, App, ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Horizontal, VerticalGroup, VerticalScroll
from textual.driver import Driver
from textual.events import AppBlur, AppFocus, MouseUp
from textual.widget import Widget
from textual.widgets import Static

from interface.textual_ui.constants import CORE_VERSION
from interface.textual_ui.cli_adapters import (
    copy_selection_to_clipboard,
    copy_text_to_clipboard,
    CommandAvailabilityContext,
    CommandRegistry,
    ALT_KEY,
    CompletionResult,
    HistoryManager,
    NarratorManager,
    NarratorManagerPort,
    NarratorState,
    NarratorManagerListener,
    RecordingStartError,
    VoiceManagerListener,
    HttpWhoAmIGateway,
    PlanInfo,
    decide_plan_offer,
    plan_offer_cta,
    plan_title,
    resolve_api_key_for_plan,
    WhoAmIGateway,
    WhoAmIPlanType,
    read_cache,
    write_cache,
    CACHE_FILE,
    AgentSafety,
)
from interface.textual_ui.handlers.event_handler import EventHandler
from interface.textual_ui.notifications import (
    NotificationContext,
    NotificationPort,
    TextualNotificationAdapter,
)
from interface.textual_ui.quit_manager import QuitManager
from interface.textual_ui.remote import RemoteSessionManager, is_progress_event
from interface.textual_ui.session_exit import print_session_resume_message
from interface.textual_ui.widgets.approval_app import ApprovalApp
from interface.textual_ui.widgets.banner.banner import Banner
from interface.textual_ui.widgets.chat_input import ChatInputContainer
from interface.textual_ui.widgets.chat_input.text_area import ChatTextArea
from interface.textual_ui.widgets.compact import CompactMessage
from interface.textual_ui.widgets.config_app import ConfigApp
from interface.textual_ui.widgets.connector_auth_app import ConnectorAuthApp
from interface.textual_ui.widgets.context_progress import ContextProgress, TokenState
from core.llm_sdk.context_length_manager import context_length_manager
from interface.textual_ui.widgets.debug_console import DebugConsole
from interface.textual_ui.widgets.feedback_bar import FeedbackBar
from interface.textual_ui.widgets.feedback_bar_manager import FeedbackBarManager
from interface.textual_ui.widgets.load_more import HistoryLoadMoreRequested
from interface.textual_ui.widgets.loading import (
    DEFAULT_LOADING_STATUS,
    LoadingWidget,
    paused_timer,
)
from interface.textual_ui.widgets.mcp_app import MCPApp, MCPSourceKind
from interface.textual_ui.widgets.messages import (
    AssistantMessage,
    BashOutputMessage,
    ErrorMessage,
    InterruptMessage,
    StreamingMessageBase,
    UserCommandMessage,
    UserMessage,
    WarningMessage,
    WhatsNewMessage,
)
from interface.textual_ui.widgets.model_picker import ModelPickerApp
from interface.textual_ui.widgets.narrator_status import NarratorStatus
from interface.textual_ui.widgets.no_markup_static import NoMarkupStatic
from interface.textual_ui.widgets.path_display import PathDisplay
from interface.textual_ui.widgets.proxy_setup_app import ProxySetupApp
from interface.textual_ui.widgets.question_app import QuestionApp
from interface.textual_ui.widgets.rewind_app import RewindApp
from interface.textual_ui.widgets.session_picker import SessionPickerApp
from interface.textual_ui.widgets.teleport_message import TeleportMessage
from interface.textual_ui.widgets.thinking_picker import ThinkingPickerApp
from interface.textual_ui.widgets.tools import ToolResultMessage
# from interface.textual_ui.widgets.voice_app import VoiceApp  # Not supported in core Settings
from interface.textual_ui.windowing import (
    HISTORY_RESUME_TAIL_MESSAGES,
    LOAD_MORE_BATCH_SIZE,
    HistoryLoadMoreManager,
    SessionWindowing,
    build_history_widgets,
    create_resume_plan,
    non_system_history_messages,
    should_resume_history,
    sync_backfill_state,
)
from interface.textual_ui.cli_adapters import (
    FileSystemUpdateCacheRepository,
    PyPIUpdateGateway,
    UpdateCacheRepository,
    UpdateError,
    UpdateGateway,
    get_update_if_available,
    load_whats_new_content,
    mark_version_as_seen,
    should_show_whats_new,
    do_update,
    VoiceManager,
    VoiceManagerPort,
    TranscribeState,
    TeleportError,
    AgentProfile,
    AudioPlayer,
    AudioRecorder,
    render_path_prompt,
    VibeConfig,
    ConnectorConfig,
    MCPServer,
    ThinkingLevel,
    THINKING_LEVELS,
    DATA_RETENTION_MESSAGE,
    HookStartEvent,
    HookMessageSeverity,
    LogReader,
    LogEntry,
    decode_log_message,
    logger,
    HISTORY_FILE,
    RewindError,
    ResumeSessionInfo,
    ResumeSessionSource,
    list_local_resume_sessions,
    list_remote_resume_sessions,
    short_session_id,
    SessionLoader,
    SkillManager,
    MCPRegistry,
    TeleportAuthCompleteEvent,
    TeleportAuthRequiredEvent,
    TeleportCheckingGitEvent,
    TeleportCompleteEvent,
    TeleportFetchingUrlEvent,
    TeleportPushingEvent,
    TeleportPushRequiredEvent,
    TeleportPushResponseEvent,
    TeleportStartingWorkflowEvent,
    TeleportWaitingForGitHubEvent,
    AskUserQuestionArgs,
    AskUserQuestionResult,
    Choice,
    Question,
    ConnectorRegistry,
    connectors_enabled,
    persist_mcp_toggle,
    MCPTool,
    updated_tool_list,
    RequiredPermission,
    make_transcribe_client,
    stderr_guard,
)
from interface.textual_ui.agent_loop import AgentLoop
from interface.textual_ui.types import (
    AgentStats,
    ApprovalResponse,
    BaseEvent,
    ContextTooLongError,
    LLMMessage,
    RateLimitError,
    Role,
    WaitingForInputEvent,
)
from interface.textual_ui.utils import (
    CancellationReason,
    get_user_cancellation_message,
    is_dangerous_directory,
)


def _compute_connectors_count(
    config: VibeConfig, connector_registry: ConnectorRegistry | None
) -> int:
    """Compute the count of active MCP servers.
    
    This replaces the old connector counting logic which always returned 0
    because the ConnectorRegistry is not used. Now counts actual MCP servers.
    """
    from pathlib import Path
    import json
    
    # Look for MCP config in same locations as tui_main.py
    config_path = Path(".mcp.json")
    if not config_path.exists():
        config_path = Path.home() / ".jarvis" / "mcp_servers.json"
    
    if not config_path.exists():
        return 0
    
    try:
        with open(config_path) as f:
            data = json.load(f)
        
        # Handle Claude MCP format: {"mcpServers": {"name": {...}}}
        if "mcpServers" in data:
            servers = list(data["mcpServers"].keys())
        # Handle list format: [{"name": ..., ...}]
        elif isinstance(data, list):
            servers = [s.get("name", "") for s in data if s.get("name")]
        else:
            servers = []
        
        # Get disabled MCP servers from config
        disabled_names = {c.name for c in config.connectors if c.disabled} if hasattr(config, 'connectors') else set()
        
        # Count enabled (non-disabled) MCP servers
        enabled_count = sum(1 for s in servers if s not in disabled_names)
        
        return enabled_count
    except Exception:
        return 0


class BottomApp(str, Enum):
    """Bottom panel app types.

    Convention: Each value must match the widget class name with "App" suffix removed.
    E.g., ApprovalApp -> Approval, ConfigApp -> Config, QuestionApp -> Question.
    This allows dynamic lookup via: BottomApp[type(widget).__name__.removesuffix("App")]
    """

    Approval = "Approval"
    Config = "Config"
    ConnectorAuth = "ConnectorAuth"
    Input = "Input"
    MCP = "MCP"
    ModelPicker = "ModelPicker"
    ProxySetup = "ProxySetup"
    Question = "Question"
    ThinkingPicker = "ThinkingPicker"
    Rewind = "Rewind"
    SessionPicker = "SessionPicker"
    # Voice = "Voice"  # Not supported in core Settings

    def __str__(self) -> str:
        return self.value



class ChatScroll(VerticalScroll):
    """Optimized scroll container that skips cascading style recalculations."""

    @property
    def is_at_bottom(self) -> bool:
        return self.scroll_target_y >= self.max_scroll_y

    _reanchor_pending: bool = False
    _scrolling_down: bool = False

    def watch_scroll_y(self, old_value: float, new_value: float) -> None:
        super().watch_scroll_y(old_value, new_value)
        self._scrolling_down = new_value >= old_value

    def release_anchor(self) -> None:
        super().release_anchor()
        # Textual's MRO dispatch calls Widget._on_mouse_scroll_down AFTER
        # our override, so any re-anchor we do gets immediately undone.
        # Defer the re-check until all handlers for this event have finished.
        if not self._reanchor_pending:
            self._reanchor_pending = True
            self.call_later(self._maybe_reanchor)

    def _maybe_reanchor(self) -> None:
        self._reanchor_pending = False
        if (
            self._anchored
            and self._anchor_released
            and self.is_at_bottom
            and self._scrolling_down
        ):
            self.anchor()

    def update_node_styles(self, animate: bool = True) -> None:
        pass


PRUNE_LOW_MARK = 500
PRUNE_HIGH_MARK = 800
DOUBLE_ESC_DELAY = 0.2


async def prune_oldest_children(
    messages_area: Widget, low_mark: int, high_mark: int
) -> bool:
    """Remove the oldest children so the virtual height stays within bounds.

    Walks children back-to-front to find how much to keep (up to *low_mark*
    of visible height), then removes everything before that point.
    """
    total_height = messages_area.virtual_size.height
    if total_height <= high_mark:
        return False

    children = messages_area.children
    if not children:
        return False

    accumulated = 0
    cut = len(children)

    for child in reversed(children):
        if not child.display:
            cut -= 1
            continue
        accumulated += child.outer_size.height
        cut -= 1
        if accumulated >= low_mark:
            break

    to_remove = list(children[:cut])
    if not to_remove:
        return False

    await messages_area.remove_children(to_remove)
    return True


@dataclass(frozen=True, slots=True)
class StartupOptions:
    initial_prompt: str | None = None
    teleport_on_start: bool = False
    show_resume_picker: bool = False


class VibeApp(App):  # noqa: PLR0904
    ENABLE_COMMAND_PALETTE = False
    CSS_PATH = ["tcss/app.tcss", "tcss/grep.tcss", "tcss/ls.tcss", "tcss/read.tcss", "tcss/bash.tcss"]
    PAUSE_GC_ON_SCROLL: ClassVar[bool] = True

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("ctrl+c", "interrupt_or_quit", "Quit", show=False),
        Binding("ctrl+d", "delete_right_or_quit", "Quit", show=False, priority=True),
        Binding("ctrl+z", "suspend_with_message", "Suspend", show=False, priority=True),
        Binding("escape", "interrupt", "Interrupt", show=False, priority=True),
        Binding("ctrl+o", "toggle_tool", "Toggle Tool", show=False),
        Binding("ctrl+t", "toggle_thinking", "Toggle Thinking", show=False),
        Binding("ctrl+y", "copy_selection", "Copy", show=False, priority=True),
        Binding("ctrl+shift+c", "copy_selection", "Copy", show=False, priority=True),
        Binding("shift+tab", "cycle_mode", "Cycle Mode", show=False, priority=True),
        Binding("shift+up", "scroll_chat_up", "Scroll Up", show=False, priority=True),
        Binding(
            "shift+down", "scroll_chat_down", "Scroll Down", show=False, priority=True
        ),
        Binding("ctrl+backslash", "toggle_debug_console", "Debug Console", show=False),
        Binding("alt+up", "rewind_prev", "Rewind Previous", show=False, priority=True),
        Binding("ctrl+p", "rewind_prev", "Rewind Previous", show=False, priority=True),
        Binding("alt+down", "rewind_next", "Rewind Next", show=False, priority=True),
        Binding("ctrl+n", "rewind_next", "Rewind Next", show=False, priority=True),
    ]

    def __init__(
        self,
        agent_loop: AgentLoop,
        startup: StartupOptions | None = None,
        update_notifier: UpdateGateway | None = None,
        update_cache_repository: UpdateCacheRepository | None = None,
        current_version: str = CORE_VERSION,
        plan_offer_gateway: WhoAmIGateway | None = None,
        terminal_notifier: NotificationPort | None = None,
        voice_manager: VoiceManagerPort | None = None,
        narrator_manager: NarratorManagerPort | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.scroll_sensitivity_y = 1.0
        self.agent_loop = agent_loop
        self._plan_info: PlanInfo | None = None
        self._voice_manager: VoiceManagerPort = (
            voice_manager or self._make_default_voice_manager()
        )
        self._terminal_notifier = terminal_notifier or TextualNotificationAdapter(
            self,
            get_enabled=lambda: False,  # Notifications not supported in core Settings
            default_title="Vibe",
        )
        self._agent_running = False
        self._interrupt_requested = False
        self._agent_task: asyncio.Task | None = None
        self._remote_manager = RemoteSessionManager()

        self._loading_widget: LoadingWidget | None = None
        self._pending_approval: asyncio.Future | None = None
        self._pending_question: asyncio.Future | None = None
        self._user_interaction_lock = asyncio.Lock()

        self.event_handler: EventHandler | None = None

        self._chat_input_container: ChatInputContainer | None = None
        self._current_bottom_app: BottomApp = BottomApp.Input

        self.history_file = Path(HISTORY_FILE.path)

        self._tools_collapsed = True
        self._thinking_collapsed = False
        self._windowing = SessionWindowing(load_more_batch_size=LOAD_MORE_BATCH_SIZE)
        self._load_more = HistoryLoadMoreManager()
        self._tool_call_map: dict[str, str] | None = None
        self._history_widget_indices: WeakKeyDictionary[Widget, int] = (
            WeakKeyDictionary()
        )
        self._update_notifier = update_notifier
        self._update_cache_repository = update_cache_repository
        self._current_version = current_version
        self._plan_offer_gateway = plan_offer_gateway
        opts = startup or StartupOptions()
        self._initial_prompt = opts.initial_prompt
        self._teleport_on_start = (
            opts.teleport_on_start and self.agent_loop.base_config.vibe_code_enabled
        )
        self._show_resume_picker = opts.show_resume_picker
        self._last_escape_time: float | None = None
        self._quit_manager = QuitManager(self)
        self._banner: Banner | None = None
        self._whats_new_message: WhatsNewMessage | None = None
        self._cached_messages_area: Widget | None = None
        self._cached_chat: ChatScroll | None = None
        self._cached_loading_area: Widget | None = None
        self._log_reader = LogReader()
        self._debug_console: DebugConsole | None = None
        self._switch_agent_generation = 0
        self._narrator_manager: NarratorManagerPort = (
            narrator_manager or self._make_default_narrator_manager()
        )

        self._rewind_mode = False
        self._rewind_highlighted_widget: UserMessage | None = None
        self._fatal_init_error = False
        self.commands = self._build_command_registry()

    @property
    def config(self) -> VibeConfig:
        return cast(VibeConfig, self.agent_loop.config)

    @property
    def _connectors_enabled(self) -> bool:
        return connectors_enabled() and self.agent_loop.connector_registry is not None

    def _get_command_availability_context(self) -> CommandAvailabilityContext:
        return CommandAvailabilityContext(
            vibe_code_enabled=self.agent_loop.base_config.vibe_code_enabled,
            is_active_model_mistral=False,  # Not supported in core Settings
            plan_info=self._plan_info,
        )

    def _build_command_registry(self) -> CommandRegistry:
        return CommandRegistry(
            availability_context=self._get_command_availability_context()
        )

    def _refresh_command_registry(self) -> None:
        self.commands.refresh(self._get_command_availability_context())

    def compose(self) -> ComposeResult:
        with ChatScroll(id="chat"):
            self._banner = Banner(
                config=self.agent_loop.config,
                skill_manager=self.agent_loop.skill_manager,
                model=self.agent_loop.agent.model,
            )
            yield self._banner
            yield VerticalGroup(id="messages")

        with Horizontal(id="loading-area"):
            yield NarratorStatus(self._narrator_manager)
            yield Static(id="loading-area-content")
            yield FeedbackBar()

        with Static(id="bottom-app-container"):
            yield ChatInputContainer(
                history_file=self.history_file,
                command_registry=self.commands,
                id="input-container",
                safety=self.agent_loop.agent_profile.safety,
                agent_name=self.agent_loop.agent_profile.display_name.lower(),
                skill_entries_getter=self._get_skill_entries,
                slash_argument_entries_getter=self._get_slash_argument_entries,
                file_watcher_for_autocomplete_getter=self._is_file_watcher_enabled,
                voice_manager=self._voice_manager,
            )

        with Horizontal(id="bottom-bar"):
            yield PathDisplay(Path.cwd())
            yield NoMarkupStatic(id="spacer")
            yield ContextProgress()

    async def on_mount(self) -> None:
        # Use ANSI-based theme for consistent terminal styling
        self.theme = "ansi-dark"
        self._terminal_notifier.restore()

        self._cached_messages_area = self.query_one("#messages")
        self._cached_chat = self.query_one("#chat", ChatScroll)
        self._cached_loading_area = self.query_one("#loading-area-content")
        self._feedback_bar = self.query_one(FeedbackBar)
        self._feedback_bar_manager = FeedbackBarManager()

        self.event_handler = EventHandler(
            mount_callback=self._mount_and_scroll,
            get_tools_collapsed=lambda: self._tools_collapsed,
            get_thinking_collapsed=lambda: self._thinking_collapsed,
            on_profile_changed=self._on_profile_changed,
            is_remote=self._remote_manager.is_active,
        )

        # Load model limits from API in background (runs in its own thread)
        self._load_model_limits()

        self._chat_input_container = self.query_one(ChatInputContainer)
        context_progress = self.query_one(ContextProgress)

        def update_context_progress(stats: AgentStats) -> None:
            # Get actual model context limits from context_length_manager
            model_name = getattr(self.agent_loop.agent, 'model', 'gpt-4o')
            limits = context_length_manager.get_token_limits(model_name)
            max_tokens = limits.total_context_tokens
            
            # Use cumulative context tokens (total in context window)
            current_tokens = stats.context_tokens
            
            context_progress.tokens = TokenState(
                max_tokens=max_tokens,
                current_tokens=current_tokens,
            )

        self.agent_loop.stats.add_listener("context_tokens", update_context_progress)
        self.agent_loop.stats.trigger_listeners()

        self.agent_loop.set_approval_callback(self._approval_callback)
        self.agent_loop.set_user_input_callback(self._user_input_callback)
        self._refresh_profile_widgets()

        chat_input_container = self.query_one(ChatInputContainer)
        chat_input_container.focus_input()
        await self._resolve_plan()
        await self._show_dangerous_directory_warning()
        await self._resume_history_from_messages()
        await self._check_and_show_whats_new()
        self._schedule_update_notification()
        self.agent_loop.emit_new_session_telemetry()

        self.call_after_refresh(self._refresh_banner)
        self._show_hook_config_issues_once()

        self.run_worker(self._watch_init_completion(), exclusive=False)

        if self._show_resume_picker:
            self.run_worker(self._show_session_picker(), exclusive=False)
        elif self._initial_prompt or self._teleport_on_start:
            self.call_after_refresh(self._process_initial_prompt)

        gc.collect()
        gc.freeze()

    def _show_hook_config_issues_once(self) -> None:
        for issue in self.agent_loop.hook_config_issues:
            self.notify(
                f"{issue.file}\n{issue.message}",
                severity="warning",
                markup=False,
                timeout=10,
            )

    def _load_model_limits(self) -> None:
        """Load model limits from models.dev API in background."""
        # This runs in a background thread internally
        context_length_manager.load_model_limits()

    async def _watch_init_completion(self) -> None:
        """Show 'Initializing' loading indicator until background init finishes."""
        init_widget = None
        try:
            if not self.agent_loop.is_initialized:
                await self._ensure_loading_widget("Initializing", show_hint=False)
                init_widget = self._loading_widget
            await self.agent_loop.wait_until_ready()
        except Exception as e:
            await self._mount_and_scroll(
                ErrorMessage(
                    f"Background initialization failed: {e}",
                    collapsed=self._tools_collapsed,
                )
            )
            await self._mount_and_scroll(
                Static("Press any key to exit...", classes="error-hint")
            )
            if self._chat_input_container:
                self._chat_input_container.disabled = True
                self._chat_input_container.display = False
            self._fatal_init_error = True
        finally:
            if self._loading_widget is init_widget:
                await self._remove_loading_widget()
            self._refresh_banner()
            try:
                self.query_one(MCPApp).refresh_index()
            except Exception:
                pass

    def _process_initial_prompt(self) -> None:
        if self._teleport_on_start and self.commands.has_command("teleport"):
            self.run_worker(
                self._handle_teleport_command(self._initial_prompt), exclusive=False
            )
        elif self._initial_prompt:
            self.run_worker(
                self._handle_user_message(self._initial_prompt), exclusive=False
            )

    def _is_file_watcher_enabled(self) -> bool:
        return False  # Not supported in core Settings

    def on_key(self) -> None:
        if self._fatal_init_error:
            self.exit()

    async def on_chat_input_container_submitted(
        self, event: ChatInputContainer.Submitted
    ) -> None:
        if self._banner:
            self._banner.freeze_animation()

        if self._whats_new_message:
            await self._whats_new_message.remove()
            self._whats_new_message = None

        value = event.value.strip()
        if not value:
            return

        input_widget = self.query_one(ChatInputContainer)
        input_widget.value = ""

        if self._agent_running:
            # Direct check to handle /rw or /rewind even when agent is running (similar to mistral-vibe)
            if value == "/rw" or value == "/rewind" or value.startswith("/rw ") or value.startswith("/rewind "):
                self._start_rewind_mode(skip_agent_check=True)
                # Don't switch to input app - rewind handles its own UI state
                return
            await self._interrupt_agent_loop()

        if value.startswith("!"):
            await self._handle_bash_command(value[1:])
            await self._switch_to_input_app()
            return

        if value.startswith("&") and self.commands.has_command("teleport"):
            await self._handle_teleport_command(value[1:])
            await self._switch_to_input_app()
            return

        # Handle command - returns True for normal commands, "skip_input_switch" for rewind
        result = await self._handle_command(value)
        if result:
            # For rewind, skip switching to input app to keep the rewind UI visible
            if result == "skip_input_switch":
                return
            await self._switch_to_input_app()
            return

        if await self._handle_skill(value):
            await self._switch_to_input_app()
            return

        await self._handle_user_message(value)

    async def on_approval_app_approval_granted(
        self, message: ApprovalApp.ApprovalGranted
    ) -> None:
        if self._pending_approval and not self._pending_approval.done():
            self._pending_approval.set_result((ApprovalResponse.YES, None))
        await self._switch_to_input_app()

    async def on_approval_app_approval_granted_always_tool(
        self, message: ApprovalApp.ApprovalGrantedAlwaysTool
    ) -> None:
        self.agent_loop.approve_always(message.tool_name, message.required_permissions)

        if self._pending_approval and not self._pending_approval.done():
            self._pending_approval.set_result((ApprovalResponse.YES, None))
        await self._switch_to_input_app()

    async def on_approval_app_approval_rejected(
        self, message: ApprovalApp.ApprovalRejected
    ) -> None:
        if self._pending_approval and not self._pending_approval.done():
            feedback = str(
                get_user_cancellation_message(CancellationReason.OPERATION_CANCELLED)
            )
            self._pending_approval.set_result((ApprovalResponse.NO, feedback))

        if self._loading_widget and self._loading_widget.parent:
            await self._remove_loading_widget()
        await self._switch_to_input_app()

    async def on_question_app_answered(self, message: QuestionApp.Answered) -> None:
        if self._remote_manager.has_pending_input and self._remote_manager.is_active:
            result = AskUserQuestionResult(answers=message.answers, cancelled=False)
            await self._handle_remote_answer(result)
            return

        if self._pending_question and not self._pending_question.done():
            result = AskUserQuestionResult(answers=message.answers, cancelled=False)
            self._pending_question.set_result(result)
        await self._switch_to_input_app()

    async def on_question_app_cancelled(self, message: QuestionApp.Cancelled) -> None:
        if self._remote_manager.has_pending_input:
            self._remote_manager.cancel_pending_input()
            await self._switch_to_input_app()
            return

        if self._pending_question and not self._pending_question.done():
            result = AskUserQuestionResult(answers=[], cancelled=True)
            self._pending_question.set_result(result)
        await self._switch_to_input_app()

    def on_chat_text_area_feedback_key_pressed(
        self, message: ChatTextArea.FeedbackKeyPressed
    ) -> None:
        self._feedback_bar.handle_feedback_key(message.rating)

    def on_chat_text_area_non_feedback_key_pressed(
        self, message: ChatTextArea.NonFeedbackKeyPressed
    ) -> None:
        self._feedback_bar.hide()

    def on_feedback_bar_feedback_given(
        self, message: FeedbackBar.FeedbackGiven
    ) -> None:
        # Telemetry not fully supported in core Settings
        pass

    async def _remove_loading_widget(self) -> None:
        if self._loading_widget and self._loading_widget.parent:
            await self._loading_widget.remove()
            self._loading_widget = None

    async def on_config_app_open_model_picker(
        self, _message: ConfigApp.OpenModelPicker
    ) -> None:
        config_app = self.query_one(ConfigApp)
        changes = config_app._convert_changes_for_save()
        if changes:
            VibeConfig.save_updates(changes)
            await self._reload_config()
        await self._switch_to_input_app()
        await self._switch_to_model_picker_app()

    async def on_config_app_open_thinking_picker(
        self, _message: ConfigApp.OpenThinkingPicker
    ) -> None:
        config_app = self.query_one(ConfigApp)
        changes = config_app._convert_changes_for_save()
        if changes:
            VibeConfig.save_updates(changes)
            await self._reload_config()
        await self._switch_to_input_app()
        await self._switch_to_thinking_picker_app()

    async def _ensure_loading_widget(
        self, status: str = DEFAULT_LOADING_STATUS, *, show_hint: bool = True
    ) -> None:
        if self._loading_widget and self._loading_widget.parent:
            self._loading_widget.set_status(status)
            return

        loading_area = self._cached_loading_area
        if loading_area is None:
            try:
                loading_area = self.query_one("#loading-area-content")
            except Exception:
                return
        loading = LoadingWidget(status=status, show_hint=show_hint)
        self._loading_widget = loading
        await loading_area.mount(loading)

    async def on_config_app_config_closed(
        self, message: ConfigApp.ConfigClosed
    ) -> None:
        await self._handle_config_settings_closed(message.changes)
        await self._switch_to_input_app()

    # async def on_voice_app_config_closed(self, message: VoiceApp.ConfigClosed) -> None:
    #     await self._handle_voice_settings_closed(message.changes)
    #     await self._switch_to_input_app()

    async def _handle_config_settings_closed(
        self, changes: dict[str, str | bool]
    ) -> None:
        if changes:
            VibeConfig.save_updates(changes)
            await self._reload_config()
        else:
            await self._mount_and_scroll(
                UserCommandMessage("Configuration closed (no changes saved).")
            )

    async def _handle_voice_settings_closed(
        self, changes: dict[str, str | bool]
    ) -> None:
        if not changes:
            await self._mount_and_scroll(
                UserCommandMessage("Voice settings closed (no changes saved).")
            )
            return

        if "voice_mode_enabled" in changes:
            current = self._voice_manager.is_enabled
            desired = changes["voice_mode_enabled"]
            if current != desired:
                self._voice_manager.toggle_voice_mode()
                self.agent_loop.telemetry_client.send_telemetry_event(
                    "vibe.voice_mode_toggled", {"enabled": desired}
                )
                self.agent_loop.refresh_config()
                if desired:
                    await self._mount_and_scroll(
                        UserCommandMessage(
                            "Voice mode enabled. Press ctrl+r to start recording."
                        )
                    )
                else:
                    await self._mount_and_scroll(
                        UserCommandMessage("Voice mode disabled.")
                    )

        non_voice_changes = {
            k: v for k, v in changes.items() if k != "voice_mode_enabled"
        }
        if non_voice_changes:
            VibeConfig.save_updates(non_voice_changes)
            self.agent_loop.refresh_config()
            self._narrator_manager.sync()

    async def on_model_picker_app_model_selected(
        self, message: ModelPickerApp.ModelSelected
    ) -> None:
        VibeConfig.save_updates({"active_model": message.alias})
        await self._reload_config()
        await self._switch_to_input_app()

    async def on_model_picker_app_cancelled(
        self, _event: ModelPickerApp.Cancelled
    ) -> None:
        await self._switch_to_input_app()

    async def on_thinking_picker_app_thinking_selected(
        self, message: ThinkingPickerApp.ThinkingSelected
    ) -> None:
        # Thinking level not supported in core Settings
        await self._switch_to_input_app()

    async def on_thinking_picker_app_cancelled(
        self, _event: ThinkingPickerApp.Cancelled
    ) -> None:
        await self._switch_to_input_app()

    async def on_mcpapp_mcpclosed(self, _message: MCPApp.MCPClosed) -> None:
        await self._mount_and_scroll(UserCommandMessage("MCP servers closed."))
        await self._switch_to_input_app()

    async def on_mcpapp_mcptoggled(self, message: MCPApp.MCPToggled) -> None:
        persist_mcp_toggle(
            self.agent_loop.config,
            name=message.name,
            is_connector=message.kind == MCPSourceKind.CONNECTOR,
            disabled=message.disabled,
            tool_name=message.tool_name,
        )
        self.agent_loop.refresh_config()
        self.query_one(MCPApp).refresh_index()
        self._refresh_banner()

    async def on_mcpapp_connector_auth_requested(
        self, message: MCPApp.ConnectorAuthRequested
    ) -> None:
        await self._switch_to_input_app()
        await self._switch_from_input(
            ConnectorAuthApp(
                connector_name=message.connector_name,
                connector_registry=message.connector_registry,
                tool_manager=message.tool_manager,
            )
        )

    async def on_connector_auth_app_connector_auth_closed(
        self, message: ConnectorAuthApp.ConnectorAuthClosed
    ) -> None:
        if message.refreshed:
            await self.agent_loop.refresh_system_prompt()
            self._refresh_banner()
        await self._switch_to_input_app()
        await self._show_mcp(cmd_args=message.connector_name)

    async def on_proxy_setup_app_proxy_setup_closed(
        self, message: ProxySetupApp.ProxySetupClosed
    ) -> None:
        if message.error:
            await self._mount_and_scroll(
                ErrorMessage(f"Failed to save proxy settings: {message.error}")
            )
        elif message.saved:
            await self._mount_and_scroll(
                UserCommandMessage(
                    "Proxy settings saved. Restart the CLI for changes to take effect."
                )
            )
        else:
            await self._mount_and_scroll(UserCommandMessage("Proxy setup cancelled."))

        await self._switch_to_input_app()

    async def on_compact_message_completed(
        self, message: CompactMessage.Completed
    ) -> None:
        messages_area = self._cached_messages_area or self.query_one("#messages")
        children = list(messages_area.children)

        try:
            compact_index = children.index(message.compact_widget)
        except ValueError:
            return

        if compact_index == 0:
            return

        with self.batch_update():
            for widget in children[:compact_index]:
                await widget.remove()

    async def _handle_command(self, user_input: str) -> bool:
        """Handle slash commands."""
        try:
            if resolved := self.commands.parse_command(user_input):
                cmd_name, command, cmd_args = resolved
                self.agent_loop.telemetry_client.send_slash_command_used(
                    cmd_name, "builtin"
                )
                # Skip creating UserMessage for rewind - it's a UI action, not a chat message
                if cmd_name not in ("rewind", "rw"):
                    await self._mount_and_scroll(UserMessage(user_input))
                handler = getattr(self, command.handler, None)
                if handler is None:
                    self.notify(f"Handler {command.handler} not found!", severity="error")
                    return False
                if asyncio.iscoroutinefunction(handler):
                    result = await handler(cmd_args=cmd_args)
                else:
                    result = handler(cmd_args=cmd_args)
                # For rewind commands, don't switch back to input app
                if cmd_name in ("rewind", "rw"):
                    return "skip_input_switch"
                # Command was handled (even if handler returned None), return True
                return True
        except Exception as e:
            self.notify(f"Error in command handler: {e}", severity="error")
            import traceback
            traceback.print_exc()
        return False

    def _get_skill_entries(self) -> list[tuple[str, str]]:
        if not self.agent_loop:
            return []
        return [
            (f"/{name}", info.description)
            for name, info in self.agent_loop.skill_manager.available_skills.items()
            if info.user_invocable
        ]

    def _get_slash_argument_entries(
        self, command_alias: str, text_before_cursor: str
    ) -> list[tuple[str, str]]:
        resolved = self.commands.resolve_alias(command_alias)
        if resolved is None:
            return []

        cmd_name, _ = resolved
        if cmd_name == "profile":
            current = self.agent_loop.agent_manager.get_current_profile()
            return [
                (
                    profile,
                    "Current profile" if profile == current else "Switch to profile",
                )
                for profile in self.agent_loop.agent_manager.list_profiles()
            ]

        if cmd_name == "skills":
            args = text_before_cursor[len(command_alias):].strip()
            if not args or (
                len(args.split()) == 1 and not text_before_cursor.endswith(" ")
            ):
                return [("activate", "Activate a skill for the current session")]

            parts = args.split()
            if parts[0] != "activate":
                return []

            return [
                (name, info.description)
                for name, info in sorted(
                    self.agent_loop.skill_manager.available_skills.items()
                )
            ]

        if cmd_name == "themes":
            from interface.cli.config import load_config

            config_manager = load_config()
            return [
                (theme_name, "Switch to theme")
                for theme_name in sorted(config_manager.config.themes.keys())
            ]

        return []

    async def _handle_skill(self, user_input: str) -> bool:
        if not self.agent_loop:
            return False

        skill = self.agent_loop.skill_manager.parse_skill_command(user_input)

        if skill is None:
            return False

        self.agent_loop.telemetry_client.send_slash_command_used(skill.name, "skill")
        prompt = SkillManager.build_skill_prompt(user_input, skill)
        await self._handle_user_message(prompt)
        return True

    async def _handle_bash_command(self, command: str) -> None:
        if not command:
            await self._mount_and_scroll(
                ErrorMessage(
                    "No command provided after '!'", collapsed=self._tools_collapsed
                )
            )
            return

        try:
            result = subprocess.run(
                command, shell=True, capture_output=True, text=False, timeout=30
            )
            stdout = (
                result.stdout.decode("utf-8", errors="replace") if result.stdout else ""
            )
            stderr = (
                result.stderr.decode("utf-8", errors="replace") if result.stderr else ""
            )
            output = stdout or stderr or "(no output)"
            exit_code = result.returncode
            await self._mount_and_scroll(
                BashOutputMessage(command, str(Path.cwd()), output, exit_code)
            )
            await self.agent_loop.inject_user_context(
                self._format_manual_command_context(
                    command=command,
                    cwd=str(Path.cwd()),
                    exit_code=exit_code,
                    stdout=stdout,
                    stderr=stderr,
                )
            )
        except subprocess.TimeoutExpired as error:
            stdout = (
                error.stdout.decode("utf-8", errors="replace")
                if isinstance(error.stdout, bytes)
                else (error.stdout or "")
            )
            stderr = (
                error.stderr.decode("utf-8", errors="replace")
                if isinstance(error.stderr, bytes)
                else (error.stderr or "")
            )
            await self._mount_and_scroll(
                ErrorMessage(
                    "Command timed out after 30 seconds",
                    collapsed=self._tools_collapsed,
                )
            )
            await self.agent_loop.inject_user_context(
                self._format_manual_command_context(
                    command=command,
                    cwd=str(Path.cwd()),
                    stdout=stdout,
                    stderr=stderr,
                    status="timed out after 30 seconds",
                )
            )
        except Exception as e:
            await self._mount_and_scroll(
                ErrorMessage(f"Command failed: {e}", collapsed=self._tools_collapsed)
            )
            await self.agent_loop.inject_user_context(
                self._format_manual_command_context(
                    command=command,
                    cwd=str(Path.cwd()),
                    status=f"failed before completion: {e}",
                )
            )

    def _get_bash_max_output_bytes(self) -> int:
        from interface.textual_ui.cli_adapters import BashToolConfig

        config = self.agent_loop.tool_manager.get_tool_config("bash")
        if isinstance(config, BashToolConfig):
            return config.max_output_bytes
        return BashToolConfig().max_output_bytes

    @staticmethod
    def _cap_output(text: str, limit: int) -> str:
        if len(text) <= limit:
            return text
        return text[:limit] + "\n... [truncated]"

    def _format_manual_command_context(
        self,
        *,
        command: str,
        cwd: str,
        stdout: str = "",
        stderr: str = "",
        exit_code: int | None = None,
        status: str | None = None,
    ) -> str:
        limit = self._get_bash_max_output_bytes()
        stdout = self._cap_output(stdout, limit)
        stderr = self._cap_output(stderr, limit)

        sections = [
            "Manual `!` command result from the user. Use this as context only.",
            f"Command: `{command}`",
            f"Working directory: `{cwd}`",
        ]

        if status is not None:
            sections.append(f"Status: {status}")

        if exit_code is not None:
            sections.append(f"Exit code: {exit_code}")

        if stdout:
            sections.append(f"Stdout:\n```text\n{stdout.rstrip()}\n```")

        if stderr:
            sections.append(f"Stderr:\n```text\n{stderr.rstrip()}\n```")

        if not stdout and not stderr:
            sections.append("Output:\n```text\n(no output)\n```")

        return "\n\n".join(sections)

    async def _handle_user_message(self, message: str) -> None:
        if self._remote_manager.is_active:
            await self._handle_remote_user_message(message)
            return

        # message_index is where the user message will land in agent_loop.messages
        # (checkpoint is created in agent_loop.act())
        message_index = len(self.agent_loop.messages)
        user_message = UserMessage(message, message_index=message_index)

        await self._mount_and_scroll(user_message)
        if self._feedback_bar_manager.should_show(self.agent_loop):
            self._feedback_bar.show()
            self._feedback_bar_manager.record_feedback_asked()

        if not self._agent_running:
            await self._remote_manager.stop_stream()
            await self._remove_loading_widget()
            self._agent_task = asyncio.create_task(
                self._handle_agent_loop_turn(message)
            )

    async def _handle_remote_user_message(self, message: str) -> None:
        warning = self._remote_manager.validate_input()
        if warning:
            await self._mount_and_scroll(WarningMessage(warning))
            return
        try:
            await self._remote_manager.send_prompt(message)
        except Exception as e:
            await self._mount_and_scroll(
                ErrorMessage(
                    f"Failed to send message: {e}", collapsed=self._tools_collapsed
                )
            )
            return
        await self._ensure_loading_widget()

    async def _handle_remote_waiting_input(self, event: WaitingForInputEvent) -> None:
        self._remote_manager.set_pending_input(event)
        if question_args := self._remote_manager.build_question_args(event):
            await self._switch_to_question_app(question_args)
            return
        await self._switch_to_input_app()

    async def _handle_remote_answer(self, result: AskUserQuestionResult) -> None:
        if result.cancelled or not result.answers:
            self._remote_manager.cancel_pending_input()
            await self._switch_to_input_app()
            return
        await self._remote_manager.send_prompt(
            result.answers[0].answer, require_source=False
        )
        await self._switch_to_input_app()
        await self._ensure_loading_widget()

    def _reset_ui_state(self) -> None:
        self._windowing.reset()
        self._tool_call_map = None
        self._history_widget_indices = WeakKeyDictionary()

    async def _resume_history_from_messages(self) -> None:
        messages_area = self._cached_messages_area or self.query_one("#messages")
        if not should_resume_history(list(messages_area.children)):
            return

        history_messages = non_system_history_messages(self.agent_loop.messages)
        if (
            plan := create_resume_plan(history_messages, HISTORY_RESUME_TAIL_MESSAGES)
        ) is None:
            return
        await self._mount_history_batch(
            plan.tail_messages,
            messages_area,
            plan.tool_call_map,
            start_index=plan.tail_start_index,
        )
        chat = self._cached_chat or self.query_one("#chat", ChatScroll)
        self.call_after_refresh(chat.anchor)
        self._tool_call_map = plan.tool_call_map
        self._windowing.set_backfill(plan.backfill_messages)
        await self._load_more.set_visible(
            messages_area,
            visible=self._windowing.has_backfill,
            remaining=self._windowing.remaining,
        )

    async def _mount_history_batch(
        self,
        batch: list[LLMMessage],
        messages_area: Widget,
        tool_call_map: dict[str, str],
        *,
        start_index: int,
        before: Widget | int | None = None,
        after: Widget | None = None,
    ) -> None:
        widgets = build_history_widgets(
            batch=batch,
            tool_call_map=tool_call_map,
            start_index=start_index,
            tools_collapsed=self._tools_collapsed,
            history_widget_indices=self._history_widget_indices,
        )

        with self.batch_update():
            if not widgets:
                return
            if before is not None:
                await messages_area.mount_all(widgets, before=before)
            elif after is not None:
                await messages_area.mount_all(widgets, after=after)
            else:
                await messages_area.mount_all(widgets)

        for widget in widgets:
            if isinstance(widget, StreamingMessageBase):
                await widget.write_initial_content()

    def _is_tool_enabled_in_main_agent(self, tool: str) -> bool:
        return tool in self.agent_loop.tool_manager.available_tools

    async def _approval_callback(
        self,
        tool: str,
        args: BaseModel,
        tool_call_id: str,
        required_permissions: list[RequiredPermission] | None,
    ) -> tuple[ApprovalResponse, str | None]:
        # Auto-approve only if parent is in auto-approve mode AND tool is enabled
        # This ensures subagents respect the main agent's tool restrictions
        if self.agent_loop and self.agent_loop.config.bypass_tool_permissions:
            if self._is_tool_enabled_in_main_agent(tool):
                return (ApprovalResponse.YES, None)

        async with self._user_interaction_lock:
            self._pending_approval = asyncio.Future()
            self._terminal_notifier.notify(NotificationContext.ACTION_REQUIRED)
            try:
                with paused_timer(self._loading_widget):
                    await self._switch_to_approval_app(tool, args, required_permissions)
                    result = await self._pending_approval
                return result
            finally:
                self._pending_approval = None
                # Only switch back if not already on input app (handlers now switch immediately)
                if self._current_bottom_app != BottomApp.Input:
                    await self._switch_to_input_app()

    async def _user_input_callback(self, args: BaseModel) -> BaseModel:
        question_args = cast(AskUserQuestionArgs, args)

        async with self._user_interaction_lock:
            self._pending_question = asyncio.Future()
            self._terminal_notifier.notify(NotificationContext.ACTION_REQUIRED)
            try:
                with paused_timer(self._loading_widget):
                    await self._switch_to_question_app(question_args)
                    result = await self._pending_question
                return result
            finally:
                self._pending_question = None
                # Only switch back if not already on input app (handlers now switch immediately)
                if self._current_bottom_app != BottomApp.Input:
                    await self._switch_to_input_app()

    async def _handle_turn_error(self) -> None:
        if self._loading_widget and self._loading_widget.parent:
            await self._loading_widget.remove()
        if self.event_handler:
            self.event_handler.stop_current_tool_call(success=False)

    async def _handle_agent_loop_init(self) -> None:
        show_init_spinner = not self.agent_loop.is_initialized
        if show_init_spinner:
            await self._ensure_loading_widget("Initializing", show_hint=False)
        await self.agent_loop.wait_until_ready()
        if show_init_spinner:
            await self._remove_loading_widget()
            self._refresh_banner()

    async def _handle_agent_loop_events(
        self, events: AsyncGenerator[BaseEvent]
    ) -> None:
        async for event in events:
            self._narrator_manager.on_turn_event(event)
            if isinstance(event, WaitingForInputEvent):
                await self._remove_loading_widget()
                if self._remote_manager.is_active:
                    await self._handle_remote_waiting_input(event)
            elif isinstance(event, HookStartEvent):
                await self._ensure_loading_widget(f"Running hook {event.hook_name}")
            elif self._loading_widget is None and is_progress_event(event):
                await self._ensure_loading_widget()
            if self.event_handler:
                await self.event_handler.handle_event(
                    event, loading_widget=self._loading_widget
                )

    async def _handle_agent_loop_turn(self, prompt: str) -> None:
        self._agent_running = True

        await self._remove_loading_widget()

        try:
            await self._handle_agent_loop_init()
            await self._ensure_loading_widget()
            rendered_prompt = render_path_prompt(prompt, base_dir=Path.cwd())
            self._narrator_manager.cancel()
            self._narrator_manager.on_turn_start(rendered_prompt)
            
            # DEBUG: Verify agent_loop.act is being called
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"[DEBUG] _handle_agent_loop_turn called with prompt: {prompt[:50]}")
            
            async with aclosing(self.agent_loop.act(rendered_prompt)) as events:
                await self._handle_agent_loop_events(events)
        except asyncio.CancelledError:
            await self._handle_turn_error()
            self._narrator_manager.on_turn_cancel()
            raise
        except Exception as e:
            await self._handle_turn_error()

            # _watch_init_completion already rendered the fatal startup error
            # and told the user to exit -- don't duplicate the message.
            if self._fatal_init_error:
                return

            message = self._resolve_turn_error_message(e)
            self._narrator_manager.on_turn_error(message)

            await self._mount_and_scroll(
                ErrorMessage(message, collapsed=self._tools_collapsed)
            )
        finally:
            self._narrator_manager.on_turn_end()
            self._agent_running = False
            self._interrupt_requested = False
            self._agent_task = None
            if self._loading_widget:
                await self._loading_widget.remove()
            self._loading_widget = None
            if self.event_handler:
                await self.event_handler.finalize_streaming()
            await self._refresh_windowing_from_history()
            self._terminal_notifier.notify(NotificationContext.COMPLETE)

    def _resolve_turn_error_message(self, e: Exception) -> str:
        if isinstance(e, RateLimitError):
            return self._rate_limit_message()
        if isinstance(e, ContextTooLongError):
            return self._context_too_long_message()
        return str(e)

    def _rate_limit_message(self) -> str:
        upgrade_to_pro = self._plan_info and (
            self._plan_info.plan_type
            in {WhoAmIPlanType.API, WhoAmIPlanType.UNAUTHORIZED}
            or self._plan_info.is_free_mistral_code_plan_method()
        )
        if upgrade_to_pro:
            return "Rate limits exceeded. Please wait a moment before trying again, or upgrade to Pro for higher rate limits and uninterrupted access."
        return "Rate limits exceeded. Please wait a moment before trying again."

    def _context_too_long_message(self) -> str:
        return (
            "The conversation context exceeds the model's maximum limit. "
            "The last messages and output of agent actions went above the allowed size.\n\n"
            "To recover:\n"
            "1. Use /rewind to undo recent messages and tool outputs\n"
            "2. Then use /compact to summarize the remaining conversation\n\n"
            "This will free up context space so you can continue working."
        )

    async def _teleport_command(self, **kwargs: Any) -> None:
        await self._handle_teleport_command(show_message=False)

    async def _handle_teleport_command(
        self, value: str | None = None, show_message: bool = True
    ) -> None:
        has_history = any(msg.role != Role.system for msg in self.agent_loop.messages)
        if not value:
            if show_message:
                await self._mount_and_scroll(UserMessage("/teleport"))
            if not has_history:
                await self._mount_and_scroll(
                    ErrorMessage(
                        "No conversation history to teleport.",
                        collapsed=self._tools_collapsed,
                    )
                )
                return
        elif show_message:
            await self._mount_and_scroll(UserMessage(value))
        self.run_worker(self._teleport(value), exclusive=False)

    async def _teleport(self, prompt: str | None = None) -> None:
        loading_area = self._cached_loading_area or self.query_one(
            "#loading-area-content"
        )
        loading = LoadingWidget()
        await loading_area.mount(loading)

        teleport_msg = TeleportMessage()
        await self._mount_and_scroll(teleport_msg)

        if self._remote_manager.is_active:
            await loading.remove()
            await self._mount_and_scroll(
                ErrorMessage(
                    "Teleport is not available for remote sessions.",
                    collapsed=self._tools_collapsed,
                )
            )
            return

        try:
            gen = self.agent_loop.teleport_to_vibe_code(prompt)
            async for event in gen:
                match event:
                    case TeleportCheckingGitEvent():
                        teleport_msg.set_status("Preparing workspace...")
                    case TeleportPushRequiredEvent(
                        unpushed_count=count, branch_not_pushed=branch_not_pushed
                    ):
                        await loading.remove()
                        response = await self._ask_push_approval(
                            count, branch_not_pushed
                        )
                        await loading_area.mount(loading)
                        teleport_msg.set_status("Teleporting...")
                        next_event = await gen.asend(response)  # type: ignore
                        if isinstance(next_event, TeleportPushingEvent):
                            teleport_msg.set_status("Syncing with remote...")
                    case TeleportPushingEvent():
                        teleport_msg.set_status("Syncing with remote...")
                    case TeleportStartingWorkflowEvent():
                        teleport_msg.set_status("Teleporting...")
                    case TeleportWaitingForGitHubEvent(message=msg):
                        teleport_msg.set_status(msg or "Connecting to GitHub...")
                    case TeleportAuthRequiredEvent(oauth_url=url, message=msg):
                        webbrowser.open(url)
                        teleport_msg.set_status(msg or "Authorizing GitHub...")
                    case TeleportAuthCompleteEvent():
                        teleport_msg.set_status("GitHub authorized")
                    case TeleportFetchingUrlEvent():
                        teleport_msg.set_status("Finalizing...")
                    case TeleportCompleteEvent(url=url):
                        teleport_msg.set_complete(url)
        except TeleportError as e:
            await teleport_msg.remove()
            await self._mount_and_scroll(
                ErrorMessage(str(e), collapsed=self._tools_collapsed)
            )
        finally:
            if loading.parent:
                await loading.remove()

    async def _ask_push_approval(
        self, count: int, branch_not_pushed: bool
    ) -> TeleportPushResponseEvent:
        if branch_not_pushed:
            question = "Your branch doesn't exist on remote. Push to continue?"
        else:
            word = f"commit{'s' if count != 1 else ''}"
            question = f"You have {count} unpushed {word}. Push to continue?"
        push_label = "Push and continue"
        result = await self._user_input_callback(
            AskUserQuestionArgs(
                questions=[
                    Question(
                        question=question,
                        header="Push",
                        options=[Choice(label=push_label), Choice(label="Cancel")],
                        hide_other=True,
                    )
                ]
            )
        )
        ok = (
            isinstance(result, AskUserQuestionResult)
            and not result.cancelled
            and bool(result.answers)
            and result.answers[0].answer == push_label
        )
        return TeleportPushResponseEvent(approved=ok)

    async def _interrupt_agent_loop(self) -> None:
        if not self._agent_running or self._interrupt_requested:
            return

        self._interrupt_requested = True

        if self._pending_approval and not self._pending_approval.done():
            feedback = str(
                get_user_cancellation_message(CancellationReason.TOOL_INTERRUPTED)
            )
            self._pending_approval.set_result((ApprovalResponse.NO, feedback))
        if self._pending_question and not self._pending_question.done():
            self._pending_question.set_result(
                AskUserQuestionResult(answers=[], cancelled=True)
            )

        if self._agent_task and not self._agent_task.done():
            self._agent_task.cancel()
            try:
                await self._agent_task
            except asyncio.CancelledError:
                pass

        if self.event_handler:
            self.event_handler.stop_current_tool_call(success=False)
            self.event_handler.stop_current_compact()
            await self.event_handler.finalize_streaming()

        self._agent_running = False
        loading_area = self._cached_loading_area or self.query_one(
            "#loading-area-content"
        )
        await loading_area.remove_children()
        self._loading_widget = None

        await self._mount_and_scroll(InterruptMessage())

        self._interrupt_requested = False

    async def _show_help(self, **kwargs: Any) -> None:
        help_text = self.commands.get_help_text()
        await self._mount_and_scroll(UserCommandMessage(help_text))

    async def _show_tools(self, **kwargs: Any) -> None:
        tools = self.agent_loop.tool_manager.tool_registry.get_tools()
        tool_list = "\n".join(f"  - {name}" for name in sorted(tools.keys()))
        await self._mount_and_scroll(UserCommandMessage(f"Available tools:\n{tool_list}"))

    async def _show_skills(self, cmd_args: str = "", **kwargs: Any) -> None:
        if cmd_args:
            parts = cmd_args.strip().split()
            if parts and parts[0] == "activate" and len(parts) > 1:
                skill_name = parts[1]
                success, message, content = (
                    self.agent_loop.skill_manager.activate_skill(skill_name)
                )
                if success:
                    preview = ""
                    if content:
                        preview_text = (
                            content[:400] + "..." if len(content) > 400 else content
                        )
                        preview = f"\n\n{preview_text}"
                    await self._mount_and_scroll(
                        UserCommandMessage(f"{message}{preview}")
                    )
                else:
                    await self._mount_and_scroll(UserCommandMessage(message))
                return

        skills = self.agent_loop.skill_manager.available_skills
        skill_list = "\n".join(f"  - {name}: {info.description}" for name, info in sorted(skills.items()))
        await self._mount_and_scroll(UserCommandMessage(f"Available skills:\n{skill_list}"))

    async def _switch_to_profile_app(self, cmd_args: str = "", **kwargs: Any) -> None:
        profile_name = cmd_args.strip()
        if not profile_name:
            profiles = self.agent_loop.agent_manager.list_profiles()
            current = self.agent_loop.agent_manager.get_current_profile()
            lines = ["Available profiles:"]
            lines.extend(
                f"  - {name}{' (current)' if name == current else ''}"
                for name in profiles
            )
            await self._mount_and_scroll(UserCommandMessage("\n".join(lines)))
            return

        try:
            await self.agent_loop.switch_agent(profile_name)
            self._refresh_profile_widgets()
            await self._mount_and_scroll(
                UserCommandMessage(f"Switched to profile: {profile_name}")
            )
        except Exception as e:
            await self._mount_and_scroll(
                ErrorMessage(str(e), collapsed=self._tools_collapsed)
            )

    def _get_last_assistant_message_text(self) -> str | None:
        messages_area = self._cached_messages_area or self.query_one("#messages")
        for child in reversed(messages_area.children):
            if not isinstance(child, AssistantMessage):
                continue
            if not (content := child.get_content().strip()):
                continue
            return content
        return None

    async def _copy_last_agent_message(self, **kwargs: Any) -> None:
        if (content := self._get_last_assistant_message_text()) is None:
            self.notify(
                "No agent message available to copy", severity="warning", timeout=3
            )
            return

        copied_text = copy_text_to_clipboard(
            self, content, success_message="Last agent message copied to clipboard"
        )
        if copied_text:
            self.agent_loop.telemetry_client.send_user_copied_text(content)


    async def _refresh_mcp_browser(self) -> str:
        await self.agent_loop.tool_manager.refresh_remote_tools_async()
        await self.agent_loop.refresh_system_prompt()
        self._refresh_banner()
        return "Refreshed."

    async def _show_mcp(self, cmd_args: str = "", **kwargs: Any) -> None:
        mcp_servers = []  # Not supported in core Settings
        connector_registry = (
            self.agent_loop.connector_registry if self._connectors_enabled else None
        )
        has_connectors = (
            connector_registry is not None and connector_registry.connector_count > 0
        )
        if not mcp_servers and not has_connectors:
            msg = (
                "No MCP servers or connectors configured."
                if self._connectors_enabled
                else "No MCP servers configured."
            )
            await self._mount_and_scroll(UserCommandMessage(msg))
            return

        if self._current_bottom_app == BottomApp.MCP:
            return
        name = cmd_args.strip()
        connector_names = (
            connector_registry.get_connector_names() if connector_registry else []
        )
        if (
            name
            and not any(s.name == name for s in mcp_servers)
            and name not in connector_names
        ):
            all_names = [s.name for s in mcp_servers] + connector_names
            entity = "MCP server or connector" if has_connectors else "MCP server"
            await self._mount_and_scroll(
                ErrorMessage(
                    f"Unknown {entity}: {name}. Known: " + ", ".join(all_names),
                    collapsed=self._tools_collapsed,
                )
            )
            return
        await self._mount_and_scroll(UserCommandMessage("MCP servers opened..."))
        await self._switch_from_input(
            MCPApp(
                mcp_servers=mcp_servers,
                tool_manager=self.agent_loop.tool_manager,
                initial_server=name,
                connector_registry=connector_registry,  # type: ignore
                get_connector_configs=lambda: self.agent_loop.config.connectors,
                refresh_callback=self._refresh_mcp_browser,
            )
        )

    async def _show_status(self, **kwargs: Any) -> None:
        stats = self.agent_loop.stats
        status_text = f"""## Agent Statistics

- **Steps**: {stats.steps:,}
- **Session Prompt Tokens**: {stats.session_prompt_tokens:,}
- **Session Completion Tokens**: {stats.session_completion_tokens:,}
- **Session Total LLM Tokens**: {stats.session_total_llm_tokens:,}
- **Last Turn Tokens**: {stats.last_turn_total_tokens:,}
- **Cost**: ${stats.session_cost:.4f}
"""
        await self._mount_and_scroll(UserCommandMessage(status_text))

    async def _show_themes(self, cmd_args: str = "", **kwargs: Any) -> None:
        """Show available themes and allow switching."""
        from interface.cli.config import load_config
        config_manager = load_config()
        current_theme = config_manager.config.display.theme

        if not cmd_args:
            # List available themes
            theme_lines = ["## Available Themes\n"]
            for theme_name in config_manager.config.themes.keys():
                marker = "**" if theme_name == current_theme else ""
                theme_lines.append(f"- {marker}{theme_name}{marker}")
            await self._mount_and_scroll(UserCommandMessage("\n".join(theme_lines)))
        else:
            # Switch theme
            parts = cmd_args.strip().split()
            if parts and parts[0] in config_manager.config.themes:
                theme_name = parts[0]
                config_manager.set_theme(theme_name)
                config_manager.save_config()
                await self._mount_and_scroll(
                    UserCommandMessage(f"Theme switched to: {theme_name}")
                )
            else:
                themes = ", ".join(config_manager.config.themes.keys())
                await self._mount_and_scroll(
                    UserCommandMessage(f"Unknown theme. Available: {themes}")
                )

    async def _show_config(self, **kwargs: Any) -> None:
        """Switch to the configuration app in the bottom panel."""
        if self._current_bottom_app == BottomApp.Config:
            return
        await self._switch_to_config_app()

    async def _show_model(self, **kwargs: Any) -> None:
        """Switch to the model picker in the bottom panel."""
        if self._current_bottom_app == BottomApp.ModelPicker:
            return
        await self._switch_to_model_picker_app()

    async def _show_thinking(self, **kwargs: Any) -> None:
        """Switch to the thinking level picker in the bottom panel."""
        if self._current_bottom_app == BottomApp.ThinkingPicker:
            return
        await self._switch_to_thinking_picker_app()

    async def _show_proxy_setup(self, **kwargs: Any) -> None:
        if self._current_bottom_app == BottomApp.ProxySetup:
            return
        await self._switch_to_proxy_setup_app()

    async def _show_data_retention(self, **kwargs: Any) -> None:
        await self._mount_and_scroll(UserCommandMessage(DATA_RETENTION_MESSAGE))

    async def _show_session_picker(self, **kwargs: Any) -> None:
        cwd = str(Path.cwd())
        local_sessions = []  # Session logging not supported in core Settings
        remote_list_timeout = 30.0  # Default timeout
        remote_error: str | None = None
        await self._ensure_loading_widget("Loading sessions")
        try:
            remote_sessions = await asyncio.wait_for(
                list_remote_resume_sessions(self.config), timeout=remote_list_timeout
            )
        except TimeoutError:
            remote_sessions = []
            remote_error = (
                "Timed out while listing remote sessions "
                f"after {remote_list_timeout:.0f}s."
            )
        except Exception as e:
            remote_sessions = []
            remote_error = f"Failed to list remote sessions: {e}"
        finally:
            await self._remove_loading_widget()

        if remote_error is not None:
            await self._mount_and_scroll(
                ErrorMessage(remote_error, collapsed=self._tools_collapsed)
            )

        raw_sessions = [*local_sessions, *remote_sessions]

        if not raw_sessions:
            await self._mount_and_scroll(
                UserCommandMessage("No sessions found for this directory.")
            )
            return

        sessions = sorted(raw_sessions, key=lambda s: s.end_time or "", reverse=True)

        latest_messages = {}  # Session logging not supported in core Settings
        for session in sessions:
            if session.source == "remote":
                latest_messages[session.option_id] = (
                    f"{session.title or 'Remote workflow'} ({(session.status or 'RUNNING').lower()})"
                )

        picker = SessionPickerApp(sessions=sessions, latest_messages=latest_messages)
        await self._switch_from_input(picker)

    async def on_session_picker_app_session_selected(
        self, event: SessionPickerApp.SessionSelected
    ) -> None:
        await self._switch_to_input_app()
        session = ResumeSessionInfo(
            session_id=event.session_id,
            source=event.source,
            option_id=event.option_id,
            title=None,
            status=None,
        )
        try:
            if event.source == "local":
                await self._resume_local_session(session)
            elif event.source == "remote":
                await self._resume_remote_session(session)
            else:
                raise ValueError(f"Unknown session source: {event.source}")
        except Exception as e:
            await self._mount_and_scroll(
                ErrorMessage(
                    f"Failed to load session: {e}", collapsed=self._tools_collapsed
                )
            )

    async def on_session_picker_app_cancelled(
        self, event: SessionPickerApp.Cancelled
    ) -> None:
        await self._switch_to_input_app()

        await self._mount_and_scroll(UserCommandMessage("Resume cancelled."))

    async def _resume_local_session(self, session: ResumeSessionInfo) -> None:
        await self._remote_manager.detach()
        # Session logging not supported in core Settings
        session_path = None

        if not session_path:
            raise ValueError(
                f"Session `{short_session_id(session.session_id)}` not found."
            )

        loaded_messages, metadata = SessionLoader.load_session(session_path)
        if self._chat_input_container:
            self._chat_input_container.set_custom_border(None)

        current_system_messages = [
            msg for msg in self.agent_loop.messages if msg.role == Role.system
        ]
        non_system_messages = [
            msg for msg in loaded_messages if msg.role != Role.system
        ]

        self.agent_loop.session_id = session.session_id
        self.agent_loop.parent_session_id = metadata.get("parent_session_id")
        self.agent_loop.session_logger.resume_existing_session(
            session.session_id, session_path
        )
        self.agent_loop.messages.reset(current_system_messages + non_system_messages)
        self._refresh_profile_widgets()

        self._reset_ui_state()
        await self._load_more.hide()

        messages_area = self._cached_messages_area or self.query_one("#messages")
        await messages_area.remove_children()

        if self.event_handler:
            self.event_handler.is_remote = False
        await self._resume_history_from_messages()
        await self._mount_and_scroll(
            UserCommandMessage(
                f"Resumed session `{short_session_id(session.session_id)}`"
            )
        )

    async def _resume_remote_session(self, session: ResumeSessionInfo) -> None:
        await self._remote_manager.attach(
            session_id=session.session_id, config=self.config
        )
        self._refresh_profile_widgets()
        if self._chat_input_container:
            self._chat_input_container.set_custom_border(None)

        self._reset_ui_state()
        await self._load_more.hide()

        messages_area = self._cached_messages_area or self.query_one("#messages")
        await messages_area.remove_children()

        if self.event_handler:
            self.event_handler.is_remote = True
        self._remote_manager.start_stream(self)

    async def on_remote_event(self, event: BaseEvent, loading_widget: Any) -> None:
        if self.event_handler:
            await self.event_handler.handle_event(event, loading_widget=loading_widget)

    async def on_remote_waiting_input(self, event: WaitingForInputEvent) -> None:
        await self._handle_remote_waiting_input(event)

    async def on_remote_user_message_cleared_input(self) -> None:
        await self._switch_to_input_app()

    async def on_remote_stream_error(self, error: str) -> None:
        await self._mount_and_scroll(
            ErrorMessage(error, collapsed=self._tools_collapsed)
        )

    async def on_remote_stream_ended(self, msg_type: str, text: str) -> None:
        if msg_type == "error":
            widget = ErrorMessage(text, collapsed=self._tools_collapsed)
        elif msg_type == "warning":
            widget = WarningMessage(text)
        else:
            widget = UserCommandMessage(text)
        await self._mount_and_scroll(widget)
        if self._chat_input_container:
            self._chat_input_container.set_custom_border("Remote session ended")

    async def on_remote_finalize_streaming(self) -> None:
        if self.event_handler:
            await self.event_handler.finalize_streaming()

    async def remove_loading(self) -> None:
        await self._remove_loading_widget()

    async def ensure_loading(self, status: str = DEFAULT_LOADING_STATUS) -> None:
        await self._ensure_loading_widget(status)

    @property
    def loading_widget(self) -> LoadingWidget | None:
        return self._loading_widget

    async def _reload_config(self, **kwargs: Any) -> None:
        try:
            self._reset_ui_state()
            await self._load_more.hide()
            base_config = VibeConfig.load()

            await self.agent_loop.reload_with_initial_messages(base_config=base_config)  # type: ignore
            await self._resolve_plan()
            self._narrator_manager.sync()

            if self._banner:
                self._banner.set_state(
                    base_config,  # type: ignore
                    self.agent_loop.skill_manager,
                    model=self.agent_loop.agent.model,
                )
            await self._mount_and_scroll(
                UserCommandMessage(
                    "Configuration reloaded (includes agent instructions and skills)."
                )
            )
        except Exception as e:
            await self._mount_and_scroll(
                ErrorMessage(
                    f"Failed to reload config: {e}", collapsed=self._tools_collapsed
                )
            )

    async def _install_lean(self, **kwargs: Any) -> None:
        current = list(self.agent_loop.base_config.installed_agents)
        if "lean" in current:
            await self._mount_and_scroll(
                UserCommandMessage("Lean agent is already installed.")
            )
            return
        VibeConfig.save_updates({"installed_agents": sorted([*current, "lean"])})
        await self._reload_config()

    async def _uninstall_lean(self, **kwargs: Any) -> None:
        current = list(self.agent_loop.base_config.installed_agents)
        if "lean" not in current:
            await self._mount_and_scroll(
                UserCommandMessage("Lean agent is not installed.")
            )
            return
        VibeConfig.save_updates({
            "installed_agents": [a for a in current if a != "lean"]
        })
        await self._reload_config()

    async def _clear_history(self, **kwargs: Any) -> None:
        try:
            self._reset_ui_state()
            if self._remote_manager.is_active:
                await self._remote_manager.detach()
                self._refresh_profile_widgets()
                if self.event_handler:
                    self.event_handler.is_remote = False
            if self._chat_input_container:
                self._chat_input_container.set_custom_border(None)
            await self.agent_loop.clear_history()
            if self.event_handler:
                await self.event_handler.finalize_streaming()
            messages_area = self._cached_messages_area or self.query_one("#messages")
            await messages_area.remove_children()

            await messages_area.mount(UserMessage("/clear"))
            await self._mount_and_scroll(
                UserCommandMessage("Conversation history cleared!")
            )
            chat = self._cached_chat or self.query_one("#chat", ChatScroll)
            chat.scroll_home(animate=False)

        except Exception as e:
            await self._mount_and_scroll(
                ErrorMessage(
                    f"Failed to clear history: {e}", collapsed=self._tools_collapsed
                )
            )

    async def _show_log_path(self, **kwargs: Any) -> None:
        if not self.agent_loop.session_logger.enabled:
            await self._mount_and_scroll(
                ErrorMessage(
                    "Session logging is disabled in configuration.",
                    collapsed=self._tools_collapsed,
                )
            )
            return

        try:
            log_path = str(self.agent_loop.session_logger.session_dir)
            await self._mount_and_scroll(
                UserCommandMessage(
                    f"## Current Log Directory\n\n`{log_path}`\n\nYou can send this directory to share your interaction."
                )
            )
        except Exception as e:
            await self._mount_and_scroll(
                ErrorMessage(
                    f"Failed to get log path: {e}", collapsed=self._tools_collapsed
                )
            )

    async def _compact_history(self, cmd_args: str = "", auto_triggered: bool = False, **kwargs: Any) -> None:
        if self._agent_running:
            await self._mount_and_scroll(
                ErrorMessage(
                    "Cannot compact while agent loop is processing. Please wait.",
                    collapsed=self._tools_collapsed,
                )
            )
            return

        if len(self.agent_loop.messages) <= 1:
            await self._mount_and_scroll(
                ErrorMessage(
                    "No conversation history to compact yet.",
                    collapsed=self._tools_collapsed,
                )
            )
            return

        if not self.event_handler:
            return

        old_tokens = self.agent_loop.stats.context_tokens
        compact_msg = CompactMessage(auto_triggered=auto_triggered)
        self.event_handler.current_compact = compact_msg
        await self._mount_and_scroll(compact_msg)

        self._agent_task = asyncio.create_task(
            self._run_compact(compact_msg, old_tokens, cmd_args.strip(), auto_triggered=auto_triggered)
        )

    async def _run_compact(
        self, compact_msg: CompactMessage, old_tokens: int, extra_instructions: str = "",
        auto_triggered: bool = False
    ) -> None:
        self._agent_running = True
        try:
            result = await self.agent_loop.compact(
                extra_instructions=extra_instructions,
                auto_triggered=auto_triggered
            )
            new_tokens = self.agent_loop.stats.context_tokens
            compact_msg.set_complete(
                old_tokens=old_tokens,
                new_tokens=new_tokens,
                auto_triggered=auto_triggered
            )
            if auto_triggered:
                self.notify(
                    f"Auto-compacted: {old_tokens - new_tokens} tokens saved",
                    title="Auto-Compaction",
                    severity="information"
                )

        except asyncio.CancelledError:
            compact_msg.set_error("Compaction interrupted")
            raise
        except Exception as e:
            compact_msg.set_error(str(e))
        finally:
            self._agent_running = False
            self._agent_task = None
            if self.event_handler:
                self.event_handler.current_compact = None

    def action_compact(self, extra_instructions: str = "") -> None:
        """Manually trigger compaction."""
        if self._agent_running:
            self.notify("Cannot compact while agent is running", title="Compaction", severity="warning")
            return
        self._agent_loop._ = asyncio.create_task(self._compact_history(extra_instructions))  # type: ignore

    def _get_session_resume_info(self) -> str | None:
        if self._remote_manager.is_active:
            return None
        if not self.agent_loop.session_logger.enabled:
            return None
        if not self.agent_loop.session_logger.session_id:
            return None
        session_config = self.agent_loop.session_logger.session_config
        session_path = SessionLoader.does_session_exist(
            self.agent_loop.session_logger.session_id, session_config
        )
        if session_path is None:
            return None
        return short_session_id(self.agent_loop.session_logger.session_id)

    async def _exit_app(self, **kwargs: Any) -> None:
        self._log_reader.shutdown()
        await self._narrator_manager.close()
        self.exit(result=self._get_session_resume_info())

    def _make_default_voice_manager(self) -> VoiceManager:
        # Simplified voice manager without transcription support
        transcribe_client = None

        return VoiceManager(
            lambda: self.config,
            audio_recorder=AudioRecorder(),
            transcribe_client=transcribe_client,
            telemetry_client=self.agent_loop.telemetry_client,
        )

    async def _show_voice_settings(self, **kwargs: Any) -> None:
        # Voice settings not supported in core Settings
        await self._mount_and_scroll(UserCommandMessage("Voice settings not available."))

    async def _switch_from_input(self, widget: Widget, scroll: bool = False) -> None:
        bottom_container = self.query_one("#bottom-app-container")
        chat = self._cached_chat or self.query_one("#chat", ChatScroll)
        should_scroll = scroll and chat.is_at_bottom

        if self._chat_input_container:
            self._chat_input_container.display = False
            self._chat_input_container.disabled = True

        self._feedback_bar.hide()

        await self._cleanup_bottom_apps()

        self._current_bottom_app = BottomApp[type(widget).__name__.removesuffix("App")]
        await bottom_container.mount(widget)

        self.call_after_refresh(widget.focus)
        if should_scroll:
            self.call_after_refresh(chat.anchor)

    async def _switch_to_config_app(self) -> None:
        if self._current_bottom_app == BottomApp.Config:
            return

        await self._mount_and_scroll(UserCommandMessage("Configuration opened..."))
        await self._switch_from_input(ConfigApp(self.config))

    async def _switch_to_voice_app(self) -> None:
        # Voice settings not supported in core Settings
        await self._mount_and_scroll(UserCommandMessage("Voice settings not available."))

    async def _switch_to_model_picker_app(self) -> None:
        if self._current_bottom_app == BottomApp.ModelPicker:
            return

        # Model picker not supported in core Settings - show actual model from agent
        current_model = self.agent_loop.agent.model
        await self._switch_from_input(
            ModelPickerApp(model_aliases=[current_model], current_model=current_model)
        )

    async def _switch_to_thinking_picker_app(self) -> None:
        if self._current_bottom_app == BottomApp.ThinkingPicker:
            return

        from interface.textual_ui.cli_adapters import THINKING_LEVELS

        # Thinking picker not supported in core Settings
        await self._switch_from_input(
            ThinkingPickerApp(
                THINKING_LEVELS, "medium",  # type: ignore
            )
        )

    async def _switch_to_proxy_setup_app(self) -> None:
        if self._current_bottom_app == BottomApp.ProxySetup:
            return

        await self._mount_and_scroll(UserCommandMessage("Proxy setup opened..."))
        await self._switch_from_input(ProxySetupApp())

    async def _switch_to_approval_app(
        self,
        tool_name: str,
        tool_args: BaseModel,
        required_permissions: list[RequiredPermission] | None = None,
    ) -> None:
        approval_app = ApprovalApp(
            tool_name=tool_name,
            tool_args=tool_args,
            config=self.config,
            required_permissions=required_permissions,
        )
        await self._switch_from_input(approval_app, scroll=True)

    async def _switch_to_question_app(self, args: AskUserQuestionArgs) -> None:
        await self._switch_from_input(QuestionApp(args=args), scroll=True)

    async def _switch_to_input_app(self) -> None:
        if self._chat_input_container:
            self._chat_input_container.disabled = False
            self._chat_input_container.display = True
            self._current_bottom_app = BottomApp.Input
            self._refresh_profile_widgets()

        await self._cleanup_bottom_apps()

        if self._chat_input_container:
            self.call_after_refresh(self._chat_input_container.focus_input)
            chat = self._cached_chat or self.query_one("#chat", ChatScroll)
            if chat.is_at_bottom:
                self.call_after_refresh(chat.anchor)

    async def _cleanup_bottom_apps(self) -> None:
        """Remove all bottom panel apps except the input container."""
        for app in BottomApp:
            if app != BottomApp.Input:
                try:
                    await self.query_one(f"#{app.value.lower()}-app").remove()
                except Exception:
                    pass

    def _focus_current_bottom_app(self) -> None:
        try:
            match self._current_bottom_app:
                case BottomApp.Input:
                    self.query_one(ChatInputContainer).focus_input()
                case BottomApp.Config:
                    self.query_one(ConfigApp).focus()
                case BottomApp.ModelPicker:
                    self.query_one(ModelPickerApp).focus()
                case BottomApp.ThinkingPicker:
                    self.query_one(ThinkingPickerApp).focus()
                case BottomApp.ProxySetup:
                    self.query_one(ProxySetupApp).focus()
                case BottomApp.Approval:
                    self.query_one(ApprovalApp).focus()
                case BottomApp.Question:
                    self.query_one(QuestionApp).focus()
                case BottomApp.SessionPicker:
                    self.query_one(SessionPickerApp).focus()
                case BottomApp.MCP:
                    self.query_one(MCPApp).focus()
                case BottomApp.ConnectorAuth:
                    self.query_one(ConnectorAuthApp).focus()
                case BottomApp.Rewind:
                    self.query_one(RewindApp).focus()
                # case BottomApp.Voice:  # Not supported in core Settings
                #     self.query_one(VoiceApp).focus()
                case app:
                    assert_never(app)
        except Exception:
            pass

    def _handle_config_app_escape(self) -> None:
        try:
            config_app = self.query_one(ConfigApp)
            config_app.action_close()
        except Exception:
            pass
        self._last_escape_time = None

    # def _handle_voice_app_escape(self) -> None:
    #     try:
    #         voice_app = self.query_one(VoiceApp)
    #         voice_app.action_close()
    #     except Exception:
    #         pass

    def _handle_approval_app_escape(self) -> None:
        try:
            approval_app = self.query_one(ApprovalApp)
            approval_app.action_reject()
        except Exception:
            pass
        self.agent_loop.telemetry_client.send_user_cancelled_action("reject_approval")
        self._last_escape_time = None

    def _handle_question_app_escape(self) -> None:
        try:
            question_app = self.query_one(QuestionApp)
            question_app.action_cancel()
        except Exception:
            pass
        self.agent_loop.telemetry_client.send_user_cancelled_action("cancel_question")
        self._last_escape_time = None

    def _handle_model_picker_app_escape(self) -> None:
        try:
            model_picker = self.query_one(ModelPickerApp)
            model_picker.post_message(ModelPickerApp.Cancelled())
        except Exception:
            pass
        self._last_escape_time = None

    def _handle_thinking_picker_app_escape(self) -> None:
        try:
            thinking_picker = self.query_one(ThinkingPickerApp)
            thinking_picker.post_message(ThinkingPickerApp.Cancelled())
        except Exception:
            pass
        self._last_escape_time = None

    def _handle_session_picker_app_escape(self) -> None:
        try:
            session_picker = self.query_one(SessionPickerApp)
            session_picker.post_message(SessionPickerApp.Cancelled())
        except Exception:
            pass
        self._last_escape_time = None

    # --- Rewind mode ---

    def _get_user_message_widgets(self) -> list[UserMessage]:
        """Return all UserMessage widgets currently visible in #messages.

        Only includes messages with a valid message_index (i.e. real user
        messages, not slash-command echo messages).
        """
        messages_area = self._cached_messages_area or self.query_one("#messages")
        return [
            child
            for child in messages_area.children
            if isinstance(child, UserMessage) and child.message_index is not None
        ]

    def _start_rewind_mode(self, *, skip_agent_check: bool = False, **kwargs: Any) -> bool:
        """Enter rewind mode to select a previous message for rewriting."""
        self.action_rewind_prev(skip_agent_check=skip_agent_check)
        return True  # Indicates rewind mode was entered

    def action_rewind_prev(self, *, skip_agent_check: bool = False) -> None:
        if self._agent_running and not skip_agent_check:
            self.notify("Cannot rewind while agent is running", severity="warning")
            return

        user_widgets = self._get_user_message_widgets()
        if not user_widgets:
            self.notify("No messages to rewind to", severity="warning")
            return

        if not self._rewind_mode:
            self._rewind_mode = True
            target = user_widgets[-1]
        elif self._rewind_highlighted_widget is not None:
            try:
                idx = user_widgets.index(self._rewind_highlighted_widget)
            except ValueError:
                idx = len(user_widgets)
            if idx <= 0:
                self.run_worker(self._rewind_prev_at_top(), exclusive=False)
                return
            target = user_widgets[idx - 1]
        else:
            target = user_widgets[-1]

        self.run_worker(self._select_rewind_widget(target), exclusive=False)

    async def _rewind_prev_at_top(self) -> None:
        """Handle alt+up when already at the topmost visible user message."""
        if self._load_more.widget is not None and self._windowing.has_backfill:
            await self.on_history_load_more_requested(HistoryLoadMoreRequested())
            user_widgets = self._get_user_message_widgets()
            if user_widgets and self._rewind_highlighted_widget is not None:
                # Find the current highlighted widget in the refreshed list
                # and select the one above it
                try:
                    idx = user_widgets.index(self._rewind_highlighted_widget)
                except ValueError:
                    idx = 0
                if idx > 0:
                    await self._select_rewind_widget(user_widgets[idx - 1])
                    return
        # No load more or already first message: scroll to top
        chat = self._cached_chat or self.query_one("#chat", ChatScroll)
        self.call_after_refresh(chat.scroll_home, animate=False)

    def action_rewind_next(self) -> None:
        if not self._rewind_mode:
            return

        if self._rewind_highlighted_widget is None:
            return

        user_widgets = self._get_user_message_widgets()
        try:
            idx = user_widgets.index(self._rewind_highlighted_widget)
        except ValueError:
            return
        if idx >= len(user_widgets) - 1:
            return

        self.run_worker(
            self._select_rewind_widget(user_widgets[idx + 1]), exclusive=False
        )

    async def _select_rewind_widget(self, widget: UserMessage) -> None:
        """Highlight the given user message widget and show the rewind panel."""
        try:
            if self._rewind_highlighted_widget is not None:
                self._rewind_highlighted_widget.remove_class("rewind-selected")

            widget.add_class("rewind-selected")
            self._rewind_highlighted_widget = widget

            msg_index = widget.message_index
            has_file_changes = (
                msg_index is not None
                and self.agent_loop.rewind_manager.has_file_changes_at(msg_index)
            )

            await self._switch_to_rewind_app(
                widget.get_content(), has_file_changes=has_file_changes
            )

            chat = self._cached_chat or self.query_one("#chat", ChatScroll)
            self.call_after_refresh(chat.scroll_to_widget, widget, animate=False, top=True)
        except Exception as e:
            self.notify(f"Rewind error: {e}", severity="error")

    async def _switch_to_rewind_app(
        self, message_preview: str, *, has_file_changes: bool
    ) -> None:
        """Show the rewind action panel at the bottom."""
        # Clean up existing rewind app if needed
        try:
            existing = self.query_one(RewindApp)
            if existing.has_file_changes == has_file_changes:
                existing.update_preview(message_preview)
                return
            await existing.remove()
        except Exception:
            pass

        # Hide the input container and show rewind app
        if self._chat_input_container:
            self._chat_input_container.display = False
            self._chat_input_container.disabled = True
        self._feedback_bar.hide()

        rewind_app = RewindApp(
            message_preview=message_preview, has_file_changes=has_file_changes
        )
        bottom_container = self.query_one("#bottom-app-container")
        self._current_bottom_app = BottomApp.Rewind
        await bottom_container.mount(rewind_app)
        self.call_after_refresh(rewind_app.focus)

    def _clear_rewind_state(self) -> None:
        if self._rewind_highlighted_widget is not None:
            self._rewind_highlighted_widget.remove_class("rewind-selected")
            self._rewind_highlighted_widget = None
        self._rewind_mode = False

    async def _exit_rewind_mode(self) -> None:
        """Exit rewind mode and restore the input panel."""
        self._clear_rewind_state()
        await self._switch_to_input_app()

    async def on_rewind_app_rewind_with_restore(
        self, message: RewindApp.RewindWithRestore
    ) -> None:
        await self._execute_rewind(restore_files=True)

    async def on_rewind_app_rewind_without_restore(
        self, message: RewindApp.RewindWithoutRestore
    ) -> None:
        await self._execute_rewind(restore_files=False)

    async def _execute_rewind(self, *, restore_files: bool) -> None:
        """Fork the session at the selected user message."""
        if not self._rewind_mode or self._rewind_highlighted_widget is None:
            return

        target_widget = self._rewind_highlighted_widget
        msg_index = target_widget.message_index

        if msg_index is None:
            return

        try:
            (
                message_content,
                restore_errors,
            ) = await self.agent_loop.rewind_manager.rewind_to_message(
                msg_index, restore_files=restore_files
            )
        except RewindError as exc:
            self.notify(str(exc), severity="error")
            return

        for error in restore_errors:
            self.notify(error, severity="warning")

        # Remove UI widgets from the selected message onward
        messages_area = self._cached_messages_area or self.query_one("#messages")
        children = list(messages_area.children)
        try:
            target_idx = children.index(target_widget)
        except ValueError:
            target_idx = len(children)
        to_remove = children[target_idx:]
        if to_remove:
            await messages_area.remove_children(to_remove)

        self._clear_rewind_state()

        # Switch back to input and pre-fill with the original message
        await self._switch_to_input_app()
        if self._chat_input_container:
            self._chat_input_container.value = message_content

    # --- End rewind mode ---

    def _handle_input_app_escape(self) -> None:
        try:
            input_widget = self.query_one(ChatInputContainer)
            input_widget.value = ""
        except Exception:
            pass
        self._last_escape_time = None

    def _handle_agent_running_escape(self) -> None:
        self.agent_loop.telemetry_client.send_user_cancelled_action("interrupt_agent")
        self.run_worker(self._interrupt_agent_loop(), exclusive=False)

    def _handle_bottom_app_close_escape(
        self, widget_type: type[MCPApp] | type[ProxySetupApp] | type[ConnectorAuthApp]
    ) -> None:
        try:
            self.query_one(widget_type).action_close()
        except Exception:
            pass
        self._last_escape_time = None

    def _try_interrupt_bottom_app_escape(self) -> bool:
        if self._current_bottom_app == BottomApp.Config:
            self._handle_config_app_escape()
        # elif self._current_bottom_app == BottomApp.Voice:  # Not supported in core Settings
        #     self._handle_voice_app_escape()
        elif self._current_bottom_app == BottomApp.MCP:
            self._handle_bottom_app_close_escape(MCPApp)
        elif self._current_bottom_app == BottomApp.ConnectorAuth:
            self._handle_bottom_app_close_escape(ConnectorAuthApp)
        elif self._current_bottom_app == BottomApp.ProxySetup:
            self._handle_bottom_app_close_escape(ProxySetupApp)
        elif self._current_bottom_app == BottomApp.Approval:
            self._handle_approval_app_escape()
        elif self._current_bottom_app == BottomApp.Question:
            self._handle_question_app_escape()
        elif self._current_bottom_app == BottomApp.ModelPicker:
            self._handle_model_picker_app_escape()
        elif self._current_bottom_app == BottomApp.ThinkingPicker:
            self._handle_thinking_picker_app_escape()
        elif self._current_bottom_app == BottomApp.SessionPicker:
            self._handle_session_picker_app_escape()
        elif self._current_bottom_app == BottomApp.Rewind:
            self.run_worker(self._exit_rewind_mode(), exclusive=False)
            self._last_escape_time = None
        elif (
            self._current_bottom_app == BottomApp.Input
            and self._last_escape_time is not None
            and (time.monotonic() - self._last_escape_time) < DOUBLE_ESC_DELAY
        ):
            self._handle_input_app_escape()
        else:
            return False
        return True

    def _try_interrupt(self) -> bool:
        if self._voice_manager.transcribe_state != TranscribeState.IDLE:
            self._voice_manager.cancel_recording()
            return True

        if (
            self._chat_input_container
            and self._chat_input_container.dismiss_completion()
        ):
            if self._chat_input_container.value.startswith("/"):
                self._chat_input_container.value = ""
            self._last_escape_time = None
            return True

        if self._try_interrupt_bottom_app_escape():
            return True

        if (
            self._narrator_manager.is_playing
            or self._narrator_manager.state != NarratorState.IDLE
        ):
            self._narrator_manager.cancel()
            return True

        interrupted = False
        if self._agent_running:
            self._handle_agent_running_escape()
            interrupted = True

        self._last_escape_time = time.monotonic()
        chat = self._cached_chat or self.query_one("#chat", ChatScroll)
        if chat.is_at_bottom:
            self.call_after_refresh(chat.anchor)
        self._focus_current_bottom_app()
        return interrupted

    def action_interrupt(self) -> None:
        self._try_interrupt()

    async def on_history_load_more_requested(self, _: HistoryLoadMoreRequested) -> None:
        self._load_more.set_enabled(False)
        try:
            if not self._windowing.has_backfill:
                await self._load_more.hide()
                return
            if (batch := self._windowing.next_load_more_batch()) is None:
                await self._load_more.hide()
                return
            messages_area = self._cached_messages_area or self.query_one("#messages")
            if self._tool_call_map is None:
                self._tool_call_map = {}
            if self._load_more.widget:
                before: Widget | int | None = None
                after: Widget | None = self._load_more.widget
            else:
                before = 0
                after = None
            await self._mount_history_batch(
                batch.messages,
                messages_area,
                self._tool_call_map,
                start_index=batch.start_index,
                before=before,
                after=after,
            )
            if not self._windowing.has_backfill:
                await self._load_more.hide()
            else:
                await self._load_more.show(messages_area, self._windowing.remaining)
        finally:
            self._load_more.set_enabled(True)

    async def action_toggle_tool(self) -> None:
        self._tools_collapsed = not self._tools_collapsed

        for result in self.query(ToolResultMessage):
            await result.set_collapsed(self._tools_collapsed)

        try:
            for error_msg in self.query(ErrorMessage):
                error_msg.set_collapsed(self._tools_collapsed)
        except Exception:
            pass

    async def action_toggle_thinking(self) -> None:
        self._thinking_collapsed = not self._thinking_collapsed
        for msg in self.query("ReasoningMessage"):
            msg.collapsed = self._thinking_collapsed

    def action_cycle_mode(self) -> None:
        if self._current_bottom_app != BottomApp.Input:
            return
        self._refresh_profile_widgets()
        self._focus_current_bottom_app()
        self.run_worker(self._cycle_agent(), group="mode_switch", exclusive=True)

    def _refresh_profile_widgets(self) -> None:
        self._update_profile_widgets(self.agent_loop.agent_profile)

    def _on_profile_changed(self) -> None:
        self._refresh_profile_widgets()
        self._refresh_banner()

    def _refresh_banner(self) -> None:
        if self._banner:
            connectors_count = _compute_connectors_count(
                self.config, self.agent_loop.connector_registry if self._connectors_enabled else None  # type: ignore
            )
            self._banner.set_state(
                self.config,  # type: ignore
                self.agent_loop.skill_manager,
                connectors_count=connectors_count,
                model=self.agent_loop.agent.model,
            )

    def _update_profile_widgets(self, profile: Any) -> None:
        if self._chat_input_container:
            # profile.safety might be core.AgentSafety enum or string
            safety = getattr(profile, "safety", AgentSafety.NEUTRAL)
            self._chat_input_container.set_safety(safety)
            self._chat_input_container.set_agent_name(profile.display_name.lower())
            if self._remote_manager.is_active:
                session_id = self._remote_manager.session_id
                self._chat_input_container.set_custom_border(
                    f"Remote session {short_session_id(session_id, source='remote') if session_id else ''}",
                    ChatInputContainer.REMOTE_BORDER_CLASS,
                )
            else:
                self._chat_input_container.set_custom_border(None)

    async def _cycle_agent(self) -> None:
        new_profile = self.agent_loop.agent_manager.next_agent(
            self.agent_loop.agent_profile
        )
        self._update_profile_widgets(new_profile)
        if self._chat_input_container:
            self._chat_input_container.switching_mode = True

        def schedule_switch() -> None:
            self._switch_agent_generation += 1
            my_gen = self._switch_agent_generation

            def switch_agent_sync() -> None:
                try:
                    asyncio.run(self.agent_loop.switch_agent(new_profile.name))
                    self.agent_loop.set_approval_callback(self._approval_callback)
                    self.agent_loop.set_user_input_callback(self._user_input_callback)
                finally:
                    if (
                        self._chat_input_container
                        and self._switch_agent_generation == my_gen
                    ):
                        self.call_from_thread(self._refresh_banner)
                        self.call_from_thread(
                            setattr, self._chat_input_container, "switching_mode", False
                        )

            self.run_worker(
                switch_agent_sync, group="switch_agent", exclusive=True, thread=True
            )

        self.call_after_refresh(schedule_switch)

    async def action_toggle_debug_console(self, **kwargs: Any) -> None:
        if self._debug_console is not None:
            await self._debug_console.remove()
            self._debug_console = None
        else:
            self._debug_console = DebugConsole(log_reader=self._log_reader)
            await self.mount(self._debug_console)

    def _get_chat_input(self) -> ChatInputContainer | None:
        input_widgets = self.query(ChatInputContainer)
        if input_widgets:
            return input_widgets.first()
        return None

    def action_interrupt_or_quit(self) -> None:
        if (container := self._get_chat_input()) and container.value:
            container.value = ""
            return

        if self._quit_manager.is_confirmed("Ctrl+C"):
            self._force_quit()
            return
        if self._try_interrupt():
            return
        self._quit_manager.request_confirmation("Ctrl+C")

    def action_delete_right_or_quit(self) -> None:
        if (container := self._get_chat_input()) and container.value:
            if container.input_widget:
                container.input_widget.action_delete_right()
            return

        if self._quit_manager.is_confirmed("Ctrl+D"):
            self._force_quit()
            return
        self._quit_manager.request_confirmation("Ctrl+D")

    def _force_quit(self) -> None:
        if self._agent_task and not self._agent_task.done():
            self._agent_task.cancel()
        self._remote_manager.cancel_stream_task()

        self._log_reader.shutdown()
        self._narrator_manager.cancel()
        self.exit(result=self._get_session_resume_info())

    def action_scroll_chat_up(self) -> None:
        try:
            chat = self._cached_chat or self.query_one("#chat", ChatScroll)
            chat.scroll_relative(y=-5, animate=False)
        except Exception:
            pass

    def action_scroll_chat_down(self) -> None:
        try:
            chat = self._cached_chat or self.query_one("#chat", ChatScroll)
            chat.scroll_relative(y=5, animate=False)
        except Exception:
            pass

    async def _show_dangerous_directory_warning(self) -> None:
        is_dangerous, reason = is_dangerous_directory(Path.cwd())
        if is_dangerous:
            warning = (
                f"⚠ WARNING: {reason}\n\nRunning in this location is not recommended."
            )
            await self._mount_and_scroll(WarningMessage(warning, show_border=False))

    async def _check_and_show_whats_new(self) -> None:
        if self._update_cache_repository is None:
            return

        if not await should_show_whats_new(
            self._current_version, self._update_cache_repository
        ):
            return

        content = load_whats_new_content()
        if content is not None:
            whats_new_message = WhatsNewMessage(content)
            plan_offer = plan_offer_cta(self._plan_info)
            if plan_offer is not None:
                whats_new_message = WhatsNewMessage(f"{content}\n\n{plan_offer}")
            if self._history_widget_indices:
                whats_new_message.add_class("after-history")
            messages_area = self._cached_messages_area or self.query_one("#messages")
            chat = self._cached_chat or self.query_one("#chat", ChatScroll)
            should_anchor = chat.is_at_bottom
            await chat.mount(whats_new_message, after=messages_area)
            self._whats_new_message = whats_new_message
            if should_anchor:
                chat.anchor()
        await mark_version_as_seen(self._current_version, self._update_cache_repository)

    async def _resolve_plan(self) -> None:
        if self._plan_offer_gateway is None:
            self._plan_info = None
            self._refresh_command_registry()
            return

        try:
            # Plan offer not supported in core Settings
            self._plan_info = None
            return
        except Exception as exc:
            logger.warning(
                "Plan-offer check failed (%s).", type(exc).__name__, exc_info=True
            )
            self._plan_info = None
        finally:
            self._refresh_command_registry()

    async def _mount_and_scroll(
        self, widget: Widget, after: Widget | None = None
    ) -> None:
        messages_area = self._cached_messages_area or self.query_one("#messages")
        chat = self._cached_chat or self.query_one("#chat", ChatScroll)

        is_user_initiated = isinstance(widget, (UserMessage, UserCommandMessage))
        should_anchor = is_user_initiated or chat.is_at_bottom

        with self.batch_update():
            if after is not None and after.parent is messages_area:
                await messages_area.mount(widget, after=after)
            else:
                await messages_area.mount(widget)
            if isinstance(widget, StreamingMessageBase):
                await widget.write_initial_content()

        self.call_after_refresh(self._try_prune)
        if should_anchor:
            chat.anchor()

    async def _try_prune(self) -> None:
        messages_area = self._cached_messages_area or self.query_one("#messages")
        pruned = await prune_oldest_children(
            messages_area, PRUNE_LOW_MARK, PRUNE_HIGH_MARK
        )
        if self._load_more.widget and not self._load_more.widget.parent:
            self._load_more.widget = None
        if pruned:
            chat = self._cached_chat or self.query_one("#chat", ChatScroll)
            if chat.is_at_bottom:
                self.call_later(chat.anchor)

    async def _refresh_windowing_from_history(self) -> None:
        if self._load_more.widget is None:
            return
        messages_area = self._cached_messages_area or self.query_one("#messages")
        has_backfill, tool_call_map = sync_backfill_state(
            history_messages=non_system_history_messages(self.agent_loop.messages),
            messages_children=list(messages_area.children),
            history_widget_indices=self._history_widget_indices,
            windowing=self._windowing,
        )
        self._tool_call_map = tool_call_map
        await self._load_more.set_visible(
            messages_area, visible=has_backfill, remaining=self._windowing.remaining
        )

    def _schedule_update_notification(self) -> None:
        if self._update_notifier is None:
            return

        # Update checks not supported in core Settings
        asyncio.create_task(self._check_update(), name="version-update-check")

    async def _check_update(self) -> None:
        try:
            if self._update_notifier is None or self._update_cache_repository is None:
                return

            update_availability = await get_update_if_available(
                update_notifier=self._update_notifier,
                current_version=self._current_version,
                update_cache_repository=self._update_cache_repository,
            )
        except UpdateError as error:
            self.notify(
                error.message,
                title="Update check failed",
                severity="warning",
                timeout=10,
            )
            return
        except Exception as exc:
            logger.debug("Version update check failed", exc_info=exc)
            return

        if update_availability is None or not update_availability.should_notify:
            return

        update_message_prefix = (
            f"{self._current_version} => {update_availability.latest_version}"
        )

        if False and await do_update():  # Auto update not supported in core Settings
            self.notify(
                f"{update_message_prefix}\nVibe was updated successfully. Please restart to use the new version.",
                title="Update successful",
                severity="information",
                timeout=float("inf"),
            )
            return

        message = f"{update_message_prefix}\nPlease update jarvis with your package manager"

        self.notify(
            message, title="Update available", severity="information", timeout=10
        )

    def action_copy_selection(self) -> None:
        copied_text = copy_selection_to_clipboard(self, show_toast=False)
        if copied_text:
            # We don't have the original content easily here, but telemetry 
            # usually wants the copied text if available. 
            # For now, just pass a placeholder or get it if possible.
            self.agent_loop.telemetry_client.send_user_copied_text("selection")

    def on_mouse_up(self, event: MouseUp) -> None:
        if False:  # Autocopy not supported in core Settings
            copied_text = copy_selection_to_clipboard(self, show_toast=True)
            if copied_text:
                self.agent_loop.telemetry_client.send_user_copied_text("selection")


    def on_app_blur(self, event: AppBlur) -> None:
        self._terminal_notifier.on_blur()
        if self._chat_input_container and self._chat_input_container.input_widget:
            self._chat_input_container.input_widget.set_app_focus(False)

    def on_app_focus(self, event: AppFocus) -> None:
        self._terminal_notifier.on_focus()
        if self._chat_input_container and self._chat_input_container.input_widget:
            self._chat_input_container.input_widget.set_app_focus(True)

    def action_suspend_with_message(self) -> None:
        if WINDOWS or self._driver is None or not self._driver.can_suspend:
            return
        with self.suspend():
            rprint(
                "JARVIS has been suspended. Run [bold cyan]fg[/bold cyan] to bring JARVIS back."
            )
            os.kill(os.getpid(), signal.SIGTSTP)

    def _on_driver_signal_resume(self, event: Driver.SignalResume) -> None:
        # Textual doesn't repaint after resuming from Ctrl+Z (SIGTSTP);
        # force a full layout refresh so the UI isn't garbled.
        self.refresh(layout=True)

    def _make_default_narrator_manager(self) -> NarratorManager:
        return NarratorManager(
            config_getter=lambda: self.config,
            audio_player=AudioPlayer(),
            telemetry_client=self.agent_loop.telemetry_client,
        )


def run_textual_ui(
    agent_loop: AgentLoop, startup: StartupOptions | None = None
) -> None:
    from interface.textual_ui.cli_adapters import stderr_guard
    
    update_notifier = PyPIUpdateGateway(project_name="jarvis")
    update_cache_repository = FileSystemUpdateCacheRepository()
    plan_offer_gateway = HttpWhoAmIGateway()

    with stderr_guard():
        app = VibeApp(
            agent_loop=agent_loop,
            startup=startup,
            update_notifier=update_notifier,
            update_cache_repository=update_cache_repository,
            plan_offer_gateway=plan_offer_gateway,
        )
        session_id = app.run()

    print_session_resume_message(session_id, agent_loop.stats)
