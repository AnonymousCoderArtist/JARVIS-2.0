"""File operation tools for the Cowork Agent"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from core.agents.cowork.sandbox import SandboxManager
from core.tools.base import BaseTool


class FileOperationsTool(BaseTool):
    """Tool for file operations with sandbox security"""

    name: str = "file_operations"
    description: str = (
        "Read, write, and list files in a sandboxed environment. "
        "All operations are validated against allowed paths to prevent "
        "unauthorized access."
    )

    def __init__(self, sandbox: SandboxManager | None = None):
        super().__init__()
        self.sandbox = sandbox or SandboxManager()

    async def execute(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """
        Execute a file operation.

        Args:
            input_data: Must contain 'operation' and relevant parameters

        Returns:
            Result dict with operation outcome
        """
        operation = input_data.get("operation", "read")

        if operation == "read":
            return await self._read(input_data)
        elif operation == "write":
            return await self._write(input_data)
        elif operation == "list":
            return await self._list(input_data)
        else:
            return {
                "success": False,
                "error": f"Unknown operation: {operation}",
            }

    async def _read(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Read a file"""
        path = input_data.get("path", "")
        if not path:
            return {"success": False, "error": "No path provided"}
        try:
            content = await self.sandbox.read_file(path)
            return {
                "success": True,
                "path": path,
                "content": content,
            }
        except (PermissionError, FileNotFoundError) as e:
            return {"success": False, "error": str(e)}

    async def _write(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Write a file"""
        path = input_data.get("path", "")
        content = input_data.get("content", "")
        if not path:
            return {"success": False, "error": "No path provided"}
        return await self.sandbox.write_file(path, content)

    async def _list(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """List directory contents"""
        path = input_data.get("path", ".")
        try:
            entries = await self.sandbox.ls(path)
            return {
                "success": True,
                "path": path,
                "entries": entries,
            }
        except (PermissionError, FileNotFoundError, NotADirectoryError) as e:
            return {"success": False, "error": str(e)}


class ReadFileTool(FileOperationsTool):
    """Convenience tool for reading files"""

    name: str = "read_file"
    description: str = "Read a file from the sandboxed filesystem"

    async def execute(self, input_data: dict[str, Any]) -> dict[str, Any]:
        return await self._read(input_data)


class WriteFileTool(FileOperationsTool):
    """Convenience tool for writing files"""

    name: str = "write_file"
    description: str = "Write a file to the sandboxed filesystem"

    async def execute(self, input_data: dict[str, Any]) -> dict[str, Any]:
        return await self._write(input_data)


class ListDirectoryTool(FileOperationsTool):
    """Convenience tool for listing directories"""

    name: str = "list_directory"
    description: str = "List directory contents in the sandboxed filesystem"

    async def execute(self, input_data: dict[str, Any]) -> dict[str, Any]:
        return await self._list(input_data)


class ReadMemoryTool(BaseTool):
    """Tool for reading agent memory"""

    name: str = "read_memory"
    description: str = "Search and retrieve information from agent memory"

    def __init__(self, memory=None):
        super().__init__()
        self.memory = memory

    async def execute(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """
        Search memory for relevant information.

        Args:
            input_data: Must contain 'query'

        Returns:
            Search results from memory
        """
        query = input_data.get("query", "")
        limit = input_data.get("limit", 10)

        if not query:
            return {"success": False, "error": "No query provided"}

        if self.memory is None:
            return {
                "success": False,
                "error": "Memory not initialized",
            }

        results = await self.memory.search(query, limit)
        return {
            "success": True,
            "query": query,
            "results": results,
        }