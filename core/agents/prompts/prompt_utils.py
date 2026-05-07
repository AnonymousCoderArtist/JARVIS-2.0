"""Shared prompt utilities for JARVIS agents.

This module provides utility functions for building and managing agent system prompts.
"""

from datetime import datetime
import os
from pathlib import Path
from typing import Dict, List, Optional


def build_context_section(context_files: Optional[List[str]] = None, skills: Optional[List[str]] = None) -> str:
    """Build the context section for agent prompts.

    Args:
        context_files: List of context file paths to include.
        skills: List of available skills to include.

    Returns:
        Formatted context string for system prompts.
    """
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


def build_agent_header(agent_name: str, role: str, emoji: str = "🤖") -> str:
    """Build a standardized agent header.

    Args:
        agent_name: Name of the agent.
        role: Description of the agent's role.
        emoji: Emoji for visual identification.

    Returns:
        Formatted header string.
    """
    return f"{emoji} **{agent_name}** - {role}"


def read_context_files(file_paths: List[str]) -> Dict[str, str]:
    """Read content from specified context files.

    Args:
        file_paths: List of file paths to read.

    Returns:
        Dictionary mapping file paths to their contents.
    """
    contents = {}
    for path in file_paths:
        try:
            full_path = Path(path)
            if full_path.exists():
                contents[path] = full_path.read_text(encoding="utf-8")
        except Exception:
            pass
    return contents


def format_tool_list(tools: List[str]) -> str:
    """Format a list of tools for display in prompts.

    Args:
        tools: List of tool names.

    Returns:
        Formatted tool list string.
    """
    return "\n".join(f"- {tool}" for tool in tools)


def get_project_root() -> Path:
    """Find the project root by looking for .git directory.

    Returns:
        Path to the project root directory.
    """
    cwd = Path.cwd()
    project_root = cwd
    while project_root.parent != project_root and not (project_root / ".git").exists():
        project_root = project_root.parent
    return project_root