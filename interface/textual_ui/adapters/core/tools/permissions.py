"""Permissions adapter."""

from dataclasses import dataclass


@dataclass
class RequiredPermission:
    """Required permission."""
    permission: str
