"""Utility functions for textual_ui - replaces adapter.core.utils"""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Any


class CancellationReason(StrEnum):
    """Reason for cancellation"""
    OPERATION_CANCELLED = "operation_cancelled"
    TOOL_INTERRUPTED = "tool_interrupted"


class TaggedText:
    """Text with optional tagging for display"""

    def __init__(self, text: str = "", tags: list[str] | None = None):
        self.text = text
        self.tags = tags or []

    @property
    def message(self) -> str:
        """Return the text content"""
        return self.text

    @classmethod
    def from_string(cls, text: str) -> "TaggedText":
        """Create a TaggedText from a string"""
        return cls(text=text)


def get_user_cancellation_message(reason: Any) -> str:
    """Get a user-friendly cancellation message"""
    return "Operation was cancelled"


def is_dangerous_directory(path: Path | str) -> tuple[bool, str]:
    """Check if a directory is potentially dangerous to operate on"""
    dangerous_paths = {
        "/",
        "/usr",
        "/bin",
        "/sbin",
        "/etc",
        "/var",
        "/sys",
        "/proc",
        "/dev",
        "C:\\",
        "C:\\Windows",
        "C:\\Program Files",
        "C:\\Program Files (x86)",
    }
    
    path_str = str(path)
    for dangerous in dangerous_paths:
        if path_str == dangerous or path_str.startswith(dangerous + "/") or path_str.startswith(dangerous + "\\"):
            return True, f"Running in system directory: {path_str}"
    
    return False, ""


def compact_reduction_display(old_tokens: int | None, new_tokens: int | None) -> str:
    """Format token reduction for display"""
    if old_tokens is None or new_tokens is None:
        return "Unknown reduction"
    reduction = (old_tokens - new_tokens) / old_tokens if old_tokens > 0 else 0
    return f"{reduction:.1%} reduction ({old_tokens} → {new_tokens} tokens)"
