"""Tests for conversation history system matching OpenAI/Anthropic SDK format."""

import json
import tempfile
from pathlib import Path

import pytest

from core.history import (
    ConversationHistory,
    HistoryMessage,
    Role,
    create_user_message,
    create_assistant_message,
    create_system_message,
    create_tool_message,
    create_openai_tool_call,
    create_anthropic_tool_use,
    create_anthropic_tool_result,
)


class TestHistoryMessage:
    """Tests for HistoryMessage dataclass."""

    def test_create_user_message(self):
        """Test creating a user message in SDK format."""
        msg = create_user_message("Hello, JARVIS!")
        assert msg.role == "user"
        assert msg.content == "Hello, JARVIS!"
        assert msg.uuid != ""

    def test_create_assistant_message(self):
        """Test creating an assistant message in SDK format."""
        msg = create_assistant_message("I'm ready to help!")
        assert msg.role == "assistant"
        assert msg.content == "I'm ready to help!"

    def test_create_system_message(self):
        """Test creating a system message in SDK format."""
        msg = create_system_message("You are a helpful assistant.")
        assert msg.role == "system"
        assert msg.content == "You are a helpful assistant."

    def test_create_tool_message(self):
        """Test creating a tool result message in OpenAI format."""
        msg = create_tool_message("call_123", '{"result": "success"}')
        assert msg.role == "tool"
        assert msg.tool_call_id == "call_123"
        assert msg.content == '{"result": "success"}'

    def test_message_to_dict(self):
        """Test message serialization - matches SDK format."""
        msg = create_user_message("Test message")
        data = msg.to_dict()
        assert isinstance(data, dict)
        assert data["role"] == "user"
        assert data["content"] == "Test message"
        assert "uuid" in data
        assert "timestamp" in data

    def test_message_from_dict(self):
        """Test message deserialization from SDK format."""
        data = {
            "role": "user",
            "content": "Test",
            "uuid": "test-uuid",
            "session_id": "test-session"
        }
        msg = HistoryMessage.from_dict(data)
        assert msg.role == "user"
        assert msg.content == "Test"
        assert msg.uuid == "test-uuid"


class TestOpenAIToolCalls:
    """Tests for OpenAI SDK tool call format."""

    def test_create_openai_tool_call(self):
        """Test creating OpenAI-style tool call."""
        tool_call = create_openai_tool_call("call_123", "get_weather", {"location": "Paris"})

        assert tool_call["id"] == "call_123"
        assert tool_call["type"] == "function"
        assert tool_call["function"]["name"] == "get_weather"
        assert tool_call["function"]["arguments"] == '{"location": "Paris"}'

    def test_openai_assistant_with_tool_calls(self):
        """Test OpenAI assistant message with tool calls."""
        tool_call = create_openai_tool_call("call_123", "get_weather", {"location": "Paris"})
        msg = create_assistant_message(None, tool_calls=[tool_call])

        assert msg.role == "assistant"
        assert msg.content is None
        assert msg.tool_calls == [tool_call]
        assert msg.tool_calls is not None and len(msg.tool_calls) == 1

    def test_openai_tool_message(self):
        """Test OpenAI tool result message."""
        msg = create_tool_message("call_123", "20 degrees Celsius")

        assert msg.role == "tool"
        assert msg.tool_call_id == "call_123"
        assert msg.content == "20 degrees Celsius"


class TestAnthropicToolCalls:
    """Tests for Anthropic SDK tool call format."""

    def test_create_anthropic_tool_use(self):
        """Test creating Anthropic-style tool use."""
        tool_use = create_anthropic_tool_use("toolu_123", "get_weather", {"location": "Paris"})

        assert tool_use["type"] == "tool_use"
        assert tool_use["id"] == "toolu_123"
        assert tool_use["name"] == "get_weather"
        assert tool_use["input"] == {"location": "Paris"}

    def test_create_anthropic_tool_result(self):
        """Test creating Anthropic-style tool result."""
        result = create_anthropic_tool_result("toolu_123", "20 degrees Celsius")

        assert result["type"] == "tool_result"
        assert result["tool_use_id"] == "toolu_123"
        assert result["content"] == "20 degrees Celsius"

    def test_anthropic_assistant_with_tool_use(self):
        """Test Anthropic assistant message with tool use in content."""
        tool_use = create_anthropic_tool_use("toolu_123", "get_weather", {"location": "Paris"})
        msg = create_assistant_message([tool_use])

        assert msg.role == "assistant"
        assert isinstance(msg.content, list)
        assert len(msg.content) == 1
        assert msg.content[0]["type"] == "tool_use"

    def test_anthropic_tool_result_as_user_message(self):
        """Test Anthropic tool result as user message."""
        tool_result = create_anthropic_tool_result("toolu_123", "20 degrees Celsius")
        msg = create_user_message([tool_result])

        assert msg.role == "user"
        assert isinstance(msg.content, list)
        assert msg.content[0]["type"] == "tool_result"


class TestConversationHistory:
    """Tests for ConversationHistory class."""

    @pytest.fixture
    def temp_history_dir(self):
        """Create a temporary directory for history files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def history(self, temp_history_dir):
        """Create a ConversationHistory instance with temp directory."""
        return ConversationHistory(
            session_id="test-session-123",
            history_dir=temp_history_dir
        )

    def test_initialization(self, history, temp_history_dir):
        """Test history initialization."""
        assert history.session_id == "test-session-123"
        assert history.history_dir == temp_history_dir
        assert temp_history_dir.exists()

    def test_append_message(self, history):
        """Test appending a message to history."""
        msg = create_user_message("Hello!")
        history.append_message(msg)

        messages = history.get_messages()
        assert len(messages) == 1
        assert messages[0].content == "Hello!"
        assert messages[0].role == "user"

    def test_multiple_messages(self, history):
        """Test appending multiple messages."""
        history.append_message(create_user_message("Hello"))
        history.append_message(create_assistant_message("Hi there!"))
        history.append_message(create_user_message("How are you?"))

        messages = history.get_messages()
        assert len(messages) == 3

    def test_get_messages_empty(self, history):
        """Test getting messages when history is empty."""
        messages = history.get_messages()
        assert messages == []

    def test_get_messages_limit(self, history):
        """Test limiting number of messages returned."""
        for i in range(10):
            history.append_message(create_user_message(f"Message {i}"))

        messages = history.get_messages(limit=3)
        assert len(messages) == 3

    def test_clear_history(self, history):
        """Test clearing history."""
        history.append_message(create_user_message("Hello"))
        assert len(history.get_messages()) == 1

        history.clear_history()
        assert len(history.get_messages()) == 0

    def test_persistence(self, history):
        """Test that messages persist across instances."""
        history.append_message(create_user_message("Hello"))
        history.append_message(create_assistant_message("Hi!"))

        # Create new instance with same session ID
        new_history = ConversationHistory(
            session_id="test-session-123",
            history_dir=history.history_dir
        )
        messages = new_history.get_messages()
        assert len(messages) == 2

    def test_jsonl_format(self, history):
        """Test that history is stored as valid JSONL."""
        history.append_message(create_user_message("Test"))

        history_file = history._history_file()
        assert history_file.exists()

        with open(history_file) as f:
            line = f.readline().strip()
            data = json.loads(line)
            assert data["role"] == "user"
            assert data["content"] == "Test"

    def test_role_enum_values(self):
        """Test Role enum values match SDK format."""
        assert Role.USER.value == "user"
        assert Role.ASSISTANT.value == "assistant"
        assert Role.SYSTEM.value == "system"
        assert Role.TOOL.value == "tool"

    def test_openai_sdk_format_compatibility(self):
        """Test OpenAI SDK format compatibility."""
        # OpenAI expects: [{"role": "user", "content": "..."}, ...]
        msg = create_user_message("Hello")
        data = msg.to_dict()

        assert data["role"] == "user"
        assert isinstance(data["content"], str)

    def test_anthropic_sdk_format_compatibility(self):
        """Test Anthropic SDK format compatibility."""
        # Anthropic expects: {"role": "user", "content": [...]}
        tool_result = create_anthropic_tool_result("toolu_123", "result")
        msg = create_user_message([tool_result])
        data = msg.to_dict()

        assert data["role"] == "user"
        assert isinstance(data["content"], list)


class TestSDKFormatCompatibility:
    """Tests for OpenAI/Anthropic SDK format compatibility."""

    def test_openai_tool_call_format(self):
        """Test OpenAI tool call format matches SDK."""
        tool_call = create_openai_tool_call("call_123", "get_weather", {"location": "Paris"})

        # OpenAI SDK expects: {"id": "...", "type": "function", "function": {"name": "...", "arguments": "..."}}
        assert "id" in tool_call
        assert "type" in tool_call
        assert "function" in tool_call
        assert tool_call["type"] == "function"

    def test_anthropic_tool_use_format(self):
        """Test Anthropic tool use format matches SDK."""
        tool_use = create_anthropic_tool_use("toolu_123", "get_weather", {"location": "Paris"})

        # Anthropic SDK expects: {"type": "tool_use", "id": "...", "name": "...", "input": {...}}
        assert tool_use["type"] == "tool_use"
        assert "id" in tool_use
        assert "name" in tool_use
        assert "input" in tool_use