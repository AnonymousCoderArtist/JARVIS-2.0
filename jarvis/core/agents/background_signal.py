"""Background signal system for foreground-to-background agent transitions.

Inspired by OpenClaude's backgroundSignal pattern. When a foreground agent is
running, this module provides a Promise (asyncio.Future) that resolves when
the agent should be backgrounded, allowing the main loop to race between
agent completion and backgrounding events.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

logger = logging.getLogger(__name__)


class BackgroundSignalManager:
    """Manages background signal promises for foreground agents.

    When a foreground agent is running, register it with this manager.
    The returned signal (asyncio.Future) resolves when the agent is
    backgrounded, allowing the caller to race between completion and
    backgrounding.
    """

    def __init__(self):
        self._signal_resolvers: dict[str, asyncio.Future] = {}
        self._auto_background_timers: dict[str, asyncio.TimerHandle] = {}

    def register_foreground_agent(
        self,
        agent_id: str,
        auto_background_ms: int | None = None,
    ) -> asyncio.Future:
        """Register a foreground agent and return a background signal.

        Args:
            agent_id: Unique identifier for the agent
            auto_background_ms: If set, automatically background the agent
                after this many milliseconds

        Returns:
            An asyncio.Future that resolves when the agent is backgrounded
        """
        loop = asyncio.get_event_loop()
        signal = loop.create_future()
        self._signal_resolvers[agent_id] = signal

        if auto_background_ms is not None and auto_background_ms > 0:
            def _auto_background():
                if agent_id in self._signal_resolvers:
                    future = self._signal_resolvers.pop(agent_id)
                    if not future.done():
                        future.set_result("auto_backgrounded")
                    logger.info(
                        "Agent %s auto-backgrounded after %dms",
                        agent_id,
                        auto_background_ms,
                    )

            self._auto_background_timers[agent_id] = loop.call_later(
                auto_background_ms / 1000.0,
                _auto_background,
            )

        logger.debug("Registered foreground agent: %s", agent_id)
        return signal

    def background_agent(self, agent_id: str) -> None:
        """Signal that an agent should be moved to background execution.

        This resolves the background signal for the given agent, allowing
        the foreground execution loop to detect the transition.

        Args:
            agent_id: Unique identifier for the agent
        """
        if agent_id in self._signal_resolvers:
            future = self._signal_resolvers.pop(agent_id)
            if not future.done():
                future.set_result("backgrounded")

        if agent_id in self._auto_background_timers:
            timer = self._auto_background_timers.pop(agent_id)
            timer.cancel()

        logger.debug("Agent %s moved to background", agent_id)

    def unregister_agent(self, agent_id: str) -> None:
        """Clean up an agent's background signal without resolving it.

        Called when a foreground agent completes normally.

        Args:
            agent_id: Unique identifier for the agent
        """
        if agent_id in self._signal_resolvers:
            future = self._signal_resolvers.pop(agent_id)
            if not future.done():
                future.cancel()

        if agent_id in self._auto_background_timers:
            timer = self._auto_background_timers.pop(agent_id)
            timer.cancel()

        logger.debug("Unregistered foreground agent: %s", agent_id)

    def is_foreground(self, agent_id: str) -> bool:
        """Check if an agent is currently running in foreground mode."""
        return agent_id in self._signal_resolvers


# Module-level singleton
_background_signal_manager = BackgroundSignalManager()


def get_background_signal_manager() -> BackgroundSignalManager:
    """Get the global background signal manager singleton."""
    return _background_signal_manager


async def race_agent_execution(
    agent_coro,
    background_signal: asyncio.Future,
) -> tuple[str, Any]:
    """Race between agent completion and backgrounding.

    Args:
        agent_coro: The agent's execution coroutine
        background_signal: Future that resolves when agent is backgrounded

    Returns:
        Tuple of (outcome, result) where outcome is one of:
        - "completed": Agent finished normally
        - "backgrounded": Agent was moved to background
        - "failed": Agent raised an exception
    """
    try:
        done, pending = await asyncio.wait(
            [agent_coro, background_signal],
            return_when=asyncio.FIRST_COMPLETED,
        )

        for task in pending:
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass

        if background_signal in done:
            return ("backgrounded", background_signal.result())

        return ("completed", list(done)[0].result())

    except Exception as e:
        return ("failed", e)
