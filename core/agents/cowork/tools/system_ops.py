"""System operations tools for the Cowork Agent"""

from __future__ import annotations

import asyncio
import platform
import os
from typing import Any

from core.agents.cowork.sandbox import SandboxManager
from core.agents.cowork.memory import CoworkMemory
from core.tools.base import BaseTool


class ShellExecutionTool(BaseTool):
    """Tool for executing shell commands in a sandbox"""

    name: str = "shell_execution"
    description: str = (
        "Execute shell commands in a sandboxed environment. "
        "Commands are validated and subject to timeout controls."
    )

    def __init__(self, sandbox: SandboxManager | None = None):
        super().__init__()
        self.sandbox = sandbox or SandboxManager()

    async def execute(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """
        Execute a shell command.

        Args:
            input_data: Must contain 'command' and optionally 'timeout'

        Returns:
            Command execution result
        """
        command = input_data.get("command", "")
        timeout = input_data.get("timeout", 30)

        if not command:
            return {"success": False, "error": "No command provided"}

        return await self.sandbox.execute_command(command, timeout=timeout)


class SystemInfoTool(BaseTool):
    """Tool for retrieving system information"""

    name: str = "system_info"
    description: str = "Retrieve system and environment information"

    async def execute(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """
        Get system information.

        Returns:
            System information dictionary
        """
        cwd = Path.cwd()
        py_version = platform.python_version()

        return {
            "success": True,
            "platform": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "python_version": py_version,
            "cwd": str(cwd),
            "home": str(Path.home()),
            "env_vars": {
                k: v
                for k, v in os.environ.items()
                if k.startswith("JARVIS") or k.startswith("PATH")
            },
        }


class MemoryManagementTool(BaseTool):
    """Tool for managing agent memory"""

    name: str = "memory_management"
    description: str = (
        "Add, retrieve, search, and manage persistent memory entries. "
        "Supports session-scoped and persistent memory."
    )

    def __init__(self, memory: CoworkMemory | None = None):
        super().__init__()
        self.memory = memory or CoworkMemory()

    async def execute(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """
        Manage memory operations.

        Args:
            input_data: Must contain 'action' (add/get/search/delete/clear/cleanup)

        Returns:
            Memory operation result
        """
        action = input_data.get("action", "")

        if action == "add":
            key = input_data.get("key", "")
            value = input_data.get("value")
            scope = input_data.get("scope", "session")
            if not key:
                return {"success": False, "error": "No key provided"}
            await self.memory.add(key, value, scope=scope)
            return {"success": True, "message": f"Added to memory: {key}"}

        elif action == "get":
            key = input_data.get("key", "")
            scope = input_data.get("scope", None)
            if not key:
                return {"success": False, "error": "No key provided"}
            value = await self.memory.get(key, scope=scope)
            return {"success": True, "key": key, "value": value}

        elif action == "search":
            query = input_data.get("query", "")
            limit = input_data.get("limit", 10)
            results = await self.memory.search(query, limit)
            return {"success": True, "query": query, "results": results}

        elif action == "delete":
            key = input_data.get("key", "")
            if not key:
                return {"success": False, "error": "No key provided"}
            result = await self.memory.delete(key)
            return {"success": result, "key": key}

        elif action == "clear":
            await self.memory.clear()
            return {"success": True, "message": "Memory cleared"}

        elif action == "cleanup":
            removed = await self.memory.cleanup_expired()
            return {"success": True, "removed": removed}

        elif action == "summary":
            summary = await self.memory.summarize()
            return {"success": True, "summary": summary}

        else:
            return {
                "success": False,
                "error": f"Unknown action: {action}",
            }