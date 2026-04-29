"""Tool Registry for managing tools"""

import importlib.util
import sys
from pathlib import Path
from typing import Any

from .base import BaseTool, ToolOutput


class ToolRegistry:
    """Registry for managing tools"""

    def __init__(self):
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool):
        """
        Register a tool

        Args:
            tool: Tool instance to register
        """
        self._tools[tool.name] = tool

    def get(self, name: str) -> BaseTool | None:
        """
        Get a registered tool by name

        Args:
            name: Tool name

        Returns:
            Tool instance or None if not found
        """
        return self._tools.get(name)

    def list_tools(self) -> list[dict[str, Any]]:
        """
        List all registered tools

        Returns:
            List of tool information dictionaries
        """
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.input_schema,
            }
            for tool in self._tools.values()
        ]

    def get_function_definitions(self) -> list[dict[str, Any]]:
        """
        Get all tools in OpenAI function calling format

        Returns:
            List of function definitions
        """
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
        tool = self.get(name)
        if not tool:
            return ToolOutput(
                success=False,
                result=None,
                error=f"Tool '{name}' not found",
            )

        return await tool.safe_execute(input_data)

    def register_plugin(self, plugin_path: str):
        """
        Dynamically load a tool plugin

        Args:
            plugin_path: Path to the plugin Python file
        """
        try:
            path = Path(plugin_path)
            if not path.exists():
                raise FileNotFoundError(f"Plugin file not found: {plugin_path}")

            spec = importlib.util.spec_from_file_location(
                f"tool_plugin_{path.stem}", plugin_path
            )
            if spec is None or spec.loader is None:
                raise ImportError(f"Failed to load plugin: {plugin_path}")

            module = importlib.util.module_from_spec(spec)
            sys.modules[f"tool_plugin_{path.stem}"] = module
            spec.loader.exec_module(module)

            # Look for classes that inherit from BaseTool
            registered_count = 0
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (
                    isinstance(attr, type)
                    and issubclass(attr, BaseTool)
                    and attr != BaseTool
                ):
                    try:
                        tool_instance = attr()
                        self.register(tool_instance)
                        registered_count += 1
                        print(f"Registered tool plugin: {tool_instance.name}")
                    except Exception as e:
                        print(f"Failed to instantiate tool {attr_name}: {str(e)}")

            if registered_count == 0:
                raise ImportError(f"No valid tool class found in {plugin_path}")

        except Exception as e:
            raise RuntimeError(f"Failed to load tool plugin {plugin_path}: {str(e)}") from e
