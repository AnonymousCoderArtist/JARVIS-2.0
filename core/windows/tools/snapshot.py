"""Snapshot and Screenshot tools — desktop state capture."""

import logging
from typing import Any

from core.windows.analytics import with_analytics
from core.windows.desktop.service import Desktop
from core.windows.tools._snapshot_helpers import (
    _as_bool,
    capture_desktop_state,
    build_snapshot_response,
)

logger = logging.getLogger(__name__)


def create_state_tool(desktop: Desktop, analytics=None):
    """Create a state snapshot tool."""
    @with_analytics(analytics, "State-Tool")
    def state_tool(
        use_vision: bool | str = False,
        use_dom: bool | str = False,
        use_annotation: bool | str = True,
        use_ui_tree: bool | str = True,
        width_reference_line: int | None = None,
        height_reference_line: int | None = None,
        display: list[int] | None = None,
    ) -> Any:
        try:
            capture_result = capture_desktop_state(
                desktop,
                use_vision=_as_bool(use_vision),
                use_dom=_as_bool(use_dom),
                use_annotation=_as_bool(use_annotation),
                use_ui_tree=_as_bool(use_ui_tree),
                width_reference_line=width_reference_line,
                height_reference_line=height_reference_line,
                display=display,
                tool_name="Snapshot tool",
            )
        except Exception as e:
            logger.warning(
                "Snapshot failed with display=%s use_vision=%s use_dom=%s",
                display,
                use_vision if 'use_vision' in locals() else None,
                use_dom if 'use_dom' in locals() else None,
                exc_info=True,
            )
            return [f'Error capturing desktop state: {str(e)}. Please try again.']

        return build_snapshot_response(capture_result, include_ui_details=True)
    
    return state_tool


def create_screenshot_tool(desktop: Desktop, analytics=None):
    """Create a screenshot tool."""
    @with_analytics(analytics, "Screenshot-Tool")
    def screenshot_tool(
        use_annotation: bool | str = False,
        width_reference_line: int | None = None,
        height_reference_line: int | None = None,
        display: list[int] | None = None,
    ) -> Any:
        try:
            capture_result = capture_desktop_state(
                desktop,
                use_vision=True,
                use_dom=False,
                use_annotation=_as_bool(use_annotation),
                use_ui_tree=False,
                width_reference_line=width_reference_line,
                height_reference_line=height_reference_line,
                display=display,
                tool_name="Screenshot tool",
            )
        except Exception as e:
            logger.warning(
                "Screenshot failed with display=%s",
                display,
                exc_info=True,
            )
            return [f'Error capturing screenshot: {str(e)}. Please try again.']

        return build_snapshot_response(
            capture_result,
            include_ui_details=False,
            ui_detail_note="UI Tree: Skipped for fast screenshot-only capture. Call Snapshot when you need interactive or scrollable elements.",
        )
    
    return screenshot_tool