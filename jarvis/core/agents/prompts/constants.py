"""Prompt constants and configuration for JARVIS agents.

This module contains shared constants, configuration values, and base utilities
used across all agent system prompts.
"""

import os
import platform
import sys
from datetime import datetime
from pathlib import Path

# Fork detection marker
FORK_PROMPT_MARKER = " FORK:"

# Default emoji mappings for agents
DEFAULT_EMOJI_MAP = {
    "jarvis": "🤖",
    "explore": "🔍",
    "plan": "📋",
    "jarvis-help": "❓",
    "statusline-setup": "💻",
    "verification": "✅",
    "rubber-duck": "🦆",
    "general-purpose": "⚡",
    "fork": "🍴",
}


def get_system_context() -> str:
    """Get system context for the main agent.

    Returns:
        String containing system information for agent context.
    """
    cwd = os.getcwd()
    return f"## System Information\n- **Working Directory**: {cwd}\n"


def get_base_context() -> str:
    """Get base context including date and working directory.

    Returns:
        Formatted string with current date and working directory.
    """
    date = datetime.now().strftime("%Y-%m-%d")
    cwd = os.getcwd()
    return f"Current date: {date}\nCurrent working directory: {cwd}"


def discover_context_files() -> list[str]:
    """Scan for context files in the working directory.

    Looks for AGENTS.md, .jarvis/SYSTEM.md, and .claude/rules/*.md files.

    Returns:
        List of discovered context file paths.
    """
    cwd = Path.cwd()
    discovered = []

    if (cwd / "AGENTS.md").exists():
        discovered.append("AGENTS.md")
    if (cwd / ".jarvis" / "SYSTEM.md").exists():
        discovered.append(".jarvis/SYSTEM.md")

    import glob
    for f in glob.glob(str(cwd / ".claude" / "rules" / "*.md")):
        discovered.append(f)
    return discovered


def enhance_prompt_with_env_details(prompt: str, agent_name: str = "jarvis", emoji: str = "🤖") -> str:
    """Enhance system prompt with environment details for agent identification.

    Args:
        prompt: The original system prompt to enhance.
        agent_name: Name of the agent for identification.
        emoji: Emoji to display for the agent.

    Returns:
        Enhanced prompt with environment details appended.
    """
    cwd = Path.cwd()
    project_root = cwd
    while project_root.parent != project_root and not (project_root / ".git").exists():
        project_root = project_root.parent

    context_lines = [
        "\n\n---\n",
        "# Agent Environment Details",
        f"- **Emoji**: {emoji}",
        f"- **Agent Name**: {agent_name}",
        f"- **Working Directory**: {cwd}",
        f"- **Project Root**: {project_root}",
        f"- **OS**: {platform.system()} {platform.release()}",
        f"- **Python**: {sys.version.split()[0]}",
        f"- **Platform**: {platform.machine()}",
        "---\n",
    ]
    return prompt + "\n".join(context_lines)


def get_platform_info() -> dict:
    """Get platform information for prompt context.

    Returns:
        Dictionary with platform, OS, Python version, and machine info.
    """
    return {
        "platform": platform.system(),
        "os": f"{platform.system()} {platform.release()}",
        "python": sys.version.split()[0],
        "machine": platform.machine(),
    }
