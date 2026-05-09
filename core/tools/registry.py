"""Tool Registry for managing tools"""

import importlib.util
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any, Coroutine

from .base import BaseTool, ToolOutput


class ToolRegistry:
    """Registry for managing tools"""

    def __init__(self, llm_provider=None, model=None, config_getter=None):
        self._tools: dict[str, BaseTool] = {}
        self.llm_provider = llm_provider
        self.model = model
        self.config_getter = config_getter
        self.active_skills: dict[str, str] = {}
        self.event_queue = None

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

        self._tools[tool.name] = tool


    def get_prompt_snippets(self) -> dict[str, str]:
        """
        Get prompt snippets for all custom tools.

        Returns:
            Dictionary mapping tool names to their prompt snippets
        """
        snippets = {}
        for tool in self._tools.values():
            snippet = getattr(tool, "get_prompt_snippet", lambda: None)()
            if snippet:
                snippets[tool.name] = snippet
        return snippets

    def get_prompt_guidelines(self) -> list[str]:
        """
        Get prompt guidelines from all custom tools.

        Returns:
            List of guideline strings from all custom tools
        """
        guidelines = []
        for tool in self._tools.values():
            tool_guidelines = getattr(tool, "get_prompt_guidelines", lambda: [])()
            guidelines.extend(tool_guidelines)
        return guidelines

    def update_tool_providers(self, llm_provider=None, model=None, config_getter=None, event_queue=None):
        """
        Update the provider and model references for all registered tools.
        Call this after the provider is initialized.

        Only non-None arguments overwrite the existing values so that callers
        that only want to inject an event_queue don't accidentally clear a
        previously configured llm_provider or model.

        Args:
            llm_provider: LLM provider instance (skipped when None)
            model: Model name string (skipped when None)
            config_getter: Config getter callable (skipped when None)
            event_queue: Event queue for tools that need to emit events (skipped when None)
        """
        if llm_provider is not None:
            self.llm_provider = llm_provider
        if model is not None:
            self.model = model
        if config_getter is not None:
            self.config_getter = config_getter
        if event_queue is not None:
            self.event_queue = event_queue
        for tool in self._tools.values():
            # Ensure tools always have a back-reference to the registry.
            # Some tools (e.g. `agents`) require this and may fail if created outside `register()`.
            tool.tool_registry = self
            if llm_provider is not None:
                tool.llm_provider = llm_provider
            if model is not None:
                tool.model = model
            if self.event_queue is not None:
                tool.event_queue = self.event_queue

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
                        tool_instance = attr(
                            tool_registry=self,
                            llm_provider=self.llm_provider,
                            model=self.model
                        )
                        self.register(tool_instance)
                        registered_count += 1
                        print(f"Registered tool plugin: {tool_instance.name}")
                    except Exception as e:
                        print(f"Failed to instantiate tool {attr_name}: {str(e)}")

            if registered_count == 0:
                raise ImportError(f"No valid tool class found in {plugin_path}")

        except Exception as e:
            raise RuntimeError(f"Failed to load tool plugin {plugin_path}: {str(e)}") from e

    def discover_and_register_plugins(self) -> int:
        """
        Discover and register tool plugins from .jarvis/tools/ directories.
        
        Returns:
            Number of successfully registered plugins
        """
        search_paths = [
            Path.home() / ".jarvis" / "tools",
            Path.home() / ".jarvis" / "tool",
            Path.cwd() / ".jarvis" / "tools",
            Path.cwd() / ".jarvis" / "tool",
        ]
        
        registered_count = 0
        processed_files = set()
        
        for path in search_paths:
            if path.exists() and path.is_dir():
                for file in path.glob("*.py"):
                    resolved_file = file.resolve()
                    if resolved_file not in processed_files:
                        processed_files.add(resolved_file)
                        try:
                            self.register_plugin(str(resolved_file))
                            registered_count += 1
                        except Exception as e:
                            print(f"Error loading plugin from {resolved_file}: {e}")
                            
        return registered_count
