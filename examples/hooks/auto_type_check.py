"""Auto type-check hook — runs `uvx ty check` after every edit/write tool call.

This hook registers at AFTER_TOOL_CALL. When an edit or write tool succeeds,
it runs `uvx ty check` on the project and feeds the results back to the agent
so it can fix type errors in the same turn.

Usage as an extension:
    async def jarvis_extension(api: ExtensionAPI):
        api.register_hook(HookStage.AFTER_TOOL_CALL, auto_type_check)

Usage directly:
    registry.register(HookStage.AFTER_TOOL_CALL, auto_type_check)
"""

import asyncio
import logging
import subprocess
from pathlib import Path

from core.events.hooks import HookContext, HookResult, HookStage

logger = logging.getLogger(__name__)

# Tools that modify files and should trigger a type check
WRITE_TOOLS = {"edit", "write", "create"}


class AutoTypeCheckHook:
    """Runs `uvx ty check` after file-modifying tool calls.

    If type errors are found, the hook injects the error output into the
    conversation so the LLM can fix them in the next turn.

    Attributes:
        max_errors: Maximum number of errors to report (prevents huge outputs)
        check_root: Project root for running ty check (defaults to cwd)
    """

    def __init__(
        self,
        max_errors: int = 20,
        check_root: str | Path | None = None,
    ):
        self.max_errors = max_errors
        self.check_root = Path(check_root) if check_root else Path.cwd()

    async def __call__(self, ctx: HookContext) -> HookResult:
        """Run after a tool call. If it was a write/edit, run ty check."""
        # Only act on successful write/edit tool calls
        if ctx.tool_name not in WRITE_TOOLS:
            return HookResult(proceed=True)

        if ctx.tool_error:
            return HookResult(proceed=True)  # Tool failed, skip type check

        # Run ty check asynchronously
        try:
            errors = await self._run_ty_check()
        except Exception:
            logger.exception("Auto type-check hook failed")
            return HookResult(proceed=True)

        if not errors:
            return HookResult(proceed=True)

        # Inject type errors into the conversation for the LLM to fix
        error_text = self._format_errors(errors)
        return HookResult(
            proceed=True,
            inject=error_text,
        )

    async def _run_ty_check(self) -> list[str]:
        """Run `uvx ty check` and return error lines."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "uvx", "ty", "check",
                cwd=str(self.check_root),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()
            output = stdout.decode("utf-8", errors="replace")

            if proc.returncode == 0:
                return []  # No errors

            # Parse error lines from output
            errors = []
            for line in output.splitlines():
                line = line.strip()
                if line and ("error" in line.lower() or ":" in line):
                    errors.append(line)
                    if len(errors) >= self.max_errors:
                        break

            return errors

        except FileNotFoundError:
            logger.warning("uvx not found — skipping auto type-check")
            return []
        except Exception:
            logger.exception("ty check failed")
            return []

    def _format_errors(self, errors: list[str]) -> str:
        """Format type errors as a message for the LLM."""
        header = (
            "\n\n⚠️ TYPE CHECK FAILED — `uvx ty check` found errors after your edit.\n"
            "Please fix these type errors in your next response:\n"
        )
        body = "\n".join(errors[:self.max_errors])
        footer = (
            f"\n\n({len(errors)} error(s) total. "
            "Fix the errors above and re-run will be checked automatically.)"
        )
        return header + body + footer


# Singleton instance for direct registration
auto_type_check = AutoTypeCheckHook()
