"""
Tests for text-embedded tool call handling.
"""

import os
import sys

import pytest

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jarvis.core.llm_sdk.tool_parser import (
    extract_text_and_tool_calls,
    extract_tool_calls_from_text,
    has_text_tool_calls,
    normalize_tool_calls,
)


class TestHasTextToolCalls:
    """Tests for has_text_tool_calls function."""

    def test_no_tool_calls(self):
        content = "This is just plain text without any tool calls."
        assert has_text_tool_calls(content) is False

    def test_with_function_equals_format(self):
        content = "Let me read that file.\n<function=read><parameter name=\"path\">test.txt</parameter></function>"
        assert has_text_tool_calls(content) is True

    def test_with_function_name_format(self):
        content = '<function name="read"><parameter name="path">test.txt</parameter></function>'
        assert has_text_tool_calls(content) is True

    def test_with_self_closing_tag(self):
        content = "<function=read/>"
        assert has_text_tool_calls(content) is True


class TestExtractToolCallsFromText:
    """Tests for extract_tool_calls_from_text function."""

    def test_extract_single_tool_call(self):
        content = "I'll read that file for you.\n<function=read><parameter name=\"path\">/path/to/file.txt</parameter></function>"
        tool_calls = extract_tool_calls_from_text(content)

        assert len(tool_calls) == 1
        assert tool_calls[0]["name"] == "read"
        assert tool_calls[0]["arguments"]["path"] == "/path/to/file.txt"

    def test_extract_with_function_name_format(self):
        content = '<function name="grep"><parameter name="query">def </parameter><parameter name="path">src/</parameter></function>'
        tool_calls = extract_tool_calls_from_text(content)

        assert len(tool_calls) == 1
        assert tool_calls[0]["name"] == "grep"
        assert tool_calls[0]["arguments"]["query"] == "def "
        assert tool_calls[0]["arguments"]["path"] == "src/"

    def test_extract_multiple_tool_calls(self):
        content = """
        I'll read those files for you.
        <function=read><parameter name="path">file1.txt</parameter></function>
        <function=read><parameter name="path">file2.txt</parameter></function>
        """
        tool_calls = extract_tool_calls_from_text(content)

        assert len(tool_calls) == 2
        assert tool_calls[0]["arguments"]["path"] == "file1.txt"
        assert tool_calls[1]["arguments"]["path"] == "file2.txt"

    def test_extract_with_json_value(self):
        content = '<function=write><parameter name="path">test.txt</parameter><parameter name="content">{"key": "value"}</parameter></function>'
        tool_calls = extract_tool_calls_from_text(content)

        assert len(tool_calls) == 1
        assert tool_calls[0]["name"] == "write"
        assert tool_calls[0]["arguments"]["path"] == "test.txt"
        # JSON value should be parsed
        assert tool_calls[0]["arguments"]["content"] == '{"key": "value"}'

    def test_no_tool_calls(self):
        content = "This is just a regular response without any tool calls."
        tool_calls = extract_tool_calls_from_text(content)
        assert len(tool_calls) == 0

    def test_with_multiline_content(self):
        content = """I'll help you with that.
<function=read>
<parameter name="path">/some/long/path/to/file.txt</parameter>
</function>
Let me do that..."""
        tool_calls = extract_tool_calls_from_text(content)

        assert len(tool_calls) == 1
        assert tool_calls[0]["name"] == "read"
        assert tool_calls[0]["arguments"]["path"] == "/some/long/path/to/file.txt"


class TestNormalizeToolCalls:
    """Tests for normalize_tool_calls function."""

    def test_normalize_simple(self):
        tool_calls = [
            {"name": "read", "arguments": {"path": "test.txt"}}
        ]
        normalized = normalize_tool_calls(tool_calls)

        assert len(normalized) == 1
        assert normalized[0]["name"] == "read"
        assert isinstance(normalized[0]["arguments"], str)
        assert '"path"' in normalized[0]["arguments"]

    def test_normalize_multiple(self):
        tool_calls = [
            {"name": "read", "arguments": {"path": "file1.txt"}},
            {"name": "grep", "arguments": {"query": "test"}}
        ]
        normalized = normalize_tool_calls(tool_calls)

        assert len(normalized) == 2
        assert normalized[0]["name"] == "read"
        assert normalized[1]["name"] == "grep"


class TestExtractTextAndToolCalls:
    """Tests for extract_text_and_tool_calls function."""

    def test_extract_both(self):
        content = """I'll read that file for you.

<function=read><parameter name="path">test.txt</parameter></function>

Let me do that..."""
        cleaned, tool_calls = extract_text_and_tool_calls(content)

        assert "I'll read that file for you." in cleaned
        assert "Let me do that..." in cleaned
        assert "<function" not in cleaned
        assert len(tool_calls) == 1
        assert tool_calls[0]["name"] == "read"

    def test_no_tool_calls(self):
        content = "Just a regular text response."
        cleaned, tool_calls = extract_text_and_tool_calls(content)

        assert cleaned == content
        assert len(tool_calls) == 0

    def test_only_tool_calls(self):
        content = "<function=read><parameter name=\"path\">test.txt</parameter></function>"
        cleaned, tool_calls = extract_text_and_tool_calls(content)

        assert cleaned == ""
        assert len(tool_calls) == 1


class TestIntegrationWithMockResponse:
    """Integration tests simulating real LLM responses."""

    def test_mock_response_with_text_tool_call(self):
        # Simulate a model response with embedded tool call
        mock_response = """I'll read that file for you.

<function=read>
<parameter name="path">/path/to/test.txt</parameter>
</function>

Let me do that..."""

        assert has_text_tool_calls(mock_response) is True

        cleaned, tool_calls = extract_text_and_tool_calls(mock_response)
        normalized = normalize_tool_calls(tool_calls)

        assert len(normalized) == 1
        assert normalized[0]["name"] == "read"

        # Verify the arguments can be parsed back to dict
        import json
        args = json.loads(normalized[0]["arguments"])
        assert args["path"] == "/path/to/test.txt"

    def test_multiple_tool_calls_in_response(self):
        mock_response = """I'll search for those patterns.

<function=grep>
<parameter name="query">class </parameter>
<parameter name="path">src/</parameter>
</function>

And also read this file:

<function=read>
<parameter name="path">README.md</parameter>
</function>"""

        tool_calls = extract_tool_calls_from_text(mock_response)
        assert len(tool_calls) == 2
        assert tool_calls[0]["name"] == "grep"
        assert tool_calls[1]["name"] == "read"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
