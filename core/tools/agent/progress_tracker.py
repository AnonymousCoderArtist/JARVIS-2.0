"""Progress tracking for agent operations with callback support.

This module provides the ProgressTracker class for monitoring agent execution
with event-driven callbacks for UI updates and token usage tracking.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable

logger = logging.getLogger(__name__)

# Type aliases for callbacks
ProgressCallback = Callable[[str, float, str], None]
ToolCallCallback = Callable[[str, dict[str, Any], str], None]
ToolResultCallback = Callable[[str, dict[str, Any], Any, str], None]


@dataclass
class TokenUsage:
    """Token usage tracking for an agent session.
    
    Attributes:
        prompt_tokens: Tokens used in prompts
        completion_tokens: Tokens used in completions
        total_tokens: Total tokens used
        tool_call_tokens: Tokens used for tool calls
        last_updated: When usage was last updated
    """
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    tool_call_tokens: int = 0
    last_updated: datetime = field(default_factory=datetime.now)


@dataclass
class ProgressUpdate:
    """Progress update event for an agent.
    
    Attributes:
        timestamp: When the update occurred
        stage: Current stage name (e.g., "starting", "tool_use", "complete")
        progress: Progress value from 0.0 to 1.0
        message: Human-readable status message
        task_id: Optional task identifier
        token_delta: Optional token usage delta
    """
    timestamp: datetime = field(default_factory=datetime.now)
    stage: str = ""
    progress: float = 0.0
    message: str = ""
    task_id: str = ""
    token_delta: int = 0


class ProgressTracker:
    """Tracks progress of agent operations with callback support.
    
    This class provides:
    - Progress update callbacks for UI components
    - Token usage tracking
    - Tool call/result tracking
    - Thread-safe event emission
    
    Example:
        tracker = ProgressTracker(task_id="task-123")
        tracker.set_tool_call_callback(lambda name, args, task_id: print(f"Tool: {name}"))
        tracker.emit_progress("tool_use", 0.5, "Running file_search")
    """

    def __init__(self, task_id: str = ""):
        """Initialize the progress tracker.
        
        Args:
            task_id: Optional task identifier for tracking
        """
        self.task_id = task_id
        self.token_usage = TokenUsage()
        self._progress_callbacks: list[ProgressCallback] = []
        self._tool_call_callbacks: list[ToolCallCallback] = []
        self._tool_result_callbacks: list[ToolResultCallback] = []
        self._lock = asyncio.Lock()
        self._start_time: float | None = None
        self._current_stage: str = ""
        self._tool_uses: int = 0

    def set_task_id(self, task_id: str) -> None:
        """Set or update the task identifier.
        
        Args:
            task_id: The new task identifier
        """
        self.task_id = task_id

    def add_progress_callback(self, callback: ProgressCallback) -> None:
        """Add a progress update callback.
        
        Args:
            callback: Function to call on progress updates (stage, progress, message)
        """
        self._progress_callbacks.append(callback)

    def add_tool_call_callback(self, callback: ToolCallCallback) -> None:
        """Add a tool call callback.
        
        Args:
            callback: Function to call on tool calls (tool_name, args, task_id)
        """
        self._tool_call_callbacks.append(callback)

    def add_tool_result_callback(self, callback: ToolResultCallback) -> None:
        """Add a tool result callback.
        
        Args:
            callback: Function to call on tool results (tool_name, args, result, task_id)
        """
        self._tool_result_callbacks.append(callback)

    def emit_progress(
        self,
        stage: str,
        progress: float,
        message: str = "",
        token_delta: int = 0,
    ) -> ProgressUpdate:
        """Emit a progress update to all registered callbacks.
        
        Args:
            stage: Current stage name
            progress: Progress value (0.0 to 1.0)
            message: Human-readable message
            token_delta: Token usage delta
            
        Returns:
            The created ProgressUpdate instance
        """
        update = ProgressUpdate(
            stage=stage,
            progress=min(1.0, max(0.0, progress)),
            message=message,
            task_id=self.task_id,
            token_delta=token_delta,
        )

        # Update token usage
        if token_delta:
            self.token_usage.total_tokens += token_delta
            self.token_usage.last_updated = datetime.now()

        # Update internal state
        self._current_stage = stage

        # Call all registered callbacks
        for callback in self._progress_callbacks:
            try:
                callback(stage, update.progress, message)
            except Exception as e:
                logger.warning(f"Progress callback failed: {e}")

        return update

    def emit_tool_call(self, tool_name: str, tool_args: dict[str, Any]) -> None:
        """Emit a tool call event.
        
        Args:
            tool_name: Name of the tool being called
            tool_args: Tool arguments
        """
        self._tool_uses += 1
        self.emit_progress("tool_use", min(0.9, self._tool_uses * 0.1), f"Calling {tool_name}")

        for callback in self._tool_call_callbacks:
            try:
                callback(tool_name, tool_args, self.task_id)
            except Exception as e:
                logger.warning(f"Tool call callback failed: {e}")

    def emit_tool_result(
        self,
        tool_name: str,
        tool_args: dict[str, Any],
        result: Any,
        duration_ms: float = 0,
    ) -> None:
        """Emit a tool result event.
        
        Args:
            tool_name: Name of the tool
            tool_args: Tool arguments
            result: Tool execution result
            duration_ms: Execution duration in milliseconds
        """
        for callback in self._tool_result_callbacks:
            try:
                callback(tool_name, tool_args, result, self.task_id)
            except Exception as e:
                logger.warning(f"Tool result callback failed: {e}")

    async def emit_progress_async(
        self,
        stage: str,
        progress: float,
        message: str = "",
        token_delta: int = 0,
    ) -> ProgressUpdate:
        """Emit a progress update asynchronously.
        
        Args:
            stage: Current stage name
            progress: Progress value (0.0 to 1.0)
            message: Human-readable message
            token_delta: Token usage delta
            
        Returns:
            The created ProgressUpdate instance
        """
        async with self._lock:
            return self.emit_progress(stage, progress, message, token_delta)

    def start_tracking(self) -> None:
        """Mark the start of tracking."""
        self._start_time = time.time()
        self.emit_progress("starting", 0.0, "Initializing agent")

    def stop_tracking(self) -> float:
        """Stop tracking and return elapsed time.
        
        Returns:
            Elapsed time in seconds, or 0 if not started
        """
        if self._start_time is None:
            return 0.0
        elapsed = time.time() - self._start_time
        self._start_time = None
        self.emit_progress("complete", 1.0, "Agent finished")
        return elapsed

    def update_token_usage(self, prompt: int = 0, completion: int = 0, tool: int = 0) -> None:
        """Update token usage counters.
        
        Args:
            prompt: Prompt tokens to add
            completion: Completion tokens to add
            tool: Tool call tokens to add
        """
        self.token_usage.prompt_tokens += prompt
        self.token_usage.completion_tokens += completion
        self.token_usage.tool_call_tokens += tool
        self.token_usage.total_tokens = (
            self.token_usage.prompt_tokens
            + self.token_usage.completion_tokens
            + self.token_usage.tool_call_tokens
        )
        self.token_usage.last_updated = datetime.now()


async def run_with_tracking(
    tracker: ProgressTracker,
    coro_factory: Any,
) -> Any:
    """Run a coroutine with progress tracking wrapper.
    
    Args:
        tracker: ProgressTracker instance to use
        coro_factory: Callable that returns the coroutine to run
        
    Returns:
        Result of the coroutine
    """
    tracker.start_tracking()
    try:
        result = await coro_factory()
        return result
    finally:
        tracker.stop_tracking()