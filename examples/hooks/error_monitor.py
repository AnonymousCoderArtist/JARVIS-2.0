"""Error monitor — collects errors and summarizes them at session end.

Subscribe to AgentError and ToolCallError to track failures.
"""

import logging
from dataclasses import dataclass

from jarvis.core.events.types import AgentError, ToolCallError

logger = logging.getLogger(__name__)


@dataclass
class ErrorEntry:
    """A single error entry."""
    error_type: str  # "agent" or "tool"
    name: str  # agent_name or tool_name
    message: str
    recoverable: bool = False


class ErrorMonitor:
    """Collects errors during a session and provides summaries.

    Usage:
        monitor = ErrorMonitor()
        bus.subscribe(AgentError, monitor.on_agent_error)
        bus.subscribe(ToolCallError, monitor.on_tool_error)

        # At session end:
        summary = monitor.get_summary()
    """

    def __init__(self, max_entries: int = 100):
        self._errors: list[ErrorEntry] = []
        self._max_entries = max_entries

    async def on_agent_error(self, event: AgentError) -> None:
        """Record an agent-level error."""
        entry = ErrorEntry(
            error_type="agent",
            name=event.agent_name,
            message=event.error,
            recoverable=event.recoverable,
        )
        self._errors.append(entry)
        self._trim()

        logger.error(
            "Agent error: %s — %s (recoverable: %s)",
            event.agent_name,
            event.error,
            event.recoverable,
        )

    async def on_tool_error(self, event: ToolCallError) -> None:
        """Record a tool-level error."""
        entry = ErrorEntry(
            error_type="tool",
            name=event.tool_name,
            message=event.error,
        )
        self._errors.append(entry)
        self._trim()

        logger.error(
            "Tool error: %s — %s",
            event.tool_name,
            event.error,
        )

    def _trim(self):
        """Keep only the most recent errors."""
        if len(self._errors) > self._max_entries:
            self._errors = self._errors[-self._max_entries:]

    def get_summary(self) -> dict:
        """Return error summary for the session."""
        tool_errors = [e for e in self._errors if e.error_type == "tool"]
        agent_errors = [e for e in self._errors if e.error_type == "agent"]
        recoverable = [e for e in self._errors if e.recoverable]

        # Count by tool/agent name
        tool_counts: dict[str, int] = {}
        for e in tool_errors:
            tool_counts[e.name] = tool_counts.get(e.name, 0) + 1

        agent_counts: dict[str, int] = {}
        for e in agent_errors:
            agent_counts[e.name] = agent_counts.get(e.name, 0) + 1

        return {
            "total_errors": len(self._errors),
            "tool_errors": len(tool_errors),
            "agent_errors": len(agent_errors),
            "recoverable": len(recoverable),
            "by_tool": tool_counts,
            "by_agent": agent_counts,
            "recent": [
                {
                    "type": e.error_type,
                    "name": e.name,
                    "message": e.message[:200],
                }
                for e in self._errors[-10:]
            ],
        }
