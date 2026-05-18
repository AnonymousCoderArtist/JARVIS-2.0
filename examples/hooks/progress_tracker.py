"""Progress tracker — tracks tool call durations and success rates via EventBus.

Subscribe to ToolCallStarted and ToolCallEnded to build execution statistics.
"""

import logging
import time

from jarvis.core.events.types import ToolCallEnded, ToolCallError, ToolCallStarted

logger = logging.getLogger(__name__)


class ProgressTracker:
    """Tracks tool call metrics for the current session.

    Usage:
        tracker = ProgressTracker()
        bus.subscribe(ToolCallStarted, tracker.on_start)
        bus.subscribe(ToolCallEnded, tracker.on_end)
        bus.subscribe(ToolCallError, tracker.on_error)

        # At session end:
        stats = tracker.get_stats()
    """

    def __init__(self):
        self._start_times: dict[str, float] = {}
        self._total_calls = 0
        self._successful_calls = 0
        self._failed_calls = 0
        self._durations: dict[str, list[float]] = {}

    async def on_start(self, event: ToolCallStarted) -> None:
        """Record tool call start time."""
        self._start_times[event.tool_call_id] = time.time()
        self._total_calls += 1

    async def on_end(self, event: ToolCallEnded) -> None:
        """Record tool call completion and duration."""
        self._successful_calls += 1
        duration = event.duration_ms or 0

        if event.tool_name not in self._durations:
            self._durations[event.tool_name] = []
        self._durations[event.tool_name].append(duration)

    async def on_error(self, event: ToolCallError) -> None:
        """Record tool call failure."""
        self._failed_calls += 1
        logger.error(
            "Tool error: %s — %s",
            event.tool_name,
            event.error,
        )

    def get_stats(self) -> dict:
        """Return session tool call statistics."""
        tool_stats = {}
        for tool_name, durations in self._durations.items():
            tool_stats[tool_name] = {
                "calls": len(durations),
                "avg_ms": round(sum(durations) / len(durations), 1),
                "max_ms": round(max(durations), 1),
                "min_ms": round(min(durations), 1),
            }

        return {
            "total_calls": self._total_calls,
            "successful": self._successful_calls,
            "failed": self._failed_calls,
            "success_rate": round(
                self._successful_calls / max(self._total_calls, 1) * 100, 1
            ),
            "by_tool": tool_stats,
        }
