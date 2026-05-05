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

    def test_sdk_format_compatibility(self):
        """Test that format matches OpenAI/Anthropic SDK expectations."""
        # OpenAI format: {"role": "user", "content": "Hello"}
        msg = create_user_message("Hello")
        data = msg.to_dict()

        assert "role" in data
        assert data["role"] == "user"
        assert "content" in data
        assert isinstance(data["content"], str)


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
        assert messages[0].content == "Hello"
        assert messages[1].content == "Hi there!"
        assert messages[2].content == "How are you?"

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
        assert messages[0].content == "Message 7"
        assert messages[2].content == "Message 9"

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


class TestSDKFormatCompatibility:
    """Tests for OpenAI/Anthropic SDK format compatibility."""

    def test_openai_format(self):
        """Test compatibility with OpenAI chat completions format."""
        # OpenAI expects: [{"role": "user", "content": "..."}, ...]
        msg = create_user_message("What is the meaning of life?")
        data = msg.to_dict()

        assert data["role"] == "user"
        assert isinstance(data["content"], str)

    def test_anthropic_format(self):
        """Test compatibility with Anthropic Messages API format."""
        # Anthropic expects: {"role": "user", "content": "..."}
        msg = create_user_message("Hello Claude")
        data = msg.to_dict()

        assert data["role"] == "user"
        assert isinstance(data["content"], str)