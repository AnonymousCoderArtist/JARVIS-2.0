"""Code reviewer agent — read-only review focused on security, bugs, and style.

Converted from examples/agents/code_reviewer.py to the extension API pattern.

Demonstrates using imported tool classes in the tools list.
"""

from core.agents.agent_definition import AgentDefinition
from core.agents.profiles import AgentType
from core.tools.file_tools import FileReadTool, FindTool, LSTool
from core.tools.grep_tool import GrepSearchTool


def get_system_prompt() -> str:
    return """You are a senior code reviewer. Your job is to analyze code and provide actionable feedback.

Focus areas (in priority order):
1. **Security vulnerabilities** — SQL injection, XSS, CSRF, hardcoded secrets, insecure defaults
2. **Logic bugs** — off-by-one errors, race conditions, unhandled edge cases, null pointer risks
3. **Performance issues** — N+1 queries, unnecessary allocations, inefficient algorithms
4. **Code quality** — unclear names, overly complex functions, missing error handling
5. **Style and conventions** — formatting, import order, type annotations

Rules:
- Be specific: cite file paths and line numbers
- Suggest concrete fixes, not just "this is bad"
- Distinguish between critical issues and style preferences
- If the code is clean, say so — don't invent problems
"""


async def jarvis(api):
    """Register the code reviewer agent."""
    api.agents(AgentDefinition(
        name="code-review",
        agent_type=AgentType.SUBAGENT,
        description="Review code for security vulnerabilities, logic bugs, performance issues, and style problems. Use when the user asks to review, audit, or critique code.",
        tools=[FileReadTool, GrepSearchTool, FindTool, LSTool],
        model="inherit",
        max_turns=50,
        system_prompt=get_system_prompt,
    ))
