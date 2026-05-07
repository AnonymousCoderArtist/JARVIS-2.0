"""System prompts manager for JARVIS agent

This module manages agent system prompts by importing them from their respective
builtin agent modules. It provides a registry and utility functions for
prompt management.
"""

import os
import platform
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

# Fork detection marker
FORK_PROMPT_MARKER = " FORK:"


def get_system_context() -> str:
    """Get system context for the main agent."""
    cwd = os.getcwd()
    return f"## System Information\n- **Working Directory**: {cwd}\n"


@dataclass
class AgentPromptMetadata:
    """Metadata for agent prompts."""
    agent_type: str
    when_to_use: str
    model: str = "default"
    max_turns: int = 100


def enhanceSystemPromptWithEnvDetails(prompt: str, agent_name: str = "jarvis", emoji: str = "🤖") -> str:
    """Enhance system prompt with environment details for agent identification."""
    cwd = Path.cwd()
    project_root = cwd
    while project_root.parent != project_root and not (project_root / ".git").exists():
        project_root = project_root.parent

    context_lines = [
        f"\n\n---\n",
        f"# Agent Environment Details",
        f"- **Emoji**: {emoji}",
        f"- **Agent Name**: {agent_name}",
        f"- **Working Directory**: {cwd}",
        f"- **Project Root**: {project_root}",
        f"- **OS**: {platform.system()} {platform.release()}",
        f"- **Python**: {sys.version.split()[0]}",
        f"- **Platform**: {platform.machine()}",
        f"---\n",
    ]
    return prompt + "\n".join(context_lines)


# ==============================================================================
# AGENT PROMPTS REGISTRY
# ==============================================================================

def get_jarvis_v2_tools() -> str:
    """Get the list of available tools."""
    return """Available tools:
- read: Read file contents (always read before editing)
- write: Create new or overwrite files
- edit: Make precise text replacements
- ls: List directory contents
- find: Search for files using glob patterns
- grep: Search file contents using ripgrep
- bash: Execute shell commands
- web_search: Search the internet
- fetch_webpage: Fetch webpage content
- agents: Delegate tasks to subagents"""


def get_jarvis_v2_guidelines() -> str:
    """Get the guidelines."""
    return """Guidelines:
1. Be agentic — use tools to act, not just describe
2. Read before you edit
3. Use edit for surgical changes, write for new files
4. Be concise
5. Run tests after code changes"""


def get_jarvis_v2_context(context_files: Optional[List[str]] = None, skills: Optional[List[str]] = None) -> str:
    """Get v2 context for JARVIS."""
    date = datetime.now().strftime("%Y-%m-%d")
    cwd = os.getcwd()
    parts = [f"Current date: {date}", f"Current working directory: {cwd}"]

    if context_files:
        parts.append("\n# Project context files:")
        for p in context_files:
            parts.append(f"- {p}")

    if skills:
        parts.append("\n# Available skills:")
        for s in skills:
            parts.append(f"- {s}")

    return "\n".join(parts)


def discover_context_files() -> List[str]:
    """Scan for context files."""
    import glob
    cwd = Path.cwd()
    discovered = []

    if (cwd / "AGENTS.md").exists():
        discovered.append("AGENTS.md")
    if (cwd / ".jarvis" / "SYSTEM.md").exists():
        discovered.append(".jarvis/SYSTEM.md")

    for f in glob.glob(str(cwd / ".claude" / "rules" / "*.md")):
        discovered.append(f)
    return discovered


def build_jarvis_v2_system_prompt(
    context_files: Optional[List[str]] = None,
    skills: Optional[List[str]] = None,
    append_text: Optional[str] = None,
    auto_discover: bool = True,
) -> str:
    """Construct the JARVIS v2 system prompt."""
    from datetime import datetime
    
    if context_files is None and auto_discover:
        context_files = discover_context_files()
    elif context_files is None:
        context_files = []

    date = datetime.now().strftime("%Y-%m-%d")
    cwd = os.getcwd()
    context = get_jarvis_v2_context(context_files, skills)
    append = f"\n\n{append_text}" if append_text else ""

    return f"""You are JARVIS, a friendly but capable interactive agent that helps users with software engineering tasks.

## System Information
- **Working Directory**: {cwd}
- **Current Date**: {date}

## How You Work
You have access to a rich set of tools that let you take action rather than just provide suggestions. You're designed to be helpful, thorough, and proactive in completing tasks.

## Communication Style
- If you can answer a question accurately in a sentence or two, do so without using tools
- For complex requests, use tools to understand the codebase and implement solutions
- Be concise but complete — include essential details without excess verbosity
- When showing code, explain it briefly unless the user asks for more detail

## Tool Usage Philosophy
1. **Read before you edit** — Always understand existing code before modifying it
2. **Be surgical with edits** — Prefer `edit` for targeted changes, `write` for new files
3. **Verify your work** — Run tests, check outputs, don't just assume things work
4. **Think before acting** — Consider the impact of changes on the broader codebase

## Code Style Guidelines
- Match the existing codebase style (indentation, naming conventions, etc.)
- Don't add features, refactor code, or make "improvements" beyond what was asked
- Don't add docstrings, comments, or type annotations to code you didn't change
- Only add error handling where genuinely needed for the task at hand
- Prefer simple, direct solutions over complex abstractions

## Security
- Never commit secrets or credentials to the repository
- Be careful about command injection when using bash
- Validate user input before using it in sensitive operations

## Available Tools
- **read**: Read file contents (always read before editing)
- **write**: Create new or overwrite files  
- **edit**: Make precise text replacements in existing files
- **ls**: List directory contents
- **find**: Search for files using glob patterns
- **grep**: Search file contents using ripgrep (rg)
- **bash**: Execute shell commands
- **web_search**: Search the internet for information
- **fetch_webpage**: Fetch and read webpage content
- **agents**: Delegate tasks to specialized subagents (explore, plan, verification, jarvis-help, statusline-setup)
{context}{append}"""


JARVIS_V2_SYSTEM_PROMPT = build_jarvis_v2_system_prompt(auto_discover=True)

# Build prompts directly in this file (avoids circular imports with builtin modules)
# Prompts are kept here to maintain the manager-only role of this module
# For explore and plan, we inline the prompts to match the module structure

def _get_builtin_prompts() -> dict:
    """Lazy import of builtin prompts to avoid circular imports."""
    from core.agents.builtin.explore_prompt import GetExploreSystemPrompt
    from core.agents.builtin.plan_prompt import GetPlanSystemPrompt
    from core.agents.builtin.jarvis_help_agent import GetJarvisHelpPrompt
    from core.agents.builtin.statusline_setup_agent import GetStatuslineSetupPrompt
    from core.agents.builtin.verification_agent import GetVerificationPrompt
    return {
        'explore': GetExploreSystemPrompt(),
        'plan': GetPlanSystemPrompt(),
        'jarvis-help': GetJarvisHelpPrompt(),
        'statusline-setup': GetStatuslineSetupPrompt(),
        'verification': GetVerificationPrompt(),
    }


# Prompt modules loaded lazily - call these functions at runtime
def get_explore_prompt() -> str:
    """Get the explore system prompt."""
    from core.agents.builtin.explore_prompt import GetExploreSystemPrompt
    return GetExploreSystemPrompt()


def get_plan_prompt() -> str:
    """Get the plan system prompt."""
    from core.agents.builtin.plan_prompt import GetPlanSystemPrompt
    return GetPlanSystemPrompt()


def get_jarvis_help_prompt() -> str:
    """Get the JARVIS help system prompt."""
    from core.agents.builtin.jarvis_help_agent import GetJarvisHelpPrompt
    return GetJarvisHelpPrompt()


def get_statusline_prompt() -> str:
    """Get the statusline setup system prompt."""
    from core.agents.builtin.statusline_setup_agent import GetStatuslineSetupPrompt
    return GetStatuslineSetupPrompt()


def get_verification_prompt() -> str:
    """Get the verification system prompt."""
    from core.agents.builtin.verification_agent import GetVerificationPrompt
    return GetVerificationPrompt()


def _build_general_purpose_prompt() -> str:
    """Build the explore agent prompt."""
    from datetime import datetime
    date = datetime.now().strftime("%Y-%m-%d")
    cwd = os.getcwd()
    return f"""You are the Explore Agent, a specialized subagent for codebase exploration and analysis.

Available tools:
- read: Read file contents
- ls: List directory contents  
- find: Find files by pattern
- grep: Search file contents
- bash: Execute shell commands
- web_search: Search the internet

Guidelines:
- Use tools proactively to inspect the repository
- Be systematic: start broad, then narrow, then deep dive
- Focus on actionable insights

Current date: {date}
Current working directory: {cwd}
"""


def _build_plan_prompt() -> str:
    """Build the plan agent prompt."""
    from datetime import datetime
    date = datetime.now().strftime("%Y-%m-%d")
    cwd = os.getcwd()
    return f"""You are the Plan Agent, specialized in task decomposition and planning.

Available tools:
- read, ls, find, grep, web_search, fetch_webpage
- save_memory, read_memory

Guidelines:
- Break down complex tasks into clear steps
- Provide structured plans with phases and dependencies
- Identify risks and verification methods

Current date: {date}
Current working directory: {cwd}
"""


def _build_jarvis_help_prompt() -> str:
    """Build the JARVIS help agent prompt."""
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
    """Build the statusline setup agent prompt."""
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


def _build_verification_prompt() -> str:
    """Build the verification agent prompt."""
    from datetime import datetime
    date = datetime.now().strftime("%Y-%m-%d")
    cwd = os.getcwd()
    return f"""You are the Verification Agent for post-implementation testing.

Methodology:
1. Build verification
2. Test execution
3. Adversarial testing
4. Edge case analysis
5. Verification report

Guidelines:
- Be thorough to find issues before production
- Document findings with specific examples

Current date: {date}
Current working directory: {cwd}
"""


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


# Placeholder prompts for registry (actual prompts loaded lazily)
_EXPLORE_PLACEHOLDER = "Loading..."
_PLAN_PLACEHOLDER = "Loading..."
_JARVIS_HELP_PLACEHOLDER = "Loading..."
_STATUSLINE_PLACEHOLDER = "Loading..."
_VERIFICATION_PLACEHOLDER = "Loading..."

# Runtime loaded prompts (initialized by _init_prompts)
_RUNTIME_EXPLORE_PROMPT = None
_RUNTIME_PLAN_PROMPT = None
_RUNTIME_JARVIS_HELP_PROMPT = None
_RUNTIME_STATUSLINE_PROMPT = None
_RUNTIME_VERIFICATION_PROMPT = None

# Build the prompts that don't need lazy loading
GENERAL_PURPOSE_SYSTEM_PROMPT = _build_general_purpose_prompt()
FORK_SYSTEM_PROMPT = _build_fork_prompt()


def _init_prompts():
    """Initialize prompts by calling lazy load functions."""
    global _RUNTIME_EXPLORE_PROMPT, _RUNTIME_PLAN_PROMPT, _RUNTIME_JARVIS_HELP_PROMPT
    global _RUNTIME_STATUSLINE_PROMPT, _RUNTIME_VERIFICATION_PROMPT
    
    if _RUNTIME_EXPLORE_PROMPT is None:
        _RUNTIME_EXPLORE_PROMPT = get_explore_prompt()
    if _RUNTIME_PLAN_PROMPT is None:
        _RUNTIME_PLAN_PROMPT = get_plan_prompt()
    if _RUNTIME_JARVIS_HELP_PROMPT is None:
        _RUNTIME_JARVIS_HELP_PROMPT = get_jarvis_help_prompt()
    if _RUNTIME_STATUSLINE_PROMPT is None:
        _RUNTIME_STATUSLINE_PROMPT = get_statusline_prompt()
    if _RUNTIME_VERIFICATION_PROMPT is None:
        _RUNTIME_VERIFICATION_PROMPT = get_verification_prompt()


AGENT_PROMPTS: dict[str, Tuple[str, AgentPromptMetadata]] = {
    "jarvis": (
        JARVIS_V2_SYSTEM_PROMPT,
        AgentPromptMetadata(agent_type="main", when_to_use="Use for general coding tasks.", model="inherit", max_turns=100),
    ),
    "explore": (
        _EXPLORE_PLACEHOLDER,
        AgentPromptMetadata(agent_type="subagent", when_to_use="Use for codebase exploration.", model="default", max_turns=50),
    ),
    "plan": (
        _PLAN_PLACEHOLDER,
        AgentPromptMetadata(agent_type="subagent", when_to_use="Use for task planning.", model="default", max_turns=50),
    ),
    "jarvis-help": (
        _JARVIS_HELP_PLACEHOLDER,
        AgentPromptMetadata(agent_type="subagent", when_to_use="Use for JARVIS help.", model="inherit", max_turns=50),
    ),
    "statusline-setup": (
        _STATUSLINE_PLACEHOLDER,
        AgentPromptMetadata(agent_type="subagent", when_to_use="Use for prompt setup.", model="inherit", max_turns=50),
    ),
    "verification": (
        _VERIFICATION_PLACEHOLDER,
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
    """Get the system prompt for a named agent (lazy loads prompts)."""
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
    return prompts.get(agent_name, JARVIS_V2_SYSTEM_PROMPT)


def get_agent_metadata(agent_name: str) -> Optional[AgentPromptMetadata]:
    """Get the metadata for a named agent."""
    return AGENT_PROMPTS.get(agent_name, (None, None))[1] if agent_name in AGENT_PROMPTS else None


def get_enhanced_prompt(agent_name: str, emoji: Optional[str] = None) -> str:
    """Get an enhanced system prompt with environment details."""
    prompt = get_agent_prompt(agent_name)
    emoji_map = {
        "jarvis": "🤖", "explore": "🔍", "plan": "📋", "jarvis-help": "❓",
        "statusline-setup": "💻", "verification": "✅", "general-purpose": "⚡", "fork": "🍴",
    }
    return enhanceSystemPromptWithEnvDetails(prompt, agent_name, emoji or emoji_map.get(agent_name, "🤖"))