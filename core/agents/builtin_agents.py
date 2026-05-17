"""Built-in agent definitions for JARVIS

This module aggregates all built-in agent definitions from their respective modules.
"""

from __future__ import annotations

from core.agents.agent_definition import AgentDefinition
from core.agents.profiles import AgentType

# Import agent definitions from their modules
from .builtin.jarvis_help_agent import JARVIS_HELP_AGENT
from .builtin.rubber_duck_agent import RUBBER_DUCK_AGENT
from .builtin.statusline_setup_agent import STATUSLINE_SETUP_AGENT
from .builtin.verification_agent import VERIFICATION_AGENT

# Explore Agent - for codebase exploration and analysis
EXPLORE_AGENT = AgentDefinition(
    name='explore',
    agent_type=AgentType.SUBAGENT,
    description='''Use this agent for codebase exploration and analysis. It excels at:
- Understanding project structure and architecture
- Finding specific files, functions, or patterns
- Analyzing code dependencies and relationships
- Investigating technical implementation details
- Researching how specific features work''',
    tools=['read', 'ls', 'find', 'grep', 'bash(read-only)', 'web_search', 'fetch_webpage'],
    model='inherit',
)

# Plan Agent - for task decomposition and planning
PLAN_AGENT = AgentDefinition(
    name='plan',
    agent_type=AgentType.SUBAGENT,
    description='''Use this agent for task decomposition and planning. It excels at:
- Breaking down complex tasks into manageable steps
- Creating structured plans with phases and milestones
- Estimating effort and identifying dependencies
- Organizing work into logical sequences
- Creating detailed implementation roadmaps''',
    tools=['read', 'ls', 'find', 'grep', 'bash(read-only)', 'web_search', 'fetch_webpage'],
    model='inherit',
)

# General Purpose Agent - full capability agent
GENERAL_PURPOSE_AGENT = AgentDefinition(
    name='general-purpose',
    agent_type=AgentType.SUBAGENT,
    description='''Use this agent for complex, multi-step tasks requiring full capabilities. It:
- Has access to all tools
- Can perform file operations, bash commands, and web searches
- Handles complex coding tasks, debugging, and refactoring
- Manages background processes and long-running tasks
- Suitable for tasks that require extensive tool usage''',
    tools=['*'],
    model='inherit',
)

# Fork Agent - for parallel task execution
FORK_AGENT = AgentDefinition(
    name='fork',
    agent_type=AgentType.SUBAGENT,
    description='''Use this agent to delegate parallel or independent sub-tasks. It:
- Executes tasks in parallel without blocking the main agent
- Handles independent work that doesn't require main context
- Returns results when complete for main agent to review
- Useful for research, exploration, or background analysis tasks''',
    tools=['read', 'ls', 'find', 'grep', 'bash(read-only)', 'web_search', 'fetch_webpage'],
    model='inherit',
)


def get_builtin_agents() -> list[AgentDefinition]:
    """Get all built-in agent definitions.

    Returns:
        List of all AgentDefinition instances for built-in agents
    """
    return [
        EXPLORE_AGENT,
        PLAN_AGENT,
        GENERAL_PURPOSE_AGENT,
        FORK_AGENT,
        JARVIS_HELP_AGENT,
        STATUSLINE_SETUP_AGENT,
        VERIFICATION_AGENT,
        RUBBER_DUCK_AGENT,
    ]


def is_fork_subagent_enabled() -> bool:
    """Check if fork subagent functionality is enabled.

    Per design decision, fork subagents are always available.

    Returns:
        Always returns True
    """
    return True
