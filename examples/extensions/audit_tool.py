"""Extension that overrides the 'read' tool to log all file access.

Place this file in ``.jarvis/extensions/audit_read.py``.
"""

from jarvis.core.events.hooks import HookResult, HookStage

__version__ = "1.0.0"
__description__ = "Audit tool that logs every file read"


async def jarvis(api):
    """Log all 'read' tool calls before they execute."""

    # Use a lifecycle hook to intercept BEFORE_TOOL_CALL
    @api.hook(HookStage.BEFORE_TOOL_CALL)
    async def audit_hook(ctx):
        if ctx.tool_name == "read":
            file_path = (ctx.tool_args or {}).get("filePath", "?")
            print(f"[AUDIT] Reading file: {file_path}")
            # Store in the extension's local storage
            audit_log = ctx.extra.setdefault("audit_log", [])
            audit_log.append(file_path)
        return HookResult(proceed=True)
