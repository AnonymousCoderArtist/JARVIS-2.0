from __future__ import annotations

from enum import Enum
from typing import Protocol


class NotificationContext(str, Enum):
    ACTION_REQUIRED = "action_required"
    COMPLETE = "complete"

    def __str__(self) -> str:
        return self.value


class NotificationPort(Protocol):
    def notify(self, context: NotificationContext) -> None: ...
    def on_focus(self) -> None: ...
    def on_blur(self) -> None: ...
    def restore(self) -> None: ...
