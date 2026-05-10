"""Sandboxed execution environment for the Cowork Agent"""

from __future__ import annotations

import asyncio
import os
import subprocess
from pathlib import Path
from typing import Any

from core.agents.cowork.config.settings import CoworkConfig


class SandboxManager:
    """Manages sandboxed file and command execution for the Cowork Agent"""

    def __init__(self, config: CoworkConfig | None = None):
        if config is None:
            config = CoworkConfig()
        self.config = config
        self._allowed_paths = [
            Path(p).resolve() for p in config.allowed_paths
        ]
        # Always allow working directory
        self._allowed_paths.append(Path.cwd().resolve())

    def validate_path(self, path: str) -> bool:
        """
        Validate that a path is within allowed boundaries.

        Prevents path traversal attacks by checking resolved paths
        against the allowed paths list.

        Args:
            path: Path string to validate

        Returns:
            True if the path is allowed, False otherwise
        """
        try:
            resolved = Path(path).resolve()
        except (ValueError, OSError):
            return False

        # Check if path is within any allowed directory
        for allowed in self._allowed_paths:
            try:
                resolved.relative_to(allowed)
                return True
            except ValueError:
                continue

        return False

    async def execute_command(
        self, command: str, timeout: int = 30
    ) -> dict[str, Any]:
        """
        Execute a shell command in a sandboxed environment.

        Args:
            command: Shell command to execute
            timeout: Timeout in seconds

        Returns:
            Dictionary with stdout, stderr, return code, and success status
        """
        if not self.config.sandbox_enabled:
            return {
                "success": False,
                "error": "Sandbox is disabled",
                "stdout": "",
                "stderr": "",
                "return_code": -1,
            }

        # Validate command does not contain path traversal
        if ".." in command:
            return {
                "success": False,
                "error": "Path traversal detected in command",
                "stdout": "",
                "stderr": "",
                "return_code": -1,
            }

        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(), timeout=timeout
                )
                return {
                    "success": proc.returncode == 0,
                    "stdout": stdout.decode("utf-8", errors="replace"),
                    "stderr": stderr.decode("utf-8", errors="replace"),
                    "return_code": proc.returncode,
                }
            except asyncio.TimeoutError:
                proc.kill()
                return {
                    "success": False,
                    "error": f"Command timed out after {timeout}s",
                    "stdout": "",
                    "stderr": "",
                    "return_code": -1,
                }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "stdout": "",
                "stderr": "",
                "return_code": -1,
            }

    async def read_file(self, path: str) -> str:
        """
        Read a file with path validation.

        Args:
            path: Path to file to read

        Returns:
            File contents as a string

        Raises:
            PermissionError: If path is not allowed
            FileNotFoundError: If file does not exist
        """
        if not self.validate_path(path):
            raise PermissionError(f"Access denied: {path} is outside allowed paths")

        resolved = Path(path).resolve()
        if not resolved.exists():
            raise FileNotFoundError(f"File not found: {path}")

        return resolved.read_text(encoding="utf-8")

    async def write_file(self, path: str, content: str) -> dict[str, Any]:
        """
        Write a file with path validation.

        Args:
            path: Path to write file to
            content: Content to write

        Returns:
            Dictionary with success status and message
        """
        if not self.validate_path(path):
            return {
                "success": False,
                "error": f"Access denied: {path} is outside allowed paths",
            }

        resolved = Path(path).resolve()

        # Create parent directories if they don't exist
        resolved.parent.mkdir(parents=True, exist_ok=True)

        try:
            resolved.write_text(content, encoding="utf-8")
            return {
                "success": True,
                "path": str(resolved),
                "message": f"File written successfully: {path}",
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to write file: {str(e)}",
            }

    async def ls(self, path: str) -> list[dict[str, Any]]:
        """
        List directory contents with path validation.

        Args:
            path: Path to directory to list

        Returns:
            List of file/directory info dictionaries
        """
        if not self.validate_path(path):
            raise PermissionError(f"Access denied: {path} is outside allowed paths")

        resolved = Path(path).resolve()
        if not resolved.exists():
            raise FileNotFoundError(f"Path not found: {path}")

        if not resolved.is_dir():
            raise NotADirectoryError(f"Not a directory: {path}")

        results = []
        try:
            for entry in sorted(resolved.iterdir(), key=lambda p: (p.is_file(), p.name)):
                stat = entry.stat()
                results.append(
                    {
                        "name": entry.name,
                        "path": str(entry),
                        "is_dir": entry.is_dir(),
                        "size": stat.st_size,
                        "modified": stat.st_mtime,
                    }
                )
        except PermissionError:
            raise PermissionError(f"Permission denied: {path}")

        return results