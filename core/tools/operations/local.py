"""Default local implementations of operation protocols.

These use ``aiofiles`` / ``pathlib`` / ``asyncio.create_subprocess_shell``
and represent the standard JARVIS behaviour before any backend override.
"""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path

import aiofiles

logger = logging.getLogger(__name__)


class LocalFileOperations:
    """Default filesystem operations using ``aiofiles`` + ``pathlib``."""

    async def read_file(self, path: str | Path, offset: int = 1, limit: int | None = None) -> str:
        path = Path(path)
        if not path.exists() or not path.is_file():
            raise FileNotFoundError(f"File not found: {path}")

        async with aiofiles.open(path, "r", encoding="utf-8", errors="replace") as f:
            content = await f.read()

        if offset > 1 or limit is not None:
            lines = content.splitlines(keepends=True)
            start = max(0, offset - 1)
            if limit is not None:
                lines = lines[start : start + limit]
            else:
                lines = lines[start:]
            content = "".join(lines)

        return content

    async def write_file(self, path: str | Path, content: str) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        async with aiofiles.open(path, "w", encoding="utf-8") as f:
            await f.write(content)

    async def file_exists(self, path: str | Path) -> bool:
        return Path(path).exists() and Path(path).is_file()

    async def list_dir(self, path: str | Path) -> list[dict]:
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"Directory not found: {path}")
        if not p.is_dir():
            raise NotADirectoryError(f"Not a directory: {path}")

        entries = []
        for child in sorted(p.iterdir()):
            try:
                stat = child.stat()
                entries.append({
                    "name": child.name,
                    "type": "dir" if child.is_dir() else "file",
                    "size": stat.st_size,
                    "modified": stat.st_mtime,
                })
            except OSError:
                entries.append({
                    "name": child.name,
                    "type": "unknown",
                    "size": 0,
                    "modified": 0,
                })
        return entries

    async def delete_file(self, path: str | Path) -> None:
        Path(path).unlink(missing_ok=True)


class LocalBashOperations:
    """Default shell operations using ``asyncio.create_subprocess_shell``."""

    async def run(
        self,
        command: str,
        timeout: float | None = None,
        cwd: str | None = None,
        env: dict[str, str] | None = None,
    ) -> dict:
        process = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd or os.getcwd(),
            env={**os.environ, **(env or {})},
        )

        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=timeout
            )
        except asyncio.TimeoutError:
            process.kill()
            stdout, stderr = await process.communicate()
            return {
                "stdout": stdout.decode("utf-8", errors="replace") if stdout else "",
                "stderr": (stderr.decode("utf-8", errors="replace") if stderr else "")
                          + f"\n[Timeout after {timeout}s]",
                "exit_code": -1,
            }

        return {
            "stdout": stdout.decode("utf-8", errors="replace") if stdout else "",
            "stderr": stderr.decode("utf-8", errors="replace") if stderr else "",
            "exit_code": process.returncode or 0,
        }

    async def spawn(
        self,
        command: list[str],
        cwd: str | None = None,
        env: dict[str, str] | None = None,
    ) -> dict:
        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd or os.getcwd(),
            env={**os.environ, **(env or {})},
        )
        return {
            "pid": process.pid,
            "process": process,
        }

    async def terminate(self, pid: int) -> None:
        try:
            import signal
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass  # Already dead


class LocalEditOperations:
    """Default file edit operations using local filesystem."""

    async def apply_edit(
        self,
        path: str | Path,
        old_string: str,
        new_string: str,
    ) -> dict:
        p = Path(path)
        if not p.exists():
            return {"success": False, "matches": 0, "error": f"File not found: {path}"}

        content = p.read_text(encoding="utf-8", errors="replace")
        matches = content.count(old_string)

        if matches == 0:
            return {"success": False, "matches": 0, "error": "old_string not found in file"}
        if matches > 1:
            return {"success": False, "matches": matches, "error": f"old_string found {matches} times, must be unique"}

        new_content = content.replace(old_string, new_string, 1)
        p.write_text(new_content, encoding="utf-8")
        return {"success": True, "matches": 1, "error": None}

    async def read_with_encoding(
        self, path: str | Path, encoding: str = "utf-8"
    ) -> str:
        return Path(path).read_text(encoding=encoding, errors="replace")
