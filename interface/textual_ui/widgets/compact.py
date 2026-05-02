from __future__ import annotations

from textual.message import Message

from interface.textual_ui.widgets.status_message import StatusMessage
from interface.textual_ui.utils import compact_reduction_display


class CompactMessage(StatusMessage):
    """Widget to display compaction progress."""

    class Completed(Message):
        def __init__(self, compact_widget: CompactMessage, auto_triggered: bool = False) -> None:
            super().__init__()
            self.compact_widget = compact_widget
            self.auto_triggered = auto_triggered

    def __init__(self, auto_triggered: bool = False) -> None:
        super().__init__()
        self.add_class("compact-message")
        self.old_tokens: int | None = None
        self.new_tokens: int | None = None
        self.error_message: str | None = None
        self.auto_triggered = auto_triggered

    def get_content(self) -> str:
        if self._is_spinning:
            if self.auto_triggered:
                return "[cyan]⟳ Auto-compacting conversation history...[/cyan]"
            return "Compacting conversation history..."

        if self.error_message:
            return f"Error: {self.error_message}"

        return compact_reduction_display(self.old_tokens, self.new_tokens)

    def set_complete(
        self, old_tokens: int | None = None, new_tokens: int | None = None,
        auto_triggered: bool = False
    ) -> None:
        self.old_tokens = old_tokens
        self.new_tokens = new_tokens
        self.auto_triggered = auto_triggered
        self.stop_spinning(success=True)
        self.post_message(self.Completed(self, auto_triggered=auto_triggered))

    def set_error(self, error_message: str) -> None:
        self.error_message = error_message
        self.stop_spinning(success=False)