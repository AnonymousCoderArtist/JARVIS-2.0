"""Agent definition dataclass for JARVIS built-in agents.

This module contains only the AgentDefinition dataclass to avoid circular imports.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from core.agents.profiles import AgentType


@dataclass
class AgentDefinition:
    """Definition of a built-in agent with its configuration.

    Attributes:
        name: Unique identifier for the agent (e.g., 'explore', 'plan')
        when_to_use: Description of when this agent should be used
        tools: List of allowed tool names.
               None (default) = inherit all tools from parent agent.
               ["*"] = explicitly allow all tools.
               ["read", "grep"] = restrict to only these tools.
        model: Model to use ('inherit' for parent's model, or specific model name)
        max_turns: Maximum number of turns for the agent
        agent_type: Whether this is an AGENT (appears in profiles + agents tool)
                    or SUBAGENT (only invocable via agents tool)
        get_system_prompt: Optional callable to get the system prompt
        source: Source of the agent definition ('built-in' or custom path)
        base_dir: Base directory for the agent ('built-in' or custom path)
    """
    name: str
    when_to_use: str
    tools: list[str] | None = None
    model: str | None = None
    max_turns: int = 100
    agent_type: AgentType = AgentType.AGENT
    get_system_prompt: Callable[[], str] | None = None
    source: str = 'built-in'
    base_dir: str = 'built-in'
