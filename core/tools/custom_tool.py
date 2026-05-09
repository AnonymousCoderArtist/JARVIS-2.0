"""Custom tool implementation for user-defined tools."""

from __future__ import annotations

from typing import Any, Coroutine, Callable

from .base import BaseTool, ToolInput, ToolOutput


# Type alias for tool execution functions
ToolExecuteFunc = Callable[..., Coroutine[Any, Any, ToolOutput]]


class CustomTool(BaseTool):
    """
    A tool wrapper for user-defined custom tools.

    Custom tools allow users to extend JARVIS with their own tool functionality
    without modifying the core codebase.

    Example:
        tool = CustomTool(
            name="my_tool",
            description="Does something useful",
            parameters={"type": "object", "properties": {...}},
            execute_func=my_async_function,
            prompt_snippet="Use my_tool for custom operations",
            prompt_guidelines=["Use my_tool when you need to..."],
        )
    """

    # Class-level attributes that BaseTool checks in __init__
    name: str = ""
    description: str = ""

    def __init__(
        self,
        name: str,
        description: str,
        parameters: dict[str, Any],
        execute_func: ToolExecuteFunc,
        prompt_snippet: str | None = None,
        prompt_guidelines: list[str] | None = None,
        target_file_path: str | None = None,
    ):
        """
        Initialize a custom tool.

        Args:
            name: Unique tool name
            description: Description shown to the LLM
            parameters: JSON schema for tool parameters
            execute_func: Async function that executes the tool
            prompt_snippet: Short one-line entry for "Available tools" section
            prompt_guidelines: Tool-specific bullets for Guidelines section
            target_file_path: Target file path if this tool mutates files
        """
        # Set class-level attributes before calling super().__init__
        # BaseTool checks these in __init__
        self.__class__.name = name
        self.__class__.description = description
        self.input_schema = parameters
        self._execute_func = execute_func
        self._prompt_snippet = prompt_snippet
        self._prompt_guidelines = prompt_guidelines
        self._target_file_path = target_file_path
        super().__init__()

    async def execute(self, input_data: ToolInput) -> ToolOutput:
        """Execute the custom tool."""
        # Only extract parameters that are defined in our schema
        if not self.input_schema or "properties" not in self.input_schema:
            params = {k: v for k, v in input_data.model_dump().items() if v is not None}
        else:
            valid_keys = set(self.input_schema["properties"].keys())
            params = {k: v for k, v in input_data.model_dump().items() if k in valid_keys and v is not None}
        return await self._execute_func(**params)

    def get_prompt_snippet(self) -> str | None:
        """Get the prompt snippet for this tool."""
        return self._prompt_snippet

    def get_prompt_guidelines(self) -> list[str]:
        """Get the prompt guidelines for this tool."""
        return self._prompt_guidelines or []

    def get_target_file_path(self) -> str | None:
        """Get the target file path for mutation queue."""
        return self._target_file_path


def with_file_mutation_queue(
    target_path: str,
    execute_func: Callable[..., Coroutine[Any, Any, ToolOutput]],
) -> CustomTool:
    """
    Create a custom tool that participates in the file mutation queue.

    This is useful for tools that read and write files, ensuring they don't
    conflict with other file-modifying operations.

    Args:
        target_path: The file path this tool mutates
        execute_func: Async function that executes the tool

    Returns:
        CustomTool configured for file mutation

    Example:
        tool = with_file_mutation_queue(
            "/path/to/target.py",
            my_edit_function,
        )
    """
    return CustomTool(
        name="",  # Will be set by caller
        description="",  # Will be set by caller
        parameters={},  # Will be set by caller
        execute_func=execute_func,
        target_file_path=target_path,
    )