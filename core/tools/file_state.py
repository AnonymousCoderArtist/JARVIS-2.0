"""File state tracking system for deduplication and modification detection"""

import os
import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional


@dataclass
class FileReadState:
    """State information for a file read operation"""
    mtime: float
    offset: int
    limit: int
    content_hash: str
    can_dedup: bool


class FileStates:
    """Track file read/write operations for deduplication and safety checks"""

    def __init__(self):
        self._state: Dict[str, FileReadState] = {}

    def _hash_file(self, path: str) -> str:
        """Calculate hash of file content"""
        try:
            hash_obj = hashlib.sha256()
            with open(path, 'rb') as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_obj.update(chunk)
            return hash_obj.hexdigest()
        except Exception:
            return ""

    def record_read(self, path: str | Path, offset: int = 1, limit: int | None = None) -> None:
        """Record that a file was read"""
        p = str(Path(path).resolve())
        try:
            mtime = os.path.getmtime(p)
        except OSError:
            return

        self._state[p] = FileReadState(
            mtime=mtime,
            offset=offset,
            limit=limit or 0,
            content_hash=self._hash_file(p),
            can_dedup=True
        )

    def record_write(self, path: str | Path) -> None:
        """Record that a file was written"""
        p = str(Path(path).resolve())
        try:
            mtime = os.path.getmtime(p)
        except OSError:
            self._state.pop(p, None)
            return

        self._state[p] = FileReadState(
            mtime=mtime,
            offset=1,
            limit=0,
            content_hash=self._hash_file(p),
            can_dedup=False
        )

    def check_read(self, path: str | Path) -> Optional[str]:
        """Check if a file has been read and is fresh"""
        p = str(Path(path).resolve())
        entry = self._state.get(p)
        
        if entry is None:
            return "Warning: file has not been read yet. Read it first to verify content before editing."

        try:
            current_mtime = os.path.getmtime(p)
        except OSError:
            return None

        if current_mtime != entry.mtime:
            if entry.content_hash and self._hash_file(p) == entry.content_hash:
                entry.mtime = current_mtime
                return None
            return "Warning: file has been modified since last read. Re-read to verify content before editing."

        if entry.content_hash and self._hash_file(p) != entry.content_hash:
            return "Warning: file has been modified since last read. Re-read to verify content before editing."

        return None

    def get(self, path: str | Path) -> Optional[FileReadState]:
        """Get file state by path"""
        p = str(Path(path).resolve())
        return self._state.get(p)


# Global file states instance
current_file_states = FileStates()