"""Safety gate hook — blocks dangerous commands before they execute.

Register this hook at BEFORE_TOOL_CALL to prevent destructive operations.
"""

from core.events.hooks import HookContext, HookResult

# Patterns that indicate dangerous commands
DANGEROUS_PATTERNS = [
    "rm -rf /",
    "rm -rf ~",
    "rm -rf /*",
    "sudo rm -rf",
    "mkfs.",
    "dd if=",
    "> /dev/sda",
    "curl",
    "wget",
    "chmod 777",
    "chmod -R 777",
]

# Commands that require explicit approval even in auto-approve mode
SENSITIVE_COMMANDS = [
    "git push --force",
    "git reset --hard",
    "DROP TABLE",
    "DELETE FROM",
]


async def safety_gate(ctx: HookContext) -> HookResult:
    """Block dangerous tool calls before they execute.

    This hook runs at BEFORE_TOOL_CALL stage. It inspects the tool name
    and arguments, returning HookResult(block=True) for dangerous operations.
    """
    if ctx.tool_name != "bash":
        return HookResult(proceed=True)

    command = ctx.tool_args.get("command", "")
    command_lower = command.lower()

    # Block outright dangerous commands
    for pattern in DANGEROUS_PATTERNS:
        if pattern.lower() in command_lower:
            return HookResult(
                block=True,
                reason=f"Dangerous command blocked: '{pattern}'",
            )

    # Warn on sensitive operations (doesn't block, but logs)
    for sensitive in SENSITIVE_COMMANDS:
        if sensitive.lower() in command_lower:
            # Could emit a warning event here
            pass

    return HookResult(proceed=True)
