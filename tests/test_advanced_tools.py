"""Test advanced tool system features"""

import tempfile
from pathlib import Path

import pytest

from core.tools.base import ToolInput
from core.tools.code_tools import BashTool
from core.tools.file_state import current_file_states
from core.tools.file_tools import FileReadTool, FileWriteTool
from core.tools.web_tools import ExaWebSearchTool


class TestFileState:
    """Test file state tracking system"""

    def test_file_state_tracking(self):
        """Test that file read/write operations are tracked"""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.txt"
            test_file.write_text("Hello, World!")

            # Test initial state
            state = current_file_states.get(str(test_file))
            assert state is None

            # Test record read
            current_file_states.record_read(str(test_file), offset=1, limit=10)
            state = current_file_states.get(str(test_file))
            assert state is not None
            assert state.offset == 1
            assert state.limit == 10

            # Test record write
            current_file_states.record_write(str(test_file))
            state = current_file_states.get(str(test_file))
            assert state is not None
            assert state.can_dedup is False

    def test_file_modification_detection(self):
        """Test that file modifications are detected"""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.txt"
            test_file.write_text("Original content")

            # Record initial read
            current_file_states.record_read(str(test_file))

            # Check should pass for unchanged file
            warning = current_file_states.check_read(str(test_file))
            assert warning is None

            # Modify file
            test_file.write_text("Modified content")

            # Check should detect modification
            warning = current_file_states.check_read(str(test_file))
            assert warning is not None
            assert "modified" in warning.lower()


class TestFileTools:
    """Test enhanced file tools"""

    async def test_file_read_deduplication(self):
        """Test file read deduplication"""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.txt"
            test_file.write_text("Line 1\nLine 2\nLine 3\nLine 4\nLine 5")

            tool = FileReadTool()

            # First read
            input_data = ToolInput(
                files=[{"filePath": str(test_file), "offset": 1, "limit": 3}]
            )
            result1 = await tool.execute(input_data)
            assert result1.success
            assert "Line 1" in result1.result

            # Second read (should be deduplicated)
            result2 = await tool.execute(input_data)
            assert result2.success
            assert "unchanged since last read" in result2.result.lower()

    async def test_file_write_state_tracking(self):
        """Test that file writes are tracked"""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "new_file.txt"

            tool = FileWriteTool()
            input_data = ToolInput(
                filePath=str(test_file),
                content="New content"
            )
            result = await tool.execute(input_data)
            assert result.success
            assert test_file.exists()

            # Check that write was recorded
            state = current_file_states.get(str(test_file))
            assert state is not None
            assert state.can_dedup is False


class TestBashTool:
    """Test enhanced bash tool"""

    async def test_command_guard(self):
        """Test that dangerous commands require approval"""
        tool = BashTool()

        # Test dangerous command - use mkfs which should be caught by pattern matching
        input_data = ToolInput(command="mkfs.ext4 /dev/sda1")

        # Test the permission resolution - should require approval
        permission_result = tool.resolve_permission({"command": "mkfs.ext4 /dev/sda1"})

        # Should require ASK permission for dangerous commands
        assert permission_result is not None
        assert permission_result.permission == "ask"
        assert len(permission_result.required_permissions) > 0
        assert "mkfs" in permission_result.required_permissions[0].label

    async def test_workspace_restriction(self):
        """Test workspace restriction feature"""
        tool = BashTool()
        tool.restrict_to_workspace = True

        # Test command with absolute path outside workspace
        input_data = ToolInput(command="cat /etc/passwd")
        result = await tool.execute(input_data)
        assert not result.success
        assert result.error and "working directory" in result.error.lower()

    async def test_safe_command(self):
        """Test that safe commands work"""
        tool = BashTool()

        # Test safe command
        input_data = ToolInput(command="echo 'Hello, World!'")
        result = await tool.execute(input_data)
        assert result.success
        assert "Hello, World!" in result.result


class TestWebSearchTool:
    """Test enhanced web search tool"""

    async def test_query_validation(self):
        """Test query validation"""
        tool = ExaWebSearchTool()

        # Test empty query
        input_data = ToolInput(query="")
        result = await tool.execute(input_data)
        assert not result.success
        assert result.error and "empty" in result.error.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
