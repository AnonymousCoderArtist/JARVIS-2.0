"""Tool logger hook — logs every tool call with duration and result summary.

Register this hook at AFTER_TOOL_CALL to record tool execution details.
"""

import logging

from jarvis.core.events.hooks import HookContext, HookResult

logger = logging.getLogger("jarvis.tool_audit")


async def tool_logger(ctx: HookContext) -> HookResult:
    """Log every tool call with timing and result summary.

    This hook runs at AFTER_TOOL_CALL stage. It records:
    - Tool name and arguments (truncated)
    - Success/failure status
    - Error message if any
    """
    # Truncate args for readability
    args = ctx.tool_args
    args_summary = str(args)[:200] + ("..." if len(str(args)) > 200 else "")

    if ctx.tool_error:
        logger.warning(
            "TOOL FAILED: %s | args: %s | error: %s",
            ctx.tool_name,
            args_summary,
            ctx.tool_error,
        )
    else:
        # Truncate result for readability
        result_str = str(ctx.tool_result)[:300]
        logger.info(
            "TOOL OK: %s | args: %s | result: %s",
            ctx.tool_name,
            args_summary,
            result_str + ("..." if len(str(ctx.tool_result)) > 300 else ""),
        )

    return HookResult(proceed=True)
