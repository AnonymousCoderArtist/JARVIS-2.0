from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.timer import Timer
from textual.widgets import Static

from interface.textual_ui.cli_adapters import ToolUIDataAdapter
from interface.textual_ui.types import ToolCallEvent, ToolResultEvent
from interface.textual_ui.widgets.messages import NonSelectableStatic
from interface.textual_ui.widgets.no_markup_static import NoMarkupStatic
from interface.textual_ui.widgets.tool_widgets import get_result_widget

# Tool-specific icons for visual identification
TOOL_ICONS: dict[str, str] = {
    "read": "📄",
    "read_file": "📄",
    "write": "📝",
    "write_file": "📝",
    "edit": "✏️",
    "edit_file": "✏️",
    "ls": "📁",
    "find": "🔍",
    "grep": "🔎",
    "bash": "⚡",
    "web_search": "🌐",
    "fetch_webpage": "🌐",
    "AskUserQuestion": "❓",
    "agents": "🤖",
    "save_memory": "💾",
    "read_memory": "📖",
    "skill": "🎯",
    "repl": "🐍",
}


def _get_tool_icon(tool_name: str) -> str:
    """Get icon for a tool name."""
    return TOOL_ICONS.get(tool_name, "●")


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
        "filePath",
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


def _get_inline_summary(tool_name: str, args: dict[str, Any] | None) -> str:
    """Get a compact inline summary of tool arguments for the call header.

    Returns something like:
      read: src/main.py (3 files)
      bash: npm test
      edit: src/main.py (+2 replacements)
      grep: TODO (in **/*.py)
    """
    if not args:
        return ""

    # Tool-specific summaries
    if tool_name in ("read", "read_file"):
        files = args.get("files") or args.get("path") or args.get("filePath", "")
        if isinstance(files, list):
            return f"({len(files)} file{'s' if len(files) != 1 else ''})"
        return str(files) if files else ""

    if tool_name in ("write", "write_file"):
        path = args.get("path") or args.get("filePath", "")
        return str(path) if path else ""

    if tool_name in ("edit", "edit_file"):
        path = args.get("path") or args.get("filePath", "")
        replacements = args.get("replacements", [])
        if isinstance(replacements, list):
            count = len(replacements)
            parts = []
            if path:
                parts.append(str(path))
            parts.append(f"{count} replacement{'s' if count != 1 else ''}")
            return " ".join(parts)
        return str(path) if path else ""

    if tool_name == "bash":
        cmd = args.get("command", "")
        if cmd:
            # Truncate long commands
            if len(cmd) > 60:
                return cmd[:57] + "…"
            return cmd
        return ""

    if tool_name == "grep":
        pattern = args.get("pattern") or args.get("query", "")
        glob = args.get("glob") or args.get("include", "")
        parts = []
        if pattern:
            parts.append(f'"{pattern}"')
        if glob:
            parts.append(f"in {glob}")
        return " ".join(parts) if parts else ""

    if tool_name == "find":
        pattern = args.get("pattern") or args.get("glob", "")
        return str(pattern) if pattern else ""

    if tool_name in ("ls",):
        path = args.get("path", "")
        return str(path) if path else ""

    if tool_name == "agents":
        agent_name = args.get("agent_name") or args.get("name", "")
        return str(agent_name) if agent_name else ""

    if tool_name in ("web_search",):
        query = args.get("query", "")
        return f'"{query}"' if query else ""

    # Default: show first priority arg
    for key in ("path", "file_path", "filePath", "command", "pattern", "query"):
        if key in args and args[key]:
            return _format_tool_value(args[key], max_length=60)
    return ""


class ToolCallMessage(Static):
    """Tool call message with rich display:
    ⚡ Bash  npm test  (2.3s)
    └─ running…
    """
    MARKER = "●"
    BRANCH = "└─"
    # Spinner frames using dot/circle characters for tool calls
    SPINNER_FRAMES = ("◉", "○", "◌", "◎")

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
        self._args_widget: Static | None = None
        self._duration_widget: Static | None = None
        self._info_widget: Static | None = None
        self._spinner_timer: Timer | None = None
        self._duration_timer: Timer | None = None
        self._is_spinning = False
        self._frame_index = 0
        self._start_time: float = 0.0
        self._duration: float = 0.0

        super().__init__()
        self.add_class("tool-call")

    def compose(self) -> ComposeResult:
        with Vertical(classes="tool-call-container"):
            with Horizontal(classes="tool-call-header"):
                # Tool icon/indicator
                icon = _get_tool_icon(self._tool_name)
                self._indicator_widget = NonSelectableStatic(
                    icon, classes="tool-indicator"
                )
                yield self._indicator_widget

                # Tool name (bold)
                tool_label = self._tool_name.upper() if len(self._tool_name) <= 6 else self._tool_name.title()
                self._tool_name_widget = NoMarkupStatic(
                    tool_label, classes="tool-name"
                )
                yield self._tool_name_widget

                # Inline argument summary
                args_summary = self._get_inline_args()
                if args_summary:
                    self._args_widget = NoMarkupStatic(
                        args_summary, classes="tool-call-args"
                    )
                    yield self._args_widget

                # Duration timer (shows while running)
                if not self._is_history:
                    self._duration_widget = NoMarkupStatic(
                        "", classes="tool-call-duration"
                    )
                    yield self._duration_widget

    def _get_inline_args(self) -> str:
        """Get compact inline argument summary."""
        if self._event:
            return _get_inline_summary(self._tool_name, self._event.tool_args)
        return ""

    def on_mount(self) -> None:
        """Start the spinning animation when mounted."""
        if not self._is_history:
            self._is_spinning = True
            self._frame_index = 0
            self._start_time = time.monotonic()
            self._spinner_timer = self.set_interval(0.3, self._update_spinner_frame)
            # Update duration every second
            self._duration_timer = self.set_interval(1.0, self._update_duration)
            if self._indicator_widget:
                self._indicator_widget.remove_class("success")
                self._indicator_widget.remove_class("error")

    def on_unmount(self) -> None:
        """Stop the spinner timer when unmounted."""
        if self._spinner_timer:
            self._spinner_timer.stop()
            self._spinner_timer = None
        if self._duration_timer:
            self._duration_timer.stop()
            self._duration_timer = None

    def _update_spinner_frame(self) -> None:
        """Update with rotating frames."""
        if not self._is_spinning or not self._indicator_widget:
            return
        frame = self.SPINNER_FRAMES[self._frame_index % len(self.SPINNER_FRAMES)]
        self._indicator_widget.update(frame)
        self._frame_index += 1

    def _update_duration(self) -> None:
        """Update the duration display."""
        if not self._is_spinning or not self._duration_widget:
            return
        elapsed = time.monotonic() - self._start_time
        if elapsed >= 60:
            mins = int(elapsed) // 60
            secs = int(elapsed) % 60
            text = f"({mins}m{secs}s)"
        else:
            text = f"({elapsed:.1f}s)"
        self._duration_widget.update(text)

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
            tool_label = self._tool_name.upper() if len(self._tool_name) <= 6 else self._tool_name.title()
            self._tool_name_widget.update(tool_label)

    def set_stream_message(self, message: str) -> None:
        """Set additional info below the tool call."""
        if self._info_widget:
            self._info_widget.update(f"{self.BRANCH} {message}")

    def stop_spinning(self, success: bool = True) -> None:
        """Update indicator when tool completes."""
        self._is_spinning = False
        self._duration = time.monotonic() - self._start_time if self._start_time else 0

        if self._spinner_timer:
            self._spinner_timer.stop()
            self._spinner_timer = None
        if self._duration_timer:
            self._duration_timer.stop()
            self._duration_timer = None

        if self._indicator_widget:
            icon = _get_tool_icon(self._tool_name)
            self._indicator_widget.update(icon)
            if success:
                self._indicator_widget.add_class("success")
                self._indicator_widget.remove_class("error")
            else:
                self._indicator_widget.add_class("error")
                self._indicator_widget.remove_class("success")

        # Show final duration
        if self._duration_widget:
            if self._duration >= 60:
                mins = int(self._duration) // 60
                secs = int(self._duration) % 60
                text = f"({mins}m{secs}s)"
            else:
                text = f"({self._duration:.1f}s)"
            self._duration_widget.update(text)


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
        self._error_message: str | None = None

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
                    self._error_message = self._get_error_message()

                    # Show green for success, red for failure
                    # White (no color class) will be set by stop_spinning() for running state
                    self._indicator_widget = NonSelectableStatic(
                        self.MARKER,
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
        if self._event.skipped:
            return False
        # Check success field from ToolOutput result
        if isinstance(self._event.result, dict):
            return self._event.result.get("success", True)
        if self._event.error:
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

    def _get_error_message(self) -> str | None:
        """Get error message from event."""
        if self._event is None:
            return None

        if self._event.error:
            return self._event.error

        # Also check result for error
        if isinstance(self._event.result, dict):
            return self._event.result.get("error")

        return None

    async def on_mount(self) -> None:
        if self._call_widget:
            self._call_widget.stop_spinning(success=self._success)
        await self._render_result()

    def on_tool_result_widget_toggle_request(self, message: Any) -> None:
        """Keep our state in sync with the child widget."""
        self.collapsed = message.collapsed

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

        # For failures: only show error message when expanded (not collapsed)
        if not self._success and self._error_message and not self.collapsed:
            error_widget = NoMarkupStatic(f"Error: {self._error_message}", classes="tool-result-error")
            if self._diff_container:
                await self._diff_container.mount(error_widget)

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
    old_line_number: int | None = None
    new_line_number: int | None = None
    is_hunk_header: bool = False
    is_file_header: bool = False


class DiffBlock(Static):
    """Enhanced diff block with rich rendering:

       ▌ src/main.py
       ▌ ─────────────────────────────────
       ▌     │ @@ -41,3 +41,4 @@ class Foo
       ▌  41 │  def foo():
       ▌  42- │      return None
       ▌  42+ │      return 42
       ▌  43 │  # end
       ▌ ─────────────────────────────────
       ▌ +1 -1

    Features:
    - File path header
    - Hunk headers with line numbers
    - Dual line numbers (old/new) for changes
    - Summary bar showing additions/deletions
    """

    def __init__(
        self,
        lines: list[DiffLine],
        context_lines: int = 0,
        file_path: str | None = None,
    ) -> None:
        super().__init__()
        self.add_class("diff-block")
        self._lines = lines
        self._context_lines = context_lines
        self._file_path = file_path
        self._added = sum(1 for l in lines if l.prefix == "+")
        self._removed = sum(1 for l in lines if l.prefix == "-")

    def compose(self) -> ComposeResult:
        # File path header
        if self._file_path:
            yield NonSelectableStatic(
                f"▌ {self._file_path}", classes="diff-file-header"
            )

        # Top border
        yield NonSelectableStatic("▌" + "─" * 40, classes="diff-border")

        # Diff lines
        for line in self._lines:
            # File header lines (--- / +++)
            if line.is_file_header:
                yield NonSelectableStatic(
                    f"▌     │ {line.content}", classes="diff-hunk-header"
                )
                continue

            # Hunk header lines (@@ ... @@)
            if line.is_hunk_header:
                yield NonSelectableStatic(
                    f"▌     │ {line.content}", classes="diff-hunk-header"
                )
                continue

            # Regular diff lines
            prefix = line.prefix if line.prefix else " "

            # Use dual line numbers for change lines, single for context
            if prefix in ("+", "-"):
                old_num = f"{line.old_line_number:>4}" if line.old_line_number else "    "
                new_num = f"{line.new_line_number:>4}" if line.new_line_number else "    "
                gutter = f"▌ {old_num} {new_num} │ {prefix} "
            else:
                num = f"{line.line_number:>4}" if line.line_number else "    "
                gutter = f"▌ {num}     │   "

            from rich.text import Text
            gutter_text = Text(gutter, style="ansi_bright_black")
            content_text = Text(line.content, style=self._get_line_style(prefix))
            yield NonSelectableStatic(gutter_text + content_text, classes="diff-line")

        # Bottom border
        yield NonSelectableStatic("▌" + "─" * 40, classes="diff-border")

        # Summary bar
        parts = []
        if self._added:
            parts.append(f"+{self._added}")
        if self._removed:
            parts.append(f"-{self._removed}")
        if parts:
            summary = "▌ " + " ".join(parts)
            yield NonSelectableStatic(summary, classes="diff-summary")

    def _get_line_style(self, prefix: str) -> str:
        """Get Rich style based on line prefix."""
        if prefix == "+":
            return "ansi_green"
        elif prefix == "-":
            return "ansi_red"
        else:
            return "ansi_default"


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
