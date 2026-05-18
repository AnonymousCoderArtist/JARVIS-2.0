"""Lifecycle hook registry — before/after hooks for agent execution stages.

Hooks are higher-level than raw EventBus subscriptions.  They allow
extensions to **block**, **modify**, or **inject** content at specific
stages of the agent's execution.

Usage
-----
.. code-block:: python

    registry = HookRegistry()

    # Register a hook that blocks destructive bash commands
    @registry.register(HookStage.BEFORE_TOOL_CALL)
    async def safety_gate(ctx):
        if ctx.tool_name == "bash" and "rm -rf" in ctx.args.get("command", ""):
            return HookResult(block=True, reason="Destructive command blocked")
        return HookResult(proceed=True)
"""

from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, TypeAlias, cast

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Hook Stages
# ---------------------------------------------------------------------------


class HookStage(str, Enum):
    """Well-known lifecycle stages where hooks can be registered."""

    # Agent lifecycle
    BEFORE_AGENT_START = "before_agent_start"
    AFTER_AGENT_START = "after_agent_start"
    BEFORE_AGENT_END = "before_agent_end"
    AFTER_AGENT_END = "after_agent_end"

    # Turn lifecycle
    BEFORE_TURN = "before_turn"
    AFTER_TURN = "after_turn"

    # Message / prompt building
    BEFORE_PROMPT_BUILD = "before_prompt_build"
    AFTER_PROMPT_BUILD = "after_prompt_build"

    # Tool execution
    BEFORE_TOOL_CALL = "before_tool_call"
    AFTER_TOOL_CALL = "after_tool_call"

    # Session
    BEFORE_SESSION_START = "before_session_start"
    AFTER_SESSION_START = "after_session_start"
    BEFORE_SESSION_SHUTDOWN = "before_session_shutdown"
    AFTER_SESSION_SHUTDOWN = "after_session_shutdown"

    # System prompt
    BEFORE_SYSTEM_PROMPT = "before_system_prompt"
    AFTER_SYSTEM_PROMPT = "after_system_prompt"

    # Skills
    BEFORE_SKILL_ACTIVATE = "before_skill_activate"
    AFTER_SKILL_ACTIVATE = "after_skill_activate"


# ---------------------------------------------------------------------------
# Hook Context & Result
# ---------------------------------------------------------------------------


@dataclass
class HookContext:
    """Context passed to every hook handler.

    Extensions can read from this to make decisions, and in some stages
    can *write* back to modify behaviour.
    """
    # Agent state
    agent_name: str = ""
    agent_input: str = ""
    agent_output: str = ""
    agent_error: str | None = None

    # Turn state
    turn_number: int = 0
    messages: list[dict[str, Any]] | None = None

    # Tool state
    tool_name: str = ""
    tool_args: dict[str, Any] = field(default_factory=dict)
    tool_result: Any = None
    tool_error: str | None = None

    # System prompt
    system_prompt: str = ""

    # Session
    session_id: str = ""
    model: str = ""
    cwd: str = ""

    # Skills
    skill_name: str = ""

    # Custom extension data (arbitrary key-value store)
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class HookResult:
    """Return value from a hook handler.

    Attributes
    ----------
    proceed : bool
        If True, normal execution continues.
        If False (and ``block`` is also False), the stage is skipped
        without error.
    block : bool
        If True, the action is blocked with a reason message.
    reason : str
        Human-readable explanation for blocking or skipping.
    modify : dict | None
        For stages that support modification (e.g. ``BEFORE_TOOL_CALL``),
        return updated args here.
    inject : str | None
        Content to inject into the pipeline
        (e.g. an extra system prompt message).
    """
    proceed: bool = True
    block: bool = False
    reason: str = ""
    modify: dict[str, Any] | None = None
    inject: str | None = None


HookHandler: TypeAlias = Callable[[HookContext], Coroutine[Any, Any, HookResult] | HookResult]

# ---------------------------------------------------------------------------
# Hook Registry
# ---------------------------------------------------------------------------


class HookRegistry:
    """Registry for lifecycle hooks.

    Hooks are organised by ``HookStage``.  Multiple handlers can be
    registered per stage; they are called in registration order.

    If **any** handler returns ``HookResult(block=True)``, the action
    is blocked and the remaining handlers are skipped.
    """

    def __init__(self) -> None:
        self._hooks: dict[HookStage, list[HookHandler]] = defaultdict(list)

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(
        self,
        stage: HookStage,
        handler: HookHandler | None = None,
    ) -> Callable[[HookHandler], HookHandler] | None:
        """Register a handler for *stage*.

        Can be used as a decorator::

            @registry.register(HookStage.BEFORE_TOOL_CALL)
            async def my_hook(ctx): ...

        Or called directly::

            registry.register(HookStage.BEFORE_TOOL_CALL, my_hook)
        """
        def decorator(fn: HookHandler) -> HookHandler:
            if fn not in self._hooks[stage]:
                self._hooks[stage].append(fn)
            return fn

        if handler is not None:
            decorator(handler)
            return None
        return decorator

    def unregister(self, stage: HookStage, handler: HookHandler) -> None:
        """Remove a specific handler from *stage*."""
        self._hooks[stage] = [h for h in self._hooks[stage] if h is not handler]

    def clear(self) -> None:
        """Remove ALL registered hooks."""
        self._hooks.clear()

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    async def run(
        self,
        stage: HookStage,
        ctx: HookContext | None = None,
    ) -> HookResult:
        """Run all handlers registered for *stage*.

        Returns the **last** non-default ``HookResult``.  If any handler
        returns ``block=True``, execution stops immediately.
        """
        if ctx is None:
            ctx = HookContext()

        handlers = self._hooks.get(stage, [])
        if not handlers:
            return HookResult(proceed=True)

        final_result = HookResult(proceed=True)

        for handler in handlers:
            try:
                result = handler(ctx)
                if isinstance(result, Coroutine):
                    result = await result
            except Exception:
                logger.exception("Hook handler %s failed at stage %s", handler, stage.value)
                continue

            if result is None:
                continue

            # After the None check, result is definitely a HookResult
            hook_result = cast(HookResult, result)

            if hook_result.block:
                logger.info(
                    "Hook %s blocked at stage %s: %s",
                    getattr(handler, "__name__", str(handler)),
                    stage.value,
                    hook_result.reason,
                )
                return hook_result  # Short-circuit on block

            if not hook_result.proceed:
                final_result = hook_result

            if hook_result.modify is not None:
                final_result.modify = hook_result.modify

            if hook_result.inject is not None:
                final_result.inject = hook_result.inject

        return final_result

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def get_handlers(self, stage: HookStage | None = None) -> dict[str, list[str]]:
        """Return handler names, optionally filtered by *stage*."""
        result: dict[str, list[str]] = {}
        for s, handlers in self._hooks.items():
            if stage is None or s is stage:
                result[s.value] = [
                    getattr(h, "__name__", str(h)) for h in handlers
                ]
        return result

    @property
    def total_handlers(self) -> int:
        return sum(len(v) for v in self._hooks.values())
