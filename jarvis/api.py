"""Public API for JARVIS extensions.

All extension development should import from this module.  Extension files
placed in ``.jarvis/extensions/`` or ``~/.jarvis/extensions/`` receive an
``ExtensionAPI`` instance and can register tools, hooks, commands, shortcuts,
and custom agents.

Basic usage::

    from jarvis.api import ExtensionAPI, BaseTool, ToolInput, ToolOutput

    async def jarvis(api: ExtensionAPI):
        class MyTool(BaseTool):
            name = "my_tool"
            description = "Does something useful"
            input_schema = {"type": "object", "properties": {}}

            async def execute(self, input_data: ToolInput) -> ToolOutput:
                return ToolOutput(success=True, result="done")

        api.tools(MyTool())
"""

from __future__ import annotations

# ── Extension System ──────────────────────────────────────────────
from jarvis.core.extensions.api import ExtensionAPI
from jarvis.core.extensions.loader import (
    discover_and_load_all,
    discover_extension_paths,
    load_from_directory,
    load_from_file,
)
from jarvis.core.extensions.registry import ExtensionRegistry
from jarvis.core.extensions.runner import ExtensionRunner
from jarvis.core.extensions.types import ExtensionContext, ExtensionManifest

# ── Tool System ───────────────────────────────────────────────────
from jarvis.core.tools.base import BaseTool, ToolInput, ToolOutput
from jarvis.core.tools.registry import ToolRegistry

# ── Agent System ──────────────────────────────────────────────────
from jarvis.core.agents.agent_definition import AgentDefinition
from jarvis.core.agents.profiles import AgentProfile, AgentSafety, AgentType

# ── Built-in Agent Profiles ───────────────────────────────────────
from jarvis.core.agents.builtin_profiles import (
    ACCEPT_EDITS,
    AGENT_ORDER,
    AUTO_APPROVE,
    BUILTIN_AGENTS,
    DEFAULT,
    EXPLORE,
    PLAN,
)

# ── Event & Hook System ───────────────────────────────────────────
from jarvis.core.events.bus import EventBus
from jarvis.core.events.hooks import HookContext, HookRegistry, HookResult, HookStage
from jarvis.core.events.types import (
    # Agent lifecycle
    AgentEnded,
    AgentError,
    AgentEvent,
    AgentStarted,
    # Extension lifecycle
    ExtensionError,
    ExtensionEvent,
    ExtensionLoaded,
    ExtensionUnloaded,
    # Message streaming
    MessageComplete,
    MessageDelta,
    MessageEvent,
    ThinkingDelta,
    # Progress
    ProgressEvent,
    ProgressUpdated,
    # Session lifecycle
    SessionEvent,
    SessionShutdown,
    SessionStarted,
    SkillActivated,
    SkillDeactivated,
    # Status
    StatusEvent,
    StatusUpdated,
    # System
    SystemEvent,
    SystemWarning,
    # Tool execution
    ToolCallEnded,
    ToolCallError,
    ToolCallStarted,
    ToolEvent,
    # Turn lifecycle
    TurnEnded,
    TurnEvent,
    TurnStarted,
)

# ── Public API ────────────────────────────────────────────────────
__all__: list[str] = [
    # Extension system
    "ExtensionAPI",
    "ExtensionManifest",
    "ExtensionContext",
    "ExtensionRegistry",
    "ExtensionRunner",
    "discover_extension_paths",
    "load_from_file",
    "load_from_directory",
    "discover_and_load_all",
    # Tool system
    "BaseTool",
    "ToolInput",
    "ToolOutput",
    "ToolRegistry",
    # Agent system
    "AgentDefinition",
    "AgentType",
    "AgentSafety",
    "AgentProfile",
    # Built-in profiles
    "DEFAULT",
    "PLAN",
    "ACCEPT_EDITS",
    "AUTO_APPROVE",
    "EXPLORE",
    "BUILTIN_AGENTS",
    "AGENT_ORDER",
    # Event & hook system
    "HookStage",
    "HookContext",
    "HookResult",
    "HookRegistry",
    "EventBus",
    # Event types — agent lifecycle
    "AgentEvent",
    "AgentStarted",
    "AgentEnded",
    "AgentError",
    # Event types — turn lifecycle
    "TurnEvent",
    "TurnStarted",
    "TurnEnded",
    # Event types — message streaming
    "MessageEvent",
    "MessageDelta",
    "MessageComplete",
    "ThinkingDelta",
    # Event types — tool execution
    "ToolEvent",
    "ToolCallStarted",
    "ToolCallEnded",
    "ToolCallError",
    # Event types — session lifecycle
    "SessionEvent",
    "SessionStarted",
    "SessionShutdown",
    "SkillActivated",
    "SkillDeactivated",
    # Event types — extension lifecycle
    "ExtensionEvent",
    "ExtensionLoaded",
    "ExtensionUnloaded",
    "ExtensionError",
    # Event types — status & progress
    "StatusEvent",
    "StatusUpdated",
    "ProgressEvent",
    "ProgressUpdated",
    # Event types — system
    "SystemEvent",
    "SystemWarning",
]
