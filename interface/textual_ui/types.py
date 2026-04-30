"""Type definitions for textual UI."""

from dataclasses import dataclass
from enum import Enum


class Role(str, Enum):
    """Message role."""
    user = "user"
    assistant = "assistant"
    system = "system"
    tool = "tool"


@dataclass
class ToolCallFunction:
    """Tool call function."""
    name: str = ""
    arguments: str = ""


@dataclass
class ToolCall:
    """Tool call."""
    id: str = ""
    function: ToolCallFunction = None
    type: str = ""

    def __post_init__(self):
        if self.function is None:
            self.function = ToolCallFunction()


@dataclass
class LLMMessage:
    """LLM message."""
    role: Role = Role.user
    content: str = ""
    tool_calls: list[ToolCall] = None
    injected: bool = False
    tool_call_id: str = ""
    name: str = ""

    def __post_init__(self):
        if self.tool_calls is None:
            self.tool_calls = []


class HookMessageSeverity(str, Enum):
    """Hook message severity."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    OK = "ok"


class ContextTooLongError(Exception):
    """Context too long error."""
    pass


class RateLimitError(Exception):
    """Rate limit error."""
    pass


@dataclass
class ApprovalResponse:
    """Approval response."""
    approved: bool = False
    message: str = ""


@dataclass
class AgentStats:
    """Agent statistics."""
    total_tokens: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_cost: float = 0.0


@dataclass
class BaseEvent:
    """Base event."""
    event_type: str = ""


@dataclass
class AssistantEvent(BaseEvent):
    """Assistant event."""
    content: str = ""


@dataclass
class ReasoningEvent(BaseEvent):
    """Reasoning event."""
    content: str = ""


@dataclass
class ToolCallEvent(BaseEvent):
    """Tool call event."""
    tool_name: str = ""
    tool_args: dict = None
    tool_call_id: str = ""
    tool_class: str = ""


@dataclass
class ToolResultEvent(BaseEvent):
    """Tool result event."""
    tool_name: str = ""
    result: str = ""
    tool_call_id: str = ""
    tool_class: str = ""
    error: str = ""
    skipped: bool = False
    skip_reason: str = ""
    cancelled: bool = False
    duration: float = 0.0


@dataclass
class ToolStreamEvent(BaseEvent):
    """Tool stream event."""
    content: str = ""


@dataclass
class UserMessageEvent(BaseEvent):
    """User message event."""
    content: str = ""


@dataclass
class CompactStartEvent(BaseEvent):
    """Compact start event."""
    pass


@dataclass
class CompactEndEvent(BaseEvent):
    """Compact end event."""
    pass


@dataclass
class AgentProfileChangedEvent(BaseEvent):
    """Agent profile changed event."""
    pass


@dataclass
class WaitingForInputEvent(BaseEvent):
    """Waiting for input event."""
    pass
