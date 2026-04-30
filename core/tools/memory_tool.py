"""Memory management tool - OpenClaude style persistent memory"""

import os
from datetime import datetime
from pathlib import Path
from typing import Any

from .base import BaseTool, ToolInput, ToolOutput


# Memory type definitions (matching OpenClaude's memoryTypes.ts)
MEMORY_TYPES = {
    "user": {
        "description": "Details about the user's role, goals, responsibilities, and knowledge",
        "when_to_save": "When you learn any details about the user's role, preferences, responsibilities, or knowledge",
        "how_to_use": "When your work should be informed by the user's profile or perspective"
    },
    "feedback": {
        "description": "Guidance the user has given about how to approach work",
        "when_to_save": "Any time the user corrects your approach or confirms a non-obvious approach worked",
        "how_to_use": "Let these memories guide your behavior so the user doesn't need to offer the same guidance twice"
    },
    "project": {
        "description": "Information about ongoing work, goals, initiatives, bugs, or incidents",
        "when_to_save": "When you learn who is doing what, why, or by when",
        "how_to_use": "Use these memories to more fully understand the context and motivation behind the user's work"
    },
    "reference": {
        "description": "Pointers to where information can be found in external systems",
        "when_to_save": "When you learn about resources in external systems and their purpose",
        "how_to_use": "When the user references an external system or information that may be in an external system"
    }
}


def get_memory_dir() -> Path:
    """Get the memory directory path, preferring .jarvis structure"""
    cwd = Path.cwd()

    # Look for .jarvis directory in current or parent directories
    for parent in [cwd] + list(cwd.parents):
        jarvis_dir = parent / ".jarvis"
        if jarvis_dir.exists():
            # Return the project-specific memory path
            return jarvis_dir / "memory"

    # Fallback to .openclaude structure if .jarvis not found
    for parent in [cwd] + list(cwd.parents):
        openclaude_dir = parent / ".openclaude"
        if openclaude_dir.exists():
            return openclaude_dir / "projects" / cwd.relative_to(parent).as_posix().replace("/", "-") / "memory"

    # Fallback to core/memory/storage
    return Path("core/memory/storage")


def get_scope_dir(memory_dir: Path, scope: str) -> Path:
    """Get the directory for a specific scope (private or team)"""
    if scope == "team":
        return memory_dir / "team"
    return memory_dir / "private"


def generate_memory_filename(name: str, timestamp: datetime) -> str:
    """Generate a filename from the memory name and timestamp"""
    # Convert name to slug format
    slug = name.lower().replace(" ", "-").replace("/", "-")
    slug = "".join(c for c in slug if c.isalnum() or c == "-")
    timestamp_str = timestamp.strftime("%Y-%m-%d")
    return f"{timestamp_str}-{slug}.md"


def update_memory_index(scope_dir: Path, memory_file: Path, action: str = "add"):
    """Update the MEMORY.md index file"""
    index_file = scope_dir / "MEMORY.md"

    # Read existing index
    entries = []
    if index_file.exists():
        with open(index_file, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("- [") and "](" in line:
                    entries.append(line)

    # Get memory name from frontmatter
    memory_name = memory_file.stem
    # Try to read frontmatter for description
    description = memory_name.replace("-", " ").title()

    try:
        with open(memory_file, encoding="utf-8") as f:
            content = f.read()
            if content.startswith("---"):
                parts = content.split("---", 2)
                if len(parts) >= 2:
                    frontmatter = parts[1]
                    for line in frontmatter.split("\n"):
                        if line.startswith("description:"):
                            description = line.split(":", 1)[1].strip()
                            break
    except Exception:
        pass

    entry = f"- [{memory_name}]({memory_file.name}) — {description}"

    if action == "add" and entry not in entries:
        entries.insert(0, entry)
    elif action == "remove":
        entries = [e for e in entries if memory_file.name in e]

    # Write index
    with open(index_file, "w", encoding="utf-8") as f:
        for entry in entries:
            f.write(entry + "\n")


def parse_frontmatter(content: str) -> tuple[dict[str, str], str]:
    """Parse YAML frontmatter from markdown content"""
    frontmatter = {}
    body = content

    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 2:
            for line in parts[1].split("\n"):
                if ":" in line:
                    key, value = line.split(":", 1)
                    frontmatter[key.strip()] = value.strip()
            body = parts[2] if len(parts) > 2 else ""

    return frontmatter, body


def get_memory_context(limit: int = 20) -> str:
    """
    Get memory context as a formatted string for inclusion in prompts.
    Returns all memories formatted for the agent to use.
    """
    memory_dir = get_memory_dir()
    results = []

    for scope in ["private", "team"]:
        scope_dir = get_scope_dir(memory_dir, scope)
        if not scope_dir.exists():
            continue

        for memory_file in sorted(scope_dir.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True):
            if memory_file.name == "MEMORY.md":
                continue

            try:
                with open(memory_file, encoding="utf-8") as f:
                    content = f.read()

                frontmatter, body = parse_frontmatter(content)

                name = frontmatter.get("name", memory_file.stem)
                description = frontmatter.get("description", "")
                memory_type = frontmatter.get("type", "user")

                results.append(f"[{scope}/{memory_type}] {name}: {description}")

                if len(results) >= limit:
                    break
            except Exception:
                continue

        if len(results) >= limit:
            break

    return "\n".join(results)


class SaveMemoryTool(BaseTool):
    """Tool for saving facts/preferences across sessions (OpenClaude style)"""

    name = "save_memory"
    description = """Saves concise user context (preferences, facts) for use across future sessions. Use this to remember important information about the user or project.

Usage:
- Provide a concise fact, preference, or piece of information to remember
- Use scope parameter to control memory visibility:
  - 'private': applies to this user (stored in .jarvis/memory/private/)
  - 'team': shared with team members (stored in .jarvis/memory/team/)
- Memory persists across sessions and can be retrieved in future conversations
- Keep facts concise and focused on actionable information
- Memories use Markdown format with YAML frontmatter for structure"""

    input_schema = {
        "type": "object",
        "properties": {
            "fact": {
                "type": "string",
                "description": "The specific fact, preference, or piece of information to remember",
                "minLength": 1
            },
            "name": {
                "type": "string",
                "description": "Optional name/title for the memory (auto-generated if not provided)"
            },
            "type": {
                "type": "string",
                "enum": ["user", "feedback", "project", "reference"],
                "description": "Type of memory to save",
                "default": "user"
            },
            "scope": {
                "type": "string",
                "enum": ["private", "team"],
                "description": "Scope for the memory: 'private' applies to this user, 'team' is shared",
                "default": "private"
            }
        },
        "required": ["fact"]
    }

    async def execute(self, input_data: ToolInput) -> ToolOutput:
        fact = getattr(input_data, "fact", None)
        scope = getattr(input_data, "scope", "private")
        memory_type = getattr(input_data, "type", "user")
        name = getattr(input_data, "name", None)

        if not isinstance(fact, str) or not fact:
            return ToolOutput(
                success=False,
                result=None,
                error="Invalid fact: fact parameter must be a non-empty string."
            )

        try:
            # Get memory directory
            memory_dir = get_memory_dir()
            scope_dir = get_scope_dir(memory_dir, scope)
            scope_dir.mkdir(parents=True, exist_ok=True)

            # Generate name if not provided
            timestamp = datetime.now()
            if not name:
                # Create a short name from the fact
                words = fact.split()[:5]
                name = " ".join(words)
                if len(fact.split()) > 5:
                    name += "..."

            # Generate filename
            filename = generate_memory_filename(name, timestamp)
            memory_file = scope_dir / filename

            # Create memory content with frontmatter
            frontmatter = f"""---
name: {name}
description: {fact[:100]}{'...' if len(fact) > 100 else ''}
type: {memory_type}
---

**Fact:** {fact}

**Why:** [Auto-generated - customize this section]

**How to apply:** [Auto-generated - customize this section]

Saved at: {timestamp.isoformat()}
"""

            # Write memory file
            with open(memory_file, "w", encoding="utf-8") as f:
                f.write(frontmatter)

            # Update index
            update_memory_index(scope_dir, memory_file, "add")

            return ToolOutput(
                success=True,
                result=f"Fact remembered in {scope} scope: '{fact[:50]}{'...' if len(fact) > 50 else ''}'",
                metadata={
                    "scope": scope,
                    "type": memory_type,
                    "file": str(memory_file)
                }
            )

        except Exception as e:
            return ToolOutput(
                success=False,
                result=None,
                error=f"Failed to save memory: {str(e)}"
            )


class ReadMemoryTool(BaseTool):
    """Tool for reading saved memories"""

    name = "read_memory"
    description = """Reads saved memories from the memory store. Use to retrieve previously saved facts and preferences.

Usage:
- Read all memories from a scope (private or team)
- Filter by memory type (user, feedback, project, reference)
- Search memories by keyword
- Returns memories with their metadata"""

    input_schema = {
        "type": "object",
        "properties": {
            "scope": {
                "type": "string",
                "enum": ["private", "team", "all"],
                "description": "Scope to read memories from",
                "default": "all"
            },
            "type": {
                "type": "string",
                "enum": ["user", "feedback", "project", "reference", "all"],
                "description": "Filter by memory type",
                "default": "all"
            },
            "query": {
                "type": "string",
                "description": "Search query to filter memories"
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of memories to return",
                "default": 10
            }
        },
        "required": []
    }

    async def execute(self, input_data: ToolInput) -> ToolOutput:
        scope = getattr(input_data, "scope", "all")
        memory_type = getattr(input_data, "type", "all")
        query = getattr(input_data, "query", None)
        limit = getattr(input_data, "limit", 10)

        try:
            memory_dir = get_memory_dir()
            results = []

            scopes_to_read = ["private", "team"] if scope == "all" else [scope]

            for s in scopes_to_read:
                scope_dir = get_scope_dir(memory_dir, s)
                if not scope_dir.exists():
                    continue

                for memory_file in sorted(scope_dir.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True):
                    if memory_file.name == "MEMORY.md":
                        continue

                    try:
                        with open(memory_file, encoding="utf-8") as f:
                            content = f.read()

                        frontmatter, body = parse_frontmatter(content)

                        # Filter by type
                        if memory_type != "all" and frontmatter.get("type") != memory_type:
                            continue

                        # Filter by query
                        if query:
                            search_text = f"{frontmatter.get('name', '')} {frontmatter.get('description', '')} {body}"
                            if query.lower() not in search_text.lower():
                                continue

                        results.append({
                            "name": frontmatter.get("name", memory_file.stem),
                            "description": frontmatter.get("description", ""),
                            "type": frontmatter.get("type", "user"),
                            "scope": s,
                            "file": str(memory_file),
                            "content": body.strip()
                        })

                        if len(results) >= limit:
                            break
                    except Exception:
                        continue

                if len(results) >= limit:
                    break

            return ToolOutput(
                success=True,
                result=results,
                metadata={"count": len(results)}
            )

        except Exception as e:
            return ToolOutput(
                success=False,
                result=None,
                error=f"Failed to read memories: {str(e)}"
            )