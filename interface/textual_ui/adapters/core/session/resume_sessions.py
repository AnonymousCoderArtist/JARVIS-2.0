"""Resume sessions adapter."""

from dataclasses import dataclass
from pathlib import Path


@dataclass
class ResumeSessionInfo:
    """Resume session info."""
    session_id: str
    path: Path
    timestamp: str


def list_local_resume_sessions() -> list[ResumeSessionInfo]:
    """List local resume sessions."""
    return []


def list_remote_resume_sessions() -> list[ResumeSessionInfo]:
    """List remote resume sessions."""
    return []


def short_session_id(session_id: str) -> str:
    """Short session ID."""
    return session_id[:8]
