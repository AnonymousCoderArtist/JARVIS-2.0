"""Built-in agent definitions for JARVIS

This module defines standardized agent configurations that can be used
for subagent invocation and agent management.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable


@dataclass
class AgentDefinition:
    """Definition of a built-in agent with its configuration.

    Attributes:
        agent_type: Type identifier for the agent (e.g., 'explore', 'plan')
        when_to_use: Description of when this agent should be used
        tools: List of allowed tools (None means inherit parent's tools)
        disallowed_tools: List of explicitly disallowed tools
        model: Model to use ('inherit' for parent's model, or specific model name)
        max_turns: Maximum number of turns for the agent
        get_system_prompt: Optional callable to get the system prompt
        source: Source of the agent definition ('built-in' or custom path)
        base_dir: Base directory for the agent ('built-in' or custom path)
    """
    agent_type: str
    when_to_use: str
    tools: list[str] | None = None
    disallowed_tools: list[str] = field(default_factory=list)
    model: str | None = None
    max_turns: int = 100
    get_system_prompt: Callable[[], str] | None = None
    source: str = 'built-in'
    base_dir: str = 'built-in'


# Explore Agent - for codebase exploration and analysis
EXPLORE_AGENT = AgentDefinition(
    agent_type='explore',
    when_to_use='''Use this agent for codebase exploration and analysis. It excels at:
- Understanding project structure and architecture
- Finding specific files, functions, or patterns
- Analyzing code dependencies and relationships
- Investigating technical implementation details
- Researching how specific features work''',
    tools=['read', 'ls', 'find', 'grep', 'bash(read-only)', 'web_search', 'fetch_webpage'],
    disallowed_tools=['write', 'edit', 'bash(modifying)'],
    model='inherit',
)

# Plan Agent - for task decomposition and planning
PLAN_AGENT = AgentDefinition(
    agent_type='plan',
    when_to_use='''Use this agent for task decomposition and planning. It excels at:
- Breaking down complex tasks into manageable steps
- Creating structured plans with phases and milestones
- Estimating effort and identifying dependencies
- Organizing work into logical sequences
- Creating detailed implementation roadmaps''',
    tools=['read', 'ls', 'find', 'grep', 'bash(read-only)', 'web_search', 'fetch_webpage'],
    disallowed_tools=['write', 'edit', 'bash(modifying)'],
    model='inherit',
)

# General Purpose Agent - full capability agent
GENERAL_PURPOSE_AGENT = AgentDefinition(
    agent_type='general-purpose',
    when_to_use='''Use this agent for complex, multi-step tasks requiring full capabilities. It:
- Has access to all tools
- Can perform file operations, bash commands, and web searches
- Handles complex coding tasks, debugging, and refactoring
- Manages background processes and long-running tasks
- Suitable for tasks that require extensive tool usage''',
    tools=['*'],
    disallowed_tools=[],
    model='inherit',
)

# Fork Agent - for parallel task execution
FORK_AGENT = AgentDefinition(
    agent_type='fork',
    when_to_use='''Use this agent to delegate parallel or independent sub-tasks. It:
- Executes tasks in parallel without blocking the main agent
- Handles independent work that doesn't require main context
- Returns results when complete for main agent to review
- Useful for research, exploration, or background analysis tasks''',
    tools=['read', 'ls', 'find', 'grep', 'bash(read-only)', 'web_search', 'fetch_webpage'],
    disallowed_tools=['write', 'edit', 'bash(modifying)'],
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
    ]


def is_fork_subagent_enabled() -> bool:
    """Check if fork subagent functionality is enabled.

    Per design decision, fork subagents are always available.

    Returns:
        Always returns True
    """
    return True