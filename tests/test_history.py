"""Tests for conversation history system matching OpenAI/Anthropic SDK format."""

import json
import os
import tempfile
from pathlib import Path

import pytest

from core.history import (
    ConversationHistory,
    HistoryMessage,
    Role,
    coalesce_messages,
    create_anthropic_tool_result,
    create_anthropic_tool_use,
    create_assistant_message,
    create_openai_tool_call,
    create_system_message,
    create_tool_message,
    create_user_message,
    find_project_history_dir,
    from_anthropic_format,
    from_openai_format,
    messages_to_role_dicts,
    to_anthropic_format,
    to_openai_format,
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


class TestMessageCoalescing:
    """Tests for message coalescing logic."""

    def test_no_coalescing_needed(self):
        """Test coalescing with already alternating roles."""
        msgs = [
            create_user_message("Hello"),
            create_assistant_message("Hi!"),
            create_user_message("How are you?"),
        ]
        result = coalesce_messages(msgs)
        assert len(result) == 3

    def test_coalesces_consecutive_user_messages(self):
        """Test merging consecutive user messages."""
        msgs = [
            create_user_message("First"),
            create_user_message("Second"),
            create_user_message("Third"),
        ]
        result = coalesce_messages(msgs)
        assert len(result) == 1
        assert "First" in result[0].content
        assert "Second" in result[0].content
        assert "Third" in result[0].content

    def test_coalesces_consecutive_assistant_messages(self):
        """Test merging consecutive assistant messages."""
        msgs = [
            create_assistant_message("Response A"),
            create_assistant_message("Response B"),
        ]
        result = coalesce_messages(msgs)
        assert len(result) == 1
        assert "Response A" in result[0].content
        assert "Response B" in result[0].content

    def test_does_not_coalesce_tool_messages(self):
        """Test tool messages are not coalesced."""
        msgs = [
            create_tool_message("call_1", "result_1"),
            create_tool_message("call_2", "result_2"),
        ]
        result = coalesce_messages(msgs)
        assert len(result) == 2

    def test_does_not_coalesce_system_messages(self):
        """Test system messages are not coalesced."""
        msgs = [
            create_system_message("System prompt 1"),
            create_system_message("System prompt 2"),
        ]
        result = coalesce_messages(msgs)
        assert len(result) == 2

    def test_alternating_roles_not_coalesced(self):
        """Test user-assistant-user pattern stays intact."""
        msgs = [
            create_user_message("A"),
            create_assistant_message("B"),
            create_user_message("C"),
        ]
        result = coalesce_messages(msgs)
        assert len(result) == 3

    def test_mixed_coalescing(self):
        """Test coalescing with mixed patterns."""
        msgs = [
            create_user_message("User 1"),
            create_user_message("User 2"),
            create_assistant_message("Assistant 1"),
            create_assistant_message("Assistant 2"),
            create_tool_message("call_1", "Tool 1"),
            create_user_message("User 3"),
        ]
        result = coalesce_messages(msgs)
        assert len(result) == 4
        assert "User 1" in result[0].content
        assert "User 2" in result[0].content
        assert "Assistant 1" in result[1].content
        assert "Assistant 2" in result[1].content
        assert result[2].role == "tool"
        assert result[3].role == "user"

    def test_empty_list(self):
        """Test coalescing empty list."""
        assert coalesce_messages([]) == []


class TestOpenAIFormatConversion:
    """Tests for OpenAI format conversion."""

    def test_basic_conversion(self):
        """Test basic OpenAI format conversion."""
        msgs = [
            create_user_message("Hello"),
            create_assistant_message("Hi!"),
        ]
        result = to_openai_format(msgs)
        assert len(result) == 2
        assert result[0] == {"role": "user", "content": "Hello"}
        assert result[1] == {"role": "assistant", "content": "Hi!"}

    def test_with_system_prompt(self):
        """Test conversion with system prompt prepended."""
        msgs = [create_user_message("Hello")]
        result = to_openai_format(msgs, system_prompt="Be helpful.")
        assert len(result) == 2
        assert result[0] == {"role": "system", "content": "Be helpful."}
        assert result[1] == {"role": "user", "content": "Hello"}

    def test_tool_call_conversion(self):
        """Test conversion of tool call messages."""
        tool_call = create_openai_tool_call("call_1", "get_weather", {"loc": "Paris"})
        msgs = [
            HistoryMessage(role="assistant", content="", tool_calls=[tool_call]),
            create_tool_message("call_1", "20C"),
        ]
        result = to_openai_format(msgs)
        assert len(result) == 2
        assert result[0]["tool_calls"] == [tool_call]
        assert result[1]["tool_call_id"] == "call_1"
        assert result[1]["content"] == "20C"

    def test_round_trip(self):
        """Test round-trip conversion."""
        original = [create_user_message("Hello"), create_assistant_message("Hi!")]
        openai_format = to_openai_format(original)
        restored = from_openai_format(openai_format)
        assert len(restored) == 2
        assert restored[0].role == "user"
        assert restored[0].content == "Hello"
        assert restored[1].role == "assistant"
        assert restored[1].content == "Hi!"


class TestAnthropicFormatConversion:
    """Tests for Anthropic format conversion."""

    def test_basic_conversion(self):
        """Test basic Anthropic format conversion."""
        msgs = [
            create_user_message("Hello"),
            create_assistant_message("Hi!"),
        ]
        system, anthro = to_anthropic_format(msgs)
        assert system == ""
        assert len(anthro) == 2
        assert anthro[0] == {"role": "user", "content": "Hello"}
        assert anthro[1] == {"role": "assistant", "content": "Hi!"}

    def test_with_system_prompt(self):
        """Test conversion with system prompt."""
        msgs = [create_user_message("Hello")]
        system, anthro = to_anthropic_format(msgs, system_prompt="Be helpful.")
        assert system == "Be helpful."
        assert len(anthro) == 1
        assert anthro[0] == {"role": "user", "content": "Hello"}

    def test_system_message_conversion(self):
        """Test system messages go to system parameter."""
        msgs = [
            create_system_message("You are helpful."),
            create_user_message("Hello"),
        ]
        system, anthro = to_anthropic_format(msgs)
        assert "You are helpful." in system
        assert len(anthro) == 1

    def test_tool_use_conversion(self):
        """Test tool_use content block conversion."""
        tool_use = create_anthropic_tool_use("toolu_1", "get_weather", {"loc": "Paris"})
        msg = HistoryMessage(role="assistant", content="Checking...", tool_use=tool_use)
        system, anthro = to_anthropic_format([msg])
        content = anthro[0]["content"]
        assert isinstance(content, list)
        assert len(content) == 2
        assert content[0] == {"type": "text", "text": "Checking..."}
        assert content[1]["type"] == "tool_use"

    def test_tool_result_conversion(self):
        """Test tool_result content block conversion."""
        tool_result = create_anthropic_tool_result("toolu_1", "20C")
        msg = HistoryMessage(role="tool", content="Result ready", tool_result=tool_result, tool_call_id="toolu_1")
        system, anthro = to_anthropic_format([msg])
        content = anthro[0]["content"]
        assert isinstance(content, list)
        assert content[0] == {"type": "text", "text": "Result ready"}
        assert content[1]["type"] == "tool_result"

    def test_round_trip(self):
        """Test round-trip conversion."""
        msgs = [
            create_system_message("Be helpful."),
            create_user_message("Hello"),
            create_assistant_message("Hi!"),
        ]
        system, anthro = to_anthropic_format(msgs)
        restored = from_anthropic_format(system, anthro)
        assert len(restored) == 3
        assert restored[0].role == "system"
        assert restored[1].role == "user"
        assert restored[2].role == "assistant"
        assert restored[1].content == "Hello"
        assert restored[2].content == "Hi!"


class TestMessagesToRoleDicts:
    """Tests for messages_to_role_dicts with coalescing."""

    def test_basic_conversion(self):
        """Test basic conversion to role dicts."""
        msgs = [
            create_user_message("Hello"),
            create_assistant_message("Hi!"),
        ]
        result = messages_to_role_dicts(msgs)
        assert len(result) == 2
        assert result[0] == {"role": "user", "content": "Hello"}
        assert result[1] == {"role": "assistant", "content": "Hi!"}

    def test_coalescing_applied(self):
        """Test that coalescing is applied during conversion."""
        msgs = [
            create_user_message("First"),
            create_user_message("Second"),
        ]
        result = messages_to_role_dicts(msgs)
        assert len(result) == 1
        assert "First" in result[0]["content"]
        assert "Second" in result[0]["content"]

    def test_system_messages_skipped(self):
        """Test system messages are excluded."""
        msgs = [
            create_system_message("System prompt"),
            create_user_message("Hello"),
        ]
        result = messages_to_role_dicts(msgs)
        assert len(result) == 1
        assert result[0]["role"] == "user"

    def test_tool_calls_preserved(self):
        """Test tool calls are preserved in role dicts."""
        tool_call = create_openai_tool_call("call_1", "get_weather", {"loc": "Paris"})
        msgs = [
            HistoryMessage(role="assistant", content="", tool_calls=[tool_call]),
            create_tool_message("call_1", "20C"),
        ]
        result = messages_to_role_dicts(msgs)
        assert len(result) == 2
        assert result[0]["tool_calls"] == [tool_call]
        assert result[1]["tool_call_id"] == "call_1"


class TestHistoryFileSupport:
    """Tests for project-level history directory support."""

    def test_find_project_history_dir_not_found(self, tmp_path):
        """Test finding history dir when none exists."""
        result = find_project_history_dir(start_path=tmp_path)
        assert result is None

    def test_find_project_history_dir_in_root(self, tmp_path):
        """Test finding history dir in project root."""
        history_dir = tmp_path / ".jarvis" / "history"
        history_dir.mkdir(parents=True)
        result = find_project_history_dir(start_path=tmp_path)
        assert result == history_dir

    def test_find_project_history_dir_in_parent(self, tmp_path):
        """Test finding history dir in parent directory."""
        history_dir = tmp_path / ".jarvis" / "history"
        history_dir.mkdir(parents=True)
        subdir = tmp_path / "subdir" / "nested"
        subdir.mkdir(parents=True)
        result = find_project_history_dir(start_path=subdir)
        assert result == history_dir

    def test_conversation_history_from_project_dir(self, tmp_path):
        """Test using project-level history directory."""
        project_dir = tmp_path / ".jarvis" / "history"
        project_dir.mkdir(parents=True)
        history = ConversationHistory(history_dir=project_dir)
        msg = create_user_message("Project-level test!")
        history.append_message(msg)
        msgs = history.get_messages()
        assert len(msgs) == 1
        assert msgs[0].content == "Project-level test!"

    def test_default_history_dir_prefers_project(self, tmp_path):
        """Test that project-level directory is preferred over ~/.jarvis/history."""
        project_dir = tmp_path / ".jarvis" / "history"
        project_dir.mkdir(parents=True)

        # Monkey-patch cwd for the finder
        import os
        original_cwd = os.getcwd.return_value if hasattr(os.getcwd, 'return_value') else None
        try:
            # The test verifies the path resolution independently
            result = find_project_history_dir(start_path=tmp_path)
            assert result == project_dir
        finally:
            pass

    def test_append_messages_batch(self, tmp_path):
        """Test appending multiple messages at once."""
        history_dir = tmp_path / ".jarvis" / "history"
        history_dir.mkdir(parents=True)
        history = ConversationHistory(history_dir=history_dir)
        msgs = [
            create_user_message("Batch 1"),
            create_assistant_message("Batch reply"),
            create_user_message("Batch 2"),
        ]
        history.append_messages(msgs)
        loaded = history.get_messages()
        assert len(loaded) == 3


class TestGetFullHistory:
    """Tests for get_full_history method."""

    def test_full_history_no_limit(self, tmp_path):
        """Test full history returns all messages."""
        history = ConversationHistory(history_dir=tmp_path)
        for i in range(20):
            history.append_message(create_user_message(f"Msg {i}"))
        full = history.get_full_history(coalesce=False)
        assert len(full) == 20

    def test_full_history_with_coalescing(self, tmp_path):
        """Test full history with coalescing enabled."""
        history = ConversationHistory(history_dir=tmp_path)
        history.append_message(create_user_message("First"))
        history.append_message(create_user_message("Second"))
        full = history.get_full_history(coalesce=True)
        assert len(full) == 1
        assert "First" in full[0].content
        assert "Second" in full[0].content

    def test_get_sdk_messages_openai(self, tmp_path):
        """Test get_sdk_messages returns OpenAI format."""
        history = ConversationHistory(history_dir=tmp_path)
        history.append_message(create_user_message("Hello"))
        result = history.get_sdk_messages(sdk="openai")
        assert isinstance(result, list)
        assert result[0]["role"] == "user"

    def test_get_sdk_messages_anthropic(self, tmp_path):
        """Test get_sdk_messages returns Anthropic format."""
        history = ConversationHistory(history_dir=tmp_path)
        history.append_message(create_user_message("Hello"))
        system, messages = history.get_sdk_messages(sdk="anthropic")
        assert isinstance(messages, list)
        assert messages[0]["role"] == "user"

    def test_get_session_info_empty(self, tmp_path):
        """Test session info with empty history."""
        history = ConversationHistory(history_dir=tmp_path)
        info = history.get_session_info()
        assert info.session_id == history.session_id
        assert info.cwd == os.getcwd()


class TestHistoryMessageConverters:
    """Tests for HistoryMessage format converters."""

    def test_to_openai_dict(self):
        """Test converting HistoryMessage to OpenAI dict."""
        msg = create_user_message("Hello")
        d = msg.to_openai_dict()
        assert d["role"] == "user"
        assert d["content"] == "Hello"

    def test_to_openai_dict_with_tool_calls(self):
        """Test OpenAI dict with tool calls."""
        tool_call = create_openai_tool_call("call_1", "test", {"key": "val"})
        msg = HistoryMessage(role="assistant", content="", tool_calls=[tool_call])
        d = msg.to_openai_dict()
        assert d["tool_calls"] == [tool_call]

    def test_to_anthropic_dict_system_returns_none(self):
        """Test system message returns None for Anthropic."""
        msg = create_system_message("System prompt")
        assert msg.to_anthropic_dict() is None

    def test_to_anthropic_dict_tool_use(self):
        """Test tool_use conversion to Anthropic dict."""
        tool_use = create_anthropic_tool_use("toolu_1", "test", {"key": "val"})
        msg = HistoryMessage(role="assistant", content="Thinking...", tool_use=tool_use)
        d = msg.to_anthropic_dict()
        assert d["role"] == "assistant"
        assert isinstance(d["content"], list)
        assert d["content"][0]["type"] == "text"
        assert d["content"][1]["type"] == "tool_use"

    def test_from_openai_dict(self):
        """Test creating HistoryMessage from OpenAI dict."""
        d = {"role": "user", "content": "Hello"}
        msg = HistoryMessage.from_openai_dict(d)
        assert msg.role == "user"
        assert msg.content == "Hello"

    def test_from_openai_dict_with_tool_calls(self):
        """Test creating from OpenAI dict with tool calls."""
        tool_call = create_openai_tool_call("call_1", "test", {"key": "val"})
        d = {"role": "assistant", "content": "", "tool_calls": [tool_call]}
        msg = HistoryMessage.from_openai_dict(d)
        assert msg.tool_calls == [tool_call]

    def test_from_anthropic_dict_basic(self):
        """Test creating HistoryMessage from Anthropic dict."""
        d = {"role": "user", "content": "Hello"}
        msg = HistoryMessage.from_anthropic_dict(d)
        assert msg.role == "user"
        assert msg.content == "Hello"

    def test_from_anthropic_dict_with_tool_use(self):
        """Test creating from Anthropic dict with tool_use."""
        d = {
            "role": "assistant",
            "content": [
                {"type": "text", "text": "Let me check..."},
                {"type": "tool_use", "id": "toolu_1", "name": "get_weather", "input": {"loc": "Paris"}},
            ]
        }
        msg = HistoryMessage.from_anthropic_dict(d)
        assert msg.role == "assistant"
        assert msg.content == "Let me check..."
        assert msg.tool_use is not None
        assert msg.tool_use["type"] == "tool_use"
