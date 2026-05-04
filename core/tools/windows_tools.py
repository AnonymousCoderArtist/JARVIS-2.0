"""Windows operation tools - Integrated as native JARVIS tools"""

import os
import time
import logging
from typing import Any, Literal
from functools import lru_cache

from .base import BaseTool, ToolInput, ToolOutput
from core.windows.desktop.service import Desktop
from core.windows.watchdog.service import WatchDog
from core.windows.tools._snapshot_helpers import (
    _as_bool,
    capture_desktop_state,
    build_snapshot_response,
)
from core.windows import WINDOWS_DATA_DIR

logger = logging.getLogger(__name__)

# Analytics is optional
_analytics = None


@lru_cache(maxsize=1)
def get_desktop_singleton():
    """Get or create the Desktop service singleton"""
    return Desktop()


@lru_cache(maxsize=1)
def get_watchdog_singleton():
    """Get or create the WatchDog service singleton"""
    desktop = get_desktop_singleton()
    watchdog = WatchDog()
    watchdog.set_focus_callback(desktop.tree.on_focus_change)
    watchdog.start()
    return watchdog


def _resolve_label(desktop, label):
    """Resolve a UI element label to screen coordinates."""
    if desktop.desktop_state is None:
        raise ValueError("Desktop state is empty. Please call Snapshot first.")
    try:
        return list(desktop.get_coordinates_from_label(label))
    except Exception as e:
        raise ValueError(f"Failed to find element with label {label}: {e}")


class WindowsSnapshotTool(BaseTool):
    """Tool for capturing desktop state and UI elements"""
    name = "windows_snapshot"
    description = (
        "Take a screenshot and inspect the screen. Captures complete desktop state including: "
        "system language, focused/opened windows, interactive elements (buttons, text fields, links, "
        "menus with coordinates), and scrollable areas. Always call this first to understand "
        "the current desktop state before taking actions."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "use_vision": {"type": "boolean", "description": "Include screenshot in the response", "default": False},
            "use_dom": {"type": "boolean", "description": "Get web page elements for browser windows", "default": False},
            "use_annotation": {"type": "boolean", "description": "Draw bounding boxes on the screenshot", "default": True},
            "use_ui_tree": {"type": "boolean", "description": "Extract interactive elements (slower)", "default": True},
            "display": {"type": "array", "items": {"type": "integer"}, "description": "Limit to specific screens (e.g. [0])"}
        }
    }

    async def execute(self, input_data: ToolInput) -> ToolOutput:
        try:
            desktop = get_desktop_singleton()
            # Ensure watchdog is running for focus tracking
            get_watchdog_singleton()
            
            use_vision = getattr(input_data, "use_vision", False)
            use_dom = getattr(input_data, "use_dom", False)
            use_annotation = getattr(input_data, "use_annotation", True)
            use_ui_tree = getattr(input_data, "use_ui_tree", True)
            display = getattr(input_data, "display", None)

            capture_result = capture_desktop_state(
                desktop,
                use_vision=use_vision,
                use_dom=use_dom,
                use_annotation=use_annotation,
                use_ui_tree=use_ui_tree,
                display=display,
                tool_name="Windows Snapshot"
            )
            
            result_data = build_snapshot_response(capture_result, include_ui_details=True)
            
            # FastMCP returns a list of items (strings and Image objects).
            # We'll collect the text for the LLM and handle images if they exist.
            text_result = ""
            for item in result_data:
                if isinstance(item, str):
                    text_result += item + "\n"
                elif hasattr(item, "data"):  # Handle FastMCP Image object
                    text_result += f"\n[Screenshot captured: {len(item.data)} bytes]\n"
                else:
                    text_result += str(item) + "\n"
            
            return ToolOutput(success=True, result=text_result.strip())
        except Exception as e:
            return ToolOutput(success=False, result=None, error=str(e))


class WindowsClickTool(BaseTool):
    """Tool for performing mouse clicks"""
    name = "windows_click"
    description = (
        "Performs mouse clicks at specified coordinates [x, y] or using a UI element's label from a snapshot. "
        "Supports buttons: 'left', 'right', 'middle'. Clicks: 1 (single), 2 (double), 0 (hover)."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "loc": {"type": "array", "items": {"type": "integer"}, "minItems": 2, "maxItems": 2},
            "label": {"type": "integer"},
            "button": {"type": "string", "enum": ["left", "right", "middle"], "default": "left"},
            "clicks": {"type": "integer", "default": 1}
        },
        "oneOf": [{"required": ["loc"]}, {"required": ["label"]}]
    }

    async def execute(self, input_data: ToolInput) -> ToolOutput:
        try:
            desktop = get_desktop_singleton()
            loc = getattr(input_data, "loc", None)
            label = getattr(input_data, "label", None)
            button = getattr(input_data, "button", "left")
            clicks = getattr(input_data, "clicks", 1)

            if label is not None:
                loc = _resolve_label(desktop, label)
            
            if not loc or len(loc) != 2:
                return ToolOutput(success=False, result=None, error="Invalid location")

            desktop.click(loc=loc, button=button, clicks=clicks)
            return ToolOutput(success=True, result=f"Clicked {button} at {loc}")
        except Exception as e:
            return ToolOutput(success=False, result=None, error=str(e))


class WindowsTypeTool(BaseTool):
    """Tool for typing text"""
    name = "windows_type"
    description = "Types text at specified coordinates or UI element label. Can clear existing text or press Enter."
    input_schema = {
        "type": "object",
        "properties": {
            "text": {"type": "string"},
            "loc": {"type": "array", "items": {"type": "integer"}, "minItems": 2, "maxItems": 2},
            "label": {"type": "integer"},
            "clear": {"type": "boolean", "default": False},
            "press_enter": {"type": "boolean", "default": False},
            "caret_position": {"type": "string", "enum": ["start", "idle", "end"], "default": "idle"}
        },
        "required": ["text"],
        "oneOf": [{"required": ["loc"]}, {"required": ["label"]}]
    }

    async def execute(self, input_data: ToolInput) -> ToolOutput:
        try:
            desktop = get_desktop_singleton()
            text = input_data.text
            loc = getattr(input_data, "loc", None)
            label = getattr(input_data, "label", None)
            clear = getattr(input_data, "clear", False)
            press_enter = getattr(input_data, "press_enter", False)
            caret_position = getattr(input_data, "caret_position", "idle")

            if label is not None:
                loc = _resolve_label(desktop, label)
            
            desktop.type(loc=loc, text=text, caret_position=caret_position, clear=clear, press_enter=press_enter)
            return ToolOutput(success=True, result=f"Typed '{text}' at {loc}")
        except Exception as e:
            return ToolOutput(success=False, result=None, error=str(e))


class WindowsScrollTool(BaseTool):
    """Tool for scrolling"""
    name = "windows_scroll"
    description = "Scrolls at coordinates, UI element label, or current mouse position."
    input_schema = {
        "type": "object",
        "properties": {
            "loc": {"type": "array", "items": {"type": "integer"}, "minItems": 2, "maxItems": 2},
            "label": {"type": "integer"},
            "type": {"type": "string", "enum": ["horizontal", "vertical"], "default": "vertical"},
            "direction": {"type": "string", "enum": ["up", "down", "left", "right"], "default": "down"},
            "wheel_times": {"type": "integer", "default": 1}
        }
    }

    async def execute(self, input_data: ToolInput) -> ToolOutput:
        try:
            desktop = get_desktop_singleton()
            loc = getattr(input_data, "loc", None)
            label = getattr(input_data, "label", None)
            scroll_type = getattr(input_data, "type", "vertical")
            direction = getattr(input_data, "direction", "down")
            wheel_times = getattr(input_data, "wheel_times", 1)

            if label is not None:
                loc = _resolve_label(desktop, label)
            
            response = desktop.scroll(loc, scroll_type, direction, wheel_times)
            if response:
                return ToolOutput(success=False, result=None, error=response)
            return ToolOutput(success=True, result=f"Scrolled {scroll_type} {direction}")
        except Exception as e:
            return ToolOutput(success=False, result=None, error=str(e))


class WindowsShortcutTool(BaseTool):
    """Tool for keyboard shortcuts"""
    name = "windows_shortcut"
    description = "Executes keyboard shortcuts like 'ctrl+c', 'alt+tab', 'win+r'."
    input_schema = {
        "type": "object",
        "properties": {
            "shortcut": {"type": "string", "description": "Shortcut combination, e.g. 'ctrl+v'"}
        },
        "required": ["shortcut"]
    }

    async def execute(self, input_data: ToolInput) -> ToolOutput:
        try:
            get_desktop_singleton().shortcut(input_data.shortcut)
            return ToolOutput(success=True, result=f"Pressed {input_data.shortcut}")
        except Exception as e:
            return ToolOutput(success=False, result=None, error=str(e))


class WindowsAppTool(BaseTool):
    """Tool for application management (launch, switch, resize)"""
    name = "windows_app"
    description = "Launch, switch to, or resize applications."
    input_schema = {
        "type": "object",
        "properties": {
            "mode": {"type": "string", "enum": ["launch", "switch", "resize"]},
            "name": {"type": "string", "description": "Application name"},
            "loc": {"type": "array", "items": {"type": "integer"}, "minItems": 2, "maxItems": 2},
            "size": {"type": "array", "items": {"type": "integer"}, "minItems": 2, "maxItems": 2}
        },
        "required": ["mode", "name"]
    }

    async def execute(self, input_data: ToolInput) -> ToolOutput:
        try:
            desktop = get_desktop_singleton()
            mode = input_data.mode
            name = input_data.name
            loc = getattr(input_data, "loc", None)
            size = getattr(input_data, "size", None)

            # Convert lists to tuples if needed by the desktop service
            if loc: loc = tuple(loc)
            if size: size = tuple(size)

            result = desktop.app(mode=mode, name=name, loc=loc, size=size)
            return ToolOutput(success=True, result=str(result))
        except Exception as e:
            return ToolOutput(success=False, result=None, error=str(e))


class WindowsClipboardTool(BaseTool):
    """Tool for clipboard management"""
    name = "windows_clipboard"
    description = "Read from or write to the Windows clipboard."
    input_schema = {
        "type": "object",
        "properties": {
            "mode": {"type": "string", "enum": ["get", "set"]},
            "text": {"type": "string", "description": "Text to set (for 'set' mode)"}
        },
        "required": ["mode"]
    }

    async def execute(self, input_data: ToolInput) -> ToolOutput:
        try:
            import win32clipboard
            mode = input_data.mode
            text = getattr(input_data, "text", None)

            if mode == "get":
                win32clipboard.OpenClipboard()
                try:
                    if win32clipboard.IsClipboardFormatAvailable(win32clipboard.CF_UNICODETEXT):
                        data = win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT)
                        return ToolOutput(success=True, result=f"Clipboard content:\n{data}")
                    else:
                        return ToolOutput(success=True, result="Clipboard is empty or contains non-text data.")
                finally:
                    win32clipboard.CloseClipboard()
            elif mode == "set":
                if text is None:
                    return ToolOutput(success=False, result=None, error="Text required for 'set' mode")
                win32clipboard.OpenClipboard()
                try:
                    win32clipboard.EmptyClipboard()
                    win32clipboard.SetClipboardText(text, win32clipboard.CF_UNICODETEXT)
                    return ToolOutput(success=True, result=f"Clipboard set to: {text[:100]}...")
                finally:
                    win32clipboard.CloseClipboard()
            return ToolOutput(success=False, result=None, error="Invalid mode")
        except Exception as e:
            return ToolOutput(success=False, result=None, error=str(e))


class WindowsNotificationTool(BaseTool):
    """Tool for sending Windows notifications"""
    name = "windows_notification"
    description = "Send a Windows toast notification."
    input_schema = {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "message": {"type": "string"},
            "app_id": {"type": "string", "description": "Application User Model ID"}
        },
        "required": ["title", "message", "app_id"]
    }

    async def execute(self, input_data: ToolInput) -> ToolOutput:
        try:
            result = get_desktop_singleton().send_notification(
                input_data.title, input_data.message, input_data.app_id
            )
            return ToolOutput(success=True, result=result)
        except Exception as e:
            return ToolOutput(success=False, result=None, error=str(e))


class WindowsProcessTool(BaseTool):
    """Tool for process management"""
    name = "windows_process"
    description = "List or kill running processes."
    input_schema = {
        "type": "object",
        "properties": {
            "mode": {"type": "string", "enum": ["list", "kill"]},
            "name": {"type": "string", "description": "Process name"},
            "pid": {"type": "integer", "description": "Process ID"},
            "sort_by": {"type": "string", "enum": ["memory", "cpu", "name"], "default": "memory"},
            "limit": {"type": "integer", "default": 20},
            "force": {"type": "boolean", "default": False}
        },
        "required": ["mode"]
    }

    async def execute(self, input_data: ToolInput) -> ToolOutput:
        try:
            desktop = get_desktop_singleton()
            mode = input_data.mode
            name = getattr(input_data, "name", None)
            pid = getattr(input_data, "pid", None)
            sort_by = getattr(input_data, "sort_by", "memory")
            limit = getattr(input_data, "limit", 20)
            force = getattr(input_data, "force", False)

            if mode == "list":
                result = desktop.list_processes(name=name, sort_by=sort_by, limit=limit)
                return ToolOutput(success=True, result=result)
            elif mode == "kill":
                result = desktop.kill_process(name=name, pid=pid, force=force)
                return ToolOutput(success=True, result=result)
            return ToolOutput(success=False, result=None, error="Invalid mode")
        except Exception as e:
            return ToolOutput(success=False, result=None, error=str(e))