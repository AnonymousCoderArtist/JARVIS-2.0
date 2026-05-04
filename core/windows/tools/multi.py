"""MultiSelect and MultiEdit tools — batch element interaction."""

from typing import Any

from core.windows.analytics import with_analytics


def _resolve_labels(desktop, labels):
    """Resolve labels to coordinates."""
    if desktop.desktop_state is None:
        raise ValueError("Desktop state is empty. Please call Snapshot first.")
    try:
        resolved = desktop.get_coordinates_from_labels(labels)
        return [list(loc) for loc in resolved]
    except Exception as e:
        raise ValueError(f"Failed to resolve labels {labels}: {e}")


def create_multi_select_tool(desktop, analytics=None):
    """Create a multi-select tool."""
    @with_analytics(analytics, "Multi-Select-Tool")
    def multi_select_tool(
        locs: list[list[int]] | None = None,
        labels: list[int] | None = None,
        press_ctrl: bool | str = True,
    ) -> str:
        if locs is None and labels is None:
            raise ValueError("Either locs or labels must be provided.")
        locs = locs or []
        if labels is not None:
            locs.extend(_resolve_labels(desktop, labels))

        press_ctrl = press_ctrl is True or (
            isinstance(press_ctrl, str) and press_ctrl.lower() == "true"
        )
        desktop.multi_select(press_ctrl, locs)
        elements_str = "\n".join([f"({loc[0]},{loc[1]})" for loc in locs])
        return f"Multi-selected elements at:\n{elements_str}"
    
    return multi_select_tool


def create_multi_edit_tool(desktop, analytics=None):
    """Create a multi-edit tool."""
    @with_analytics(analytics, "Multi-Edit-Tool")
    def multi_edit_tool(
        locs: list[list] | None = None,
        labels: list[list] | None = None,
    ) -> str:
        if locs is None and labels is None:
            raise ValueError("Either locs or labels must be provided.")
        locs = locs or []
        if labels is not None:
            processed_labels = []
            for item in labels:
                if len(item) != 2:
                    raise ValueError(f"Each label item must be [label, text]. Invalid: {item}")
                try:
                    processed_labels.append((int(item[0]), item[1]))
                except (ValueError, TypeError):
                    raise ValueError(f"Invalid label id in item: {item}")

            label_ids = [item[0] for item in processed_labels]
            resolved_coords = _resolve_labels(desktop, label_ids)
            for (x, y), (_, text) in zip(resolved_coords, processed_labels):
                locs.append([x, y, text])

        desktop.multi_edit(locs)
        elements_str = ", ".join([f"({e[0]},{e[1]}) with text '{e[2]}'" for e in locs])
        return f"Multi-edited elements at: {elements_str}"
    
    return multi_edit_tool