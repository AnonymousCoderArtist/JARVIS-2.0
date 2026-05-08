"""Background agent task dataclass and management functions."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class BackgroundAgentTask:
    """Represents a background agent task.
    
    Attributes:
        task_id: Unique identifier for the task
        agent_name: Name of the agent type (explore, plan, etc.)
        prompt: The prompt/task description for the agent
        status: Current status (pending, running, completed, failed)
        result: The result/output from the agent
        error: Error message if the task failed
        created_at: When the task was created
        completed_at: When the task completed
        task: The asyncio Task reference
        tool_uses: Count of tool calls made
        token_usage: Token usage count
        max_tokens: Maximum context tokens allowed
        retries: Number of retry attempts
        max_retries: Maximum retry attempts allowed
        current_activity: Description of current activity (e.g., "editing", "searching")
    """
    task_id: str
    agent_name: str
    prompt: str
    status: str = "pending"  # pending, running, completed, failed
    result: str = ""
    error: str | None = None
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: datetime | None = None
    task: asyncio.Task | None = None
    # Metrics
    tool_uses: int = 0
    token_usage: int = 0
    max_tokens: int = 0
    retries: int = 0
    max_retries: int = 30
    current_activity: str = ""  # e.g., "editing", "searching"


# Global background agent tracker with activity support
_background_agents: dict[str, BackgroundAgentTask] = {}
_background_lock = asyncio.Lock()


async def get_background_agent(task_id: str) -> BackgroundAgentTask | None:
    """Get a background agent task by ID.
    
    Args:
        task_id: The unique task identifier
        
    Returns:
        The BackgroundAgentTask if found, None otherwise
    """
    async with _background_lock:
        return _background_agents.get(task_id)


async def list_background_agents() -> list[BackgroundAgentTask]:
    """List all background agent tasks.
    
    Returns:
        List of all BackgroundAgentTask instances
    """
    async with _background_lock:
        return list(_background_agents.values())


async def get_completed_background_agents() -> list[BackgroundAgentTask]:
    """Get list of completed background agent tasks.
    
    Returns:
        List of BackgroundAgentTask instances with status 'completed'
    """
    async with _background_lock:
        return [agent for agent in _background_agents.values() if agent.status == "completed"]


async def clear_completed_background_agents() -> None:
    """Clear completed background agent tasks from the registry."""
    async with _background_lock:
        completed_task_ids = [task_id for task_id, agent in _background_agents.items() if agent.status == "completed"]
        for task_id in completed_task_ids:
            del _background_agents[task_id]
