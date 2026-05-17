"""Agent activity tracking for subagent view-only display.

This module provides thread-safe activity tracking for subagent tasks with
enhanced memory snapshot capabilities and progress tracking support.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class SubagentActivity:
    """Activity event from a subagent for view-only display.
    
    Attributes:
        timestamp: When the activity occurred
        event_type: Type of event (info, tool_use, tool_result, output)
        message: Human-readable message
        tool_name: Name of tool if this is a tool event
        tool_input: Tool input if this is a tool event
        tool_output: Tool output if this is a tool event
        duration_ms: Optional duration in milliseconds for tool execution
        token_delta: Optional token usage delta for this activity
    """
    timestamp: datetime = field(default_factory=datetime.now)
    event_type: str = "info"  # info, tool_use, tool_result, output
    message: str = ""
    tool_name: str | None = None
    tool_input: dict | None = None
    tool_output: str | None = None
    duration_ms: float | None = None
    token_delta: int | None = None


@dataclass
class AgentMemorySnapshot:
    """Snapshot of agent memory state for forking and persistence.
    
    Attributes:
        messages: List of message dictionaries representing conversation history
        context: Agent context dictionary with key-value pairs
        system_prompt: The system prompt string at snapshot time
        created_at: When the snapshot was created
        token_count: Approximate token count for the snapshot
    """
    messages: list[dict[str, Any]] = field(default_factory=list)
    context: dict[str, Any] = field(default_factory=dict)
    system_prompt: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    token_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert snapshot to dictionary for serialization.
        
        Returns:
            Dictionary representation of the snapshot
        """
        return {
            "messages": self.messages,
            "context": self.context,
            "system_prompt": self.system_prompt,
            "created_at": self.created_at.isoformat(),
            "token_count": self.token_count,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentMemorySnapshot:
        """Create snapshot from dictionary.
        
        Args:
            data: Dictionary containing snapshot data
            
        Returns:
            New AgentMemorySnapshot instance
        """
        return cls(
            messages=data.get("messages", []),
            context=data.get("context", {}),
            system_prompt=data.get("system_prompt", ""),
            created_at=datetime.fromisoformat(data["created_at"]) if "created_at" in data else datetime.now(),
            token_count=data.get("token_count", 0),
        )


# Activity registry for view-only display with thread-safe access
_subagent_activities: dict[str, list[SubagentActivity]] = {}
_activities_lock = asyncio.Lock()

# Memory snapshot registry for fork isolation
_memory_snapshots: dict[str, AgentMemorySnapshot] = {}
_snapshots_lock = asyncio.Lock()


def add_subagent_activity(task_id: str, activity: SubagentActivity) -> None:
    """Add an activity event for a subagent task.
    
    Thread-safe operation using asyncio lock.
    
    Args:
        task_id: The task identifier
        activity: The activity to record
    """
    if task_id not in _subagent_activities:
        _subagent_activities[task_id] = []
    _subagent_activities[task_id].append(activity)


async def add_subagent_activity_async(task_id: str, activity: SubagentActivity) -> None:
    """Add an activity event for a subagent task (async version).
    
    Thread-safe operation using asyncio lock.
    
    Args:
        task_id: The task identifier
        activity: The activity to record
    """
    async with _activities_lock:
        if task_id not in _subagent_activities:
            _subagent_activities[task_id] = []
        _subagent_activities[task_id].append(activity)


def get_subagent_activities(task_id: str) -> list[SubagentActivity]:
    """Get all activities for a subagent task.
    
    Args:
        task_id: The task identifier
        
    Returns:
        List of activities for the task, empty list if none
    """
    return _subagent_activities.get(task_id, [])


async def get_subagent_activities_async(task_id: str) -> list[SubagentActivity]:
    """Get all activities for a subagent task (async version).
    
    Args:
        task_id: The task identifier
        
    Returns:
        List of activities for the task, empty list if none
    """
    async with _activities_lock:
        return list(_subagent_activities.get(task_id, []))


def clear_subagent_activities(task_id: str | None = None) -> None:
    """Clear activities for a specific task or all tasks.
    
    Args:
        task_id: Optional task ID to clear specific task, or None to clear all
    """
    if task_id:
        _subagent_activities.pop(task_id, None)
    else:
        _subagent_activities.clear()


async def clear_subagent_activities_async(task_id: str | None = None) -> None:
    """Clear activities for a specific task or all tasks (async version).
    
    Args:
        task_id: Optional task ID to clear specific task, or None to clear all
    """
    async with _activities_lock:
        if task_id:
            _subagent_activities.pop(task_id, None)
        else:
            _subagent_activities.clear()


# Memory Snapshot Functions

async def save_memory_snapshot(
    task_id: str,
    messages: list[dict[str, Any]],
    context: dict[str, Any],
    system_prompt: str,
    token_count: int = 0,
) -> AgentMemorySnapshot:
    """Save a memory snapshot for a task.
    
    Creates a snapshot that can be inherited by forked agents.
    
    Args:
        task_id: The task identifier
        messages: List of message dictionaries
        context: Context dictionary
        system_prompt: System prompt string
        token_count: Approximate token count
        
    Returns:
        The created AgentMemorySnapshot
    """
    snapshot = AgentMemorySnapshot(
        messages=messages,
        context=context,
        system_prompt=system_prompt,
        token_count=token_count,
    )
    async with _snapshots_lock:
        _memory_snapshots[task_id] = snapshot
    return snapshot


async def load_memory_snapshot(task_id: str) -> AgentMemorySnapshot | None:
    """Load a memory snapshot for a task.
    
    Args:
        task_id: The task identifier
        
    Returns:
        The snapshot if found, None otherwise
    """
    async with _snapshots_lock:
        return _memory_snapshots.get(task_id)


async def clear_memory_snapshot(task_id: str | None = None) -> None:
    """Clear memory snapshots for a specific task or all tasks.
    
    This is called between forks to ensure clean memory state.
    
    Args:
        task_id: Optional task ID to clear, or None to clear all
    """
    async with _snapshots_lock:
        if task_id:
            _memory_snapshots.pop(task_id, None)
        else:
            _memory_snapshots.clear()


async def save_memory_snapshot_to_file(
    task_id: str,
    file_path: Path,
    messages: list[dict[str, Any]],
    context: dict[str, Any],
    system_prompt: str,
) -> None:
    """Save a memory snapshot to a file for persistence.
    
    Args:
        task_id: The task identifier
        file_path: Path to save the snapshot
        messages: List of message dictionaries
        context: Context dictionary
        system_prompt: System prompt string
    """
    snapshot = AgentMemorySnapshot(
        messages=messages,
        context=context,
        system_prompt=system_prompt,
    )
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(json.dumps(snapshot.to_dict(), indent=2))


async def load_memory_snapshot_from_file(file_path: Path) -> AgentMemorySnapshot | None:
    """Load a memory snapshot from a file.
    
    Args:
        file_path: Path to load the snapshot from
        
    Returns:
        The snapshot if found and valid, None otherwise
    """
    if not file_path.exists():
        return None
    try:
        data = json.loads(file_path.read_text())
        return AgentMemorySnapshot.from_dict(data)
    except (json.JSONDecodeError, KeyError):
        return None


def create_tool_activity(tool_name: str, tool_args: dict[str, Any]) -> SubagentActivity:
    """Create a tool_use activity entry.
    
    Args:
        tool_name: Name of the tool
        tool_args: Tool arguments
        
    Returns:
        SubagentActivity with tool_use event type
    """
    return SubagentActivity(
        event_type="tool_use",
        message=f"Using tool: {tool_name}",
        tool_name=tool_name,
        tool_input=tool_args,
    )


def create_tool_result_activity(
    tool_name: str,
    tool_args: dict[str, Any],
    result: Any,
    duration_ms: float | None = None,
    token_delta: int | None = None,
) -> SubagentActivity:
    """Create a tool_result activity entry.
    
    Args:
        tool_name: Name of the tool
        tool_args: Tool arguments
        result: Tool execution result
        duration_ms: Optional execution duration
        token_delta: Optional token usage delta
        
    Returns:
        SubagentActivity with tool_result event type
    """
    result_str = str(result) if result is not None else ""
    # Truncate large results for display
    if len(result_str) > 1000:
        result_str = result_str[:1000] + "..."

    return SubagentActivity(
        event_type="tool_result",
        message=f"Tool {tool_name} completed",
        tool_name=tool_name,
        tool_input=tool_args,
        tool_output=result_str,
        duration_ms=duration_ms,
        token_delta=token_delta,
    )


def create_info_activity(message: str) -> SubagentActivity:
    """Create an info activity entry.
    
    Args:
        message: Human-readable message
        
    Returns:
        SubagentActivity with info event type
    """
    return SubagentActivity(
        event_type="info",
        message=message,
    )


def create_output_activity(output: str) -> SubagentActivity:
    """Create an output activity entry.
    
    Args:
        output: Agent output message
        
    Returns:
        SubagentActivity with output event type
    """
    return SubagentActivity(
        event_type="output",
        message=output,
    )
