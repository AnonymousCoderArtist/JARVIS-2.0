"""Simple full-screen subagent output overlay.

Shows running subagent output in real-time - full screen, simple toggle with Tab."""

from __future__ import annotations

from typing import Any

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Static

from interface.textual_ui.widgets.no_markup_static import NoMarkupStatic


class SubagentOverlay(ModalScreen):
    """Simple full-screen overlay showing subagent output in real-time.
    
    Press Tab or Esc to close and return to main chat.
    """

    CSS = """
    SubagentOverlay {
        layout: grid;
        grid-size: 1;
    }
    
    #header {
        height: 3;
        background: $primary;
        color: $text;
        padding: 0 2;
    }
    
    #output {
        height: 100%;
        background: $surface;
        padding: 1 2;
        overflow-y: scroll;
    }
    
    #output Line {
        color: $text;
    }
    
    .empty-msg {
        color: $text-muted;
    }
    """

    BINDINGS = [
        Binding("escape", "close", "Close", show=True),
        Binding("tab", "close", "Back to Chat", show=True),
    ]

    def __init__(self, agent_name: str = "explore", **kwargs):
        super().__init__(**kwargs)
        self.agent_name = agent_name
        self._output_lines: list[str] = []

    def compose(self) -> ComposeResult:
        yield Vertical(
            Static(f"🚀 SUBAGENT: {self.agent_name.upper()} | Press Tab or Esc to return to chat", id="header"),
            Static("Waiting for output...", id="output", classes="empty-msg")
        )

    def append_output(self, text: str) -> None:
        """Add new output line."""
        self._output_lines.append(text)
        self._refresh_output()

    def _refresh_output(self) -> None:
        """Refresh the output display."""
        try:
            output = self.query_one("#output")
            if self._output_lines:
                output.update("\n".join(self._output_lines))
                output.remove_class("empty-msg")
            else:
                output.update("Waiting for output...")
                output.add_class("empty-msg")
        except Exception:
            pass

    def set_completed(self, success: bool = True) -> None:
        """Mark as completed."""
        status = "✅ Completed" if success else "❌ Failed"
        self.append_output(f"\n{'='*40}\n{status}\n{'='*40}")

    def action_close(self) -> None:
        """Close the overlay."""
        self.dismiss()