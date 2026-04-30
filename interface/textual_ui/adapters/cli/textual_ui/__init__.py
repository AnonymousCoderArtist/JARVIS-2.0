"""Textual UI adapters - re-export existing UI components."""

# Re-export all the existing UI components
from interface.textual_ui.handlers.event_handler import EventHandler
from interface.textual_ui.notifications import NotificationContext, NotificationPort
from interface.textual_ui.notifications.adapters.textual_notification_adapter import TextualNotificationAdapter
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
from interface.textual_ui.widgets.voice_app import VoiceApp
from interface.textual_ui.windowing import (
    HISTORY_RESUME_TAIL_MESSAGES,
    LOAD_MORE_BATCH_SIZE,
    HistoryLoadMoreManager,
    SessionWindowing,
    build_history_widgets,
)
