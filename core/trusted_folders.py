"""Trust folder system for directory safety"""

from __future__ import annotations

from pathlib import Path

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore

tomli_w = None
try:
    import tomli_w as _tomli_w
    tomli_w = _tomli_w
except ImportError:
    pass


class TrustedFoldersManager:
    """Manages trusted and untrusted folders"""

    def __init__(self):
        self._file_path = Path.home() / ".jarvis" / "trusted_folders.toml"
        self._trusted: list[str] = []
        self._untrusted: list[str] = []
        self._session_trusted: list[str] = []
        self._load()

    def trust_for_session(self, path: Path) -> None:
        """
        Trust a path for the current session only

        Args:
            path: Path to trust
        """
        self._session_trusted.append(self._normalize_path(path))

    def untrust_for_session(self, path: Path) -> None:
        """
        Remove a path from the current session trust list.

        Args:
            path: Path to untrust for the current session
        """
        normalized = self._normalize_path(path)
        self._session_trusted = [p for p in self._session_trusted if p != normalized]

    def _normalize_path(self, path: Path) -> str:
        """Normalize a path to absolute string"""
        return str(path.expanduser().resolve())

    def _load(self) -> None:
        """Load trusted folders from disk"""
        if not self._file_path.is_file():
            self._trusted = []
            self._untrusted = []
            self._save()
            return

        try:
            with self._file_path.open("rb") as f:
                data = tomllib.load(f)
            self._trusted = list(data.get("trusted", []))
            self._untrusted = list(data.get("untrusted", []))
        except (OSError, Exception):
            self._trusted = []
            self._untrusted = []
            self._save()

    def _save(self) -> None:
        """Save trusted folders to disk"""
        self._file_path.parent.mkdir(parents=True, exist_ok=True)
        data = {"trusted": self._trusted, "untrusted": self._untrusted}

        if tomli_w is None:
            return

        try:
            with self._file_path.open("wb") as f:
                tomli_w.dump(data, f)
        except OSError:
            pass

    def is_trusted(self, path: Path) -> bool | None:
        """
        Check if a path is trusted (walks up directory tree)

        Args:
            path: Path to check

        Returns:
            True if trusted, False if untrusted, None if no decision exists
        """
        current = Path(self._normalize_path(path))

        while True:
            s = str(current)
            if s in self._trusted or s in self._session_trusted:
                return True
            if s in self._untrusted:
                return False

            parent = current.parent
            if parent == current:
                break
            current = parent

        return None

    def find_trust_root(self, path: Path) -> Path | None:
        """
        Find the closest ancestor (or path itself) that is explicitly trusted

        Args:
            path: Path to search from

        Returns:
            Trusted path or None
        """
        current = Path(self._normalize_path(path))

        while True:
            s = str(current)
            if s in self._trusted or s in self._session_trusted:
                return current

            parent = current.parent
            if parent == current:
                break
            current = parent

        return None

    def add_trusted(self, path: Path) -> None:
        """
        Add a path to the trusted list

        Args:
            path: Path to trust
        """
        normalized = self._normalize_path(path)
        if normalized not in self._trusted:
            self._trusted.append(normalized)
        if normalized in self._untrusted:
            self._untrusted.remove(normalized)
        self._save()

    def add_untrusted(self, path: Path) -> None:
        """
        Add a path to the untrusted list

        Args:
            path: Path to untrust
        """
        normalized = self._normalize_path(path)
        if normalized not in self._untrusted:
            self._untrusted.append(normalized)
        if normalized in self._trusted:
            self._trusted.remove(normalized)
        self._save()

    def clear_session_trust(self) -> None:
        """Clear all session-level trust"""
        self._session_trusted.clear()

    def get_stats(self) -> dict:
        """Get trust folder statistics"""
        return {
            "trusted": len(self._trusted),
            "untrusted": len(self._untrusted),
            "session_trusted": len(self._session_trusted),
        }


# Global instance
trusted_folders_manager = TrustedFoldersManager()
