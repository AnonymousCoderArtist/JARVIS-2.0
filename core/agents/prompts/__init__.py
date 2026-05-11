"""JARVIS Agent Prompts Module.

This package provides modular system prompts for all JARVIS agents.
It maintains backward compatibility with the original system_prompts.py module.

Usage:
    from core.agents.prompts import get_agent_prompt, get_jarvis_v2_prompt

    prompt = get_agent_prompt("jarvis")
    explore_prompt = get_agent_prompt("explore")
"""

import os
from dataclasses import dataclass
from typing import Dict, Optional

# Import constants
from .constants import (
    DEFAULT_EMOJI_MAP,
    FORK_PROMPT_MARKER,
    discover_context_files,
    enhance_prompt_with_env_details,
    get_base_context,
    get_platform_info,
    get_system_context,
)

# Import Explore agent prompts
from .explore import (
    EXPLORE_SYSTEM_PROMPT,
    get_explore_metadata,
    get_explore_prompt,
)

# Import JARVIS v2 prompts
from .jarvis_v2 import (
    JARVIS_V2_SYSTEM_PROMPT,
    build_jarvis_v2_system_prompt,
    get_jarvis_v2_guidelines,
    get_jarvis_v2_metadata,
    get_jarvis_v2_tools,
)

# Import Plan agent prompts
from .plan import (
    PLAN_SYSTEM_PROMPT,
    get_plan_metadata,
    get_plan_prompt,
)

# Import prompt utilities
from .prompt_utils import (
    build_agent_header,
    build_context_section,
    format_tool_list,
    get_project_root,
    read_context_files,
)

# Import Verification agent prompts
from .verification import (
    VERIFICATION_SYSTEM_PROMPT,
    get_verification_metadata,
    get_verification_prompt,
)


@dataclass
class AgentPromptMetadata:
    """Metadata for agent prompts.

    Attributes:
        agent_type: Type of agent (main, subagent).
        when_to_use: Description of when to use this agent.
        model: Model to use (default, inherit, or specific model name).
        max_turns: Maximum number of turns for the agent.
    """
    agent_type: str
    when_to_use: str
    model: str = "default"
    max_turns: int = 100


# General purpose prompts (built-in functions preserved from original)
def _build_general_purpose_prompt() -> str:
    """Build the general-purpose agent prompt."""
    from datetime import datetime
    date = datetime.now().strftime("%Y-%m-%d")
    cwd = os.getcwd()
    return f"""You are a General Purpose Agent with full tool capabilities.

Available tools: read, write, edit, ls, find, grep, bash, web_search, fetch_webpage, agents

Guidelines:
- Handle complex multi-step tasks
- Use tools proactively
- Be thorough and methodical

Current date: {date}
Current working directory: {cwd}
"""


def _build_fork_prompt() -> str:
    """Build the fork agent prompt."""
    from datetime import datetime
    date = datetime.now().strftime("%Y-%m-%d")
    cwd = os.getcwd()
    return f"""You are a Fork Agent for parallel task execution.

Purpose: Execute independent sub-tasks in parallel without blocking the main agent.

Guidelines:
- Work independently without main context
- Return results for main agent to review
- Good for research, exploration, background analysis

Current date: {date}
Current working directory: {cwd}
"""


# Build prompts that don't need lazy loading
GENERAL_PURPOSE_SYSTEM_PROMPT = _build_general_purpose_prompt()
FORK_SYSTEM_PROMPT = _build_fork_prompt()

# Lazy-loaded prompts for builtin agents (initialized on first access)
_BUILTIN_PROMPTS_LOADED = False
_BUILTIN_PROMPTS: dict[str, str] = {}


def _load_builtin_prompts() -> None:
    """Load builtin agent prompts lazily to avoid circular imports."""
    global _BUILTIN_PROMPTS_LOADED, _BUILTIN_PROMPTS
    if not _BUILTIN_PROMPTS_LOADED:
        try:
            from core.agents.builtin.jarvis_help_agent import GetJarvisHelpPrompt
            from core.agents.builtin.statusline_setup_agent import GetStatuslineSetupPrompt

            _BUILTIN_PROMPTS['jarvis-help'] = GetJarvisHelpPrompt()
            _BUILTIN_PROMPTS['statusline-setup'] = GetStatuslineSetupPrompt()
        except ImportError:
            # Fallback to inline prompts if builtin module not available
            _BUILTIN_PROMPTS['jarvis-help'] = _build_jarvis_help_prompt()
            _BUILTIN_PROMPTS['statusline-setup'] = _build_statusline_prompt()
        _BUILTIN_PROMPTS_LOADED = True


def _build_jarvis_help_prompt() -> str:
    """Build the JARVIS help agent prompt (fallback)."""
    from datetime import datetime
    date = datetime.now().strftime("%Y-%m-%d")
    cwd = os.getcwd()
    return f"""You are the JARVIS Help Agent, helping users understand JARVIS features, tools, and configuration.

JARVIS Features & Tools:
- TUI/CLI Interface, Agent Profiles, MCP Integration, Heartbeat System
- Tools: read, write, edit, ls, find, grep, bash, web_search, fetch_webpage, agents

Guidelines:
- Focus on helping users understand the codebase and JARVIS features
- Provide clear, actionable guidance
- Reference JARVIS-specific resources

Current date: {date}
Current working directory: {cwd}
"""


def _build_statusline_prompt() -> str:
    """Build the statusline setup agent prompt (fallback)."""
    from datetime import datetime
    date = datetime.now().strftime("%Y-%m-%d")
    cwd = os.getcwd()
    return f"""You are a statusline customization specialist for shell prompts.

Frameworks: Oh My Zsh, Starship, Bash-it, Oh My Posh, PowerShell

Guidelines:
- Provide guidance only, don't modify files
- Include PowerShell support
- Focus on the user's specific shell and use case

Current date: {date}
Current working directory: {cwd}
"""


# Prompt functions for jarvis-help and statusline (delegating to builtin agents)
def get_jarvis_help_prompt() -> str:
    """Get the JARVIS help system prompt.

    Returns:
        System prompt for the JARVIS help agent.
    """
    _load_builtin_prompts()
    return _BUILTIN_PROMPTS.get('jarvis-help', _build_jarvis_help_prompt())


def get_statusline_prompt() -> str:
    """Get the statusline setup system prompt.

    Returns:
        System prompt for the statusline setup agent.
    """
    _load_builtin_prompts()
    return _BUILTIN_PROMPTS.get('statusline-setup', _build_statusline_prompt())


# Runtime loaded prompts (initialized by _init_prompts)
_RUNTIME_EXPLORE_PROMPT = None
_RUNTIME_PLAN_PROMPT = None
_RUNTIME_JARVIS_HELP_PROMPT = None
_RUNTIME_STATUSLINE_PROMPT = None
_RUNTIME_VERIFICATION_PROMPT = None


def _init_prompts() -> None:
    """Initialize prompts by calling lazy load functions."""
    global _RUNTIME_EXPLORE_PROMPT, _RUNTIME_PLAN_PROMPT, _RUNTIME_JARVIS_HELP_PROMPT
    global _RUNTIME_STATUSLINE_PROMPT, _RUNTIME_VERIFICATION_PROMPT

    if _RUNTIME_EXPLORE_PROMPT is None:
        _RUNTIME_EXPLORE_PROMPT = get_explore_prompt()
    if _RUNTIME_PLAN_PROMPT is None:
        _RUNTIME_PLAN_PROMPT = get_plan_prompt()
    if _RUNTIME_VERIFICATION_PROMPT is None:
        _RUNTIME_VERIFICATION_PROMPT = get_verification_prompt()
    # Load builtin prompts lazily
    _load_builtin_prompts()
    if _RUNTIME_JARVIS_HELP_PROMPT is None:
        _RUNTIME_JARVIS_HELP_PROMPT = _BUILTIN_PROMPTS.get('jarvis-help', '')
    if _RUNTIME_STATUSLINE_PROMPT is None:
        _RUNTIME_STATUSLINE_PROMPT = _BUILTIN_PROMPTS.get('statusline-setup', '')


# Agent prompts registry
AGENT_PROMPTS: dict[str, tuple[str, AgentPromptMetadata]] = {
    "jarvis": (
        JARVIS_V2_SYSTEM_PROMPT,
        AgentPromptMetadata(agent_type="main", when_to_use="Use for general coding tasks.", model="inherit", max_turns=100),
    ),
    "explore": (
        EXPLORE_SYSTEM_PROMPT,
        AgentPromptMetadata(agent_type="subagent", when_to_use="Use for codebase exploration.", model="default", max_turns=50),
    ),
    "plan": (
        PLAN_SYSTEM_PROMPT,
        AgentPromptMetadata(agent_type="subagent", when_to_use="Use for task planning.", model="default", max_turns=50),
    ),
    "jarvis-help": (
        "Loading...",
        AgentPromptMetadata(agent_type="subagent", when_to_use="Use for JARVIS help.", model="inherit", max_turns=50),
    ),
    "statusline-setup": (
        "Loading...",
        AgentPromptMetadata(agent_type="subagent", when_to_use="Use for prompt setup.", model="inherit", max_turns=50),
    ),
    "verification": (
        VERIFICATION_SYSTEM_PROMPT,
        AgentPromptMetadata(agent_type="subagent", when_to_use="Use for verification.", model="inherit", max_turns=10),
    ),
    "general-purpose": (
        GENERAL_PURPOSE_SYSTEM_PROMPT,
        AgentPromptMetadata(agent_type="subagent", when_to_use="Use for complex multi-step tasks.", model="inherit", max_turns=100),
    ),
    "fork": (
        FORK_SYSTEM_PROMPT,
        AgentPromptMetadata(agent_type="subagent", when_to_use="Use for parallel task execution.", model="inherit", max_turns=50),
    ),
}


def get_agent_prompt(agent_name: str) -> str:
    """Get the system prompt for a named agent (lazy loads prompts).

    Args:
        agent_name: Name of the agent (jarvis, explore, plan, verification, etc.)

    Returns:
        System prompt for the specified agent.
    """
    _init_prompts()
    prompts = {
        'jarvis': JARVIS_V2_SYSTEM_PROMPT,
        'explore': _RUNTIME_EXPLORE_PROMPT,
        'plan': _RUNTIME_PLAN_PROMPT,
        'jarvis-help': _RUNTIME_JARVIS_HELP_PROMPT,
        'statusline-setup': _RUNTIME_STATUSLINE_PROMPT,
        'verification': _RUNTIME_VERIFICATION_PROMPT,
        'general-purpose': GENERAL_PURPOSE_SYSTEM_PROMPT,
        'fork': FORK_SYSTEM_PROMPT,
    }
    return prompts.get(agent_name) or JARVIS_V2_SYSTEM_PROMPT


def get_agent_metadata(agent_name: str) -> AgentPromptMetadata | None:
    """Get the metadata for a named agent.

    Args:
        agent_name: Name of the agent.

    Returns:
        AgentPromptMetadata for the agent, or None if not found.
    """
    return AGENT_PROMPTS.get(agent_name, (None, None))[1] if agent_name in AGENT_PROMPTS else None


def get_enhanced_prompt(agent_name: str, emoji: str | None = None) -> str:
    """Get an enhanced system prompt with environment details.

    Args:
        agent_name: Name of the agent.
        emoji: Optional emoji override for the agent.

    Returns:
        Enhanced system prompt with environment details appended.
    """
    prompt = get_agent_prompt(agent_name)
    emoji_map = {
        "jarvis": "🤖", "explore": "🔍", "plan": "📋", "jarvis-help": "❓",
        "statusline-setup": "💻", "verification": "✅", "general-purpose": "⚡", "fork": "🍴",
    }
    return enhance_prompt_with_env_details(prompt, agent_name, emoji or emoji_map.get(agent_name, "🤖"))


# Re-export original function names for backward compatibility
enhanceSystemPromptWithEnvDetails = enhance_prompt_with_env_details

__all__ = [
    # Constants
    "FORK_PROMPT_MARKER",
    "DEFAULT_EMOJI_MAP",
    # Utility functions
    "get_system_context",
    "discover_context_files",
    "get_base_context",
    "get_platform_info",
    "enhance_prompt_with_env_details",
    "enhanceSystemPromptWithEnvDetails",
    # Prompt utilities
    "build_context_section",
    "build_agent_header",
    "read_context_files",
    "format_tool_list",
    "get_project_root",
    # JARVIS v2
    "get_jarvis_v2_tools",
    "get_jarvis_v2_guidelines",
    "build_jarvis_v2_system_prompt",
    "JARVIS_V2_SYSTEM_PROMPT",
    "get_jarvis_v2_metadata",
    # Explore agent
    "get_explore_prompt",
    "EXPLORE_SYSTEM_PROMPT",
    "get_explore_metadata",
    # Plan agent
    "get_plan_prompt",
    "PLAN_SYSTEM_PROMPT",
    "get_plan_metadata",
    # Verification agent
    "get_verification_prompt",
    "VERIFICATION_SYSTEM_PROMPT",
    "get_verification_metadata",
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
