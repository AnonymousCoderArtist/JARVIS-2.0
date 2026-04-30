"""Utility functions adapter."""

from dataclasses import dataclass
from typing import Any

from .types import CancellationReason, get_user_cancellation_message, is_dangerous_directory


@dataclass
class TaggedText:
    """Tagged text."""
    text: str
    tags: list[str] | None = None


__all__ = ["CancellationReason", "get_user_cancellation_message", "is_dangerous_directory", "TaggedText"]
