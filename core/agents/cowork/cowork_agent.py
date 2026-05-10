"""Cowork Agent - Multi-agent collaborative task execution"""

from __future__ import annotations

import asyncio
from typing import Any

from core.agents.base import BaseAgent
from core.agents.cowork.config.settings import CoworkConfig
from core.agents.cowork.memory import CoworkMemory
from core.agents.cowork.prompts.system_prompt import COWORK_SYSTEM_PROMPT
from core.agents.cowork.sandbox import SandboxManager
from core.agents.cowork.task_scheduler import TaskScheduler
from core.tools.registry import ToolRegistry


class CoworkAgent(BaseAgent):
    """
    Cowork Agent: Multi-agent collaborative task execution system.

    Orchestrates sub-agents and tools to decompose and execute complex tasks
    in a sandboxed environment with persistent memory.
    """

    SYSTEM_PROMPT = COWORK_SYSTEM_PROMPT

    def __init__(
        self,
        llm_provider,
        tool_registry: ToolRegistry,
        system_prompt: str = COWORK_SYSTEM_PROMPT,
        model: str | None = None,
        config_getter: callable | None = None,
        bypass_tool_permissions: bool = False,
        use_concurrent_tools: bool = True,
        config: CoworkConfig | None = None,
        **kwargs,
    ):
        self.cowork_config = config or CoworkConfig()
        self.sandbox = SandboxManager(self.cowork_config)
        self.memory = CoworkMemory(
            max_entries=self.cowork_config.max_memory_entries,
            retention_days=self.cowork_config.memory_retention_days,
        )
        self.task_scheduler = TaskScheduler(
            max_concurrent=self.cowork_config.max_concurrent_tasks
        )

        super().__init__(
            llm_provider=llm_provider,
            tool_registry=tool_registry,
            system_prompt=system_prompt,
            model=model,
            config_getter=config_getter,
            bypass_tool_permissions=bypass_tool_permissions,
            use_concurrent_tools=use_concurrent_tools,
            auto_discover_context=False,
            **kwargs,
        )

        # Register cowork-specific tools with the registry
        cowork_tools = self._build_tools()
        for tool in cowork_tools:
            tool_registry.register(tool)

        self.rebuild_system_prompt()

    def _build_tools(self) -> list[Any]:
        """Build the list of cowork-specific tools"""
        from core.agents.cowork.tools.codegen import CodeGenerationTool
        from core.agents.cowork.tools.fileops import (
            ListDirectoryTool,
            ReadFileTool,
            ReadMemoryTool,
            WriteFileTool,
        )
        from core.agents.cowork.tools.system_ops import (
            MemoryManagementTool,
            ShellExecutionTool,
            SystemInfoTool,
        )

        return [
            CodeGenerationTool(self.sandbox),
            ReadFileTool(self.sandbox),
            WriteFileTool(self.sandbox),
            ListDirectoryTool(self.sandbox),
            ReadMemoryTool(self.memory),
            ShellExecutionTool(self.sandbox),
            SystemInfoTool(),
            MemoryManagementTool(self.memory),
        ]

    async def process(self, input: str, context: dict[str, Any] | None = None) -> str:
        """
        Process a user request through the Cowork agentic loop.

        Args:
            input: User input describing the task
            context: Optional context dictionary

        Returns:
            Agent response string
        """
        user_content = self._build_prompt(input, context)
        messages = self._build_messages(user_content, include_memory=True)

        self._current_state = {
            "messages": messages,
            "iteration": 0,
            "actions_taken": [],
            "memory_updates": [],
        }

        result = await self._process_loop()

        self.add_to_memory({
            "content": f"Task: {input}",
            "response": result,
            "type": "cowork_task",
        })

        return result

    def _build_prompt(self, input: str, context: dict | None) -> str:
        """Build the prompt for the cowork task"""
        prompt = f"Task: {input}\n\n"
        if context:
            if "current_file" in context:
                prompt += f"Current file: {context['current_file']}\n"
            if "project_path" in context:
                prompt += f"Project path: {context['project_path']}\n"
            if "file_content" in context:
                prompt += f"\nFile content:\n{context['file_content']}\n"
        return prompt

    async def _process_loop(self) -> str:
        """
        Main agentic loop: generate -> decide -> act -> repeat.

        Returns:
            Final response string
        """
        max_iterations = self.cowork_config.max_iterations or 100
        timeout_per_action = self.cowork_config.timeout_per_action or 60

        while self._current_state["iteration"] < max_iterations:
            messages = self._current_state["messages"]

            try:
                response = await asyncio.wait_for(
                    self._process_with_tools(messages, stream=False),
                    timeout=timeout_per_action,
                )
            except asyncio.TimeoutError:
                return "Task timed out."
            except Exception as e:
                return f"Processing error: {str(e)}"

            if self._is_task_complete(response):
                return self._finalize(response)

            action = self._select_next_action(response)
            if action is None:
                return self._finalize(response)

            action_result = await self._execute_action(action)
            await self._update_state(response, action, action_result)
            self._current_state["iteration"] += 1

        return "Maximum iterations reached."

    def _is_task_complete(self, response: str) -> bool:
        content = response.upper()
        markers = [
            "COMPLETE", "DONE", "FINISHED",
            "FINAL ANSWER", "FINAL RESULT",
            "NO FURTHER ACTION", "TASK COMPLETE",
        ]
        return any(m in content for m in markers)

    def _select_next_action(self, response: str) -> dict[str, Any] | None:
        content_lower = response.lower()
        action_patterns = {
            "shell_execution": ["shell:", "exec:", "command:", "bash:"],
            "file_read": ["read file:", "read:", "open:"],
            "file_write": ["write file:", "write:", "create:"],
            "list_directory": ["list:", "ls:", "dir:"],
            "code_generation": ["generate code:", "code:", "generate:"],
            "memory_store": ["remember:", "store:", "save memory:"],
            "memory_recall": ["recall:", "search memory:", "memory:"],
            "plan_task": ["plan:", "decompose:", "break down:"],
        }
        for action_type, patterns in action_patterns.items():
            for pattern in patterns:
                if pattern in content_lower:
                    idx = content_lower.find(pattern)
                    return {
                        "type": action_type,
                        "content": response[idx + len(pattern):].strip(),
                    }
        return None

    async def _execute_action(
        self, action: dict[str, Any]
    ) -> dict[str, Any]:
        action_type = action.get("type", "")
        content = action.get("content", "")
        try:
            tool_name, tool_args = self._map_action_to_tool(action_type, content)
            result = await self.tools.execute_tool(tool_name, tool_args)
            if hasattr(result, "success"):
                return {
                    "success": result.success,
                    "result": result.result,
                    "action_type": action_type,
                }
            return {"success": True, "result": str(result), "action_type": action_type}
        except Exception as e:
            return {"success": False, "error": str(e), "action_type": action_type}

    def _map_action_to_tool(self, action_type: str, content: str) -> tuple[str, dict[str, Any]]:
        if action_type == "shell_execution":
            return ("shell_execution", {"command": content})
        elif action_type == "file_read":
            return ("read_file", {"path": content})
        elif action_type == "file_write":
            lines = content.split("\n", 1)
            path = lines[0].strip()
            file_content = lines[1].strip() if len(lines) > 1 else ""
            return ("write_file", {"path": path, "content": file_content})
        elif action_type == "list_directory":
            return ("list_directory", {"path": content or "."})
        elif action_type == "code_generation":
            return ("code_generation", {"action": "generate", "specification": content, "language": "python"})
        elif action_type == "memory_store":
            return ("memory_management", {"action": "add", "key": "note", "value": content, "scope": "session"})
        elif action_type == "memory_recall":
            return ("read_memory", {"query": content})
        return ("shell_execution", {"command": content})

    async def _update_state(
        self,
        response: str,
        action: dict[str, Any],
        action_result: dict[str, Any],
    ) -> None:
        self._current_state["actions_taken"].append({
            "iteration": self._current_state["iteration"],
            "action": action,
            "result": action_result,
        })
        result_message = {
            "role": "tool",
            "tool_name": action.get("type", "action"),
            "content": str(action_result),
        }
        self._current_state["messages"].append(result_message)
        if action_result.get("success"):
            self.memory.add(
                f"action_{self._current_state['iteration']}",
                {"action": action, "result": action_result},
                scope="session",
            )

    async def plan(self, task: str) -> list[dict[str, Any]]:
        """
        Plan a task using decomposition.

        Args:
            task: Task description to plan

        Returns:
            List of planned steps
        """
        return await self.task_scheduler.decompose_and_plan(task)

    def _finalize(self, response: str) -> str:
        summary = (
            f"[Cowork completed in {self._current_state['iteration']} iterations. "
            f"Actions taken: {len(self._current_state['actions_taken'])}]"
        )
        return f"{response}\n\n--- Cowork Agent Summary ---\n{summary}\n"
