"""Shared prompt utilities for JARVIS agents."""

import os
from datetime import datetime
from pathlib import Path


def build_context_section(context_files: list[str] | None = None, skills: list[str] | None = None) -> str:
    """Build context section for agent prompts."""
    date = datetime.now().strftime("%Y-%m-%d")
    cwd = os.getcwd()
    parts = [f"Date: {date}", f"Dir: {cwd}"]
    if context_files:
        parts.append("\nContext files:")
        parts.extend(f"- {p}" for p in context_files)
    if skills:
        parts.append("\nSkills:")
        parts.extend(f"- {s}" for s in skills)
    return "\n".join(parts)


def build_agent_header(agent_name: str, role: str, emoji: str = "🤖") -> str:
    """Build standardized agent header."""
    return f"{emoji} **{agent_name}** - {role}"


def read_context_files(file_paths: list[str]) -> dict[str, str]:
    """Read context files. Returns {path: content} for existing files."""
    contents = {}
    for path in file_paths:
        try:
            full_path = Path(path)
            if full_path.exists():
                contents[path] = full_path.read_text(encoding="utf-8")
        except Exception:
            pass
    return contents


def format_tool_list(tools: list[str]) -> str:
    """Format tool list for prompts."""
    return "\n".join(f"- {tool}" for tool in tools)


def get_project_root() -> Path:
    """Find project root by .git directory."""
    cwd = Path.cwd()
    root = cwd
    while root.parent != root and not (root / ".git").exists():
        root = root.parent
    return root
