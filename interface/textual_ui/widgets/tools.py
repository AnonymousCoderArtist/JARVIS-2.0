from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Static

from interface.textual_ui.cli_adapters import ToolUIDataAdapter
from interface.textual_ui.types import ToolCallEvent, ToolResultEvent
from interface.textual_ui.widgets.messages import ExpandingBorder, NonSelectableStatic
from interface.textual_ui.widgets.no_markup_static import NoMarkupStatic
from interface.textual_ui.widgets.tool_widgets import get_result_widget


def _format_tool_value(value: Any, *, max_length: int = 80) -> str:
    if isinstance(value, str):
        text = value.replace("\n", "\\n")
    else:
        try:
            text = json.dumps(value, ensure_ascii=False, sort_keys=True)
        except TypeError:
            text = str(value)
    if len(text) > max_length:
        hidden = len(text) - max_length
        text = f"{text[:max_length]}…"
    return text


def _format_tool_args(args: dict[str, Any] | None) -> list[str]:
    if not args:
        return []
    priority_keys = [
        "path",
        "file_path",
        "command",
        "pattern",
        "query",
        "url",
        "agent_name",
        "name",
    ]
    ordered = [key for key in priority_keys if key in args]
    ordered.extend(key for key in args if key not in priority_keys)
    return [f"{key}: {_format_tool_value(args[key])}" for key in ordered[:4]]


class ToolCallMessage(Static):
    """Tool call message with target design:
    ● Read  src/main.py
    └─ 120 lines loaded • Ctrl+O to expand
    """
    MARKER = "●"
    BRANCH = "└─"

    def __init__(
        self, event: ToolCallEvent | None = None, *, tool_name: str | None = None
    ) -> None:
        if event is None and tool_name is None:
            raise ValueError("Either event or tool_name must be provided")

        self._event = event
        self._tool_name = tool_name or (event.tool_name if event else None) or "unknown"
        self._is_history = event is None
        self._info_text: str = ""
        self._indicator_widget: Static | None = None
        self._tool_name_widget: Static | None = None
        self._info_widget: Static | None = None
        self._flicker_timer = None
        self._is_flickering = False

        super().__init__()
        self.add_class("tool-call")

    def compose(self) -> ComposeResult:
        with Vertical(classes="tool-call-container"):
            with Horizontal(classes="tool-call-header"):
                self._indicator_widget = NonSelectableStatic(
                    self.MARKER, classes="tool-indicator"
                )
                yield self._indicator_widget
                
                summary = self.get_content()
                self._tool_name_widget = NoMarkupStatic(
                    summary, classes="tool-name"
                )
                yield self._tool_name_widget

    def on_mount(self) -> None:
        """Start the flickering animation when mounted."""
        if not self._is_history:
            self._is_flickering = True
            self._flicker_timer = self.set_interval(0.5, self._toggle_flicker)
            if self._indicator_widget:
                self._indicator_widget.add_class("success")  # Green while running

    def _toggle_flicker(self) -> None:
        if not self._is_flickering or not self._indicator_widget:
            return
        # Get current content - handle both Static and NonSelectableStatic
        try:
            current = self._indicator_widget.renderable.strip()
        except AttributeError:
            try:
                current = str(self._indicator_widget.renderable).strip()
            except Exception:
                current = ""
        # Toggle between space and marker
        self._indicator_widget.update(" " if current == self.MARKER else self.MARKER)

    @property
    def tool_call_id(self) -> str | None:
        return self._event.tool_call_id if self._event else None

    def get_content(self) -> str:
        if self._event:
            adapter = ToolUIDataAdapter(self._event.tool_class)
            display = adapter.get_call_display(self._event)
            return display.summary
        return self._tool_name

    def _get_argument_lines(self) -> list[str]:
        if not self._event:
            return []
        return _format_tool_args(self._event.tool_args)

    def update_event(self, event: ToolCallEvent) -> None:
        self._event = event
        self._tool_name = event.tool_name
        if self._tool_name_widget:
            self._tool_name_widget.update(event.tool_name.ljust(10))

    def set_stream_message(self, message: str) -> None:
        """Set additional info below the tool call."""
        if self._info_widget:
            self._info_widget.update(f"{self.BRANCH} {message}")

    def stop_spinning(self, success: bool = True) -> None:
        """Update indicator when tool completes."""
        self._is_flickering = False
        if self._flicker_timer:
            self._flicker_timer.stop()
            self._flicker_timer = None
            
        if self._indicator_widget:
            icon = self.MARKER
            self._indicator_widget.update(icon)
            self._indicator_widget.remove_class("spinning")
            if success:
                self._indicator_widget.add_class("success")
                self._indicator_widget.remove_class("error")
            else:
                self._indicator_widget.add_class("error")
                self._indicator_widget.remove_class("success")


class ToolResultMessage(Static):
    """Tool result message with target design:
    ● Edit  src/main.py
    └─ +3 -1 [━━━━━] at line 42
       ─────────────────────────────────
       │ 41  │  def foo():
       │ 42- │      return None
       │ 42+ │      return 42
       ─────────────────────────────────
    """
    MARKER = "●"
    BRANCH = "└─"

    def __init__(
        self,
        event: ToolResultEvent | None = None,
        call_widget: ToolCallMessage | None = None,
        collapsed: bool = True,
        *,
        tool_name: str | None = None,
        content: str | None = None,
    ):
        if event is None and tool_name is None:
            raise ValueError("Either event or tool_name must be provided")

        self._event = event
        self._call_widget = call_widget
        self._tool_name = tool_name or (event.tool_name if event else "unknown")
        self._content = content
        self.collapsed = collapsed
        self._indicator_widget: Static | None = None
        self._tool_name_widget: Static | None = None
        self._stats_widget: Static | None = None
        self._diff_container: Vertical | None = None
        self._success = True

        super().__init__()
        self.add_class("tool-result")

    @property
    def tool_name(self) -> str:
        return self._tool_name

    def compose(self) -> ComposeResult:
        with Vertical(classes="tool-result-container"):
            # Only show header if there's no call widget above us
            if not self._call_widget:
                with Horizontal(classes="tool-result-header"):
                    # Determine success from event
                    self._success = self._determine_success()
                    self._indicator_widget = NonSelectableStatic(
                        self.MARKER if self._success else "●",
                        classes="tool-result-indicator"
                    )
                    if self._success:
                        self._indicator_widget.add_class("success")
                    else:
                        self._indicator_widget.add_class("error")
                    yield self._indicator_widget
                    
                    # Use summary instead of just tool name
                    summary = self._get_summary()
                    self._tool_name_widget = NoMarkupStatic(
                        summary, classes="tool-result-name"
                    )
                    yield self._tool_name_widget
                    # Get stats from event or compute from content
                    stats = self._get_stats()
                    if stats:
                        self._stats_widget = NoMarkupStatic(stats, classes="tool-stats")
                        yield self._stats_widget
            
            self._diff_container = Vertical(classes="tool-result-content")
            yield self._diff_container

    def _get_summary(self) -> str:
        """Get summary text for the tool call."""
        if self._event and self._event.tool_class:
            adapter = ToolUIDataAdapter(self._event.tool_class)
            display = adapter.get_call_display(self._event)
            return display.summary
        return self._tool_name.capitalize()

    def _determine_success(self) -> bool:
        if self._event is None:
            return True
        if self._event.error or self._event.skipped:
            return False
        if self._event.tool_class:
            adapter = ToolUIDataAdapter(self._event.tool_class)
            display = adapter.get_result_display(self._event)
            return display.success
        return True

    def _get_stats(self) -> str:
        """Compute stats string from event or content."""
        if self._event is None:
            return ""
        
        if self._event.error:
            return "error"
        
        if self._event.skipped:
            return "skipped"
        
        # Try to get stats from result if it's a dict with stats info
        result = self._event.result
        if isinstance(result, dict):
            added = result.get("added_lines", 0) or result.get("added", 0) or 0
            removed = result.get("removed_lines", 0) or result.get("removed", 0) or 0
            if added or removed:
                parts = []
                if added:
                    parts.append(f"+{added}")
                if removed:
                    parts.append(f"-{removed}")
                return " ".join(parts)
        
        return ""

    async def on_mount(self) -> None:
        if self._call_widget:
            self._call_widget.stop_spinning(success=self._success)
        await self._render_result()

    def set_stream_message(self, message: str) -> None:
        """Set additional info below the tool result."""
        if self._stats_widget:
            self._stats_widget.update(f"{self.BRANCH} {message}")

    async def _render_result(self) -> None:
        if self._event is None:
            return
        
        if self._event.error:
            self.add_class("error-text")
            return
        
        if self._event.skipped:
            self.add_class("warning-text")
            return
        
        # Try to render diff if available
        if self._event.tool_class is None:
            return
        
        adapter = ToolUIDataAdapter(self._event.tool_class)
        display = adapter.get_result_display(self._event)
        
        widget = get_result_widget(
            self._event.tool_name,
            self._event.result,
            success=display.success,
            message=display.message,
            collapsed=self.collapsed,
            warnings=display.warnings,
        )
        
        # Mount result widget to container if exists
        if self._diff_container and widget:
            await self._diff_container.remove_children()
            await self._diff_container.mount(widget)

    async def set_collapsed(self, collapsed: bool) -> None:
        if self.collapsed == collapsed:
            return
        self.collapsed = collapsed
        await self._render_result()

    async def toggle_collapsed(self) -> None:
        self.collapsed = not self.collapsed
        await self._render_result()


@dataclass
class DiffLine:
    """Represents a line in a diff."""
    line_number: int | None
    content: str
    prefix: str  # " ", "+", "-"


class DiffBlock(Static):
    """Diff block with target design:
       ─────────────────────────────────
       │ 41  │  def foo():
       │ 42- │      return None
       │ 42+ │      return 42
       ─────────────────────────────────

    Markers: ▌ for left border, │ for divider
    """

    def __init__(self, lines: list[DiffLine], context_lines: int = 0) -> None:
        super().__init__()
        self.add_class("diff-block")
        self._lines = lines
        self._context_lines = context_lines
        self._border_widget: Static | None = None

    def compose(self) -> ComposeResult:
        # Top border with marker at start
        yield NonSelectableStatic("▌" + "─" * 39, classes="diff-border")
        
        # Diff lines
        for line in self._lines:
            with Horizontal(classes="diff-line"):
                # Line number column
                line_num = f"{line.line_number:>4}" if line.line_number else "    "
                # Prefix marker (+/-/ )
                prefix = line.prefix if line.prefix else " "
                yield NoMarkupStatic(
                    f"▌ {line_num} │ {prefix} ",
                    classes="diff-gutter"
                )
                yield NoMarkupStatic(
                    line.content,
                    classes=self._get_line_class(prefix)
                )
        
        # Bottom border
        yield NonSelectableStatic("▌" + "─" * 39, classes="diff-border")

    def _get_line_class(self, prefix: str) -> str:
        """Get CSS class based on line prefix."""
        if prefix == "+":
            return "diff-line-content diff-added"
        elif prefix == "-":
            return "diff-line-content diff-removed"
        else:
            return "diff-line-content diff-context"


class ToolStatsWidget(Static):
    """Widget showing tool statistics: +3 -1 at line 42"""

    def __init__(self, added: int = 0, removed: int = 0, line_number: int | None = None) -> None:
        super().__init__()
        self.add_class("tool-stats-widget")
        self._added = added
        self._removed = removed
        self._line_number = line_number

    def compose(self) -> ComposeResult:
        # Build stats string
        parts = []
        if self._added > 0:
            parts.append(f"+{self._added}")
        if self._removed > 0:
            parts.append(f"-{self._removed}")
        
        stats_str = " ".join(parts) if parts else ""
        
        # Progress bar (8 chars max)
        total = self._added + self._removed
        if total > 0:
            bar_length = min(total, 8)
            filled = min(self._added, bar_length)
            bar = "█" * filled + "─" * (bar_length - filled)
        else:
            bar = ""
        
        with Horizontal(classes="tool-stats-container"):
            if stats_str:
                yield NoMarkupStatic(stats_str, classes="tool-stats-numbers")
            if bar:
                yield NoMarkupStatic(f"[{bar}]", classes="tool-stats-bar")
            if self._line_number:
                yield NoMarkupStatic(f"at line {self._line_number}", classes="tool-stats-location")