from __future__ import annotations

from typing import Any

from rich.cells import cell_len
from rich.text import Text
from textual.containers import VerticalScroll
from textual.widgets import Static

COMPLETION_POPUP_MAX_HEIGHT = 12
COMPLETION_POPUP_MAX_WIDTH = 80
COMPLETION_POPUP_PADDING_X = 1


class _CompletionItem(Static):
    pass


class CompletionPopup(VerticalScroll):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(id="completion-popup", **kwargs)
        self.styles.display = "none"
        self.styles.max_height = COMPLETION_POPUP_MAX_HEIGHT
        self.styles.max_width = COMPLETION_POPUP_MAX_WIDTH
        self.styles.padding = (0, 1)
        self.styles.border = ("solid", "gray")
        self.styles.background = "#1a1a1a"
        self.can_focus = False

    def update_suggestions(
        self, suggestions: list[tuple[str, str, str]], selected: int
    ) -> None:
        if not suggestions:
            self.hide()
            return

        self.remove_children()

        items: list[_CompletionItem] = []
        for idx, (label, description, _) in enumerate(suggestions):
            is_selected = idx == selected

            # Use Rich Text for better control
            text = Text()
            display_label = self._display_label(label)

            if is_selected:
                text.append(display_label, style="bold black on white")
            else:
                text.append(display_label, style="bold white")

            if description:
                text.append("  ")
                text.append(description, style="italic dim" if not is_selected else "italic black on white")

            item = _CompletionItem(text)
            if is_selected:
                item.styles.background = "white"
                item.styles.color = "black"
            else:
                item.styles.background = None
                item.styles.color = None

            items.append(item)

        self.mount_all(items)
        self.styles.display = "block"

        if 0 <= selected < len(items):
            items[selected].scroll_visible(animate=False)

    def hide(self) -> None:
        self.remove_children()
        self.styles.display = "none"

    @property
    def content_text(self) -> str:
        return "\n".join(str(child.render()) for child in self.query(_CompletionItem))

    @staticmethod
    def _display_label(label: str) -> str:
        if label.startswith("@"):
            return label[1:]
        return label

    @classmethod
    def rendered_text_length(cls, label: str, description: str) -> int:
        text_length = cell_len(cls._display_label(label)) + cell_len(description)
        if description:
            text_length += 2
        return text_length
