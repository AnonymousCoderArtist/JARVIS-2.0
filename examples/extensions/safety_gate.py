"""Extension that blocks destructive bash commands.

This is a 'safety gate' — it prevents the agent from running commands
that contain ``rm -rf`` or similar destructive patterns.
"""

from core.events.hooks import HookResult, HookStage

__version__ = "1.0.0"
__description__ = "Safety gate that blocks destructive bash commands"

DESTRUCTIVE_PATTERNS = [
    "rm -rf",
    "rm -fr",
    "mkfs",
    "dd if=",
    "> /dev/",
    ":(){ :|:& };:",  # Fork bomb
]


async def jarvis(api):
    """Register a before-tool-call hook that blocks dangerous commands."""

    @api.hook(HookStage.BEFORE_TOOL_CALL)
    async def safety_gate(ctx):
        if ctx.tool_name != "bash":
            return HookResult(proceed=True)

        command = (ctx.tool_args or {}).get("command", "")
        command_lower = command.lower()

        for pattern in DESTRUCTIVE_PATTERNS:
            if pattern in command_lower:
                return HookResult(
                    block=True,
                    reason=f"Destructive command pattern '{pattern}' blocked by safety gate extension",
                )

        return HookResult(proceed=True)
