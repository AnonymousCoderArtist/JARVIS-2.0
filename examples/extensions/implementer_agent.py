"""Implementer agent — full-stack implementation with all tools.

Converted from examples/agents/implementer.py to the extension API pattern.
"""

from jarvis.core.agents.agent_definition import AgentDefinition
from jarvis.core.agents.profiles import AgentType


def get_system_prompt() -> str:
    return """You are a senior software engineer. Your job is to implement features, fix bugs, and refactor code.

Guidelines:
- Read existing code before making changes to understand patterns and conventions
- Write clean, maintainable code that follows the project's style
- Test your changes when possible
- Make minimal, focused changes — don't refactor unrelated code
- Explain what you're doing and why
"""


async def jarvis(api):
    """Register the implementer agent."""
    api.agents(AgentDefinition(
        name="implementer",
        agent_type=AgentType.AGENT,
        description="Implement features, fix bugs, refactor code, and make code changes. Use when the user asks to build, create, fix, or modify code.",
        tools=["*"],
        model="inherit",
        max_turns=100,
        system_prompt=get_system_prompt,
    ))
