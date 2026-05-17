"""JARVIS AI Assistant — A next-generation agentic harness.

Import paths::

    from jarvis.api import ExtensionAPI, BaseTool, ToolInput, ToolOutput
    from jarvis.core.tools import BashTool, FileReadTool, GrepSearchTool
    from jarvis.core.agents import JarvisV2, AgentDefinition, AgentType
    from jarvis.core.events import EventBus, HookStage, ToolCallStarted
    from jarvis.core.config import get_settings, JarvisSettings
"""

from jarvis import api
from jarvis._version import __version__

__all__ = ["__version__", "api"]
