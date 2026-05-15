"""Turn counter hook — tracks and limits turn count with warnings.

Register this hook at BEFORE_TURN and AFTER_TURN to monitor iteration count.
"""

import logging
from core.events.hooks import HookContext, HookResult

logger = logging.getLogger(__name__)


class TurnCounter:
    """Tracks turn count and warns when approaching limits.

    Usage:
        counter = TurnCounter(warn_at=40, hard_limit=50)
        registry.register(HookStage.BEFORE_TURN, counter.on_before_turn)
        registry.register(HookStage.AFTER_TURN, counter.on_after_turn)
    """

    def __init__(self, warn_at: int = 40, hard_limit: int = 50):
        self.warn_at = warn_at
        self.hard_limit = hard_limit
        self.turn_count = 0

    async def on_before_turn(self, ctx: HookContext) -> HookResult:
        """Called before each turn. Warns when approaching limit."""
        self.turn_count += 1
        ctx.turn_number = self.turn_count

        if self.turn_count >= self.hard_limit:
            return HookResult(
                block=True,
                reason=f"Turn limit reached: {self.turn_count}/{self.hard_limit}",
            )

        if self.turn_count >= self.warn_at:
            remaining = self.hard_limit - self.turn_count
            logger.warning(
                "Approaching turn limit: %d/%d (%d remaining)",
                self.turn_count,
                self.hard_limit,
                remaining,
            )

        return HookResult(proceed=True)

    async def on_after_turn(self, ctx: HookContext) -> HookResult:
        """Called after each turn completes."""
        logger.info("Turn %d completed", self.turn_count)
        return HookResult(proceed=True)

    def reset(self):
        """Reset the counter for a new session."""
        self.turn_count = 0


# Singleton instance
turn_counter = TurnCounter(warn_at=40, hard_limit=50)
