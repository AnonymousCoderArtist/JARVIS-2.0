"""Research agent — deep research with web search and documentation tools.

Converted from examples/agents/researcher.py to the extension API pattern.
"""

from core.agents.agent_definition import AgentDefinition
from core.agents.profiles import AgentType


def get_system_prompt() -> str:
    return """You are a research assistant. Your job is to find accurate, up-to-date information.

Guidelines:
- Use web search to find current information, not just your training data
- Cross-reference multiple sources when possible
- Cite your sources with URLs
- Distinguish between facts, opinions, and speculation
- If you can't find a definitive answer, say so
- Summarize findings in a clear, structured format
"""


async def jarvis(api):
    """Register the researcher agent."""
    api.agents(AgentDefinition(
        name="researcher",
        agent_type=AgentType.SUBAGENT,
        description="Deep research on technical topics, APIs, libraries, frameworks, or any topic requiring web search and documentation lookup. Use when the user asks to research, investigate, or find information.",
        tools=["web_search", "fetch_webpage", "read", "grep", "find", "ls"],
        model="inherit",
        max_turns=30,
        system_prompt=get_system_prompt,
    ))
