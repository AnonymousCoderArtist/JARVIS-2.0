"""Backward-compatible agent tool module.

This module re-exports from the new modular agent package for backward compatibility.
"""

# Re-export all public symbols from the new modular package
from jarvis.core.tools.agent.agent_lifecycle import _run_agent_in_background
from jarvis.core.tools.agent.agent_memory import (
    SubagentActivity,
    add_subagent_activity,
    clear_subagent_activities,
    get_subagent_activities,
)
from jarvis.core.tools.agent.agent_tool import AgentsTool, AgentTool
from jarvis.core.tools.agent.background_task import (
    BackgroundAgentTask,
    list_background_agents,
)
from jarvis.core.tools.agent.constants import (
    AGENT_TOOL_NAME,
    DEFAULT_MAX_TOKENS,
    EXPLORE_ALLOWED_TOOLS,
    JARVIS_HELP_ALLOWED_TOOLS,
    ONE_SHOT_BUILTIN_AGENT_TYPES,
    PLAN_ALLOWED_TOOLS,
    STATUSLINE_SETUP_ALLOWED_TOOLS,
    VERIFICATION_ALLOWED_TOOLS,
)
from jarvis.core.tools.agent.filtered_registry import _FilteredToolRegistry
from jarvis.core.tools.agent.utils import get_agent_param

__all__ = [
    "AgentTool",
    "AgentsTool",
    "BackgroundAgentTask",
    "SubagentActivity",
    "get_agent_param",
    "list_background_agents",
    "add_subagent_activity",
    "get_subagent_activities",
    "clear_subagent_activities",
    "AGENT_TOOL_NAME",
    "ONE_SHOT_BUILTIN_AGENT_TYPES",
    "EXPLORE_ALLOWED_TOOLS",
    "PLAN_ALLOWED_TOOLS",
    "JARVIS_HELP_ALLOWED_TOOLS",
    "VERIFICATION_ALLOWED_TOOLS",
    "STATUSLINE_SETUP_ALLOWED_TOOLS",
    "DEFAULT_MAX_TOKENS",
    "_run_agent_in_background",
    "_FilteredToolRegistry",
]
