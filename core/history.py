"""
Conversation History Management - Matches OpenAI/Anthropic SDK format.

Storage format matches both OpenAI and Anthropic SDKs:
- role: "user" | "assistant" | "system"
- content: string | array of content blocks

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
from typing import Optional, Any, Union


# Role types used by both OpenAI and Anthropic SDKs
class Role(str, Enum):
    """Role types matching OpenAI/Anthropic SDK format."""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


@dataclass
class HistoryMessage:
    """
    Represents a single message in conversation history.
    Matches OpenAI/Anthropic SDK message format.

    OpenAI format: {"role": "user", "content": "Hello"}
    Anthropic format: {"role": "user", "content": "Hello"}

    This class stores messages in the exact SDK format for compatibility.
    """
    role: str  # "user", "assistant", or "system"
    content: Union[str, list, None] = None
    uuid: str = field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    # Optional metadata
    name: Optional[str] = None
    tool_calls: Optional[list] = None
    tool_call_id: Optional[str] = None
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
            message: The message to append (must have role and content)
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
    """
    Create a user message in SDK format.

    Args:
        content: The user message content (string)
        **kwargs: Additional fields (name, etc.)

    Returns:
        HistoryMessage in SDK format
    """
    return HistoryMessage(
        role=Role.USER.value,
        content=content,
        **kwargs
    )


def create_assistant_message(content: Union[str, list], **kwargs) -> HistoryMessage:
    """
    Create an assistant message in SDK format.

    Args:
        content: The assistant message content (string or list for tool calls)
        **kwargs: Additional fields (tool_calls, etc.)

    Returns:
        HistoryMessage in SDK format
    """
    return HistoryMessage(
        role=Role.ASSISTANT.value,
        content=content,
        **kwargs
    )


def create_system_message(content: str, **kwargs) -> HistoryMessage:
    """
    Create a system message in SDK format.

    Args:
        content: The system message content
        **kwargs: Additional fields

    Returns:
        HistoryMessage in SDK format
    """
    return HistoryMessage(
        role=Role.SYSTEM.value,
        content=content,
        **kwargs
    )