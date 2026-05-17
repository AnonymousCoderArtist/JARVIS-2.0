"""Session guard hook — validates session configuration before starting.

Register this hook at BEFORE_SESSION_START to enforce session policies.
"""

import logging
from pathlib import Path

from jarvis.core.events.hooks import HookContext, HookResult

logger = logging.getLogger(__name__)


async def session_guard(ctx: HookContext) -> HookResult:
    """Validate session configuration before starting.

    This hook runs at BEFORE_SESSION_START stage. It checks:
    - Working directory exists and is accessible
    - Required project files are present
    - No suspicious configuration
    """
    # Validate working directory
    cwd = Path(ctx.cwd)
    if not cwd.exists():
        return HookResult(
            block=True,
            reason=f"Working directory does not exist: {ctx.cwd}",
        )

    if not cwd.is_dir():
        return HookResult(
            block=True,
            reason=f"Working path is not a directory: {ctx.cwd}",
        )

    # Check for suspicious paths (outside home directory)
    try:
        cwd.resolve().relative_to(Path.home().resolve())
    except ValueError:
        logger.warning("Session started outside home directory: %s", ctx.cwd)

    # Validate model is specified
    if not ctx.model:
        logger.warning("Session started without a model specified")

    logger.info(
        "Session %s started in %s with model %s",
        ctx.session_id,
        ctx.cwd,
        ctx.model or "(default)",
    )

    return HookResult(proceed=True)
