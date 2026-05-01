"""Async Tool Registry for concurrent tool execution"""

import asyncio
import logging
from typing import Any

from .base import BaseTool, ToolInput, ToolOutput
from .registry import ToolRegistry

logger = logging.getLogger(__name__)


class AsyncToolRegistry(ToolRegistry):
    """Enhanced tool registry with async execution support"""

    def __init__(self, llm_provider=None, model=None, max_concurrent_tools: int = 10):
        super().__init__(llm_provider, model)
        self.max_concurrent_tools = max_concurrent_tools
        self.semaphore = asyncio.Semaphore(max_concurrent_tools)

    async def execute_tool_async(self, name: str, input_data: dict) -> ToolOutput:
        """
        Execute a tool asynchronously with semaphore control

        Args:
            name: Tool name
            input_data: Input parameters dictionary

        Returns:
            ToolOutput with execution results
        """
        async with self.semaphore:
            tool = self.get(name)
            if not tool:
                return ToolOutput(
                    success=False,
                    result=None,
                    error=f"Tool '{name}' not found",
                )

            return await tool.safe_execute(input_data)

    async def execute_tools_concurrent(
        self,
        tool_calls: list[tuple[str, dict]]
    ) -> list[ToolOutput]:
        """
        Execute multiple tools concurrently

        Args:
            tool_calls: List of (tool_name, input_data) tuples

        Returns:
            List of ToolOutput results
        """
        tasks = [
            self.execute_tool_async(name, args)
            for name, args in tool_calls
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Convert exceptions to error outputs
        return [
            result if isinstance(result, ToolOutput)
            else ToolOutput(
                success=False,
                result=None,
                error=f"Tool execution failed: {str(result)}",
            )
            for result in results
        ]

    async def execute_tools_with_timeout(
        self,
        name: str,
        input_data: dict,
        timeout: float = 30.0
    ) -> ToolOutput:
        """
        Execute a tool with timeout

        Args:
            name: Tool name
            input_data: Input parameters dictionary
            timeout: Timeout in seconds

        Returns:
            ToolOutput with execution results
        """
        try:
            return await asyncio.wait_for(
                self.execute_tool_async(name, input_data),
                timeout=timeout
            )
        except asyncio.TimeoutError:
            return ToolOutput(
                success=False,
                result=None,
                error=f"Tool execution timed out after {timeout}s",
            )

    async def execute_tools_with_retry(
        self,
        name: str,
        input_data: dict,
        max_retries: int = 3,
        retry_delay: float = 1.0
    ) -> ToolOutput:
        """
        Execute a tool with automatic retry on failure

        Args:
            name: Tool name
            input_data: Input parameters dictionary
            max_retries: Maximum number of retry attempts
            retry_delay: Delay between retries in seconds

        Returns:
            ToolOutput with execution results
        """
        last_error = None

        for attempt in range(max_retries + 1):
            result = await self.execute_tool_async(name, input_data)

            if result.success:
                return result

            last_error = result.error
            if attempt < max_retries:
                logger.warning(
                    f"Tool '{name}' failed (attempt {attempt + 1}/{max_retries + 1}), "
                    f"retrying in {retry_delay}s..."
                )
                await asyncio.sleep(retry_delay)
                # Exponential backoff
                retry_delay *= 2

        return ToolOutput(
            success=False,
            result=None,
            error=f"Tool '{name}' failed after {max_retries + 1} attempts. Last error: {last_error}",
        )
