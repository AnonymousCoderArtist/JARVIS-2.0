"""Memory management tool - OpenClaude style persistent memory"""

import os
import re
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
    "project_context": {
        "description": "Detailed project-specific context, architecture, and technical decisions",
        "when_to_save": "When learning about project structure, technical choices, architecture patterns, or specific implementation details",
        "how_to_use": "Use for understanding project-specific context and making informed technical decisions"
    },
    "reference": {
        "description": "Pointers to where information can be found in external systems",
        "when_to_save": "When you learn about resources in external systems and their purpose",
        "how_to_use": "When the user references an external system or information that may be in an external system"
    },
    "global": {
        "description": "General knowledge and patterns that apply across multiple projects or contexts",
        "when_to_save": "When learning universal patterns, best practices, or knowledge that transcends specific projects",
        "how_to_use": "Apply these learnings across different projects and contexts"
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

    # Create .jarvis directory in current directory if not found
    jarvis_dir = cwd / ".jarvis"
    jarvis_dir.mkdir(exist_ok=True)
    memory_dir = jarvis_dir / "memory"
    memory_dir.mkdir(exist_ok=True)
    return memory_dir


def get_project_name() -> str:
    """Get project name from directory structure or git"""
    cwd = Path.cwd()
    
    # Try to get from git remote
    try:
        import subprocess
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            url = result.stdout.strip()
            # Extract project name from git URL
            if "/" in url:
                project_name = url.split("/")[-1].replace(".git", "")
                return project_name
    except Exception:
        pass
    
    # Fallback to directory name
    return cwd.name


def get_global_memory_dir() -> Path:
    """Get global memory directory for cross-project knowledge"""
    home = Path.home()
    global_dir = home / ".jarvis" / "global_memory"
    global_dir.mkdir(parents=True, exist_ok=True)
    return global_dir


def get_scope_dir(memory_dir: Path, scope: str) -> Path:
    """Get the directory for a specific scope (private, team, or global)"""
    if scope == "team":
        return memory_dir / "team"
    elif scope == "global":
        return get_global_memory_dir()
    return memory_dir / "private"


def generate_memory_filename(name: str, timestamp: datetime, memory_type: str = "user") -> str:
    """Generate a filename from the memory name, timestamp, and type"""
    # Convert name to slug format
    slug = name.lower().replace(" ", "-").replace("/", "-")
    slug = "".join(c for c in slug if c.isalnum() or c == "-")
    timestamp_str = timestamp.strftime("%Y-%m-%d")
    
    # Add type prefix for better organization
    type_prefix = memory_type[0].upper()  # First letter of memory type
    return f"{timestamp_str}-{type_prefix}-{slug}.md"


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
    """Enhanced tool for saving detailed memories with project-specific and global capabilities"""

    name = "save_memory"
    description = """Save memories for future sessions. Supports private, team, and global scopes.

{"fact": "User prefers dark mode", "scope": "private", "memory_type": "user"}

Scopes: private, team, global. Types: user, feedback, project, reference, global."""

    input_schema = {
        "type": "object",
        "properties": {
            "fact": {
                "type": "string",
                "description": "The main fact or information to remember",
                "minLength": 1
            },
            "name": {
                "type": "string",
                "description": "Optional name/title for the memory (auto-generated if not provided)"
            },
            "type": {
                "type": "string",
                "enum": ["user", "feedback", "project", "project_context", "reference", "global"],
                "description": "Type of memory to save",
                "default": "user"
            },
            "scope": {
                "type": "string",
                "enum": ["private", "team", "global"],
                "description": "Scope for the memory: 'private' applies to this user, 'team' is shared, 'global' is cross-project",
                "default": "private"
            },
            "context": {
                "type": "string",
                "description": "Additional context or background information"
            },
            "reasoning": {
                "type": "string",
                "description": "Why this information is important or should be remembered"
            },
            "application": {
                "type": "string",
                "description": "How this information should be applied in future work"
            },
            "tags": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Tags for categorizing and searching memories"
            },
            "priority": {
                "type": "string",
                "enum": ["low", "medium", "high", "critical"],
                "description": "Priority level for this memory",
                "default": "medium"
            },
            "project_name": {
                "type": "string",
                "description": "Override auto-detected project name"
            }
        },
        "required": ["fact"]
    }

    async def execute(self, input_data: ToolInput) -> ToolOutput:
        fact = getattr(input_data, "fact", None)
        scope = getattr(input_data, "scope", "private")
        memory_type = getattr(input_data, "type", "user")
        name = getattr(input_data, "name", None)
        context = getattr(input_data, "context", "")
        reasoning = getattr(input_data, "reasoning", "")
        application = getattr(input_data, "application", "")
        tags = getattr(input_data, "tags", [])
        priority = getattr(input_data, "priority", "medium")
        project_name = getattr(input_data, "project_name", None)

        if not isinstance(fact, str) or not fact:
            return ToolOutput(
                success=False,
                result=None,
                error="Invalid fact: fact parameter must be a non-empty string."
            )

        try:
            # Get memory directory
            if scope == "global":
                memory_dir = get_global_memory_dir()
            else:
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

            # Get project name
            if not project_name and scope != "global":
                project_name = get_project_name()

            # Generate filename
            filename = generate_memory_filename(name, timestamp, memory_type)
            memory_file = scope_dir / filename

            # Create enhanced memory content with rich structure
            tags_str = ", ".join(tags) if tags else ""
            
            frontmatter = f"""---
name: {name}
description: {fact[:100]}{'...' if len(fact) > 100 else ''}
type: {memory_type}
scope: {scope}
priority: {priority}
tags: [{tags_str}]
project: {project_name or 'N/A'}
created: {timestamp.isoformat()}
---

# {name}

## Core Information
**Fact:** {fact}

"""

            # Add optional sections
            content_sections = []
            
            if context:
                content_sections.append(f"## Context\n{context}\n")
            
            if reasoning:
                content_sections.append(f"## Reasoning\n{reasoning}\n")
            
            if application:
                content_sections.append(f"## Application\n{application}\n")
            
            # Add metadata section
            content_sections.append(f"## Metadata\n- **Type:** {memory_type}\n- **Scope:** {scope}\n- **Priority:** {priority}\n- **Tags:** {tags_str or 'None'}\n- **Project:** {project_name or 'N/A'}\n- **Created:** {timestamp.isoformat()}\n")
            
            # Combine all content
            full_content = frontmatter + "\n".join(content_sections)

            # Write memory file
            with open(memory_file, "w", encoding="utf-8") as f:
                f.write(full_content)

            # Update index
            update_memory_index(scope_dir, memory_file, "add")

            return ToolOutput(
                success=True,
                result=f"Memory saved in {scope} scope ({memory_type}): '{name}'",
                metadata={
                    "scope": scope,
                    "type": memory_type,
                    "file": str(memory_file),
                    "project": project_name,
                    "priority": priority,
                    "tags": tags
                }
            )

        except Exception as e:
            return ToolOutput(
                success=False,
                result=None,
                error=f"Failed to save memory: {str(e)}"
            )


class ReadMemoryTool(BaseTool):
    """Enhanced tool for reading saved memories with advanced filtering"""

    name = "read_memory"
    description = """Read saved memories with filtering. Retrieve past facts, preferences, and context.

{"scope": "private", "type": "user", "query": "search term"}

Scopes: private, team, global, all. Types: user, feedback, project, reference, global."""

    input_schema = {
        "type": "object",
        "properties": {
            "scope": {
                "type": "string",
                "enum": ["private", "team", "global", "all"],
                "description": "Scope to read memories from",
                "default": "all"
            },
            "type": {
                "type": "string",
                "enum": ["user", "feedback", "project", "project_context", "reference", "global", "all"],
                "description": "Filter by memory type",
                "default": "all"
            },
            "query": {
                "type": "string",
                "description": "Search query to filter memories"
            },
            "tags": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Filter by specific tags"
            },
            "priority": {
                "type": "string",
                "enum": ["low", "medium", "high", "critical"],
                "description": "Filter by priority level"
            },
            "project": {
                "type": "string",
                "description": "Filter by project name"
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
        tags = getattr(input_data, "tags", [])
        priority = getattr(input_data, "priority", None)
        project = getattr(input_data, "project", None)
        limit = getattr(input_data, "limit", 10)

        try:
            results = []

            # Determine which scopes to read
            if scope == "all":
                scopes_to_read = ["private", "team", "global"]
            else:
                scopes_to_read = [scope]

            for s in scopes_to_read:
                if s == "global":
                    memory_dir = get_global_memory_dir()
                else:
                    memory_dir = get_memory_dir()
                
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

                        # Filter by priority
                        if priority and frontmatter.get("priority") != priority:
                            continue

                        # Filter by project
                        if project and frontmatter.get("project") != project:
                            continue

                        # Filter by tags
                        if tags:
                            memory_tags = frontmatter.get("tags", "")
                            if isinstance(memory_tags, str):
                                memory_tags = [tag.strip() for tag in memory_tags.split(",") if tag.strip()]
                            if not any(tag in memory_tags for tag in tags):
                                continue

                        # Filter by query
                        if query:
                            search_text = f"{frontmatter.get('name', '')} {frontmatter.get('description', '')} {body}"
                            if query.lower() not in search_text.lower():
                                continue

                        # Enhanced result with rich metadata
                        memory_tags = frontmatter.get("tags", "")
                        if isinstance(memory_tags, str):
                            memory_tags = [tag.strip() for tag in memory_tags.split(",") if tag.strip()]

                        results.append({
                            "name": frontmatter.get("name", memory_file.stem),
                            "description": frontmatter.get("description", ""),
                            "type": frontmatter.get("type", "user"),
                            "scope": s,
                            "priority": frontmatter.get("priority", "medium"),
                            "tags": memory_tags,
                            "project": frontmatter.get("project"),
                            "created": frontmatter.get("created"),
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


# Hermes-style memory management (MEMORY.md and USER.md)

HERMES_MEMORY_LIMITS = {
    "memory": 2200,   # Agent notes limit
    "user": 1375,     # User profile limit
}

SENSITIVE_PATTERNS = [
    r"api[_-]?key",
    r"password",
    r"secret",
    r"token",
    r"private[_-]?key",
    r"credential",
    r"bearer\s+",
]


def get_hermes_memory_dir() -> Path:
    """Get Hermes-style memory directory (~/.hermes/memory/)"""
    home = Path.home()
    hermes_dir = home / ".hermes" / "memory"
    hermes_dir.mkdir(parents=True, exist_ok=True)
    return hermes_dir


def check_memory_security(content: str) -> tuple[bool, str]:
    """
    Check memory content for sensitive patterns
    Returns (is_safe, warning_message)
    """
    import re
    
    content_lower = content.lower()
    for pattern in SENSITIVE_PATTERNS:
        if re.search(pattern, content_lower, re.IGNORECASE):
            return False, f"Memory content contains sensitive pattern: {pattern}"
    
    return True, ""


class MemoryManagementTool(BaseTool):
    """
    Hermes-style memory management tool supporting MEMORY.md and USER.md
    
    Provides add/replace/remove actions with character limits:
    - MEMORY.md: 2,200 char limit (agent notes)
    - USER.md: 1,375 char limit (user profile)
    """

    name = "memory"
    description = """Manage persistent memory in MEMORY.md and USER.md files.

{"action": "add", "memory_type": "user", "content": "User prefers dark mode"}

Actions: add, replace, remove, read. Types: memory (2200 chars), user (1375 chars)."""

    input_schema = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["add", "replace", "remove", "read"],
                "description": "Action to perform: add, replace, remove, or read"
            },
            "memory_type": {
                "type": "string",
                "enum": ["memory", "user"],
                "description": "Type of memory: 'memory' for agent notes, 'user' for user profile",
                "default": "memory"
            },
            "content": {
                "type": "string",
                "description": "Content to add (for add action)"
            },
            "match": {
                "type": "string",
                "description": "Substring to match for replace/remove actions"
            },
            "new_content": {
                "type": "string",
                "description": "New content to replace matched entry with (for replace action)"
            }
        },
        "required": ["action"]
    }

    async def execute(self, input_data: ToolInput) -> ToolOutput:
        action = getattr(input_data, "action", "read")
        memory_type = getattr(input_data, "memory_type", "memory")
        content = getattr(input_data, "content", None)
        match = getattr(input_data, "match", None)
        new_content = getattr(input_data, "new_content", None)

        try:
            memory_dir = get_hermes_memory_dir()
            memory_file = memory_dir / f"{memory_type.upper()}.md"
            
            # Get character limit for this memory type
            char_limit = HERMES_MEMORY_LIMITS.get(memory_type, 2200)
            
            if action == "read":
                return await self._read_memory(memory_file, memory_type)
            
            elif action == "add":
                if not content:
                    return ToolOutput(
                        success=False,
                        result=None,
                        error="Content is required for add action"
                    )
                return await self._add_memory(memory_file, content, memory_type, char_limit)
            
            elif action == "replace":
                if not match or not new_content:
                    return ToolOutput(
                        success=False,
                        result=None,
                        error="Match and new_content are required for replace action"
                    )
                return await self._replace_memory(memory_file, match, new_content, memory_type, char_limit)
            
            elif action == "remove":
                if not match:
                    return ToolOutput(
                        success=False,
                        result=None,
                        error="Match is required for remove action"
                    )
                return await self._remove_memory(memory_file, match, memory_type)
            
            else:
                return ToolOutput(
                    success=False,
                    result=None,
                    error=f"Unknown action: {action}"
                )
                
        except Exception as e:
            return ToolOutput(
                success=False,
                result=None,
                error=f"Memory operation failed: {str(e)}"
            )

    async def _read_memory(self, memory_file: Path, memory_type: str) -> ToolOutput:
        """Read memory content from file"""
        if not memory_file.exists():
            return ToolOutput(
                success=True,
                result={
                    "type": memory_type,
                    "content": "",
                    "exists": False,
                    "char_limit": HERMES_MEMORY_LIMITS.get(memory_type, 2200)
                }
            )
        
        with open(memory_file, encoding="utf-8") as f:
            memory_content = f.read()
        
        return ToolOutput(
            success=True,
            result={
                "type": memory_type,
                "content": memory_content,
                "exists": True,
                "char_limit": HERMES_MEMORY_LIMITS.get(memory_type, 2200),
                "char_count": len(memory_content)
            }
        )

    async def _add_memory(
        self, memory_file: Path, content: str, memory_type: str, char_limit: int
    ) -> ToolOutput:
        """Add new memory content"""
        # Check security
        is_safe, warning = check_memory_security(content)
        if not is_safe:
            return ToolOutput(
                success=False,
                result=None,
                error=f"Security check failed: {warning}"
            )
        
        # Check character limit
        if len(content) > char_limit:
            return ToolOutput(
                success=False,
                result=None,
                error=f"Content exceeds {char_limit} char limit for {memory_type}"
            )
        
        # Add timestamp
        timestamp = datetime.now().isoformat()
        full_content = f"""<!-- Last updated: {timestamp} -->
{content}
"""
        
        with open(memory_file, "w", encoding="utf-8") as f:
            f.write(full_content)
        
        return ToolOutput(
            success=True,
            result=f"Added {memory_type} memory ({len(content)} chars)",
            metadata={"type": memory_type, "char_count": len(content), "char_limit": char_limit}
        )

    async def _replace_memory(
        self, memory_file: Path, match: str, new_content: str, memory_type: str, char_limit: int
    ) -> ToolOutput:
        """Replace memory content using substring matching"""
        # Check security for new content
        is_safe, warning = check_memory_security(new_content)
        if not is_safe:
            return ToolOutput(
                success=False,
                result=None,
                error=f"Security check failed: {warning}"
            )
        
        # Check character limit
        if len(new_content) > char_limit:
            return ToolOutput(
                success=False,
                result=None,
                error=f"New content exceeds {char_limit} char limit for {memory_type}"
            )
        
        # Read current content
        if not memory_file.exists():
            return ToolOutput(
                success=False,
                result=None,
                error=f"No existing {memory_type} memory found"
            )
        
        with open(memory_file, encoding="utf-8") as f:
            current_content = f.read()
        
        # Find and replace using substring matching
        if match not in current_content:
            return ToolOutput(
                success=False,
                result=None,
                error=f"Match string not found in {memory_type} memory"
            )
        
        # Replace only the matched portion, keeping the timestamp comment if exists
        timestamp = datetime.now().isoformat()
        
        # Remove old timestamp comment and add new one
        current_content = re.sub(r"<!-- Last updated: .*? -->", "", current_content)
        current_content = current_content.strip()
        
        new_full_content = f"<!-- Last updated: {timestamp} -->\n{new_content}"
        
        with open(memory_file, "w", encoding="utf-8") as f:
            f.write(new_full_content)
        
        return ToolOutput(
            success=True,
            result=f"Replaced content in {memory_type} memory",
            metadata={"type": memory_type, "char_count": len(new_content), "char_limit": char_limit}
        )

    async def _remove_memory(self, memory_file: Path, match: str, memory_type: str) -> ToolOutput:
        """Remove memory content using substring matching"""
        if not memory_file.exists():
            return ToolOutput(
                success=False,
                result=None,
                error=f"No existing {memory_type} memory found"
            )
        
        with open(memory_file, encoding="utf-8") as f:
            current_content = f.read()
        
        # Check if match exists
        if match not in current_content:
            return ToolOutput(
                success=False,
                result=None,
                error=f"Match string not found in {memory_type} memory"
            )
        
        # Remove the matched content
        # Since we're removing, we need to be careful - just clear the file
        timestamp = datetime.now().isoformat()
        new_content = f"<!-- Last updated: {timestamp} -->\n[Content removed]"
        
        with open(memory_file, "w", encoding="utf-8") as f:
            f.write(new_content)
        
        return ToolOutput(
            success=True,
            result=f"Removed content from {memory_type} memory",
            metadata={"type": memory_type}
        )