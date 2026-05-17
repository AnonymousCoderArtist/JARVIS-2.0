"""Central event bus for pub/sub communication across JARVIS"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import defaultdict
from collections.abc import Callable, Coroutine
from typing import Any, TypeAlias

logger = logging.getLogger(__name__)

# Type alias for event handler functions
EventHandler: TypeAlias = Callable[[Any], Coroutine[Any, Any, None] | None]


class EventBus:
    """A per-session pub/sub event bus.

    Pattern
    -------
    - Subscribers register for specific event types (via the event class).
    - Emitters call ``emit(event_instance)`` to fire an event.
    - All registered async handlers are ``await``-ed; sync handlers are
      called sequentially.
    - Priority ordering: higher priority handlers run first.

    Thread-safety
    -------------
    This class is **not** thread-safe by default.  Each agent session
    should own its own ``EventBus`` instance.

    Usage
    -----
    .. code-block:: python

        bus = EventBus()
        bus.subscribe(ToolCallStarted, my_handler, priority=10)

        # Inside the agent loop:
        await bus.emit(ToolCallStarted(timestamp=t, tool_name="read", ...))
    """

    def __init__(self) -> None:
        # event_type -> [(priority, handler), ...]  (sorted by priority desc)
        self._subscribers: dict[type, list[tuple[int, EventHandler]]] = defaultdict(list)
        # Statistics for introspection / debugging
        self._stats: dict[str, Any] = {
            "total_emitted": 0,
            "per_type": defaultdict(int),
            "slowest_handler_ms": 0.0,
            "slowest_handler_name": "",
        }

    # ------------------------------------------------------------------
    # Subscription
    # ------------------------------------------------------------------

    def subscribe(
        self,
        event_type: type,
        handler: EventHandler,
        *,
        priority: int = 0,
    ) -> Callable[[], None]:
        """Register *handler* to be called when *event_type* is emitted.

        Returns an ``unsubscribe`` callable for easy cleanup.
        """
        if handler not in [h for _, h in self._subscribers[event_type]]:
            self._subscribers[event_type].append((priority, handler))
            self._subscribers[event_type].sort(key=lambda x: x[0], reverse=True)

        def unsubscribe() -> None:
            self.unsubscribe(event_type, handler)

        return unsubscribe

    def unsubscribe(self, event_type: type, handler: EventHandler) -> None:
        """Remove a previously registered handler."""
        self._subscribers[event_type] = [
            (p, h) for p, h in self._subscribers[event_type] if h is not handler
        ]
        # Clean up empty type keys
        if not self._subscribers[event_type]:
            del self._subscribers[event_type]

    def clear(self) -> None:
        """Remove ALL subscribers.  Used during session teardown."""
        self._subscribers.clear()

    # ------------------------------------------------------------------
    # Emission
    # ------------------------------------------------------------------

    async def emit(self, event: Any) -> None:
        """Fire *event* to all subscribed handlers (async-aware).

        Async handlers are gathered concurrently. Sync (non-async) handlers
        are called sequentially before gathering async ones.
        """
        self._stats["total_emitted"] += 1
        type_key = type(event)
        self._stats["per_type"][type_key.__name__] += 1

        handlers = self._subscribers.get(type_key, [])
        if not handlers:
            # Also check parent classes for polymorphic dispatch
            for cls in type_key.__mro__[1:]:
                if cls in self._subscribers:
                    handlers.extend(self._subscribers[cls])

        if not handlers:
            return

        sync_handlers: list[EventHandler] = []
        async_handlers: list[Coroutine[Any, Any, None]] = []

        for _priority, handler in handlers:
            start = time.perf_counter()
            try:
                result = handler(event)
                if asyncio.iscoroutine(result):
                    async_handlers.append(result)
                else:
                    sync_handlers.append(handler)
            except Exception:
                logger.exception("Sync handler %s failed for event %s", handler, type_key.__name__)
            finally:
                elapsed = (time.perf_counter() - start) * 1000
                if elapsed > self._stats["slowest_handler_ms"]:
                    self._stats["slowest_handler_ms"] = elapsed
                    self._stats["slowest_handler_name"] = getattr(handler, "__name__", str(handler))

        # Await all async handlers concurrently
        if async_handlers:
            results = await asyncio.gather(*async_handlers, return_exceptions=True)
            for i, res in enumerate(results):
                if isinstance(res, Exception):
                    logger.exception(
                        "Async handler failed for event %s: %s",
                        type_key.__name__,
                        res,
                    )

    async def emit_async(self, event: Any) -> None:
        """Fire-and-forget variant — logs errors but does not propagate them."""
        try:
            await self.emit(event)
        except Exception:
            logger.exception("emit_async failed for event %s", type(event).__name__)

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    @property
    def subscriber_count(self) -> int:
        """Total number of registered handler slots."""
        return sum(len(v) for v in self._subscribers.values())

    @property
    def event_type_count(self) -> int:
        """Number of distinct event types with subscribers."""
        return len(self._subscribers)

    def get_stats(self) -> dict[str, Any]:
        """Return a snapshot of bus statistics for debugging."""
        return {
            "total_emitted": self._stats["total_emitted"],
            "per_type": dict(self._stats["per_type"]),
            "subscriber_count": self.subscriber_count,
            "event_type_count": self.event_type_count,
            "slowest_handler_ms": self._stats["slowest_handler_ms"],
            "slowest_handler_name": self._stats["slowest_handler_name"],
        }

    def get_subscribers(self, event_type: type | None = None) -> dict[str, list[str]]:
        """Return subscriber names for *event_type* (or all if ``None``)."""
        result: dict[str, list[str]] = {}
        for typ, handlers in self._subscribers.items():
            if event_type is None or typ is event_type:
                result[typ.__name__] = [
                    getattr(h, "__name__", str(h)) for _, h in handlers
                ]
        return result
