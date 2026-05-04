"""Snapshot helper functions for desktop state capture."""

import logging
from typing import Any

from core.windows.desktop.service import Desktop, Size
from core.windows.desktop.utils import remove_private_use_chars

logger = logging.getLogger(__name__)


def _as_bool(value: Any) -> bool:
    """Convert a value to boolean."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in ("true", "1", "yes", "on")
    return bool(value)


def capture_desktop_state(
    desktop: Desktop,
    use_vision: bool = False,
    use_dom: bool = False,
    use_annotation: bool = True,
    use_ui_tree: bool = True,
    width_reference_line: int | None = None,
    height_reference_line: int | None = None,
    display: list[int] | None = None,
    tool_name: str = "Snapshot",
) -> Any:
    """Capture the current desktop state."""
    return desktop.get_state(
        use_vision=use_vision,
        use_dom=use_dom,
        use_annotation=use_annotation,
        use_ui_tree=use_ui_tree,
        display_indices=display,
    )


def build_snapshot_response(
    capture_result: Any,
    include_ui_details: bool = True,
    ui_detail_note: str | None = None,
) -> list[Any]:
    """Build the response for a snapshot."""
    from PIL import Image
    
    result = []
    
    # Add text summary
    if hasattr(capture_result, 'to_markdown'):
        result.append(capture_result.to_markdown())
    else:
        result.append(str(capture_result))
    
    # Add screenshot if available
    if hasattr(capture_result, 'screenshot') and capture_result.screenshot:
        screenshot = capture_result.screenshot
        if isinstance(screenshot, Image.Image):
            # Convert to bytes for transmission
            import io
            buffered = io.BytesIO()
            screenshot.save(buffered, format="PNG")
            result.append(f"\n[Screenshot: {len(buffered.getvalue())} bytes]")
    
    # Add UI details if requested
    if include_ui_details and hasattr(capture_result, 'tree_state'):
        tree_state = capture_result.tree_state
        if tree_state:
            result.append(f"\nInteractive elements: {len(tree_state.interactive_nodes)}")
            result.append(f"Scrollable elements: {len(tree_state.scrollable_nodes)}")
            if ui_detail_note:
                result.append(ui_detail_note)
    
    return result