"""
Conversation History Management - Matches OpenAI/Anthropic SDK format.

Storage format matches both OpenAI and Anthropic SDKs:
- role: "user" | "assistant" | "system" | "tool"
- content: string | array of content blocks

Supports tool calls/results in both SDK formats:
- OpenAI: assistant with tool_calls, tool with tool_call_id
- Anthropic: assistant with tool_use content, user with tool_result content

Includes message coalescing (merging consecutive same-role messages)
and bidirectional format converters for OpenAI/Anthropic SDKs.

See: https://platform.openai.com/docs/guides/chat/completions
See: https://docs.anthropic.com/en/docs/reference/messages_post
"""

import json
import os
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path


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
    function: dict | None = None

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
    content: str | list | None = None
    uuid: str = field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    # OpenAI-specific: tool calls from assistant
    tool_calls: list[dict] | None = None

    # OpenAI-specific: tool call ID for tool role
    tool_call_id: str | None = None

    # Anthropic-specific: tool use in content array
    tool_use: dict | None = None

    # Anthropic-specific: tool result in content array
    tool_result: dict | None = None

    # Optional metadata
    name: str | None = None
    refusal: bool | None = None
    additional_kwargs: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        d = asdict(self)
        return {k: v for k, v in d.items() if v is not None}

    def to_openai_dict(self) -> dict:
        """Convert to OpenAI SDK format dict.

        Returns a dict with role, content, tool_calls, tool_call_id, name
        matching the OpenAI Chat Completions API format.
        """
        d: dict = {"role": self.role}
        if self.content is not None:
            d["content"] = self.content
        else:
            d["content"] = ""
        if self.tool_calls:
            d["tool_calls"] = self.tool_calls
        if self.tool_call_id:
            d["tool_call_id"] = self.tool_call_id
        if self.name:
            d["name"] = self.name
        return d

    def to_anthropic_dict(self) -> dict | None:
        """Convert to Anthropic SDK format dict.

        System messages return None (handled separately by Anthropic API).
        Tool calls are converted to tool_use content blocks.
        Tool results are converted to tool_result content blocks.
        """
        if self.role == "system":
            return None

        if self.tool_use:
            content: list = [self.tool_use]
            if self.content:
                content.insert(0, {"type": "text", "text": str(self.content)})
            return {"role": "assistant", "content": content}

        if self.tool_result:
            content = [self.tool_result]
            if self.content:
                content.insert(0, {"type": "text", "text": str(self.content)})
            return {"role": "user", "content": content}

        return {"role": self.role, "content": self.content or ""}

    @classmethod
    def from_dict(cls, data: dict) -> "HistoryMessage":
        """Create from dictionary (SDK format)."""
        return cls(**data)

    @classmethod
    def from_openai_dict(cls, data: dict) -> "HistoryMessage":
        """Create from OpenAI SDK format dict."""
        return cls(
            role=data.get("role", "user"),
            content=data.get("content"),
            tool_calls=data.get("tool_calls"),
            tool_call_id=data.get("tool_call_id"),
            name=data.get("name"),
        )

    @classmethod
    def from_anthropic_dict(cls, data: dict) -> "HistoryMessage":
        """Create from Anthropic SDK format dict.

        Handles tool_use content blocks (convert to assistant with tool_use field)
        and tool_result content blocks (convert to tool role).
        """
        role = data.get("role", "user")
        content = data.get("content", "")

        if isinstance(content, list):
            text_parts = []
            tool_use = None
            tool_result = None
            for block in content:
                if isinstance(block, dict):
                    if block.get("type") == "text":
                        text_parts.append(block.get("text", ""))
                    elif block.get("type") == "tool_use":
                        tool_use = block
                    elif block.get("type") == "tool_result":
                        tool_result = block

            text_content = "\n".join(text_parts) if text_parts else None

            if tool_use:
                return cls(
                    role=Role.ASSISTANT.value,
                    content=text_content,
                    tool_use=tool_use,
                )
            if tool_result:
                return cls(
                    role=Role.TOOL.value,
                    content=text_content or tool_result.get("content"),
                    tool_call_id=tool_result.get("tool_use_id", ""),
                    tool_result=tool_result,
                )
            return cls(role=role, content=text_content or "")

        return cls(role=role, content=content)


@dataclass
class SessionInfo:
    """Session metadata."""
    session_id: str
    created_at: str
    cwd: str
    name: str = ""
    kind: str = "interactive"


# ============================================================================
# Message Coalescing
# ============================================================================

def coalesce_messages(messages: list[HistoryMessage]) -> list[HistoryMessage]:
    """Merge consecutive messages with the same role.

    OpenAI and Anthropic APIs require strict user/assistant alternation.
    This merges consecutive messages of the same role by concatenating
    content and merging tool_calls arrays. Tool and system messages are
    not coalesced (they have strict ordering requirements).

    Args:
        messages: List of HistoryMessage objects

    Returns:
        Coalesced list with consecutive same-role messages merged
    """
    if not messages:
        return []

    coalesced = [messages[0]]
    for msg in messages[1:]:
        prev = coalesced[-1]
        # Don't coalesce tool, system, or messages with tool_calls
        if (msg.role == prev.role
                and msg.role not in ("tool", "system")
                and not prev.tool_calls
                and not msg.tool_calls):
            # Merge content
            if msg.content and prev.content:
                prev.content = f"{prev.content}\n\n{msg.content}"
            elif msg.content and not prev.content:
                prev.content = msg.content

            # Merge timestamps (keep oldest)
            if msg.timestamp and (not prev.timestamp or msg.timestamp < prev.timestamp):
                prev.timestamp = msg.timestamp
        else:
            coalesced.append(msg)

    return coalesced


# ============================================================================
# SDK Format Converters
# ============================================================================

def to_openai_format(
    messages: list[HistoryMessage],
    system_prompt: str | None = None,
) -> list[dict]:
    """Convert HistoryMessage list to OpenAI Chat Completions API format.

    Each message becomes {"role": ..., "content": ..., "tool_calls": ..., "tool_call_id": ...}

    Args:
        messages: List of HistoryMessage objects
        system_prompt: Optional system prompt to prepend as first message

    Returns:
        List of dicts matching OpenAI SDK format
    """
    result: list[dict] = []
    if system_prompt:
        result.append({"role": "system", "content": system_prompt})

    for msg in messages:
        if msg.role == "system" and system_prompt:
            continue
        result.append(msg.to_openai_dict())

    return result


def to_anthropic_format(
    messages: list[HistoryMessage],
    system_prompt: str | None = None,
) -> tuple[str | list, list[dict]]:
    """Convert HistoryMessage list to Anthropic Messages API format.

    System prompt is returned separately (Anthropic API has a top-level
    system parameter). Tool use and tool result content blocks are
    converted appropriately.

    Args:
        messages: List of HistoryMessage objects
        system_prompt: Optional system prompt override

    Returns:
        Tuple of (system_text_or_array, anthropic_messages_list)
    """
    system_parts: list[str] = []
    anthropic_messages: list[dict] = []

    if system_prompt:
        system_parts.append(system_prompt)

    for msg in messages:
        if msg.role == "system":
            if msg.content:
                system_parts.append(str(msg.content))
            continue
        anthro_dict = msg.to_anthropic_dict()
        if anthro_dict is not None:
            anthropic_messages.append(anthro_dict)

    return "\n".join(system_parts), anthropic_messages


def from_openai_format(openai_messages: list[dict]) -> list[HistoryMessage]:
    """Parse OpenAI Chat Completions API messages into HistoryMessages."""
    return [HistoryMessage.from_openai_dict(m) for m in openai_messages]


def from_anthropic_format(
    system: str | None,
    anthropic_messages: list[dict],
) -> list[HistoryMessage]:
    """Parse Anthropic Messages API format into HistoryMessages.

    Args:
        system: System prompt text (from Anthropic's top-level system parameter)
        anthropic_messages: List of Anthropic-format message dicts

    Returns:
        List of HistoryMessage objects
    """
    result: list[HistoryMessage] = []
    if system:
        result.append(HistoryMessage(role=Role.SYSTEM.value, content=system))
    for msg in anthropic_messages:
        result.append(HistoryMessage.from_anthropic_dict(msg))
    return result


def messages_to_role_dicts(messages: list[HistoryMessage]) -> list[dict]:
    """Convert HistoryMessages to simple role dicts for LLM calls.

    This produces the standard list[dict] format with role/content/tool_calls
    that JARVIS's LLM providers expect internally, coalescing same-role messages.

    Args:
        messages: List of HistoryMessage objects

    Returns:
        List of dicts with role, content, optional tool_calls/tool_call_id
    """
    coalesced = coalesce_messages(messages)
    result: list[dict] = []
    for msg in coalesced:
        if msg.role == "system":
            continue
        d: dict = {"role": msg.role, "content": msg.content or ""}
        if msg.tool_calls:
            d["tool_calls"] = msg.tool_calls
        if msg.tool_call_id:
            d["tool_call_id"] = msg.tool_call_id
        if msg.name:
            d["name"] = msg.name
        result.append(d)
    return result


# ============================================================================
# Conversation History Storage
# ============================================================================

def find_project_history_dir(start_path: Path | None = None) -> Path | None:
    """Find the nearest project-level .jarvis/history directory by walking up.

    Searches for .jarvis/history/ in project directories (subdirectories of
    the user's home). Does NOT return ~/.jarvis/history/ — that fallback
    is handled separately by _default_history_dir().

    Args:
        start_path: Starting directory (defaults to cwd)

    Returns:
        Path to project .jarvis/history directory, or None if not found
    """
    current = (start_path or Path.cwd()).resolve()
    home = Path.home().resolve()
    for parent in [current] + list(current.parents):
        # Stop at home boundary — don't return ~/.jarvis/history here
        if parent == home:
            return None
        candidate = parent / ".jarvis" / "history"
        if candidate.is_dir():
            return candidate
    return None


class ConversationHistory:
    """
    Manages conversation history storage and retrieval.
    Uses JSONL format matching OpenAI/Anthropic SDK message format.
    Supports both per-session files (~/.jarvis/history/{session_id}.jsonl)
    and project-level .jarvis-history files.
    """

    def __init__(
        self,
        session_id: str | None = None,
        history_dir: Path | None = None,
        history_file: Path | None = None,
    ):
        """
        Initialize conversation history.

        Args:
            session_id: Optional session ID (generated if not provided)
            history_dir: Directory for history files (defaults to ~/.jarvis/history)
            history_file: Specific history file path (overrides history_dir)
        """
        self.session_id = session_id or str(uuid.uuid4())
        self.history_dir = history_dir or self._default_history_dir()
        self._history_file_override = history_file
        self._ensure_history_dir()

    def _default_history_dir(self) -> Path:
        """Get default history directory.

        Priority:
        1. Project-level .jarvis/history/ in project root (walk up from cwd)
        2. Fall back to ~/.jarvis/history/
        """
        project_dir = find_project_history_dir()
        if project_dir is not None:
            return project_dir
        return Path.home() / ".jarvis" / "history"

    def _ensure_history_dir(self) -> None:
        """Ensure history directory exists."""
        self.history_dir.mkdir(parents=True, exist_ok=True)

    def _history_file(self) -> Path:
        """Get path to this session's history file.

        If a specific history_file was provided, use it.
        Otherwise, use history_dir/{session_id}.jsonl where history_dir
        is either a project-level .jarvis/history/ or ~/.jarvis/history/.
        """
        if self._history_file_override:
            return self._history_file_override

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

        with open(self._history_file(), "a", encoding="utf-8") as f:
            f.write(json.dumps(message.to_dict(), ensure_ascii=False) + "\n")

    def append_messages(self, messages: list[HistoryMessage]) -> None:
        """Append multiple messages to history."""
        if not messages:
            return
        with open(self._history_file(), "a", encoding="utf-8") as f:
            for msg in messages:
                msg.session_id = self.session_id
                if not msg.timestamp:
                    msg.timestamp = datetime.now(timezone.utc).isoformat()
                f.write(json.dumps(msg.to_dict(), ensure_ascii=False) + "\n")

    def get_messages(self, limit: int | None = None) -> list[HistoryMessage]:
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
        with open(history_file, encoding="utf-8") as f:
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

    def get_full_history(self, coalesce: bool = True) -> list[HistoryMessage]:
        """Get all messages with optional coalescing.

        Unlike get_messages(), this always returns the complete history
        without a limit. Use this for building the LLM message context.

        Args:
            coalesce: Whether to coalesce consecutive same-role messages

        Returns:
            Full list of HistoryMessage objects (optionally coalesced)
        """
        messages = self.get_messages()
        if coalesce:
            return coalesce_messages(messages)
        return messages

    def get_sdk_messages(
        self,
        system_prompt: str | None = None,
        sdk: str = "openai",
    ) -> list[dict] | tuple[str | list, list[dict]]:
        """Get history in a specific SDK format.

        Args:
            system_prompt: System prompt to prepend (overrides existing system messages)
            sdk: Target SDK format - "openai" or "anthropic"

        Returns:
            For openai: list of message dicts
            For anthropic: tuple of (system_text, messages_list)
        """
        messages = self.get_full_history(coalesce=True)
        if sdk == "anthropic":
            return to_anthropic_format(messages, system_prompt=system_prompt)
        return to_openai_format(messages, system_prompt=system_prompt)

    def to_openai(self, system_prompt: str | None = None) -> list[dict]:
        """Get full history in OpenAI format."""
        messages = self.get_full_history(coalesce=True)
        return to_openai_format(messages, system_prompt=system_prompt)

    def to_anthropic(self, system_prompt: str | None = None) -> tuple[str | list, list[dict]]:
        """Get full history in Anthropic format."""
        messages = self.get_full_history(coalesce=True)
        return to_anthropic_format(messages, system_prompt=system_prompt)

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

    @classmethod
    def from_file(cls, path: Path) -> "ConversationHistory":
        """Load conversation history from a specific file.

        Creates a ConversationHistory instance reading from the given path.
        The session_id is derived from the filename.

        Args:
            path: Path to a .jsonl or .jarvis-history file

        Returns:
            ConversationHistory instance reading from that file
        """
        session_id = path.stem if path.suffix == ".jsonl" else str(uuid.uuid4())
        return cls(session_id=session_id, history_file=path)


# ============================================================================
# Convenience functions matching SDK format
# ============================================================================

def create_user_message(content: str | list | None, **kwargs) -> HistoryMessage:
    """Create a user message in SDK format."""
    return HistoryMessage(role=Role.USER.value, content=content, **kwargs)


def create_assistant_message(content: str | list | None, **kwargs) -> HistoryMessage:
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
    """Create an OpenAI-style tool call dict."""
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
