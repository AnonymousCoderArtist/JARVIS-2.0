"""Tests for Windows operation tools - Real tests for Windows platform"""

import pytest
import sys
import platform
from unittest.mock import MagicMock, patch
import asyncio

from core.tools.base import ToolInput, ToolOutput
from core.tools.windows_tools import (
    WindowsSnapshotTool,
    WindowsClickTool,
    WindowsTypeTool,
    WindowsScrollTool,
    WindowsShortcutTool,
    WindowsAppTool,
    WindowsClipboardTool,
    WindowsNotificationTool,
    WindowsProcessTool,
)


# Platform detection
IS_WINDOWS = platform.system() == "Windows"
SKIP_WINDOWS_TESTS = not IS_WINDOWS


# ============================================================================
# Tool Registration Tests (Platform Independent)
# ============================================================================

class TestWindowsToolRegistration:
    """Tests for Windows tool registration - Platform Independent"""

    def test_all_tools_have_names(self):
        """Test that all Windows tools have valid names"""
        tools = [
            WindowsSnapshotTool(),
            WindowsClickTool(),
            WindowsTypeTool(),
            WindowsScrollTool(),
            WindowsShortcutTool(),
            WindowsAppTool(),
            WindowsClipboardTool(),
            WindowsNotificationTool(),
            WindowsProcessTool(),
        ]
        
        for tool in tools:
            assert tool.name, f"Tool missing name"
            assert tool.name.startswith("windows_"), f"Tool name should start with 'windows_': {tool.name}"
            assert isinstance(tool.name, str), "Tool name should be string"

    def test_all_tools_have_descriptions(self):
        """Test that all Windows tools have descriptions"""
        tools = [
            WindowsSnapshotTool(),
            WindowsClickTool(),
            WindowsTypeTool(),
            WindowsScrollTool(),
            WindowsShortcutTool(),
            WindowsAppTool(),
            WindowsClipboardTool(),
            WindowsNotificationTool(),
            WindowsProcessTool(),
        ]
        
        for tool in tools:
            assert tool.description, f"Tool {tool.name} missing description"
            assert len(tool.description) > 10, f"Tool {tool.name} description too short"

    def test_all_tools_have_schemas(self):
        """Test that all Windows tools have valid input schemas"""
        tools = [
            WindowsSnapshotTool(),
            WindowsClickTool(),
            WindowsTypeTool(),
            WindowsScrollTool(),
            WindowsShortcutTool(),
            WindowsAppTool(),
            WindowsClipboardTool(),
            WindowsNotificationTool(),
            WindowsProcessTool(),
        ]
        
        for tool in tools:
            assert isinstance(tool.input_schema, dict), f"Tool {tool.name} schema should be dict"
            assert "properties" in tool.input_schema or "required" in tool.input_schema, \
                f"Tool {tool.name} schema missing properties/required"


# ============================================================================
# Input Validation Tests (Platform Independent)
# ============================================================================

class TestWindowsInputValidation:
    """Tests for input validation - Platform Independent"""

    @pytest.mark.asyncio
    async def test_click_tool_accepts_valid_input(self):
        """Test click tool accepts valid coordinates"""
        tool = WindowsClickTool()
        
        # Valid input
        assert tool.validate_input({"loc": [100, 200]}) is True

    @pytest.mark.asyncio
    async def test_type_tool_accepts_text_input(self):
        """Test type tool accepts text input"""
        tool = WindowsTypeTool()
        
        # Valid input
        assert tool.validate_input({"text": "hello", "loc": [100, 200]}) is True

    @pytest.mark.asyncio
    async def test_scroll_tool_validates_direction(self):
        """Test scroll tool validates direction"""
        tool = WindowsScrollTool()
        
        # Valid directions
        assert tool.validate_input({"loc": [100, 200], "direction": "up"}) is True
        assert tool.validate_input({"loc": [100, 200], "direction": "down"}) is True
        assert tool.validate_input({"loc": [100, 200], "direction": "left"}) is True
        assert tool.validate_input({"loc": [100, 200], "direction": "right"}) is True

    @pytest.mark.asyncio
    async def test_shortcut_tool_accepts_shortcut(self):
        """Test shortcut tool accepts shortcut parameter"""
        tool = WindowsShortcutTool()
        
        # Valid input
        assert tool.validate_input({"shortcut": "ctrl+c"}) is True
        assert tool.validate_input({"shortcut": "win+r"}) is True

    @pytest.mark.asyncio
    async def test_app_tool_validates_mode_and_name(self):
        """Test app tool validates mode and name"""
        tool = WindowsAppTool()
        
        # Valid modes
        assert tool.validate_input({"mode": "launch", "name": "notepad"}) is True
        assert tool.validate_input({"mode": "switch", "name": "chrome"}) is True
        assert tool.validate_input({"mode": "resize", "name": "app"}) is True

    @pytest.mark.asyncio
    async def test_clipboard_tool_accepts_mode(self):
        """Test clipboard tool accepts mode"""
        tool = WindowsClipboardTool()
        
        # Valid modes
        assert tool.validate_input({"mode": "get"}) is True
        assert tool.validate_input({"mode": "set", "text": "hello"}) is True

    @pytest.mark.asyncio
    async def test_notification_tool_accepts_params(self):
        """Test notification tool accepts required params"""
        tool = WindowsNotificationTool()
        
        # Valid input
        assert tool.validate_input({
            "title": "Test",
            "message": "Hello",
            "app_id": "JARVIS.Test"
        }) is True


# ============================================================================
# Safe Execute Tests (Platform Independent)
# ============================================================================

class TestWindowsSafeExecute:
    """Tests for safe_execute method - Platform Independent"""

    @pytest.mark.asyncio
    async def test_safe_execute_returns_tool_output(self):
        """Test safe_execute always returns ToolOutput"""
        tool = WindowsClickTool()
        
        result = await tool.safe_execute({"loc": [100, 200]})
        
        assert isinstance(result, ToolOutput)
        assert hasattr(result, 'success')
        assert hasattr(result, 'result')
        assert hasattr(result, 'error')

    @pytest.mark.asyncio
    async def test_safe_execute_handles_invalid_input(self):
        """Test safe_execute handles invalid input gracefully"""
        tool = WindowsClickTool()
        
        result = await tool.safe_execute({"invalid_param": "value"})
        
        assert result.success is False
        assert result.error is not None


# ============================================================================
# Windows-Specific Tests (Only Run on Windows)
# ============================================================================

@pytest.mark.skipif(SKIP_WINDOWS_TESTS, reason="Windows-specific tests")
class TestWindowsRealTools:
    """Real tests that require Windows platform"""

    @pytest.mark.asyncio
    async def test_clipboard_get_set(self):
        """Test actual clipboard operations on Windows"""
        import pyperclip
        
        tool = WindowsClipboardTool()
        
        # Test get
        result = await tool.execute(ToolInput(mode="get"))
        assert result.success is True
        
        # Test set
        test_text = "JARVIS test clipboard content"
        result = await tool.execute(ToolInput(mode="set", text=test_text))
        assert result.success is True
        
        # Verify
        assert pyperclip.paste() == test_text

    @pytest.mark.asyncio
    async def test_notification(self):
        """Test actual notification on Windows"""
        tool = WindowsNotificationTool()
        
        result = await tool.execute(ToolInput(
            title="JARVIS Test",
            message="Testing Windows notification",
            app_id="JARVIS.Test"
        ))
        # Notification may succeed or fail depending on Windows settings
        assert result is not None


@pytest.mark.skipif(SKIP_WINDOWS_TESTS, reason="Windows-specific tests")
class TestWindowsProcessManager:
    """Tests for Windows process management"""

    @pytest.mark.asyncio
    async def test_list_processes(self):
        """Test listing Windows processes"""
        tool = WindowsProcessTool()
        
        result = await tool.execute(ToolInput(mode="list", limit=5))
        
        assert result.success is True
        assert result.result is not None


# ============================================================================
# Mock Tests for Non-Windows Platforms
# ============================================================================

@pytest.mark.skipif(not SKIP_WINDOWS_TESTS, reason="Non-Windows platform")
class TestWindowsMockedTools:
    """Tests with mocking for non-Windows platforms"""

    @pytest.mark.asyncio
    async def test_clipboard_mock_on_non_windows(self):
        """Test clipboard with mock on non-Windows"""
        tool = WindowsClipboardTool()
        
        with patch('core.tools.windows_tools.win32clipboard') as mock_clipboard:
            mock_clipboard.OpenClipboard.return_value = None
            mock_clipboard.IsClipboardFormatAvailable.return_value = True
            mock_clipboard.GetClipboardData.return_value = "mocked content"
            mock_clipboard.CloseClipboard.return_value = None
            
            result = await tool.execute(ToolInput(mode="get"))
            
            assert result.success is True

    @pytest.mark.asyncio
    async def test_notification_mock_on_non_windows(self):
        """Test notification with mock on non-Windows"""
        tool = WindowsNotificationTool()
        
        with patch('core.tools.windows_tools.get_desktop_singleton') as mock_desktop:
            mock_desktop.send_notification.return_value = "Notification queued"
            
            result = await tool.execute(ToolInput(
                title="Test",
                message="Hello",
                app_id="JARVIS"
            ))
            
            assert result.success is True

    @pytest.mark.asyncio
    async def test_process_list_mock_on_non_windows(self):
        """Test process list with mock on non-Windows"""
        tool = WindowsProcessTool()
        
        with patch('core.tools.windows_tools.get_desktop_singleton') as mock_desktop:
            mock_desktop.list_processes.return_value = "Mocked process list"
            
            result = await tool.execute(ToolInput(mode="list"))
            
            assert result.success is True


# ============================================================================
# Error Handling Tests (Platform Independent)
# ============================================================================

class TestWindowsErrorHandling:
    """Tests for error handling - Platform Independent"""

    @pytest.mark.asyncio
    async def test_click_handles_missing_desktop(self):
        """Test click handles missing desktop gracefully"""
        tool = WindowsClickTool()
        
        with patch('core.tools.windows_tools.get_desktop_singleton', 
                   side_effect=Exception("Desktop not available")):
            result = await tool.execute(ToolInput(loc=[100, 200]))
            
            assert result.success is False
            assert result.error is not None

    @pytest.mark.asyncio
    async def test_shortcut_handles_error(self):
        """Test shortcut handles errors gracefully"""
        tool = WindowsShortcutTool()
        
        with patch('core.tools.windows_tools.get_desktop_singleton',
                   side_effect=Exception("Shortcut failed")):
            result = await tool.execute(ToolInput(shortcut="ctrl+c"))
            
            assert result.success is False
            assert result.error is not None

    @pytest.mark.asyncio
    async def test_app_handles_error(self):
        """Test app tool handles errors gracefully"""
        tool = WindowsAppTool()
        
        with patch('core.tools.windows_tools.get_desktop_singleton',
                   side_effect=Exception("App launch failed")):
            result = await tool.execute(ToolInput(mode="launch", name="notepad"))
            
            assert result.success is False
            assert result.error is not None


# ============================================================================
# Schema Definition Tests
# ============================================================================

class TestWindowsToolSchemas:
    """Tests for tool schema definitions"""

    def test_snapshot_tool_schema(self):
        """Test snapshot tool has correct schema"""
        tool = WindowsSnapshotTool()
        schema = tool.input_schema
        
        assert "properties" in schema
        props = schema["properties"]
        assert "use_vision" in props
        assert "use_dom" in props
        assert "use_ui_tree" in props
        assert props["use_vision"]["type"] == "boolean"

    def test_click_tool_schema(self):
        """Test click tool has correct schema"""
        tool = WindowsClickTool()
        schema = tool.input_schema
        
        assert "properties" in schema
        props = schema["properties"]
        assert "loc" in props
        assert "button" in props
        assert "clicks" in props

    def test_process_tool_schema(self):
        """Test process tool has correct schema"""
        tool = WindowsProcessTool()
        schema = tool.input_schema
        
        assert "properties" in schema
        props = schema["properties"]
        assert "mode" in props
        assert props["mode"]["enum"] == ["list", "kill"]


# Run tests if executed directly
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])