"""Async Agent Manager for concurrent agent operations"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

from core.agents.base import BaseAgent

logger = logging.getLogger(__name__)


class AgentState(Enum):
    """Agent execution states"""
    IDLE = "idle"
    PENDING = "pending"
    RUNNING = "running"
    WAITING = "waiting"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(order=True)
class PriorityTask:
    """Priority queue item for agent tasks"""
    priority: int
    created_at: float = field(default_factory=lambda: asyncio.get_event_loop().time())
    task_id: str = ""
    agent: BaseAgent = field(default=None)
    input_text: str = ""
    context: dict[str, Any] = field(default_factory=dict)


class AsyncAgentManager:
    """
    Manages asynchronous agent operations and task scheduling.
    
    Features:
    - Priority-based task queue
    - Concurrent agent execution with semaphore limits
    - Resource monitoring and adjustment
    - Agent state tracking
    """
    
    def __init__(
        self,
        max_concurrent_agents: int = 5,
        max_concurrent_tools: int = 10,
        enable_resource_monitoring: bool = True,
    ):
        self.max_concurrent_agents = max_concurrent_agents
        self.max_concurrent_tools = max_concurrent_tools
        self.enable_resource_monitoring = enable_resource_monitoring
        
        # Task queue and execution tracking
        self.task_queue: asyncio.PriorityQueue = asyncio.PriorityQueue()
        self.running_agents: dict[str, BaseAgent] = {}
        self.agent_states: dict[str, AgentState] = {}
        
        # Semaphores for resource limiting
        self.agent_semaphore = asyncio.Semaphore(max_concurrent_agents)
        self.tool_semaphore = asyncio.Semaphore(max_concurrent_tools)
        
        # Callbacks for monitoring
        self.progress_callback: Callable[[str, float], None] | None = None
        self.status_callback: Callable[[str], None] | None = None
        
        # Task tracking
        self.completed_tasks: list[dict[str, Any]] = []
        self.failed_tasks: list[dict[str, Any]] = []
        
        # Control flag
        self._running = False
        self._processor_task: asyncio.Task | None = None
    
    async def submit_task(
        self,
        agent: BaseAgent,
        task: str,
        priority: int = 0,
        context: dict[str, Any] | None = None,
    ) -> str:
        """
        Submit a task to the async queue.
        
        Args:
            agent: Agent instance to execute the task
            task: Task description/input
            priority: Priority level (lower = higher priority)
            context: Optional context dictionary
            
        Returns:
            Task ID for tracking
        """
        import uuid
        task_id = str(uuid.uuid4())
        
        priority_task = PriorityTask(
            priority=priority,
            task_id=task_id,
            agent=agent,
            input_text=task,
            context=context or {},
        )
        
        await self.task_queue.put(priority_task)
        logger.info(f"Task {task_id} submitted with priority {priority}")
        
        return task_id
    
    async def start_processing(self):
        """Start processing tasks from the queue."""
        self._running = True
        self._processor_task = asyncio.create_task(self._process_tasks())
        logger.info("AsyncAgentManager started processing tasks")
    
    async def stop_processing(self):
        """Stop processing tasks."""
        self._running = False
        if self._processor_task:
            self._processor_task.cancel()
            try:
                await self._processor_task
            except asyncio.CancelledError:
                pass
        logger.info("AsyncAgentManager stopped processing tasks")
    
    async def _process_tasks(self):
        """Internal task processing loop."""
        while self._running:
            try:
                # Wait for tasks with timeout to allow checking _running flag
                priority_task = await asyncio.wait_for(
                    self.task_queue.get(),
                    timeout=1.0
                )
                
                # Execute task concurrently
                asyncio.create_task(
                    self._execute_task(priority_task)
                )
                
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Error in task processing loop: {e}")
    
    async def _execute_task(self, priority_task: PriorityTask):
        """Execute a single task."""
        task_id = priority_task.task_id
        agent = priority_task.agent
        
        # Update state
        self.agent_states[task_id] = AgentState.PENDING
        
        async with self.agent_semaphore:
            self.agent_states[task_id] = AgentState.RUNNING
            self.running_agents[task_id] = agent
            
            try:
                if self.status_callback:
                    self.status_callback(f"Starting task {task_id}")
                
                result = await agent.process(
                    priority_task.input_text,
                    priority_task.context
                )
                
                self.agent_states[task_id] = AgentState.COMPLETED
                self.completed_tasks.append({
                    "task_id": task_id,
                    "result": result,
                    "status": "completed"
                })
                
                logger.info(f"Task {task_id} completed successfully")
                
            except Exception as e:
                self.agent_states[task_id] = AgentState.FAILED
                self.failed_tasks.append({
                    "task_id": task_id,
                    "error": str(e),
                    "status": "failed"
                })
                
                logger.error(f"Task {task_id} failed: {e}")
                
                if self.status_callback:
                    self.status_callback(f"Task {task_id} failed: {e}")
            
            finally:
                self.running_agents.pop(task_id, None)
    
    def get_agent_state(self, task_id: str) -> AgentState:
        """Get the current state of an agent task."""
        return self.agent_states.get(task_id, AgentState.IDLE)
    
    def get_running_count(self) -> int:
        """Get count of currently running agents."""
        return len(self.running_agents)
    
    def get_queue_size(self) -> int:
        """Get size of pending task queue."""
        return self.task_queue.qsize()
    
    async def execute_tool_concurrent(
        self,
        tool_name: str,
        arguments: dict[str, Any]
    ) -> Any:
        """
        Execute a tool with concurrency limiting.
        
        Args:
            tool_name: Name of the tool to execute
            arguments: Tool arguments
            
        Returns:
            Tool execution result
        """
        async with self.tool_semaphore:
            # This would need access to the tool registry
            # For now, we'll delegate to the agent's tool execution
            return None