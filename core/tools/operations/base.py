"""Abstract operation interfaces (Protocols) for file, bash, and edit operations.

These protocols define the contract that backends must implement.
The default local implementation is in :mod:`core.tools.operations.local`.
Extensions can provide alternative backends (SSH, sandbox, Docker, etc.)
by implementing these protocols and registering them with the
:class:`OperationsRegistry`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

# ---------------------------------------------------------------------------
# File Operations
# ---------------------------------------------------------------------------


@runtime_checkable
class FileOperations(Protocol):
    """Abstract filesystem operations.

    The default implementation uses ``aiofiles`` and ``pathlib``.
    """

    async def read_file(self, path: str | Path, offset: int = 1, limit: int | None = None) -> str:
        """Read file content, optionally restricted to a *offset*-based line range."""
        ...

    async def write_file(self, path: str | Path, content: str) -> None:
        """Write *content* to *path*, creating parent directories if needed."""
        ...

    async def file_exists(self, path: str | Path) -> bool:
        """Return ``True`` if *path* exists and is a regular file."""
        ...

    async def list_dir(self, path: str | Path) -> list[dict]:
        """List directory contents, returning dicts with ``name``, ``type``, ``size``."""
        ...

    async def delete_file(self, path: str | Path) -> None:
        """Delete the file at *path*."""
        ...


# ---------------------------------------------------------------------------
# Bash / Shell Operations
# ---------------------------------------------------------------------------


@runtime_checkable
class BashOperations(Protocol):
    """Abstract shell command execution.

    The default implementation uses ``asyncio.create_subprocess_shell``.
    """

    async def run(
        self,
        command: str,
        timeout: float | None = None,
        cwd: str | None = None,
        env: dict[str, str] | None = None,
    ) -> dict:
        """Run a command and return ``{"stdout": …, "stderr": …, "exit_code": …}``."""
        ...

    async def spawn(
        self,
        command: list[str],
        cwd: str | None = None,
        env: dict[str, str] | None = None,
    ) -> dict:
        """Spawn a long-running process (returns process info)."""
        ...

    async def terminate(self, pid: int) -> None:
        """Kill a process by PID."""
        ...


# ---------------------------------------------------------------------------
# Edit Operations
# ---------------------------------------------------------------------------


@runtime_checkable
class EditOperations(Protocol):
    """Abstract file editing operations."""

    async def apply_edit(
        self,
        path: str | Path,
        old_string: str,
        new_string: str,
    ) -> dict:
        """Apply a search-and-replace edit.

        Returns ``{"success": bool, "matches": int, "error": str | None}``.
        """
        ...

    async def read_with_encoding(
        self, path: str | Path, encoding: str = "utf-8"
    ) -> str:
        """Read file using explicit encoding."""
        ...
