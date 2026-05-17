"""Async Agent Manager for concurrent agent operations with lifecycle management.

This module provides comprehensive background task lifecycle management similar to
openclaude's LocalAgentTask pattern, including progress tracking, notifications,
and agent spawning with permission system integration.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum, auto
from typing import TYPE_CHECKING, Any

from jarvis.core.agents.base import BaseAgent
from jarvis.core.agents.builtin_agents import AgentDefinition, get_builtin_agents

if TYPE_CHECKING:
    from jarvis.core.config.settings import Settings
    from jarvis.core.llm.base import BaseLLMProvider
    from jarvis.core.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)


class ProgressStage(Enum):
    """Progress tracking stages for async agent tasks"""
    STARTED = auto()
    RUNNING = auto()
    COMPLETED = auto()
    FAILED = auto()


class AgentState(Enum):
    """Agent execution states"""
    IDLE = auto()
    RUNNING = auto()
    WAITING = auto()
    COMPLETED = auto()
    FAILED = auto()


@dataclass
class AgentTask:
    """A task to be executed by an agent with full lifecycle tracking"""
    agent: BaseAgent
    task: str
    priority: int = 0
    context: dict[str, Any] | None = None
    task_id: str = ""
    state: AgentState = AgentState.IDLE
    result: str | None = None
    error: str | None = None
    # Progress tracking fields
    stage: ProgressStage = ProgressStage.STARTED
    progress: float = 0.0
    started_at: float = 0.0
    completed_at: float | None = None
    # Notification callbacks
    on_progress: Callable[[dict[str, Any]], None] | None = None
    on_complete: Callable[[dict[str, Any]], None] | None = None
    on_error: Callable[[dict[str, Any]], None] | None = None


@dataclass
class AsyncAgentConfig:
    """Configuration for async agent operations"""
    max_concurrent_agents: int = 5
    max_concurrent_tools: int = 10
    default_timeout: int = 1800  # 30 minutes default for LLM operations
    enable_background_tasks: bool = True
    resource_monitoring: bool = True
    progress_updates: bool = True


@dataclass
class ActiveAgentInfo:
    """Information about an active spawned agent"""
    agent_id: str
    agent_type: str
    task: str
    created_at: float
    status: ProgressStage = ProgressStage.STARTED
    result: Any = None
    error: str | None = None


class AsyncAgentManager:
    """Manages asynchronous agent operations and task scheduling.
    
    Provides comprehensive background task lifecycle management similar to
    openclaude's LocalAgentTask pattern, including:
    - Progress tracking with stages (started, running, completed, failed)
    - Status notifications for async agent completions
    - Agent registry to track active agents by ID
    - Support for builtin_agents.py AgentDefinition
    - Agent spawning/lifecycle management with permission system
    """

    def __init__(
        self,
        config: AsyncAgentConfig | None = None,
        llm_provider: BaseLLMProvider | None = None,
        tool_registry: ToolRegistry | None = None,
        config_getter: Callable[[], Settings] | None = None,
    ):
        self.config = config or AsyncAgentConfig()
        self.llm_provider = llm_provider
        self.tool_registry = tool_registry
        self.config_getter = config_getter

        # Task queue and management
        self.task_queue: asyncio.PriorityQueue[tuple[int, AgentTask]] = asyncio.PriorityQueue()
        self.running_agents: dict[str, BaseAgent] = {}
        self.semaphore = asyncio.Semaphore(self.config.max_concurrent_agents)
        self.tool_semaphore = asyncio.Semaphore(self.config.max_concurrent_tools)

        # Agent registry - tracks active spawned agents
        self.active_agents: dict[str, ActiveAgentInfo] = {}

        # Notification handlers
        self._notification_handlers: list[Callable[[dict[str, Any]], None]] = []

        # Background tasks management
        self._processing = False
        self._task_counter = 0
        self._agent_counter = 0
        self._background_tasks: set[asyncio.Task] = set()

        # Task registry for status queries
        self._task_registry: dict[str, AgentTask] = {}

    async def submit_task(
        self,
        agent: BaseAgent,
        task: str,
        priority: int = 0,
        context: dict[str, Any] | None = None,
        on_progress: Callable[[dict[str, Any]], None] | None = None,
        on_complete: Callable[[dict[str, Any]], None] | None = None,
        on_error: Callable[[dict[str, Any]], None] | None = None,
    ) -> str:
        """
        Submit a task to the async queue

        Args:
            agent: Agent instance to execute the task
            task: Task description
            priority: Task priority (lower = higher priority)
            context: Optional context dictionary
            on_progress: Callback for progress updates
            on_complete: Callback for completion notification
            on_error: Callback for error notification

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
            state=AgentState.WAITING,
            stage=ProgressStage.STARTED,
            started_at=time.time(),
            on_progress=on_progress,
            on_complete=on_complete,
            on_error=on_error,
        )

        # Register task for status queries
        self._task_registry[task_id] = agent_task

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
        Execute a single agent task with lifecycle management

        Args:
            agent_task: AgentTask to execute
        """
        async with self.semaphore:
            agent_task.state = AgentState.RUNNING
            agent_task.stage = ProgressStage.RUNNING
            agent_task.progress = 0.1
            agent_task.started_at = time.time()
            self.running_agents[agent_task.task_id] = agent_task.agent

            # Notify progress
            self._notify_progress(agent_task, "Task started")

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
                agent_task.stage = ProgressStage.COMPLETED
                agent_task.progress = 1.0
                agent_task.completed_at = time.time()
                logger.info(f"Task {agent_task.task_id} completed successfully")

                # Notify completion
                self._notify_completion(agent_task)

            except asyncio.TimeoutError:
                agent_task.error = f"Task timed out after {self.config.default_timeout}s"
                agent_task.state = AgentState.FAILED
                agent_task.stage = ProgressStage.FAILED
                agent_task.completed_at = time.time()
                logger.error(f"Task {agent_task.task_id} timed out")

                # Notify error
                self._notify_error(agent_task)

            except Exception as e:
                agent_task.error = str(e)
                agent_task.state = AgentState.FAILED
                agent_task.stage = ProgressStage.FAILED
                agent_task.completed_at = time.time()
                logger.error(f"Task {agent_task.task_id} failed: {e}")

                # Notify error
                self._notify_error(agent_task)

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
        agent_task = self._task_registry.get(task_id)
        if not agent_task:
            return {
                "task_id": task_id,
                "status": "unknown",
                "exists": False,
            }

        return {
            "task_id": task_id,
            "status": agent_task.state.name,
            "stage": agent_task.stage.name,
            "progress": agent_task.progress,
            "result": agent_task.result,
            "error": agent_task.error,
            "exists": True,
            "started_at": agent_task.started_at,
            "completed_at": agent_task.completed_at,
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

    # === Notification and Progress Methods ===

    def register_notification_handler(
        self, handler: Callable[[dict[str, Any]], None]
    ) -> None:
        """Register a handler for task status notifications.
        
        Args:
            handler: Callable that receives task status dictionaries
        """
        self._notification_handlers.append(handler)

    def notify_handlers(self, event: dict[str, Any]) -> None:
        """Notify all registered handlers of an event."""
        for handler in self._notification_handlers:
            try:
                handler(event)
            except Exception as e:
                logger.error(f"Error in notification handler: {e}")

    def _notify_progress(self, agent_task: AgentTask, message: str) -> None:
        """Send progress notification for a task."""
        event = {
            "type": "progress",
            "task_id": agent_task.task_id,
            "stage": agent_task.stage.name,
            "progress": agent_task.progress,
            "message": message,
            "timestamp": time.time(),
        }

        # Notify registered handlers
        self.notify_handlers(event)

        # Call task-specific callback
        if agent_task.on_progress:
            try:
                agent_task.on_progress(event)
            except Exception as e:
                logger.error(f"Error in task progress callback: {e}")

    def _notify_completion(self, agent_task: AgentTask) -> None:
        """Send completion notification for a task."""
        event = {
            "type": "completion",
            "task_id": agent_task.task_id,
            "stage": agent_task.stage.name,
            "result": agent_task.result,
            "timestamp": agent_task.completed_at or time.time(),
        }

        # Notify registered handlers
        self.notify_handlers(event)

        # Call task-specific callback
        if agent_task.on_complete:
            try:
                agent_task.on_complete(event)
            except Exception as e:
                logger.error(f"Error in task completion callback: {e}")

    def _notify_error(self, agent_task: AgentTask) -> None:
        """Send error notification for a task."""
        event = {
            "type": "error",
            "task_id": agent_task.task_id,
            "stage": agent_task.stage.name,
            "error": agent_task.error,
            "timestamp": agent_task.completed_at or time.time(),
        }

        # Notify registered handlers
        self.notify_handlers(event)

        # Call task-specific callback
        if agent_task.on_error:
            try:
                agent_task.on_error(event)
            except Exception as e:
                logger.error(f"Error in task error callback: {e}")

    # === Agent Registry Methods ===

    def get_active_agents(self) -> dict[str, ActiveAgentInfo]:
        """Get all currently active spawned agents."""
        return self.active_agents.copy()

    def get_agent_by_id(self, agent_id: str) -> ActiveAgentInfo | None:
        """Get an active agent by its ID."""
        return self.active_agents.get(agent_id)

    def remove_agent(self, agent_id: str) -> None:
        """Remove an agent from the active registry."""
        self.active_agents.pop(agent_id, None)

    # === Agent Spawning and Lifecycle Methods ===

    async def spawn_agent(
        self,
        agent_type: str,
        task: str,
        context: dict[str, Any] | None = None,
        agent_definition: AgentDefinition | None = None,
        permission_check: bool = True,
    ) -> str:
        """Spawn a new agent based on AgentDefinition.
        
        Args:
            agent_type: Type of agent to spawn (e.g., 'explore', 'plan', 'general-purpose', 'fork')
            task: Task description for the agent
            context: Optional context dictionary
            agent_definition: Optional AgentDefinition to use (if None, looks up builtin)
            permission_check: Whether to check permissions before spawning
            
        Returns:
            Agent ID for tracking
            
        Raises:
            ValueError: If agent type is not recognized
            RuntimeError: If required dependencies are not configured
        """
        # Check permissions if required
        if permission_check and not self._check_spawn_permission(agent_type):
            raise RuntimeError(f"Permission denied to spawn agent type: {agent_type}")

        # Get agent definition
        if agent_definition is None:
            builtin_agents = get_builtin_agents()
            agent_def = next(
                (a for a in builtin_agents if a.agent_type == agent_type),
                None
            )
            if agent_def is None:
                raise ValueError(f"Unknown agent type: {agent_type}")
        else:
            agent_def = agent_definition

        # Generate unique agent ID
        self._agent_counter += 1
        agent_id = f"agent_{agent_type}_{self._agent_counter}_{uuid.uuid4().hex[:8]}"

        # Create agent info for registry
        agent_info = ActiveAgentInfo(
            agent_id=agent_id,
            agent_type=agent_type,
            task=task,
            created_at=time.time(),
            status=ProgressStage.STARTED,
        )
        self.active_agents[agent_id] = agent_info

        # Create the agent instance based on type
        agent = await self._create_agent_from_definition(
            agent_def,
            task=task,
            context=context,
        )

        if agent is None:
            del self.active_agents[agent_id]
            raise RuntimeError(f"Failed to create agent of type: {agent_type}")

        # Submit the task
        task_id = await self.submit_task(agent, task, context=context)
        agent_info.status = ProgressStage.RUNNING

        # Update task with agent ID for tracking
        if task_id in self._task_registry:
            self._task_registry[task_id].task = f"[{agent_id}] {task}"

        logger.info(f"Spawned agent {agent_id} of type {agent_type} with task {task_id}")
        return agent_id

    def _check_spawn_permission(self, agent_type: str) -> bool:
        """Check if spawning this agent type is permitted.
        
        Uses the permission system to validate agent spawning.
        """
        if self.config_getter is None:
            return True  # No config, allow by default

        try:
            settings = self.config_getter()
            if settings.bypass_tool_permissions:
                return True

            # Check if agent type is allowed
            allowed_types = ['explore', 'plan', 'general-purpose', 'fork']
            return agent_type in allowed_types
        except Exception as e:
            logger.warning(f"Error checking spawn permission: {e}")
            return True

    async def _create_agent_from_definition(
        self,
        agent_definition: AgentDefinition,
        task: str,
        context: dict[str, Any] | None = None,
    ) -> BaseAgent | None:
        """Create an agent instance from an AgentDefinition.
        
        Args:
            agent_definition: The AgentDefinition to create from
            task: Task for the agent
            context: Optional context

        Returns:
            BaseAgent instance or None if creation failed
        """
        # Import agent classes here to avoid circular imports
        try:
            from jarvis.core.agents.explore_agent import ExploreAgent
            from jarvis.core.agents.jarvis_v2 import JarvisV2 as CodingAgent
            from jarvis.core.agents.plan_agent import PlanAgent
        except ImportError as e:
            logger.error(f"Failed to import agent classes: {e}")
            return None

        if self.llm_provider is None or self.tool_registry is None:
            logger.error("LLM provider or tool registry not configured")
            return None

        try:
            agent_type = agent_definition.name

            if agent_type == 'explore':
                return ExploreAgent(
                    llm_provider=self.llm_provider,
                    tool_registry=self.tool_registry,
                    config_getter=self.config_getter,
                )
            elif agent_type == 'plan':
                return PlanAgent(
                    llm_provider=self.llm_provider,
                    tool_registry=self.tool_registry,
                    config_getter=self.config_getter,
                )
            elif agent_type in ('general-purpose', 'fork'):
                return CodingAgent(
                    llm_provider=self.llm_provider,
                    tool_registry=self.tool_registry,
                    config_getter=self.config_getter,
                    system_prompt=f"You are a {agent_type} agent.\n\nTask: {task}",
                )
            else:
                logger.warning(f"Unknown agent type: {agent_type}")
                return None
        except Exception as e:
            logger.error(f"Failed to create agent of type {agent_definition.name}: {e}")
            return None

    async def cancel_agent(self, agent_id: str) -> bool:
        """Cancel a running agent by ID.
        
        Args:
            agent_id: The agent ID to cancel
            
        Returns:
            True if agent was cancelled, False if not found
        """
        agent_info = self.active_agents.get(agent_id)
        if not agent_info:
            return False

        agent_info.status = ProgressStage.FAILED
        agent_info.error = "Cancelled by user"

        # Find and cancel associated task
        for task_id, task in self._task_registry.items():
            if agent_id in task.task:
                task.state = AgentState.FAILED
                task.error = "Cancelled"
                break

        logger.info(f"Cancelled agent {agent_id}")
        return True
