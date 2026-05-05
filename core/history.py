"""
Conversation History Management - Matches OpenAI/Anthropic SDK format.

Storage format matches both OpenAI and Anthropic SDKs:
- role: "user" | "assistant" | "system" | "tool"
- content: string | array of content blocks

Supports tool calls/results in both SDK formats:
- OpenAI: assistant with tool_calls, tool with tool_call_id
- Anthropic: assistant with tool_use content, user with tool_result content

See: https://platform.openai.com/docs/guides/chat/completions
See: https://docs.anthropic.com/en/docs/reference/messages_post
"""

import json
import uuid
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Optional, Any, Union, List


# Role types used by both OpenAI and Anthropic SDKs
class Role(str, Enum):
    """Role types matching OpenAI/Anthropic SDK format."""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"


@dataclass
class ToolCall:
    """Represents a tool call in OpenAI format."""
    id: str
    type: str = "function"
    function: Optional[dict] = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ToolUse:
    """Represents a tool use in Anthropic format."""
    type: str = "tool_use"
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    input: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ToolResult:
    """Represents a tool result in Anthropic format."""
    type: str = "tool_result"
    tool_use_id: str = ""
    content: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class HistoryMessage:
    """
    Represents a single message in conversation history.
    Matches OpenAI/Anthropic SDK message format.

    OpenAI format: {"role": "user", "content": "Hello"}
    Anthropic format: {"role": "user", "content": "Hello"}

    Supports tool calls/results:
    - OpenAI: {"role": "assistant", "tool_calls": [...]}, {"role": "tool", "tool_call_id": "...", "content": "..."}
    - Anthropic: {"role": "assistant", "content": [{"type": "tool_use", ...}]}, {"role": "user", "content": [{"type": "tool_result", ...}]}
    """
    role: str  # "user", "assistant", "system", or "tool"
    content: Union[str, list, None] = None
    uuid: str = field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    # OpenAI-specific: tool calls from assistant
    tool_calls: Optional[List[dict]] = None

    # OpenAI-specific: tool call ID for tool role
    tool_call_id: Optional[str] = None

    # Anthropic-specific: tool use in content array
    tool_use: Optional[dict] = None

    # Anthropic-specific: tool result in content array
    tool_result: Optional[dict] = None

    # Optional metadata
    name: Optional[str] = None
    refusal: Optional[bool] = None
    additional_kwargs: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        d = asdict(self)
        # Remove None values for cleaner output
        return {k: v for k, v in d.items() if v is not None}

    @classmethod
    def from_dict(cls, data: dict) -> "HistoryMessage":
        """Create from dictionary (SDK format)."""
        return cls(**data)


@dataclass
class SessionInfo:
    """Session metadata."""
    session_id: str
    created_at: str
    cwd: str
    name: str = ""
    kind: str = "interactive"


class ConversationHistory:
    """
    Manages conversation history storage and retrieval.
    Uses JSONL format matching OpenAI/Anthropic SDK message format.
    """

    def __init__(self, session_id: Optional[str] = None, history_dir: Optional[Path] = None):
        """
        Initialize conversation history.

        Args:
            session_id: Optional session ID (generated if not provided)
            history_dir: Directory for history files (defaults to ~/.jarvis/history)
        """
        self.session_id = session_id or str(uuid.uuid4())
        self.history_dir = history_dir or self._default_history_dir()
        self._ensure_history_dir()

    def _default_history_dir(self) -> Path:
        """Get default history directory."""
        return Path.home() / ".jarvis" / "history"

    def _ensure_history_dir(self) -> None:
        """Ensure history directory exists."""
        self.history_dir.mkdir(parents=True, exist_ok=True)

    def _history_file(self) -> Path:
        """Get path to this session's history file."""
        return self.history_dir / f"{self.session_id}.jsonl"

    def append_message(self, message: HistoryMessage) -> None:
        """
        Append a message to the history file.

        Args:
            message: The message to append
        """
        message.session_id = self.session_id
        if not message.timestamp:
            message.timestamp = datetime.now(timezone.utc).isoformat()

        with open(self._history_file(), "a") as f:
            f.write(json.dumps(message.to_dict()) + "\n")

    def get_messages(self, limit: Optional[int] = None) -> list[HistoryMessage]:
        """
        Retrieve messages from history.

        Args:
            limit: Optional limit on number of messages to retrieve

        Returns:
            List of HistoryMessage objects
        """
        history_file = self._history_file()
        if not history_file.exists():
            return []

        messages = []
        with open(history_file, "r") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        data = json.loads(line)
                        messages.append(HistoryMessage.from_dict(data))
                    except json.JSONDecodeError:
                        continue

        if limit:
            messages = messages[-limit:]

        return messages

    def clear_history(self) -> None:
        """Clear the history file for this session."""
        history_file = self._history_file()
        if history_file.exists():
            history_file.unlink()

    def get_session_info(self) -> SessionInfo:
        """Get session metadata."""
        messages = self.get_messages()
        created_at = messages[0].timestamp if messages else datetime.now(timezone.utc).isoformat()

        return SessionInfo(
            session_id=self.session_id,
            created_at=created_at,
            cwd=os.getcwd(),
            name=f"Session {self.session_id[:8]}..."
        )


# Convenience functions matching SDK format
def create_user_message(content: str, **kwargs) -> HistoryMessage:
    """Create a user message in SDK format."""
    return HistoryMessage(role=Role.USER.value, content=content, **kwargs)


def create_assistant_message(content: Union[str, list], **kwargs) -> HistoryMessage:
    """Create an assistant message in SDK format."""
    return HistoryMessage(role=Role.ASSISTANT.value, content=content, **kwargs)


def create_system_message(content: str, **kwargs) -> HistoryMessage:
    """Create a system message in SDK format."""
    return HistoryMessage(role=Role.SYSTEM.value, content=content, **kwargs)


def create_tool_message(tool_call_id: str, content: str, **kwargs) -> HistoryMessage:
    """Create a tool result message in OpenAI format."""
    return HistoryMessage(
        role=Role.TOOL.value,
        content=content,
        tool_call_id=tool_call_id,
        **kwargs
    )


def create_openai_tool_call(tool_id: str, name: str, arguments: dict) -> dict:
    """Create an OpenAI-style tool call."""
    return {
        "id": tool_id,
        "type": "function",
        "function": {
            "name": name,
            "arguments": json.dumps(arguments) if isinstance(arguments, dict) else arguments
        }
    }


def create_anthropic_tool_use(tool_id: str, name: str, input_data: dict) -> dict:
    """Create an Anthropic-style tool use content block."""
    return {
        "type": "tool_use",
        "id": tool_id,
        "name": name,
        "input": input_data
    }


def create_anthropic_tool_result(tool_use_id: str, content: str) -> dict:
    """Create an Anthropic-style tool result content block."""
    return {
        "type": "tool_result",
        "tool_use_id": tool_use_id,
        "content": content
    }