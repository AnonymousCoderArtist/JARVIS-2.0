"""Agent tool widgets for TUI - similar to LS/GREP/BASH tool UI."""

from __future__ import annotations

from typing import Any, ClassVar
from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Horizontal, Vertical
from textual.widgets import Static
from textual.reactive import reactive

from interface.textual_ui.widgets.no_markup_static import NoMarkupStatic
from interface.textual_ui.widgets.messages import NonSelectableStatic


class AgentToolCallWidget(Static):
    """Agent tool call widget with LS/GREP/BASH-like UI.
    
    Layout:
    ● Agent  explore: Find API endpoints
    └─ running • Ctrl+O to expand
    """
    MARKER = "●"
    BRANCH = "└─"
    # Spinner frames using dot/circle characters for tool calls
    SPINNER_FRAMES = ("◉", "○", "◌", "◎")

    def __init__(
        self,
        agent_name: str,
        prompt: str,
        task_id: str,
        *,
        is_history: bool = False
    ) -> None:
        super().__init__()
        self.agent_name = agent_name
        self.prompt = prompt
        self.task_id = task_id
        self._is_history = is_history
        self._indicator_widget: Static | None = None
        self._agent_name_widget: Static | None = None
        self._info_widget: Static | None = None
        self._is_spinning = False
        self._frame_index = 0
        self.add_class("agent-tool-call")

    def compose(self) -> ComposeResult:
        with Vertical(classes="agent-tool-call-container"):
            with Horizontal(classes="agent-tool-call-header"):
                self._indicator_widget = NonSelectableStatic(
                    self.MARKER, classes="agent-tool-indicator"
                )
                yield self._indicator_widget
                
                # Format: "Agent  explore: Find API endpoints"
                summary = f"Agent  {self.agent_name}: {self._truncate_prompt(self.prompt)}"
                self._agent_name_widget = NoMarkupStatic(
                    summary, classes="agent-tool-name"
                )
                yield self._agent_name_widget
            
            # Info line below
            self._info_widget = NoMarkupStatic(
                f"{self.BRANCH} running • Ctrl+O to expand", classes="agent-tool-info"
            )
            yield self._info_widget

    def _truncate_prompt(self, prompt: str, max_length: int = 50) -> str:
        """Truncate prompt for display."""
        if len(prompt) <= max_length:
            return prompt
        return prompt[:max_length-3] + "..."

    def on_mount(self) -> None:
        """Start the spinning animation when mounted."""
        if not self._is_history:
            self._is_spinning = True
            self._frame_index = 0
            self._spinner_timer = self.set_interval(0.3, self._update_spinner_frame)
            if self._indicator_widget:
                # White (no color class) while running - will be colored on completion
                self._indicator_widget.remove_class("success")
                self._indicator_widget.remove_class("error")

    def on_unmount(self) -> None:
        """Stop the spinner timer when unmounted."""
        if hasattr(self, '_spinner_timer') and self._spinner_timer:
            self._spinner_timer.stop()
            self._spinner_timer = None

    def _update_spinner_frame(self) -> None:
        """Update with rotating frames."""
        if not self._is_spinning or not self._indicator_widget:
            return
        frame = self.SPINNER_FRAMES[self._frame_index % len(self.SPINNER_FRAMES)]
        self._indicator_widget.update(frame)
        self._frame_index += 1

    def stop_spinning(self, success: bool = True) -> None:
        """Update indicator when tool completes."""
        self._is_spinning = False
        if hasattr(self, '_spinner_timer') and self._spinner_timer:
            self._spinner_timer.stop()
            self._spinner_timer = None

        if self._indicator_widget:
            icon = self.MARKER
            self._indicator_widget.update(icon)
            if success:
                self._indicator_widget.add_class("success")  # Green for success
                self._indicator_widget.remove_class("error")
            else:
                self._indicator_widget.add_class("error")  # Red for failure
                self._indicator_widget.remove_class("success")

    def update_status(self, status: str, message: str = "") -> None:
        """Update the status info line."""
        if self._info_widget:
            full_message = f"{self.BRANCH} {status}"
            if message:
                full_message += f" • {message}"
            self._info_widget.update(full_message)


class AgentToolResultWidget(Static, can_focus=True):
    """Agent tool result widget with LS/GREP/BASH-like UI.
    
    Layout:
    ● Agent  explore: Find API endpoints
    └─ completed • Task ID: abc123
       ─────────────────────────────────
       Found 12 API endpoints in 5 files
       
       Key findings:
       - GET /api/users
       - POST /api/auth
       ...
    """
    MARKER = "●"
    BRANCH = "└─"

    collapsed = reactive(True)

    def __init__(
        self,
        agent_name: str,
        prompt: str,
        task_id: str,
        result: str = "",
        status: str = "completed",
        error: str | None = None,
        collapsed: bool = True
    ) -> None:
        super().__init__()
        self.agent_name = agent_name
        self.prompt = prompt
        self.task_id = task_id
        self.result = result
        self.status = status
        self.error = error
        self.collapsed = collapsed
        self._indicator_widget: Static | None = None
        self._agent_name_widget: Static | None = None
        self._status_widget: Static | None = None
        self._content_container: Vertical | None = None
        self.add_class("agent-tool-result")

    def compose(self) -> ComposeResult:
        with Vertical(classes="agent-tool-result-container"):
            with Horizontal(classes="agent-tool-result-header"):
                # Show green for success, red for failure
                self._indicator_widget = NonSelectableStatic(
                    self.MARKER,
                    classes="agent-tool-result-indicator"
                )
                if self.status == "completed":
                    self._indicator_widget.add_class("success")
                elif self.status == "failed":
                    self._indicator_widget.add_class("error")
                else:
                    self._indicator_widget.add_class("running")
                    self._indicator_widget.add_class("error")
                yield self._indicator_widget

                # Format: "Agent  explore: Find API endpoints"
                summary = f"Agent  {self.agent_name}: {self._truncate_prompt(self.prompt)}"
                self._agent_name_widget = NoMarkupStatic(
                    summary, classes="agent-tool-result-name"
                )
                yield self._agent_name_widget
                
                # Status info
                status_text = f"{self.status}"
                if self.task_id:
                    status_text += f" • Task ID: {self._truncate_task_id(self.task_id)}"
                self._status_widget = NoMarkupStatic(
                    status_text, classes="agent-tool-status"
                )
                yield self._status_widget

            self._content_container = Vertical(classes="agent-tool-result-content")
            yield self._content_container

    def _truncate_prompt(self, prompt: str, max_length: int = 50) -> str:
        """Truncate prompt for display."""
        if len(prompt) <= max_length:
            return prompt
        return prompt[:max_length-3] + "..."

    def _truncate_task_id(self, task_id: str, max_length: int = 12) -> str:
        """Truncate task ID for display."""
        if len(task_id) <= max_length:
            return task_id
        return task_id[:max_length-3] + "..."

    def on_mount(self) -> None:
        """Render the result content."""
        self._render_result()

    def watch_collapsed(self, collapsed: bool) -> None:
        """Update the widget when collapsed state changes."""
        self._render_result()

    def _render_result(self) -> None:
        """Render the result content based on collapsed state."""
        if not self._content_container:
            return

        # Clear existing content
        self._content_container.remove_children()

        # Show result content based on collapsed state
        if self.collapsed:
            # Collapsed view - just show a hint
            if self.error:
                # Show error hint
                error_hint = f"└─ failed • {self.error[:30]}..." if len(self.error) > 30 else f"└─ failed • {self.error}"
                hint_widget = NoMarkupStatic(error_hint, classes="agent-tool-result-hint error-text")
                self._content_container.mount(hint_widget)
            elif not self.result:
                # No result content
                hint_widget = NoMarkupStatic("└─ no output • Ctrl+O to expand", classes="agent-tool-result-hint")
                self._content_container.mount(hint_widget)
            else:
                # Show result hint
                lines = self.result.split('\n')
                line_count = len(lines)
                hint_text = f"└─ {line_count} lines • Ctrl+O to expand"
                hint_widget = NoMarkupStatic(hint_text, classes="agent-tool-result-hint")
                self._content_container.mount(hint_widget)
        else:
            # Expanded view - show full content
            if self.error:
                # Show error details
                error_header = NoMarkupStatic("ERROR:", classes="agent-tool-result-error")
                self._content_container.mount(error_header)
                error_lines = self.error.split('\n')
                for line in error_lines[:15]:
                    content_widget = NoMarkupStatic(f"   {line}", classes="agent-tool-result-error")
                    self._content_container.mount(content_widget)
            elif self.result:
                # Show result
                result_lines = self.result.split('\n')
                max_lines_to_show = 20
                
                for line in result_lines[:max_lines_to_show]:
                    content_widget = NoMarkupStatic(f"   {line}", classes="agent-tool-result-line")
                    self._content_container.mount(content_widget)
                
                if len(result_lines) > max_lines_to_show:
                    remaining = len(result_lines) - max_lines_to_show
                    hint_widget = NoMarkupStatic(
                        f"   ... ({remaining} more lines)", 
                        classes="agent-tool-result-hint"
                    )
                    self._content_container.mount(hint_widget)

    def on_click(self, event) -> None:
        """Toggle collapsed/expanded state on click."""
        if self.result:  # Only toggle if we have content
            self.collapsed = not self.collapsed

    async def toggle_collapsed(self) -> None:
        """Toggle collapsed state."""
        self.collapsed = not self.collapsed

    async def set_collapsed(self, collapsed: bool) -> None:
        """Set collapsed state."""
        if self.collapsed == collapsed:
            return
        self.collapsed = collapsed
