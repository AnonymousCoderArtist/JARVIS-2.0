"""Tool rate limiter hook — prevents abuse of expensive tool calls.

Register this hook at BEFORE_TOOL_CALL to rate-limit specific tools.
"""

import time
from core.events.hooks import HookContext, HookResult


class ToolRateLimiter:
    """Rate limiter for specific tool calls.

    Usage:
        limiter = ToolRateLimiter(max_calls=10, window_seconds=60)
        registry.register(HookStage.BEFORE_TOOL_CALL, limiter)
    """

    def __init__(
        self,
        max_calls: int = 10,
        window_seconds: int = 60,
        tools: list[str] | None = None,
    ):
        self.max_calls = max_calls
        self.window_seconds = window_seconds
        self.tools = tools or ["bash", "web_search", "fetch_webpage"]
        self._call_times: dict[str, list[float]] = {t: [] for t in self.tools}

    async def __call__(self, ctx: HookContext) -> HookResult:
        if ctx.tool_name not in self.tools:
            return HookResult(proceed=True)

        now = time.time()
        window_start = now - self.window_seconds

        # Clean old entries
        self._call_times[ctx.tool_name] = [
            t for t in self._call_times[ctx.tool_name] if t > window_start
        ]

        # Check rate limit
        if len(self._call_times[ctx.tool_name]) >= self.max_calls:
            return HookResult(
                block=True,
                reason=(
                    f"Rate limit exceeded for '{ctx.tool_name}': "
                    f"{self.max_calls} calls per {self.window_seconds}s window"
                ),
            )

        # Record this call
        self._call_times[ctx.tool_name].append(now)
        return HookResult(proceed=True)


# Singleton instance for direct registration
rate_limiter = ToolRateLimiter(max_calls=10, window_seconds=60)
