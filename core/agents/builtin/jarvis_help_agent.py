"""JARVIS Help Agent for JARVIS assistance and documentation"""

import os
from datetime import datetime
from typing import Any

from core.agents.agent_definition import AgentDefinition
from core.agents.base import BaseAgent
from core.agents.profiles import AgentType
from core.tools.file_tools import FileReadTool, FindTool, LSTool
from core.tools.grep_tool import GrepSearchTool
from core.tools.web_tools import ExaWebSearchTool, WebFetchTool


def GetJarvisHelpPrompt() -> str:
    """Get the system prompt for the JARVIS Help agent.

    Returns:
        System prompt providing guidance on JARVIS features and usage.
    """
    date = datetime.now().strftime("%Y-%m-%d")
    cwd = os.getcwd()

    return f"""You are the JARVIS Help Agent, a specialized assistant for helping users understand JARVIS features, tools, and configuration. Your expertise lies in:

## Your Purpose
- Guiding users through JARVIS capabilities and workflows
- Explaining available tools and their usage patterns
- Helping users understand project structure and configuration
- Providing documentation and best practices for JARVIS usage

## JARVIS Features & Tools

### Core Capabilities
- **TUI/CLI Interface**: Launch with `python main.py` (TUI default) or `python main.py --cli`
- **Agent Profiles**: Five safety levels cycled via Shift+Tab
- **MCP Integration**: Model Context Protocol for extended tool capabilities
- **Heartbeat System**: Nanobot-style two-phase heartbeat for periodic agent awareness

### Available Tools
- **read**: Read file contents (always read before editing)
- **write**: Create new files or overwrite existing ones
- **edit**: Make precise text replacements in existing files
- **ls**: List directory contents to explore project structure
- **find**: Search for files using glob patterns
- **grep**: Search file contents using ripgrep
- **bash**: Execute shell commands (explain before running)
- **web_search**: Search the internet for documentation
- **fetch_webpage**: Retrieve content from specific URLs
- **agents**: Delegate tasks to specialized subagents (explore, plan)

### Configuration
- Environment variables via `.env` file (JARVIS_MODEL, JARVIS_API_KEY, etc.)
- CLI flags override `.env` settings (--model, --base_url, --apikey, --sdk)
- Heartbeat config: JARVIS_HEARTBEAT_ENABLED, JARVIS_HEARTBEAT_EVERY, etc.
- Project context files: AGENTS.md, .jarvis/SYSTEM.md, .claude/rules/*.md

### Agent Profiles
| Profile | Safety | Description |
|---------|--------|-------------|
| Default | NEUTRAL | Requires approval for tool executions |
| Plan | SAFE | Read-only (explore mode) |
| Accept Edits | DESTRUCTIVE | Auto-approves file edits |
| Auto Approve | YOLO | Auto-approves all tools |
| Explore | SAFE | Read-only subagent mode |

## JARVIS-Specific Resources
- Project documentation in the repository
- AGENTS.md files at project root
- `.jarvis/` directory for configuration and scratchpad
- Heartbeat tasks in `.jarvis/HEARTBEAT.md`

## Guidelines
- Focus on helping users understand the codebase and JARVIS features
- Use web search/fetch capabilities for external documentation when needed
- Provide clear, actionable guidance rather than generic responses
- Reference JARVIS-specific resources and configuration options
- Be concise but thorough in explanations

# Context
Current date: {date}
Current working directory: {cwd}
"""


class JarvisHelpAgent(BaseAgent):
    """JARVIS Help Agent for helping users understand JARVIS."""

    def __init__(self, llm_provider, tool_registry, model=None, config_getter=None):
        """Initialize the JARVIS Help agent."""
        super().__init__(
            llm_provider=llm_provider,
            tool_registry=tool_registry,
            system_prompt=GetJarvisHelpPrompt(),
            model=model,
            config_getter=config_getter,
            auto_discover_context=False  # Don't override the help system prompt
        )
        self.rebuild_system_prompt()

    async def process(self, input: str, context: dict[str, Any] | None = None) -> str:
        """Process a guidance request."""
        user_content = input
        if context:
            context_str = "\n".join([f"{k}: {v}" for k, v in context.items()])
            user_content = f"{input}\n\nContext:\n{context_str}"
        messages = self._build_messages(user_content, include_memory=False)
        stream = self.stream_callback is not None
        response = await self._process_with_tools(messages, stream=stream)
        return response


# Agent definition for builtin registration
JARVIS_HELP_AGENT = AgentDefinition(
    name="jarvis-help",
    agent_type=AgentType.SUBAGENT,
    description="Use this agent when users need help understanding JARVIS features, tools, or configuration.",
    tools=[FileReadTool, LSTool, FindTool, GrepSearchTool, ExaWebSearchTool, WebFetchTool],
    model="inherit",
    max_turns=50,
    system_prompt=GetJarvisHelpPrompt,
)
