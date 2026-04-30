"""Core type definitions compatible with vibe."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Role(str, Enum):
    """Message role."""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


@dataclass
class LLMMessage:
    """LLM message."""
    role: Role
    content: str
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    tool_call_id: str | None = None


@dataclass
class AgentStats:
    """Agent statistics."""
    total_tokens: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_cost: float = 0.0


@dataclass
class ApprovalResponse:
    """Approval response."""
    approved: bool
    response: str | None = None


@dataclass
class BaseEvent:
    """Base event class."""
    event_type: str


@dataclass
class WaitingForInputEvent(BaseEvent):
    """Event when waiting for user input."""
    event_type: str = "waiting_for_input"


@dataclass
class AssistantEvent(BaseEvent):
    """Assistant event."""
    event_type: str = "assistant"
    content: str = ""


@dataclass
class ReasoningEvent(BaseEvent):
    """Reasoning event."""
    event_type: str = "reasoning"
    content: str = ""


@dataclass
class ToolCallEvent(BaseEvent):
    """Tool call event."""
    event_type: str = "tool_call"
    tool_name: str = ""
    tool_args: dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolResultEvent(BaseEvent):
    """Tool result event."""
    event_type: str = "tool_result"
    tool_name: str = ""
    result: str = ""


@dataclass
class ToolStreamEvent(BaseEvent):
    """Tool stream event."""
    event_type: str = "tool_stream"
    content: str = ""


@dataclass
class UserMessageEvent(BaseEvent):
    """User message event."""
    event_type: str = "user_message"
    content: str = ""


@dataclass
class CompactStartEvent(BaseEvent):
    """Compact start event."""
    event_type: str = "compact_start"


@dataclass
class CompactEndEvent(BaseEvent):
    """Compact end event."""
    event_type: str = "compact_end"


@dataclass
class AgentProfileChangedEvent(BaseEvent):
    """Agent profile changed event."""
    event_type: str = "profile_changed"


class ContextTooLongError(Exception):
    """Error when context is too long."""
    pass


class RateLimitError(Exception):
    """Error when rate limited."""
    pass


class TeleportError(Exception):
    """Error during teleport."""
    pass


class RewindError(Exception):
    """Error during rewind."""
    pass


@dataclass
class CancellationReason:
    """Cancellation reason."""
    reason: str


def get_user_cancellation_message(reason: CancellationReason) -> str:
    """Get user cancellation message."""
    return f"Operation cancelled: {reason.reason}"


def is_dangerous_directory(path: str) -> bool:
    """Check if directory is dangerous."""
    dangerous_paths = ["/", "/etc", "/usr", "/System", "C:\\", "C:\\Windows"]
    return any(path.startswith(d) for d in dangerous_paths)
