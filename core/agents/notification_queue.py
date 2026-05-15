"""Agent notification queue system - push-based subagent-to-main-agent communication.

Inspired by OpenClaude's notification queue pattern. Subagents enqueue XML-formatted
notifications on completion/failure, and the main agent drains them each turn,
injecting them as context into the LLM conversation automatically.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class NotificationMode(str, Enum):
    """Notification mode for routing and filtering."""
    TASK_NOTIFICATION = "task-notification"
    PROGRESS_UPDATE = "progress-update"
    SHELL_NOTIFICATION = "shell-notification"


class NotificationPriority(str, Enum):
    """Priority levels for notification processing order."""
    HIGH = "high"
    NORMAL = "normal"
    LATER = "later"


@dataclass
class NotificationUsage:
    """Token and resource usage statistics for a completed task."""
    total_tokens: int = 0
    tool_uses: int = 0
    duration_ms: float = 0.0


@dataclass
class NotificationWorktree:
    """Worktree information for a completed task."""
    worktree_path: str = ""
    branch: str = ""


@dataclass
class QueuedNotification:
    """A single notification in the queue."""
    task_id: str
    mode: NotificationMode = NotificationMode.TASK_NOTIFICATION
    priority: NotificationPriority = NotificationPriority.NORMAL
    status: str = "completed"  # completed, failed, killed, running
    tool_use_id: str = ""
    summary: str = ""
    result: str = ""
    usage: NotificationUsage | None = None
    worktree: NotificationWorktree | None = None
    agent_id: str = ""  # Empty = main thread, non-empty = specific subagent
    timestamp: float = 0.0
    progress: float = 0.0  # 0.0-1.0 for progress updates


# Global notification queue - shared across all agents in the process
class NotificationQueue:
    """Thread-safe notification queue for inter-agent communication.

    Notifications are enqueued by subagents on completion/failure/progress,
    and drained by the main agent each turn to inject into the LLM conversation.
    """

    def __init__(self):
        self._queue: list[QueuedNotification] = []
        self._lock = threading.Lock()

    def enqueue(self, notification: QueuedNotification) -> None:
        """Add a notification to the queue."""
        with self._lock:
            self._queue.append(notification)
        logger.debug(
            "Enqueued notification: task_id=%s mode=%s status=%s",
            notification.task_id,
            notification.mode.value,
            notification.status,
        )

    def drain(
        self,
        agent_id: str = "",
        exclude_modes: set[NotificationMode] | None = None,
    ) -> list[QueuedNotification]:
        """Drain all pending notifications for the given agent.

        Args:
            agent_id: Empty string for main thread (drains all unaddressed),
                     non-empty for subagent (drains only addressed to this agent_id)
            exclude_modes: Notification modes to exclude from draining

        Returns:
            List of drained notifications
        """
        exclude = exclude_modes or set()
        with self._lock:
            kept = []
            drained = []
            for notif in self._queue:
                if notif.mode in exclude:
                    kept.append(notif)
                    continue
                # Main thread drains unaddressed notifications
                # Subagents drain notifications addressed to them
                if agent_id == "" and notif.agent_id == "":
                    drained.append(notif)
                elif agent_id != "" and notif.agent_id == agent_id:
                    drained.append(notif)
                else:
                    kept.append(notif)
            self._queue = kept
        return drained

    def clear(self) -> None:
        """Clear all pending notifications."""
        with self._lock:
            self._queue.clear()

    def pending_count(self) -> int:
        """Return the number of pending notifications."""
        with self._lock:
            return len(self._queue)


# Module-level singleton
_notification_queue = NotificationQueue()


def get_notification_queue() -> NotificationQueue:
    """Get the global notification queue singleton."""
    return _notification_queue


def set_notification_queue(queue: NotificationQueue) -> None:
    """Replace the global notification queue (for testing)."""
    global _notification_queue
    _notification_queue = queue


def build_task_notification_xml(notif: QueuedNotification) -> str:
    """Build XML-formatted task notification message.

    The XML structure is designed to be parsed by the LLM as part of
    the conversation context, providing structured task completion data.
    """
    lines = ["<task-notification>"]
    lines.append(f"  <task-id>{notif.task_id}</task-id>")

    if notif.tool_use_id:
        lines.append(f"  <tool-use-id>{notif.tool_use_id}</tool-use-id>")

    lines.append(f"  <status>{notif.status}</status>")

    if notif.summary:
        lines.append(f"  <summary>{notif.summary}</summary>")

    if notif.result:
        lines.append(f"  <result>{notif.result}</result>")

    if notif.usage:
        lines.append("  <usage>")
        lines.append(f"    <total_tokens>{notif.usage.total_tokens}</total_tokens>")
        lines.append(f"    <tool_uses>{notif.usage.tool_uses}</tool_uses>")
        lines.append(f"    <duration_ms>{notif.usage.duration_ms:.0f}</duration_ms>")
        lines.append("  </usage>")

    if notif.worktree:
        lines.append("  <worktree>")
        lines.append(f"    <worktree-path>{notif.worktree.worktree_path}</worktree-path>")
        if notif.worktree.branch:
            lines.append(f"    <worktree-branch>{notif.worktree.branch}</worktree-branch>")
        lines.append("  </worktree>")

    lines.append("</task-notification>")
    return "\n".join(lines)


def build_progress_xml(notif: QueuedNotification) -> str:
    """Build XML-formatted progress update message."""
    lines = ["<progress-update>"]
    lines.append(f"  <task-id>{notif.task_id}</task-id>")
    lines.append(f"  <agent>{notif.summary}</agent>")
    lines.append(f"  <progress>{notif.progress:.0%}</progress>")
    if notif.result:
        lines.append(f"  <activity>{notif.result}</activity>")
    lines.append("</progress-update>")
    return "\n".join(lines)


def format_notifications_for_llm(notifications: list[QueuedNotification]) -> str:
    """Format a list of notifications as a single string for LLM context.

    This is called by the main agent loop to inject pending notifications
    into the conversation as a user message.
    """
    if not notifications:
        return ""

    parts = []
    for notif in notifications:
        if notif.mode == NotificationMode.TASK_NOTIFICATION:
            parts.append(build_task_notification_xml(notif))
        elif notif.mode == NotificationMode.PROGRESS_UPDATE:
            parts.append(build_progress_xml(notif))

    if not parts:
        return ""

    return "\n\n".join([
        "The following task notifications arrived from background agents:",
        *parts,
        "\nReview these notifications and continue your work accordingly.",
    ])


def enqueue_agent_notification(
    task_id: str,
    agent_name: str,
    status: str,
    summary: str = "",
    result: str = "",
    tool_use_id: str = "",
    total_tokens: int = 0,
    tool_uses: int = 0,
    duration_ms: float = 0.0,
    worktree_path: str = "",
    worktree_branch: str = "",
    agent_id: str = "",
) -> None:
    """Enqueue a task completion notification for the main agent.

    This is the primary function called when a subagent completes, fails, or is killed.
    It constructs a QueuedNotification and adds it to the global queue.

    Args:
        task_id: Unique task identifier
        agent_name: Name of the agent that completed
        status: Task status (completed, failed, killed)
        summary: Brief summary of what was done
        result: Full result/output text
        tool_use_id: The tool call ID that launched this subagent
        total_tokens: Total tokens consumed by the subagent
        tool_uses: Number of tool calls made by the subagent
        duration_ms: Duration of the task in milliseconds
        worktree_path: Git worktree path if forked
        worktree_branch: Git worktree branch if forked
        agent_id: Target agent ID (empty = main thread)
    """
    usage = NotificationUsage(
        total_tokens=total_tokens,
        tool_uses=tool_uses,
        duration_ms=duration_ms,
    )
    worktree = None
    if worktree_path:
        worktree = NotificationWorktree(
            worktree_path=worktree_path,
            branch=worktree_branch,
        )

    import time
    notif = QueuedNotification(
        task_id=task_id,
        mode=NotificationMode.TASK_NOTIFICATION,
        priority=NotificationPriority.NORMAL,
        status=status,
        tool_use_id=tool_use_id,
        summary=summary or f"Subagent '{agent_name}' task {status}",
        result=result,
        usage=usage,
        worktree=worktree,
        agent_id=agent_id,
        timestamp=time.time(),
    )

    _notification_queue.enqueue(notif)
    logger.info(
        "Agent notification enqueued: task_id=%s agent=%s status=%s",
        task_id,
        agent_name,
        status,
    )


def enqueue_progress_update(
    task_id: str,
    agent_name: str,
    progress: float,
    activity: str = "",
    agent_id: str = "",
) -> None:
    """Enqueue a progress update from a running subagent.

    Args:
        task_id: Unique task identifier
        agent_name: Name of the agent reporting progress
        progress: Progress ratio (0.0 to 1.0)
        activity: Current activity description
        agent_id: Target agent ID (empty = main thread)
    """
    import time
    notif = QueuedNotification(
        task_id=task_id,
        mode=NotificationMode.PROGRESS_UPDATE,
        priority=NotificationPriority.LATER,
        status="running",
        summary=agent_name,
        result=activity,
        agent_id=agent_id,
        timestamp=time.time(),
        progress=progress,
    )

    _notification_queue.enqueue(notif)
