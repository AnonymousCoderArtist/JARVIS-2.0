"""Type definitions for textual UI."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Role(str, Enum):
    """Message role."""
    user = "user"
    assistant = "assistant"
    system = "system"
    tool = "tool"

    def __str__(self) -> str:
        return self.value


@dataclass
class ToolCallFunction:
    """Tool call function."""
    name: str = ""
    arguments: str = ""


@dataclass
class ToolCall:
    """Tool call."""
    id: str = ""
    function: ToolCallFunction = field(default_factory=ToolCallFunction)
    type: str = ""


@dataclass
class ImageContentPart:
    """Image content part for multimodal messages."""
    type: str = "image_url"
    image_url: dict[str, str] = field(default_factory=lambda: {"url": ""})


@dataclass
class LLMMessage:
    """LLM message."""
    role: Role = Role.user
    content: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    injected: bool = False
    tool_call_id: str = ""
    name: str = ""
    image_parts: list[ImageContentPart] = field(default_factory=list)


class HookMessageSeverity(str, Enum):
    """Hook message severity."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    OK = "ok"

    def __str__(self) -> str:
        return self.value


class ContextTooLongError(Exception):
    """Context too long error."""
    pass


class RateLimitError(Exception):
    """Rate limit error."""
    pass



@dataclass
class ToolApprovalResult:
    """Result of an approval request."""
    approved: bool = False
    message: str = ""


@dataclass
class AgentStats:
    """Agent statistics."""
    context_tokens: int = 0
    total_tokens: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_cost: float = 0.0
    session_prompt_tokens: int = 0
    session_completion_tokens: int = 0
    session_total_llm_tokens: int = 0


@dataclass
class BaseEvent:
    """Base event."""
    event_type: str = ""


@dataclass
class AssistantEvent(BaseEvent):
    """Assistant event."""
    content: str = ""
    is_heartbeat: bool = False


@dataclass
class ReasoningEvent(BaseEvent):
    """Reasoning event."""
    content: str = ""


@dataclass
class ToolCallEvent(BaseEvent):
    """Tool call event."""
    tool_name: str = ""
    tool_args: dict[str, Any] = field(default_factory=dict)
    tool_call_id: str = ""
    tool_class: str = ""


@dataclass
class ToolResultEvent(BaseEvent):
    """Tool result event."""
    tool_name: str = ""
    result: Any = None
    tool_call_id: str = ""
    tool_class: str = ""
    error: str = ""
    skipped: bool = False
    skip_reason: str = ""
    cancelled: bool = False
    duration: float = 0.0


@dataclass
class AgentToolCallEvent(BaseEvent):
    """Agent tool call event."""
    agent_name: str = ""
    prompt: str = ""
    task_id: str = ""
    event_type: str = "agent_tool_call"


@dataclass
class AgentToolResultEvent(BaseEvent):
    """Agent tool result event."""
    agent_name: str = ""
    prompt: str = ""
    task_id: str = ""
    result: str = ""
    status: str = "completed"
    error: str = ""
    event_type: str = "agent_tool_result"


@dataclass
class ToolStreamEvent(BaseEvent):
    """Tool stream event."""
    content: str = ""
    tool_call_id: str = ""


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
    predefined_answers: list[str] = field(default_factory=list)
    label: str = ""


@dataclass
class TimingEvent(BaseEvent):
    """Timing event showing duration."""
    duration: float = 0.0
