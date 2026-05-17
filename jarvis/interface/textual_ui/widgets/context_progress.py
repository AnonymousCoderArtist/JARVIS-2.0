from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from textual.reactive import reactive
from textual.widgets import Static


@dataclass
class TokenState:
    max_tokens: int = 0
    current_tokens: int = 0
    status: str = "ok"  # "ok", "warning", "critical", "compaction_ready"


class ContextProgress(Static):
    tokens = reactive(TokenState())

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

    def watch_tokens(self, new_state: TokenState) -> None:
        if new_state.max_tokens == 0:
            self.update("")
            return

        ratio = min(1, new_state.current_tokens / new_state.max_tokens)
        status = new_state.status

        # Color only the percentage based on status
        if status == "critical":
            color = "red"
        elif status == "warning":
            color = "yellow"
        elif status == "compaction_ready":
            color = "cyan"
        else:
            color = "green"

        text = f"[{color}]{ratio:.0%}[/{color}] of {new_state.max_tokens // 1000}k tokens"

        self.update(text)
