"""Async Agent Manager for concurrent agent operations"""

import asyncio
import logging
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable, cast
from collections.abc import Awaitable

from core.agents.base import BaseAgent

logger = logging.getLogger(__name__)


class AgentState(Enum):
    """Agent execution states"""
    IDLE = auto()
    RUNNING = auto()
    WAITING = auto()
    COMPLETED = auto()
    FAILED = auto()


@dataclass
class AgentTask:
    """A task to be executed by an agent"""
    agent: BaseAgent
    task: str
    priority: int = 0
    context: dict[str, Any] | None = None
    task_id: str = ""
    state: AgentState = AgentState.IDLE
    result: str | None = None
    error: str | None = None


@dataclass
class AsyncAgentConfig:
    """Configuration for async agent operations"""
    max_concurrent_agents: int = 5
    max_concurrent_tools: int = 10
    default_timeout: int = 30
    enable_background_tasks: bool = True
    resource_monitoring: bool = True
    progress_updates: bool = True


class AsyncAgentManager:
    """Manages asynchronous agent operations and task scheduling"""

    def __init__(self, config: AsyncAgentConfig | None = None):
        self.config = config or AsyncAgentConfig()
        self.task_queue: asyncio.PriorityQueue[tuple[int, AgentTask]] = asyncio.PriorityQueue()
        self.running_agents: dict[str, BaseAgent] = {}
        self.semaphore = asyncio.Semaphore(self.config.max_concurrent_agents)
        self.tool_semaphore = asyncio.Semaphore(self.config.max_concurrent_tools)
        self._processing = False
        self._task_counter = 0
        self._background_tasks: set[asyncio.Task] = set()

    async def submit_task(
        self,
        agent: BaseAgent,
        task: str,
        priority: int = 0,
        context: dict[str, Any] | None = None
    ) -> str:
        """
        Submit a task to the async queue

        Args:
            agent: Agent instance to execute the task
            task: Task description
            priority: Task priority (lower = higher priority)
            context: Optional context dictionary

        Returns:
            Task ID for tracking
        """
        self._task_counter += 1
        task_id = f"task_{self._task_counter}"

        agent_task = AgentTask(
            agent=agent,
            task=task,
            priority=priority,
            context=context,
            task_id=task_id,
            state=AgentState.WAITING
        )

        await self.task_queue.put((priority, agent_task))
        logger.info(f"Submitted task {task_id} with priority {priority}")

        return task_id

    async def start_processing(self) -> None:
        """Start processing tasks from the queue"""
        if self._processing:
            logger.warning("Processing already started")
            return

        self._processing = True
        logger.info("Starting async task processing")

        while self._processing:
            try:
                # Get task with timeout to allow checking _processing flag
                priority, agent_task = await asyncio.wait_for(
                    self.task_queue.get(),
                    timeout=1.0
                )

                # Create background task for execution
                task = asyncio.create_task(
                    self._execute_task(agent_task)
                )
                self._background_tasks.add(task)
                task.add_done_callback(self._background_tasks.discard)

            except asyncio.TimeoutError:
                # No task available, continue loop
                continue
            except Exception as e:
                logger.error(f"Error in task processing loop: {e}")

    async def stop_monitoring(self) -> None:
        """Stop processing tasks"""
        self._processing = False
        logger.info("Stopping async task processing")

        # Cancel all background tasks
        for task in self._background_tasks:
            task.cancel()

        # Wait for tasks to complete cancellation
        if self._background_tasks:
            await asyncio.gather(*self._background_tasks, return_exceptions=True)

        self._background_tasks.clear()

    async def _execute_task(self, agent_task: AgentTask) -> None:
        """
        Execute a single agent task

        Args:
            agent_task: AgentTask to execute
        """
        async with self.semaphore:
            agent_task.state = AgentState.RUNNING
            self.running_agents[agent_task.task_id] = agent_task.agent

            try:
                logger.info(f"Executing task {agent_task.task_id}")

                # Execute the agent's process method
                result = await asyncio.wait_for(
                    agent_task.agent.process(
                        agent_task.task,
                        context=agent_task.context
                    ),
                    timeout=self.config.default_timeout
                )

                agent_task.result = result
                agent_task.state = AgentState.COMPLETED
                logger.info(f"Task {agent_task.task_id} completed successfully")

            except asyncio.TimeoutError:
                agent_task.error = f"Task timed out after {self.config.default_timeout}s"
                agent_task.state = AgentState.FAILED
                logger.error(f"Task {agent_task.task_id} timed out")

            except Exception as e:
                agent_task.error = str(e)
                agent_task.state = AgentState.FAILED
                logger.error(f"Task {agent_task.task_id} failed: {e}")

            finally:
                self.running_agents.pop(agent_task.task_id, None)

    async def get_task_status(self, task_id: str) -> dict[str, Any]:
        """
        Get the status of a specific task

        Args:
            task_id: Task ID to check

        Returns:
            Dictionary with task status information
        """
        # This is a simplified implementation
        # In a full implementation, we'd maintain a task registry
        return {
            "task_id": task_id,
            "status": "unknown"
        }

    async def execute_concurrent(
        self,
        tasks: list[tuple[BaseAgent, str, dict[str, Any] | None]]
    ) -> list[str | BaseException]:
        """
        Execute multiple agent tasks concurrently

        Args:
            tasks: List of (agent, task, context) tuples

        Returns:
            List of results or exceptions
        """
        async def execute_single(agent: BaseAgent, task: str, context: dict[str, Any] | None) -> str:
            async with self.semaphore:
                return await agent.process(task, context=context)

        coroutines = [
            execute_single(agent, task, context)
            for agent, task, context in tasks
        ]

        results = await asyncio.gather(*coroutines, return_exceptions=True)

        # Return list of results or exceptions
        return [
            result
            for result in results
        ]

    def get_queue_size(self) -> int:
        """Get the current size of the task queue"""
        return self.task_queue.qsize()

    def get_running_count(self) -> int:
        """Get the number of currently running agents"""
        return len(self.running_agents)

    def is_processing(self) -> bool:
        """Check if the manager is currently processing tasks"""
        return self._processing
