"""Windowing adapter - re-export windowing components and add missing functions."""

from interface.textual_ui.windowing import (
    HISTORY_RESUME_TAIL_MESSAGES,
    LOAD_MORE_BATCH_SIZE,
    HistoryLoadMoreManager,
    SessionWindowing,
    build_history_widgets,
)


def create_resume_plan() -> dict:
    """Create resume plan."""
    return {}


def non_system_history_messages(messages: list) -> list:
    """Filter non-system history messages."""
    return [m for m in messages if hasattr(m, 'role') and m.role != 'system']


def should_resume_history() -> bool:
    """Should resume history."""
    return False


def sync_backfill_state() -> None:
    """Sync backfill state."""
    pass
