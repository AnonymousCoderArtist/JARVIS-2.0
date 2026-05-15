"""Tool Registry for managing tools"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Coroutine

from .base import BaseTool, ToolOutput


class ToolRegistry:
    """Registry for managing tools"""

    def __init__(self, llm_provider=None, model=None, config_getter=None):
        from core.tools.operations import OperationsRegistry

        self._tools: dict[str, BaseTool] = {}
        self.llm_provider = llm_provider
        self.model = model
        self.config_getter = config_getter
        self.active_skills: dict[str, str] = {}
        self.event_queue = None
        self.event_bus = None  # Set by BaseAgent after construction
        self.operations_registry = OperationsRegistry()

    def register(self, tool: BaseTool):
        """
        Register a tool

        Args:
            tool: Tool instance to register
        """
        # Inject registry and provider references into the tool
        tool.tool_registry = self
        tool.llm_provider = self.llm_provider
        tool.model = self.model
        # Inject event queue if available
        if self.event_queue is not None:
            tool.event_queue = self.event_queue
        # Inject operations registry
        tool.operations_registry = self.operations_registry

        self._tools[tool.name] = tool

    def update_tool_providers(self, llm_provider=None, model=None, config_getter=None, event_queue=None):
        if llm_provider is not None:
            self.llm_provider = llm_provider
        if model is not None:
            self.model = model
        if config_getter is not None:
            self.config_getter = config_getter
        if event_queue is not None:
            self.event_queue = event_queue
        for tool in self._tools.values():
            tool.tool_registry = self
            tool.operations_registry = self.operations_registry
            if llm_provider is not None:
                tool.llm_provider = llm_provider
            if model is not None:
                tool.model = model
            if self.event_queue is not None:
                tool.event_queue = self.event_queue

    def get(self, name: str) -> BaseTool | None:
        return self._tools.get(name)

    def list_tools(self) -> list[dict[str, Any]]:
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.input_schema,
            }
            for tool in self._tools.values()
        ]

    def get_function_definitions(self) -> list[dict[str, Any]]:
        return [tool.get_function_definition() for tool in self._tools.values()]

    def get_tools(self) -> dict[str, BaseTool]:
        """
        Get all registered tools as a dictionary

        Returns:
            Dictionary mapping tool names to tool instances
        """
        return self._tools.copy()

    async def execute_tool(self, name: str, input_data: dict) -> ToolOutput:
        """
        Execute a tool by name

        Args:
            name: Tool name
            input_data: Input parameters dictionary

        Returns:
            ToolOutput with execution results
        """
        import time

        tool = self.get(name)
        if not tool:
            return ToolOutput(
                success=False,
                result=None,
                error=f"Tool '{name}' not found",
            )

        # Emit ToolCallStarted event if event bus is available
        ts = time.time()
        tool_call_id = f"tool_{name}_{int(ts * 1000)}"

        if self.event_bus is not None:
            from core.events.types import ToolCallStarted
            try:
                await self.event_bus.emit(
                    ToolCallStarted(timestamp=ts, tool_name=name, tool_call_id=tool_call_id, args=input_data)
                )
            except Exception:
                pass

        try:
            result = await tool.safe_execute(input_data)

            # Emit ToolCallEnded event
            if self.event_bus is not None:
                from core.events.types import ToolCallEnded
                try:
                    duration = (time.time() - ts) * 1000
                    await self.event_bus.emit(
                        ToolCallEnded(
                            timestamp=time.time(),
                            tool_name=name,
                            tool_call_id=tool_call_id,
                            result=getattr(result, 'result', None),
                            duration_ms=duration,
                            success=getattr(result, 'success', False),
                        )
                    )
                except Exception:
                    pass

            return result
        except Exception as exc:
            # Emit ToolCallError event
            if self.event_bus is not None:
                from core.events.types import ToolCallError
                try:
                    duration = (time.time() - ts) * 1000
                    await self.event_bus.emit(
                        ToolCallError(
                            timestamp=time.time(),
                            tool_name=name,
                            tool_call_id=tool_call_id,
                            error=str(exc),
                            duration_ms=duration,
                        )
                    )
                except Exception:
                    pass
            return ToolOutput(
                success=False,
                result=None,
                error=str(exc),
            )
