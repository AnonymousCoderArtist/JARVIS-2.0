"""Filtered tool registry for subagent tool access control."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from jarvis.core.tools.base import BaseTool, ToolOutput, resolve_tool_ref


class _FilteredToolRegistry:
    """Read-only filtered view over a tool registry.

    This class provides a restricted view of the tool registry,
    allowing only specified tools to be accessed while blocking others.

    Attributes:
        _source_registry: The underlying tool registry
        _allowed_tools: Set of tool names that are allowed
        llm_provider: LLM provider to use
        model: Model name to use
        config_getter: Configuration getter function
        active_skills: Active skills from source registry
    """

    def __init__(
        self,
        source_registry,
        allowed_tools: Iterable[str | Any],
        llm_provider=None,
        model=None,
        config_getter=None,
    ):
        """Initialize the filtered registry.

        Args:
            source_registry: The underlying tool registry
            allowed_tools: Iterable of tool names (str), tool classes, or tool instances to allow
            llm_provider: LLM provider to use
            model: Model name to use
            config_getter: Configuration getter function
        """
        self._source_registry = source_registry
        self._allowed_tools = {resolve_tool_ref(t) for t in allowed_tools}
        self.llm_provider = llm_provider
        self.model = model
        self.config_getter = config_getter
        self.active_skills = getattr(source_registry, "active_skills", {})

    def get(self, name: str):
        """Get a tool by name if allowed.
        
        Args:
            name: Tool name to retrieve
            
        Returns:
            Tool if allowed and exists, None otherwise
        """
        if name not in self._allowed_tools:
            return None
        return self._source_registry.get(name)

    def get_tools(self) -> dict[str, BaseTool]:
        """Get all allowed tools.
        
        Returns:
            Dictionary of allowed tool names to tool instances
        """
        result: dict[str, BaseTool] = {}
        for name in self._allowed_tools:
            tool = self.get(name)
            if tool is not None:
                result[name] = tool
        return result

    def list_tools(self) -> list[dict[str, object]]:
        """List all allowed tools with metadata.
        
        Returns:
            List of tool metadata dictionaries
        """
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.input_schema,
            }
            for tool in self.get_tools().values()
        ]

    def get_function_definitions(self) -> list[dict[str, object]]:
        """Get function definitions for all allowed tools.
        
        Returns:
            List of function definition dictionaries
        """
        return [tool.get_function_definition() for tool in self.get_tools().values()]

    async def execute_tool(self, name: str, input_data: dict) -> ToolOutput:
        """Execute a tool if allowed.
        
        Args:
            name: Tool name to execute
            input_data: Input data for the tool
            
        Returns:
            ToolOutput with result or error if tool not allowed
        """
        if name not in self._allowed_tools:
            return ToolOutput(
                success=False,
                result=None,
                error=f"Tool '{name}' is not available to the explore subagent.",
            )
        return await self._source_registry.execute_tool(name, input_data)
