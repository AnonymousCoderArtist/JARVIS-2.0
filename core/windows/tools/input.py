"""Input tools — Click, Type, Scroll, Move, Shortcut, Wait."""

import time
from typing import Literal, Any

from core.windows.analytics import with_analytics


def _resolve_label(desktop, label):
    """Resolve a UI element label to screen coordinates."""
    if desktop.desktop_state is None:
        raise ValueError("Desktop state is empty. Please call Snapshot first.")
    try:
        return list(desktop.get_coordinates_from_label(label))
    except Exception as e:
        raise ValueError(f"Failed to find element with label {label}: {e}")


def create_click_tool(desktop, analytics=None):
    """Create a click tool."""
    @with_analytics(analytics, "Click-Tool")
    def click_tool(
        loc: list[int] | None = None,
        label: int | None = None,
        button: Literal["left", "right", "middle"] = "left",
        clicks: int = 1,
    ) -> str:
        if loc is None and label is None:
            raise ValueError("Either loc or label must be provided.")
        if label is not None:
            loc = _resolve_label(desktop, label)
        if len(loc) != 2:
            raise ValueError("Location must be a list of exactly 2 integers [x, y]")
        x, y = loc[0], loc[1]
        desktop.click(loc=loc, button=button, clicks=clicks)
        num_clicks = {0: "Hover", 1: "Single", 2: "Double"}
        return f"{num_clicks.get(clicks)} {button} clicked at ({x},{y})."
    
    return click_tool


def create_type_tool(desktop, analytics=None):
    """Create a type tool."""
    @with_analytics(analytics, "Type-Tool")
    def type_tool(
        text: str,
        loc: list[int] | None = None,
        label: int | None = None,
        clear: bool | str = False,
        caret_position: Literal["start", "idle", "end"] = "idle",
        press_enter: bool | str = False,
    ) -> str:
        if loc is None and label is None:
            raise ValueError("Either loc or label must be provided.")
        if label is not None:
            loc = _resolve_label(desktop, label)
        if len(loc) != 2:
            raise ValueError("Location must be a list of exactly 2 integers [x, y]")
        x, y = loc[0], loc[1]
        desktop.type(
            loc=loc,
            text=text,
            caret_position=caret_position,
            clear=clear,
            press_enter=press_enter,
        )
        return f"Typed {text} at ({x},{y})."
    
    return type_tool


def create_scroll_tool(desktop, analytics=None):
    """Create a scroll tool."""
    @with_analytics(analytics, "Scroll-Tool")
    def scroll_tool(
        loc: list[int] | None = None,
        label: int | None = None,
        type: Literal["horizontal", "vertical"] = "vertical",
        direction: Literal["up", "down", "left", "right"] = "down",
        wheel_times: int = 1,
    ) -> str:
        if label is not None:
            loc = _resolve_label(desktop, label)
        if loc and len(loc) != 2:
            raise ValueError("Location must be a list of exactly 2 integers [x, y]")
        response = desktop.scroll(loc, type, direction, wheel_times)
        if response:
            return response
        return (
            f"Scrolled {type} {direction} by {wheel_times} wheel times" + f" at ({loc[0]},{loc[1]})."
            if loc
            else ""
        )
    
    return scroll_tool


def create_move_tool(desktop, analytics=None):
    """Create a move tool."""
    @with_analytics(analytics, "Move-Tool")
    def move_tool(
        loc: list[int] | None = None,
        label: int | None = None,
        drag: bool | str = False,
    ) -> str:
        drag = drag is True or (isinstance(drag, str) and drag.lower() == "true")
        if loc is None and label is None:
            raise ValueError("Either loc or label must be provided.")
        if label is not None:
            loc = _resolve_label(desktop, label)
        if len(loc) != 2:
            raise ValueError("loc must be a list of exactly 2 integers [x, y]")
        x, y = loc[0], loc[1]
        if drag:
            desktop.drag(loc)
            return f"Dragged to ({x},{y})."
        else:
            desktop.move(loc)
            return f"Moved the mouse pointer to ({x},{y})."
    
    return move_tool


def create_shortcut_tool(desktop, analytics=None):
    """Create a shortcut tool."""
    @with_analytics(analytics, "Shortcut-Tool")
    def shortcut_tool(shortcut: str):
        desktop.shortcut(shortcut)
        return f"Pressed {shortcut}."
    
    return shortcut_tool


def create_wait_tool(desktop, analytics=None):
    """Create a wait tool."""
    @with_analytics(analytics, "Wait-Tool")
    def wait_tool(duration: int) -> str:
        time.sleep(duration)
        return f"Waited for {duration} seconds."
    
    return wait_tool