"""Concurrent Tool Executor for parallel tool execution"""

import asyncio
import logging
import psutil
import time
from dataclasses import dataclass
from typing import Any

from .base import BaseTool, ToolInput, ToolOutput
from .registry import ToolRegistry

logger = logging.getLogger(__name__)


@dataclass
class ExecutorResourceLimits:
    """Resource limits for tool execution"""
    max_memory_mb: int = 512
    max_cpu_percent: float = 80.0
    timeout_seconds: float = 30.0


class ConcurrentToolExecutor:
    """Execute multiple tools concurrently with resource limits"""

    def __init__(
        self,
        tool_registry: ToolRegistry,
        max_workers: int = 10,
        resource_limits: ExecutorResourceLimits | None = None
    ):
        self.tool_registry = tool_registry
        self.max_workers = max_workers
        self.resource_limits = resource_limits or ExecutorResourceLimits()
        self.semaphore = asyncio.Semaphore(max_workers)

    async def execute_concurrent(
        self,
        tool_calls: list[tuple[str, dict]]
    ) -> list[ToolOutput]:
        """
        Execute multiple tool calls concurrently

        Args:
            tool_calls: List of (tool_name, arguments) tuples

        Returns:
            List of ToolOutput results
        """
        tasks = [
            self.execute_single(name, args)
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

    def _check_resource_limits(self) -> tuple[bool, str]:
        """
        Check if current resource usage exceeds limits
        
        Returns:
            Tuple of (within_limits, error_message)
        """
        try:
            # Check CPU usage
            cpu_percent = psutil.cpu_percent(interval=0.1)
            if cpu_percent > self.resource_limits.max_cpu_percent:
                return False, f"CPU usage ({cpu_percent}%) exceeds limit ({self.resource_limits.max_cpu_percent}%)"
            
            # Check memory usage
            memory = psutil.virtual_memory()
            memory_used_mb = memory.used / (1024 * 1024)
            
            if memory_used_mb > self.resource_limits.max_memory_mb:
                return False, f"Memory usage ({memory_used_mb:.1f} MB) exceeds limit ({self.resource_limits.max_memory_mb} MB)"
            
            return True, ""
            
        except Exception as e:
            logger.warning(f"Failed to check resource limits: {e}")
            # If we can't check limits, allow execution (fail-safe)
            return True, ""

    async def execute_single(
        self,
        name: str,
        args: dict
    ) -> ToolOutput:
        """
        Execute a single tool with resource limits

        Args:
            name: Tool name
            args: Tool arguments

        Returns:
            ToolOutput with execution results
        """
        async with self.semaphore:
            # Check resource limits before execution
            within_limits, limit_error = self._check_resource_limits()
            if not within_limits:
                logger.warning(f"Resource limit exceeded for tool '{name}': {limit_error}")
                return ToolOutput(
                    success=False,
                    result=None,
                    error=f"Resource limit exceeded: {limit_error}",
                )
            
            tool = self.tool_registry.get(name)
            if not tool:
                return ToolOutput(
                    success=False,
                    result=None,
                    error=f"Tool '{name}' not found",
                )

            try:
                # Execute with timeout
                result = await asyncio.wait_for(
                    tool.safe_execute(args),
                    timeout=self.resource_limits.timeout_seconds
                )
                return result

            except asyncio.TimeoutError:
                return ToolOutput(
                    success=False,
                    result=None,
                    error=f"Tool execution timed out after {self.resource_limits.timeout_seconds}s",
                )
            except Exception as e:
                logger.error(f"Tool '{name}' execution failed: {e}")
                return ToolOutput(
                    success=False,
                    result=None,
                    error=f"Tool execution failed: {str(e)}",
                )

    async def execute_with_retry(
        self,
        tool_calls: list[tuple[str, dict]],
        max_retries: int = 3,
        retry_delay: float = 1.0
    ) -> list[ToolOutput]:
        """
        Execute multiple tools with automatic retry on failure

        Args:
            tool_calls: List of (tool_name, arguments) tuples
            max_retries: Maximum number of retry attempts per tool
            retry_delay: Initial delay between retries (exponential backoff)

        Returns:
            List of ToolOutput results
        """
        async def execute_with_retry_single(name: str, args: dict) -> ToolOutput:
            last_error = None
            current_delay = retry_delay

            for attempt in range(max_retries + 1):
                result = await self.execute_single(name, args)

                if result.success:
                    return result

                last_error = result.error
                if attempt < max_retries:
                    logger.warning(
                        f"Tool '{name}' failed (attempt {attempt + 1}/{max_retries + 1}), "
                        f"retrying in {current_delay}s..."
                    )
                    await asyncio.sleep(current_delay)
                    # Exponential backoff
                    current_delay *= 2

            return ToolOutput(
                success=False,
                result=None,
                error=f"Tool '{name}' failed after {max_retries + 1} attempts. Last error: {last_error}",
            )

        tasks = [
            execute_with_retry_single(name, args)
            for name, args in tool_calls
        ]

        return await asyncio.gather(*tasks)

    async def execute_batched(
        self,
        tool_calls: list[tuple[str, dict]],
        batch_size: int = 5
    ) -> list[ToolOutput]:
        """
        Execute tools in batches to control resource usage

        Args:
            tool_calls: List of (tool_name, arguments) tuples
            batch_size: Number of tools to execute concurrently per batch

        Returns:
            List of ToolOutput results
        """
        all_results = []

        for i in range(0, len(tool_calls), batch_size):
            batch = tool_calls[i:i + batch_size]
            batch_results = await self.execute_concurrent(batch)
            all_results.extend(batch_results)

            # Small delay between batches to allow resource recovery
            if i + batch_size < len(tool_calls):
                await asyncio.sleep(0.1)

        return all_results
