"""System prompts manager for JARVIS agent.

This module maintains backward compatibility by re-exporting from the new
modular prompts package. The actual prompt implementations have been moved
to core/agents/prompts/ for better organization and maintainability.

For new code, prefer importing directly from jarvis.core.agents.prompts.
"""

# Re-export everything from the new modular prompts package
# This maintains backward compatibility with existing code
from jarvis.core.agents.prompts import *  # noqa: F401, F403

# Also expose the original function name for backward compatibility
# (already re-exported as enhanceSystemPromptWithEnvDetails in __init__.py)

__all__ = [
    # From constants
    "FORK_PROMPT_MARKER",
    "DEFAULT_EMOJI_MAP",
    "get_system_context",
    "discover_context_files",
    "get_base_context",
    "get_platform_info",
    "enhance_prompt_with_env_details",
    "enhanceSystemPromptWithEnvDetails",
    # From prompt_utils
    "build_context_section",
    "build_agent_header",
    "read_context_files",
    "format_tool_list",
    "get_project_root",
    # From jarvis_v2
    "get_jarvis_v2_tools",
    "get_jarvis_v2_guidelines",
    "build_jarvis_v2_system_prompt",
    "JARVIS_V2_SYSTEM_PROMPT",
    "get_jarvis_v2_metadata",
    # From explore
    "get_explore_prompt",
    "EXPLORE_SYSTEM_PROMPT",
    "get_explore_metadata",
    # From plan
    "get_plan_prompt",
    "PLAN_SYSTEM_PROMPT",
    "get_plan_metadata",
    # From verification
    "get_verification_prompt",
    "VERIFICATION_SYSTEM_PROMPT",
    "get_verification_metadata",
    # From rubber-duck
    "get_rubber_duck_prompt",
    "RUBBER_DUCK_SYSTEM_PROMPT",
    "get_rubber_duck_metadata",
    # Other agents
    "get_jarvis_help_prompt",
    "get_statusline_prompt",
    # General purpose
    "GENERAL_PURPOSE_SYSTEM_PROMPT",
    "FORK_SYSTEM_PROMPT",
    # Metadata class
    "AgentPromptMetadata",
    # Main API functions
    "get_agent_prompt",
    "get_agent_metadata",
    "get_enhanced_prompt",
    "AGENT_PROMPTS",
]
