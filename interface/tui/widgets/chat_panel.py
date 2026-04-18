"""Chat panel widget for JARVIS TUI."""

from typing import Any

from textual.widgets import RichLog
from textual.message import Message
from rich.markdown import Markdown
from rich.syntax import Syntax
from rich.text import Text


class ChatPanel(RichLog):
    """A widget to display the chat transcript."""

    def __init__(
        self,
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
        disabled: bool = False,
    ):
        super().__init__(
            highlight=True,
            markup=True,
            name=name,
            id=id,
            classes=classes,
            disabled=disabled,
        )
        self.entries = []

    def add_entry(self, entry: dict[str, Any]) -> None:
        """Add an entry to the chat panel."""
        self.entries.append(entry)
        self._render_entry(entry)

    def _render_entry(self, entry: dict[str, Any]) -> None:
        """Render a single entry based on its kind."""
        role = entry.get("role", "unknown")
        content = entry.get("content", "")
        kind = entry.get("kind", "")

        if kind == "status":
            self._render_status(content)
        elif kind == "tool_call":
            self._render_tool_call(entry)
        elif kind == "tool_result":
            self._render_tool_result(entry)
        elif role == "assistant":
            self._render_assistant(content)
        elif role == "user":
            self._render_user(content)
        else:
            self._render_unknown(entry)

    def _render_status(self, content: str) -> None:
        """Render a status message."""
        self.write(Text.from_markup(f"[dim]{content}[/dim]"))

    def _render_tool_call(self, entry: dict[str, Any]) -> None:
        """Render a tool call."""
        tool = entry.get("tool", "unknown")
        args = entry.get("args", {})
        self.write(Text.from_markup(f"[blue]Tool call:[/blue] [bold]{tool}[/bold]"))
        if args:
            self.write(Text.from_markup(f"[dim]Args: {args}[/dim]"))

    def _render_tool_result(self, entry: dict[str, Any]) -> None:
        """Render a tool result."""
        tool = entry.get("tool", "unknown")
        result = entry.get("result", "")
        error = entry.get("error")
        metadata = entry.get("metadata", {})

        if error:
            self.write(Text.from_markup(f"[red]Tool error ({tool}):[/red] {error}"))
        else:
            self.write(Text.from_markup(f"[green]Tool result ({tool}):[/green]"))

            # If there's a diff in metadata, render it as syntax-highlighted unified diff
            if "diff" in metadata:
                diff_text = metadata["diff"]
                syntax = Syntax(diff_text, "diff", theme="monokai", line_numbers=True)
                self.write(syntax)
            else:
                # Otherwise, just write the result
                self.write(Text.from_markup(str(result)))

    def _render_assistant(self, content: str) -> None:
        """Render an assistant message."""
        # Try to render as Markdown (GFM)
        try:
            md = Markdown(str(content))
            self.write(md)
        except Exception:
            # Fallback to plain text
            self.write(Text.from_markup(str(content)))

    def _render_user(self, content: str) -> None:
        """Render a user message."""
        self.write(Text.from_markup(f"[bold]You:[/bold] {content}"))

    def _render_unknown(self, entry: dict[str, Any]) -> None:
        """Render an unknown entry."""
        self.write(Text.from_markup(f"[dim]{entry}[/dim]"))
