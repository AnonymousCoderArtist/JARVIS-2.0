"""Background Task Manager for long-running task delegation"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable
from collections.abc import Awaitable

logger = logging.getLogger(__name__)


class TaskState(Enum):
    """Background task execution states"""
    PENDING = auto()
    RUNNING = auto()
    COMPLETED = auto()
    FAILED = auto()
    CANCELLED = auto()


@dataclass
class BackgroundTask:
    """A background task to be executed"""
    task_id: str
    tool_name: str
    args: dict[str, Any]
    state: TaskState = TaskState.PENDING
    result: Any = None
    error: str | None = None
    created_at: float = field(default_factory=time.time)
    started_at: float | None = None
    completed_at: float | None = None
    timeout: int = 300  # Default 5 minutes


@dataclass
class TaskResult:
    """Cached result of a background task"""
    task_id: str
    result: Any
    timestamp: float
    ttl: int = 3600  # Time to live in seconds (default 1 hour)


class BackgroundTaskManager:
    """Manages background task execution with process pool and result caching"""

    def __init__(
        self,
        max_concurrent_tasks: int = 5,
        result_cache_ttl: int = 3600,
        cleanup_interval: int = 300
    ):
        self.max_concurrent_tasks = max_concurrent_tasks
        self.result_cache_ttl = result_cache_ttl
        self.cleanup_interval = cleanup_interval
        
        self.task_queue: asyncio.Queue[BackgroundTask] = asyncio.Queue()
        self.running_tasks: dict[str, BackgroundTask] = {}
        self.completed_tasks: dict[str, BackgroundTask] = {}
        self.result_cache: dict[str, TaskResult] = {}
        
        self.semaphore = asyncio.Semaphore(max_concurrent_tasks)
        self._task_counter = 0
        self._background_tasks: set[asyncio.Task] = set()
        self._processing = False
        self._tool_executor: Callable[[str, dict], Awaitable[Any]] | None = None

    def set_tool_executor(self, executor: Callable[[str, dict], Awaitable[Any]]) -> None:
        """
        Set the tool executor function for running tools
        
        Args:
            executor: Async function that takes (tool_name, args) and returns result
        """
        self._tool_executor = executor

    async def submit_task(
        self,
        tool_name: str,
        args: dict[str, Any],
        timeout: int = 300
    ) -> str:
        """
        Submit a task to the background manager
        
        Args:
            tool_name: Name of the tool to execute
            args: Tool arguments
            timeout: Timeout in seconds
            
        Returns:
            Task ID for tracking
        """
        if not self._tool_executor:
            raise RuntimeError("Tool executor not set. Call set_tool_executor() first.")
        
        self._task_counter += 1
        task_id = f"bg_task_{self._task_counter}"
        
        task = BackgroundTask(
            task_id=task_id,
            tool_name=tool_name,
            args=args,
            timeout=timeout
        )
        
        await self.task_queue.put(task)
        logger.info(f"Submitted background task {task_id} for tool {tool_name}")
        
        # Start processing if not already running
        if not self._processing:
            asyncio.create_task(self._start_processing())
        
        return task_id

    async def get_task_status(self, task_id: str) -> dict[str, Any]:
        """
        Get the status of a background task
        
        Args:
            task_id: Task ID to check
            
        Returns:
            Dictionary with task status information
        """
        # Check running tasks
        if task_id in self.running_tasks:
            task = self.running_tasks[task_id]
            return {
                "task_id": task_id,
                "state": task.state.name,
                "tool_name": task.tool_name,
                "result": None,
                "error": None,
                "created_at": task.created_at,
                "started_at": task.started_at,
                "completed_at": None,
            }
        
        # Check completed tasks
        if task_id in self.completed_tasks:
            task = self.completed_tasks[task_id]
            return {
                "task_id": task_id,
                "state": task.state.name,
                "tool_name": task.tool_name,
                "result": task.result,
                "error": task.error,
                "created_at": task.created_at,
                "started_at": task.started_at,
                "completed_at": task.completed_at,
            }
        
        # Check result cache
        if task_id in self.result_cache:
            cached = self.result_cache[task_id]
            return {
                "task_id": task_id,
                "state": "CACHED",
                "tool_name": "unknown",
                "result": cached.result,
                "error": None,
                "created_at": cached.timestamp,
                "started_at": cached.timestamp,
                "completed_at": cached.timestamp,
            }
        
        return {
            "task_id": task_id,
            "state": "NOT_FOUND",
            "tool_name": None,
            "result": None,
            "error": "Task not found",
            "created_at": None,
            "started_at": None,
            "completed_at": None,
        }

    async def get_task_result(self, task_id: str, wait: bool = False, timeout: float = 30.0) -> Any:
        """
        Get the result of a background task
        
        Args:
            task_id: Task ID to get result for
            wait: Whether to wait for task completion if not done
            timeout: Maximum time to wait if wait=True
            
        Returns:
            Task result or None if not available
        """
        # Check result cache first
        if task_id in self.result_cache:
            return self.result_cache[task_id].result
        
        # Check completed tasks
        if task_id in self.completed_tasks:
            task = self.completed_tasks[task_id]
            if task.state == TaskState.COMPLETED:
                return task.result
            elif task.state == TaskState.FAILED:
                raise RuntimeError(f"Task failed: {task.error}")
        
        # If waiting, poll for completion
        if wait:
            start_time = time.time()
            while time.time() - start_time < timeout:
                if task_id in self.completed_tasks:
                    task = self.completed_tasks[task_id]
                    if task.state == TaskState.COMPLETED:
                        return task.result
                    elif task.state == TaskState.FAILED:
                        raise RuntimeError(f"Task failed: {task.error}")
                await asyncio.sleep(0.1)
            raise TimeoutError(f"Task {task_id} did not complete within {timeout}s")
        
        return None

    async def cancel_task(self, task_id: str) -> bool:
        """
        Cancel a background task
        
        Args:
            task_id: Task ID to cancel
            
        Returns:
            True if task was cancelled, False if not found or already completed
        """
        if task_id in self.running_tasks:
            task = self.running_tasks[task_id]
            task.state = TaskState.CANCELLED
            # Move to completed
            self.completed_tasks[task_id] = task
            del self.running_tasks[task_id]
            logger.info(f"Cancelled background task {task_id}")
            return True
        return False

    async def _start_processing(self) -> None:
        """Start the background task processing loop"""
        if self._processing:
            return
        
        self._processing = True
        logger.info("Starting background task processing")
        
        # Start cleanup task
        cleanup_task = asyncio.create_task(self._cleanup_loop())
        self._background_tasks.add(cleanup_task)
        cleanup_task.add_done_callback(self._background_tasks.discard)
        
        # Start processing tasks
        while self._processing:
            try:
                task = await asyncio.wait_for(
                    self.task_queue.get(),
                    timeout=1.0
                )
                
                # Create background task for execution
                exec_task = asyncio.create_task(self._execute_task(task))
                self._background_tasks.add(exec_task)
                exec_task.add_done_callback(self._background_tasks.discard)
                
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Error in task processing loop: {e}")

    async def stop_processing(self) -> None:
        """Stop processing tasks and cleanup"""
        self._processing = False
        logger.info("Stopping background task processing")
        
        # Cancel all background tasks
        for task in self._background_tasks:
            task.cancel()
        
        if self._background_tasks:
            await asyncio.gather(*self._background_tasks, return_exceptions=True)
        
        self._background_tasks.clear()

    async def _execute_task(self, task: BackgroundTask) -> None:
        """
        Execute a single background task
        
        Args:
            task: BackgroundTask to execute
        """
        async with self.semaphore:
            task.state = TaskState.RUNNING
            task.started_at = time.time()
            self.running_tasks[task.task_id] = task
            
            try:
                logger.info(f"Executing background task {task.task_id}")
                
                # Execute the tool with timeout
                if self._tool_executor is None:
                    raise RuntimeError("Tool executor not set")
                
                result = await asyncio.wait_for(
                    self._tool_executor(task.tool_name, task.args),
                    timeout=task.timeout
                )
                
                task.result = result
                task.state = TaskState.COMPLETED
                task.completed_at = time.time()
                
                # Cache the result
                self.result_cache[task.task_id] = TaskResult(
                    task_id=task.task_id,
                    result=result,
                    timestamp=time.time(),
                    ttl=self.result_cache_ttl
                )
                
                logger.info(f"Background task {task.task_id} completed successfully")
                
            except asyncio.TimeoutError:
                task.error = f"Task timed out after {task.timeout}s"
                task.state = TaskState.FAILED
                task.completed_at = time.time()
                logger.error(f"Background task {task.task_id} timed out")
                
            except Exception as e:
                task.error = str(e)
                task.state = TaskState.FAILED
                task.completed_at = time.time()
                logger.error(f"Background task {task.task_id} failed: {e}")
                
            finally:
                # Move to completed
                self.completed_tasks[task.task_id] = task
                self.running_tasks.pop(task.task_id, None)

    async def _cleanup_loop(self) -> None:
        """Periodic cleanup of old tasks and cached results"""
        while self._processing:
            try:
                await asyncio.sleep(self.cleanup_interval)
                await self._cleanup()
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")

    async def _cleanup(self) -> None:
        """Clean up old tasks and cached results"""
        current_time = time.time()
        
        # Clean up old completed tasks (keep last 100)
        if len(self.completed_tasks) > 100:
            # Sort by completion time and keep newest
            sorted_tasks = sorted(
                self.completed_tasks.items(),
                key=lambda x: x[1].completed_at or 0,
                reverse=True
            )
            self.completed_tasks = dict(sorted_tasks[:100])
        
        # Clean up expired cached results
        expired_keys = [
            task_id for task_id, cached in self.result_cache.items()
            if current_time - cached.timestamp > cached.ttl
        ]
        for key in expired_keys:
            del self.result_cache[key]
        
        if expired_keys:
            logger.info(f"Cleaned up {len(expired_keys)} expired cached results")

    def get_queue_size(self) -> int:
        """Get the current size of the task queue"""
        return self.task_queue.qsize()

    def get_running_count(self) -> int:
        """Get the number of currently running tasks"""
        return len(self.running_tasks)

    def get_completed_count(self) -> int:
        """Get the number of completed tasks"""
        return len(self.completed_tasks)

    def is_processing(self) -> bool:
        """Check if the manager is currently processing tasks"""
        return self._processing
