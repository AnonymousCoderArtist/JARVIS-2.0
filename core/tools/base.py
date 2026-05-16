"""Base classes for tool system"""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, TypeAlias

from pydantic import BaseModel, ConfigDict

from core.tools.permissions import PermissionContext

if TYPE_CHECKING:
    from core.llm.base import BaseLLMProvider
    from core.tools.registry import ToolRegistry

# Type aliases
MetadataDict: TypeAlias = dict[str, Any]
ToolDefDict: TypeAlias = dict[str, Any]
ToolArgs: TypeAlias = dict[str, Any]


class ToolInput(BaseModel):
    """Base model for tool inputs"""
    model_config = ConfigDict(extra="allow", arbitrary_types_allowed=True)

    # Common file tool fields
    filePath: str | None = None
    filePaths: list[str] | None = None
    files: list[Any] | None = None
    offset: int | None = None
    limit: int | None = None
    encoding: str = "utf-8"
    exclude: list[str] | None = None
    use_default_excludes: bool = True
    file_filtering_options: dict[str, Any] | None = None

    # Common tool fields
    command: str | None = None
    query: str | None = None
    content: str | None = None
    urls: list[str] | None = None


class ToolOutput(BaseModel):
    """Base model for tool outputs"""

    success: bool
    result: Any
    error: str | None = None
    metadata: MetadataDict | None = None


class BaseTool(ABC):
    """Abstract base class for all tools"""

    name: str = ""
    description: str = ""
    input_schema: dict[str, Any] = {}
    is_deferred: bool = False  # Mark tool as deferred/lazy-loadable
    search_hint: str | None = None  # Curated hint for search matching

    def __init__(
        self,
        tool_registry: ToolRegistry | None = None,
        llm_provider: BaseLLMProvider | None = None,
        model: str | None = None
    ):
        if not self.name:
            raise ValueError("Tool must have a name")
        if not self.description:
            raise ValueError("Tool must have a description")

        # Store references for tools that need them (e.g., AgentsTool)
        self.tool_registry = tool_registry
        self.llm_provider = llm_provider
        self.model = model
        self.event_queue = None

    @abstractmethod
    async def execute(self, input_data: ToolInput) -> ToolOutput:
        """
        Execute the tool with the given input

        Args:
            input_data: ToolInput instance with tool parameters

        Returns:
            ToolOutput with execution results
        """
        pass

    async def execute_async(self, input_data: ToolInput, timeout: float | None = None) -> ToolOutput:
        """
        Execute the tool asynchronously with optional timeout

        This method can be overridden by tools that need special async handling,
        such as running sync code in an executor.

        Args:
            input_data: ToolInput instance with tool parameters
            timeout: Optional timeout in seconds

        Returns:
            ToolOutput with execution results
        """
        # Default implementation: call the async execute method with timeout
        if timeout is not None:
            try:
                return await asyncio.wait_for(self.execute(input_data), timeout=timeout)
            except asyncio.TimeoutError:
                return ToolOutput(
                    success=False,
                    result=None,
                    error=f"Tool execution timed out after {timeout}s"
                )
        return await self.execute(input_data)

    async def execute_sync_in_executor(self, input_data: ToolInput, timeout: float | None = None) -> ToolOutput:
        """
        Execute the tool's sync version in an executor (for CPU-bound or blocking I/O)

        This is a helper method for tools that have blocking operations that should
        be run in a thread pool to avoid blocking the event loop.
        Tools should override execute_sync() if they have a sync implementation.

        Args:
            input_data: ToolInput instance with tool parameters
            timeout: Optional timeout in seconds

        Returns:
            ToolOutput with execution results
        """
        # Default: just call the async version
        # Tools with blocking operations should override this and use run_in_executor
        return await self.execute_async(input_data, timeout)

    def validate_input(self, input_data: ToolArgs) -> bool:
        """
        Validate input data against the tool's schema

        Args:
            input_data: Dictionary of input parameters

        Returns:
            True if valid, False otherwise
        """
        try:
            ToolInput(**input_data)
            return True
        except Exception:
            return False

    def get_function_definition(self) -> ToolDefDict:
        """
        Get the tool definition in OpenAI function calling format

        Returns:
            Dictionary with function definition
        """
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.input_schema,
            },
        }

    async def safe_execute(self, input_data: ToolArgs) -> ToolOutput:
        """
        Safely execute the tool with error handling

        Args:
            input_data: Dictionary of input parameters

        Returns:
            ToolOutput with success/error information
        """
        try:
            if not self.validate_input(input_data):
                return ToolOutput(
                    success=False,
                    result=None,
                    error="Invalid input data",
                )

            tool_input = ToolInput(**input_data)
            return await self.execute(tool_input)

        except Exception as e:
            return ToolOutput(
                success=False,
                result=None,
                error=f"Tool execution failed: {str(e)}",
            )

    def resolve_permission(self, args: ToolArgs) -> PermissionContext | None:
        """
        Resolve permission requirements for this tool execution

        Args:
            args: Tool arguments

        Returns:
            PermissionContext if permission check is needed, None otherwise
        """
        # Default implementation - tools can override for custom permission logic
        return None

    def get_file_snapshot(self, args: ToolArgs) -> dict[str, Any] | None:
        """
        Get a snapshot of files that will be modified by this tool

        Args:
            args: Tool arguments

        Returns:
            Dictionary with file snapshots or None if not applicable
        """
        # Default implementation - tools can override for undo functionality
        return None

    def _get_param(self, input_data: ToolInput, *names: str) -> Any:
        """Extract a parameter from ToolInput using multiple possible names.
        
        Handles both snake_case (Python convention) and camelCase (JSON convention)
        parameter naming.

        Args:
            input_data: The ToolInput instance
            *names: One or more parameter names to try (in order)

        Returns:
            The parameter value or None if not found
        """
        for name in names:
            value = getattr(input_data, name, None)
            if value is not None:
                return value
        return None
