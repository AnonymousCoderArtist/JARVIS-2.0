"""Auto type-check extension — runs `uvx ty check` after every edit/write.

Drop this into .jarvis/extensions/ or ~/.jarvis/extensions/ to enable.
After every `edit`, `write`, or `create` tool call, it runs `uvx ty check`
and feeds any type errors back to the LLM so it can fix them immediately.
"""

from core.extensions.api import ExtensionAPI
from core.events.hooks import HookStage


async def jarvis_extension(api: ExtensionAPI):
    """Register the auto type-check hook."""
    # Placeholder - implement AutoTypeCheckHook or remove this extension
    pass
