"""Agent definition dataclass for JARVIS built-in agents.

This module contains only the AgentDefinition dataclass to avoid circular imports.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field


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
