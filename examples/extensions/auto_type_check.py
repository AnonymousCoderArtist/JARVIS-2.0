"""Auto type-check extension — runs `uvx ty check` after every edit/write.

Drop this into .jarvis/extensions/ or ~/.jarvis/extensions/ to enable.
After every `edit`, `write`, or `create` tool call, it runs `uvx ty check`
and feeds any type errors back to the LLM so it can fix them immediately.
"""

from core.extensions.api import ExtensionAPI
from core.events.hooks import HookStage

# Re-export the hook so it can also be registered directly
from examples.hooks.auto_type_check import AutoTypeCheckHook


async def jarvis_extension(api: ExtensionAPI):
    """Register the auto type-check hook."""
    hook = AutoTypeCheckHook(max_errors=20)
    api.register_hook(HookStage.AFTER_TOOL_CALL, hook)
