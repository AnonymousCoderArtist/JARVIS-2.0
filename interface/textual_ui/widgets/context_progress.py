from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from textual.reactive import reactive

from interface.textual_ui.widgets.no_markup_static import NoMarkupStatic


@dataclass
class TokenState:
    max_tokens: int = 0
    current_tokens: int = 0
    status: str = "ok"  # "ok", "warning", "critical", "compaction_ready"


class ContextProgress(NoMarkupStatic):
    tokens = reactive(TokenState())

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

    def watch_tokens(self, new_state: TokenState) -> None:
        if new_state.max_tokens == 0:
            self.update("")
            return

        ratio = min(1, new_state.current_tokens / new_state.max_tokens)
        status = new_state.status

        # Format with status indicator
        if status == "critical":
            text = f"[red]{ratio:.0%}[/red] of {new_state.max_tokens // 1000}k tokens [red]⚠ CRITICAL[/red]"
        elif status == "warning":
            text = f"[yellow]{ratio:.0%}[/yellow] of {new_state.max_tokens // 1000}k tokens [yellow]⚠ WARNING[/yellow]"
        elif status == "compaction_ready":
            text = f"[cyan]{ratio:.0%}[/cyan] of {new_state.max_tokens // 1000}k tokens [cyan]⟳ READY[/cyan]"
        else:
            text = f"{ratio:.0%} of {new_state.max_tokens // 1000}k tokens"

        self.update(text)
