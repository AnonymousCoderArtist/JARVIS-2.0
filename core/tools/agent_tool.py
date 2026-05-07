"""Backward-compatible agent tool module.

This module re-exports from the new modular agent package for backward compatibility.
"""

# Re-export all public symbols from the new modular package
from core.tools.agent.agent_tool import AgentTool, AgentsTool, AgentStatusTool
from core.tools.agent.background_task import (
    BackgroundAgentTask,
    get_background_agent,
    list_background_agents,
    get_completed_background_agents,
    clear_completed_background_agents,
    _background_agents,
    _background_lock,
)
from core.tools.agent.agent_memory import (
    SubagentActivity,
    add_subagent_activity,
    get_subagent_activities,
    clear_subagent_activities,
)
from core.tools.agent.utils import get_agent_param
from core.tools.agent.constants import (
    AGENT_TOOL_NAME,
    ONE_SHOT_BUILTIN_AGENT_TYPES,
    EXPLORE_ALLOWED_TOOLS,
    PLAN_ALLOWED_TOOLS,
    JARVIS_HELP_ALLOWED_TOOLS,
    VERIFICATION_ALLOWED_TOOLS,
    STATUSLINE_SETUP_ALLOWED_TOOLS,
    DEFAULT_MAX_TOKENS,
)
from core.tools.agent.agent_lifecycle import _run_agent_in_background
from core.tools.agent.filtered_registry import _FilteredToolRegistry

__all__ = [
    "AgentTool",
    "AgentsTool", 
    "AgentStatusTool",
    "BackgroundAgentTask",
    "SubagentActivity",
    "get_agent_param",
    "get_background_agent",
    "list_background_agents",
    "get_completed_background_agents",
    "clear_completed_background_agents",
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
