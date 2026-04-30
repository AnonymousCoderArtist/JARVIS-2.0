"""Update notifier adapter."""

from .gateway import PyPIUpdateGateway
from .repository import FileSystemUpdateCacheRepository


class UpdateError(Exception):
    """Update error."""
    pass


class UpdateCacheRepository:
    """Update cache repository."""
    pass


class UpdateGateway:
    """Update gateway."""
    pass


def get_update_if_available() -> str | None:
    """Get update if available."""
    return None


def load_whats_new_content() -> str:
    """Load what's new content."""
    return ""


def mark_version_as_seen(version: str) -> None:
    """Mark version as seen."""
    pass


def should_show_whats_new() -> bool:
    """Should show what's new."""
    return False
