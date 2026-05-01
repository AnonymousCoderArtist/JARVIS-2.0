"""Base classes for tool system"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, TypeAlias, TYPE_CHECKING

from pydantic import BaseModel, ConfigDict

from core.tools.permissions import PermissionContext

if TYPE_CHECKING:
    from core.tools.registry import ToolRegistry
    from core.llm.base import BaseLLMProvider

# Type aliases
MetadataDict: TypeAlias = dict[str, Any]
ToolDefDict: TypeAlias = dict[str, Any]


class ToolInput(BaseModel):
    """Base model for tool inputs"""
    model_config = ConfigDict(extra="allow")


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

        # Store references for tools that need them (e.g., InvokeAgentTool)
        self.tool_registry = tool_registry
        self.llm_provider = llm_provider
        self.model = model

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

    def validate_input(self, input_data: dict[str, Any]) -> bool:
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

    async def safe_execute(self, input_data: dict[str, Any]) -> ToolOutput:
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

    def resolve_permission(self, args: dict[str, Any]) -> PermissionContext | None:
        """
        Resolve permission requirements for this tool execution

        Args:
            args: Tool arguments

        Returns:
            PermissionContext if permission check is needed, None otherwise
        """
        # Default implementation - tools can override for custom permission logic
        return None

    def get_file_snapshot(self, args: dict[str, Any]) -> dict[str, Any] | None:
        """
        Get a snapshot of files that will be modified by this tool

        Args:
            args: Tool arguments

        Returns:
            Dictionary with file snapshots or None if not applicable
        """
        # Default implementation - tools can override for undo functionality
        return None
