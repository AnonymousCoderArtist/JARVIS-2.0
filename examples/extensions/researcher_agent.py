"""Research agent — deep research with web search and documentation tools.

Converted from examples/agents/researcher.py to the extension API pattern.

Demonstrates using imported tool classes in the tools list.
"""

from jarvis.core.agents.agent_definition import AgentDefinition
from jarvis.core.agents.profiles import AgentType
from jarvis.core.tools.file_tools import FileReadTool, FindTool, LSTool
from jarvis.core.tools.grep_tool import GrepSearchTool
from jarvis.core.tools.web_tools import ExaWebSearchTool, WebFetchTool


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
        tools=[ExaWebSearchTool, WebFetchTool, FileReadTool, GrepSearchTool, FindTool, LSTool],
        model="inherit",
        max_turns=30,
        system_prompt=get_system_prompt,
    ))
