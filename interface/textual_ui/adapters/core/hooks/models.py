"""Hooks models."""

from dataclasses import dataclass
from enum import Enum


class HookStatus(str, Enum):
    """Hook status."""
    SUCCESS = "success"
    FAILURE = "failure"
    WARNING = "warning"


@dataclass
class HookStartEvent:
    """Hook start event."""
    hook_name: str = ""


@dataclass
class HookEndEvent:
    """Hook end event."""
    hook_name: str = ""
    content: str = ""
    status: HookStatus = HookStatus.SUCCESS


@dataclass
class HookRunStartEvent:
    """Hook run start event."""
    pass


@dataclass
class HookRunEndEvent:
    """Hook run end event."""
    pass


@dataclass
class HookEvent:
    """Hook event base."""
    pass
