"""Skill management tool - Hermes-style skill creation and management"""

import os
import re
import yaml
from datetime import datetime
from pathlib import Path
from typing import Any

from .base import BaseTool, ToolInput, ToolOutput


# Default skill directories (matching SkillManager)
DEFAULT_SKILL_DIRS = [
    Path(os.path.expanduser("~/.claude/skills")),
    Path(os.path.expanduser("~/.agents/skills")),
    Path(os.path.expanduser("~/.jarvis/skills")),
    Path(".jarvis/skills"),
]


def get_skill_dir() -> Path:
    """Get the primary skill directory for JARVIS"""
    # Use ~/.jarvis/skills as primary
    skill_dir = Path(os.path.expanduser("~/.jarvis/skills"))
    skill_dir.mkdir(parents=True, exist_ok=True)
    return skill_dir


def parse_skill_file(content: str) -> dict[str, Any]:
    """Parse SKILL.md file and extract metadata and content"""
    frontmatter = {}
    body = content
    
    # Parse YAML frontmatter
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 2:
            try:
                frontmatter = yaml.safe_load(parts[1]) or {}
            except yaml.YAMLError:
                pass
            body = parts[2] if len(parts) > 2 else ""
    
    return {
        "metadata": frontmatter,
        "content": body.strip()
    }


def create_skill_markdown(name: str, description: str, when_to_use: str, 
                         when_not_to_use: str, procedure: str, 
                         pitfalls: str = "", verification: str = "",
                         version: str = "1.0.0", platforms: list[str] | None = None,
                         category: str = "general", tags: list[str] | None = None,
                         requires_toolsets: list[str] | None = None) -> str:
    """Create SKILL.md content following agentskills.io standard"""
    
    platforms = platforms if platforms is not None else ["macos", "linux", "windows"]
    tags = tags if tags is not None else []
    requires_toolsets = requires_toolsets if requires_toolsets is not None else []
    
    # Build frontmatter
    frontmatter = {
        "name": name,
        "description": description,
        "version": version,
        "platforms": platforms,
        "metadata": {
            "hermes": {
                "tags": tags,
                "category": category,
                "requires_toolsets": requires_toolsets
            }
        },
        "when_to_use": when_to_use,
        "when_not_to_use": when_not_to_use
    }
    
    # Build body
    body_parts = [f"# {name.title()}", ""]
    
    if description:
        body_parts.extend(["## Description", description, ""])
    
    if when_to_use:
        body_parts.extend(["## When to Use", when_to_use, ""])
    
    if when_not_to_use:
        body_parts.extend(["## When NOT to Use", when_not_to_use, ""])
    
    if procedure:
        body_parts.extend(["## Procedure", procedure, ""])
    
    if pitfalls:
        body_parts.extend(["## Pitfalls", pitfalls, ""])
    
    if verification:
        body_parts.extend(["## Verification", verification, ""])
    
    # Combine frontmatter and body
    yaml_str = yaml.dump(frontmatter, default_flow_style=False, sort_keys=False)
    return f"---\n{yaml_str}---\n\n" + "\n".join(body_parts)


class SkillTool(BaseTool):
    """
    Comprehensive skill management tool for creating, editing, managing, and activating skills
    
    Supports:
    - create: Create new skill with SKILL.md format
    - patch: Update specific fields in existing skill
    - edit: Full replacement of skill content
    - delete: Remove a skill
    - list: List all available skills
    - read: Read skill content
    - activate: Activate a skill for use in the current session
    
    Follows agentskills.io standard with YAML frontmatter and markdown body.
    """

    name = "skill"
    description = """Manage skills: create, patch, edit, delete, list, read, activate.

{"action": "create", "name": "my-skill", "description": "Skill description"}

Actions: create, patch, edit, delete, list, read, activate. Uses agentskills.io standard."""

    input_schema = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["create", "patch", "edit", "delete", "list", "read", "activate"],
                "description": "Action to perform: create, patch, edit, delete, list, read, or activate"
            },
            "name": {
                "type": "string",
                "description": "Skill name (used for create, patch, edit, delete, read)"
            },
            "description": {
                "type": "string",
                "description": "Brief description of the skill (for create)"
            },
            "when_to_use": {
                "type": "string",
                "description": "When this skill should be used (for create, patch)"
            },
            "when_not_to_use": {
                "type": "string",
                "description": "When this skill should NOT be used (for create, patch)"
            },
            "procedure": {
                "type": "string",
                "description": "Step-by-step procedure for the skill (for create, patch)"
            },
            "pitfalls": {
                "type": "string",
                "description": "Known failure modes or pitfalls (for create, patch)"
            },
            "verification": {
                "type": "string",
                "description": "How to verify successful execution (for create, patch)"
            },
            "version": {
                "type": "string",
                "description": "Skill version (for create, patch)",
                "default": "1.0.0"
            },
            "platforms": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Supported platforms (for create)",
                "default": ["macos", "linux", "windows"]
            },
            "category": {
                "type": "string",
                "description": "Skill category (for create, patch)",
                "default": "general"
            },
            "tags": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Tags for the skill (for create, patch)"
            },
            "field": {
                "type": "string",
                "description": "Specific field to patch (for patch action)"
            },
            "new_content": {
                "type": "string",
                "description": "New content for field or full replacement (for patch/edit)"
            }
        },
        "required": ["action"]
    }

    async def execute(self, input_data: ToolInput) -> ToolOutput:
        action = getattr(input_data, "action", "list")
        name = getattr(input_data, "name", None)
        
        try:
            if action == "list":
                return await self._list_skills()
            
            if not name:
                return ToolOutput(
                    success=False,
                    result=None,
                    error="Skill name is required for this action"
                )
            
            skill_dir = get_skill_dir()
            skill_path = skill_dir / name
            
            if action == "create":
                description = getattr(input_data, "description", "")
                when_to_use = getattr(input_data, "when_to_use", "")
                when_not_to_use = getattr(input_data, "when_not_to_use", "")
                procedure = getattr(input_data, "procedure", "")
                pitfalls = getattr(input_data, "pitfalls", "")
                verification = getattr(input_data, "verification", "")
                version = getattr(input_data, "version", "1.0.0")
                platforms = getattr(input_data, "platforms", ["macos", "linux", "windows"])
                category = getattr(input_data, "category", "general")
                tags = getattr(input_data, "tags", [])
                
                return await self._create_skill(
                    name, description, when_to_use, when_not_to_use,
                    procedure, pitfalls, verification, version, platforms,
                    category, tags
                )
            
            elif action == "read":
                return await self._read_skill(name)
            
            elif action == "patch":
                field = getattr(input_data, "field", None)
                new_content = getattr(input_data, "new_content", None)
                if not field or not new_content:
                    return ToolOutput(
                        success=False,
                        result=None,
                        error="Field and new_content are required for patch action"
                    )
                return await self._patch_skill(name, field, new_content)
            
            elif action == "edit":
                new_content = getattr(input_data, "new_content", None)
                if not new_content:
                    return ToolOutput(
                        success=False,
                        result=None,
                        error="New content is required for edit action"
                    )
                return await self._edit_skill(name, new_content)
            
            elif action == "delete":
                return await self._delete_skill(name)
            
            elif action == "activate":
                return await self._activate_skill(name)
            
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
                error=f"Skill operation failed: {str(e)}"
            )

    async def _list_skills(self) -> ToolOutput:
        """List all available skills"""
        skill_dir = get_skill_dir()
        skills = []
        
        # Also check other skill directories
        for dir_path in DEFAULT_SKILL_DIRS:
            if not dir_path.exists():
                continue
            
            for skill_folder in dir_path.iterdir():
                if skill_folder.is_dir():
                    skill_name = skill_folder.name
                    skill_file = skill_folder / "SKILL.md"
                    if skill_file.exists():
                        try:
                            with open(skill_file, encoding="utf-8") as f:
                                content = f.read()
                            parsed = parse_skill_file(content)
                            skills.append({
                                "name": skill_name,
                                "description": parsed["metadata"].get("description", ""),
                                "version": parsed["metadata"].get("version", "1.0.0"),
                                "category": parsed["metadata"].get("metadata", {}).get("hermes", {}).get("category", "general"),
                                "source": str(dir_path)
                            })
                        except Exception:
                            continue
        
        return ToolOutput(
            success=True,
            result=skills,
            metadata={"count": len(skills)}
        )

    async def _create_skill(
        self, name: str, description: str, when_to_use: str,
        when_not_to_use: str, procedure: str, pitfalls: str,
        verification: str, version: str, platforms: list[str],
        category: str, tags: list[str]
    ) -> ToolOutput:
        """Create a new skill"""
        skill_dir = get_skill_dir()
        skill_path = skill_dir / name
        
        if skill_path.exists():
            return ToolOutput(
                success=False,
                result=None,
                error=f"Skill '{name}' already exists"
            )
        
        # Create skill directory
        skill_path.mkdir(parents=True, exist_ok=True)
        
        # Create SKILL.md content
        skill_content = create_skill_markdown(
            name=name,
            description=description,
            when_to_use=when_to_use or "As needed for the task",
            when_not_to_use=when_not_to_use or "For tasks outside this skill's domain",
            procedure=procedure or "Follow the skill instructions",
            pitfalls=pitfalls,
            verification=verification,
            version=version,
            platforms=platforms,
            category=category,
            tags=tags
        )
        
        # Write skill file
        skill_file = skill_path / "SKILL.md"
        with open(skill_file, "w", encoding="utf-8") as f:
            f.write(skill_content)
        
        return ToolOutput(
            success=True,
            result=f"Created skill '{name}' at {skill_file}",
            metadata={"name": name, "version": version, "path": str(skill_file)}
        )

    async def _read_skill(self, name: str) -> ToolOutput:
        """Read skill content"""
        # Check all skill directories
        for dir_path in DEFAULT_SKILL_DIRS:
            if not dir_path.exists():
                continue
            
            skill_path = dir_path / name
            skill_file = skill_path / "SKILL.md"
            
            if skill_file.exists():
                with open(skill_file, encoding="utf-8") as f:
                    content = f.read()
                
                parsed = parse_skill_file(content)
                return ToolOutput(
                    success=True,
                    result={
                        "name": name,
                        "metadata": parsed["metadata"],
                        "content": parsed["content"]
                    }
                )
        
        return ToolOutput(
            success=False,
            result=None,
            error=f"Skill '{name}' not found"
        )

    async def _patch_skill(self, name: str, field: str, new_content: str) -> ToolOutput:
        """Patch a specific field in a skill"""
        # Check all skill directories
        for dir_path in DEFAULT_SKILL_DIRS:
            if not dir_path.exists():
                continue
            
            skill_path = dir_path / name
            skill_file = skill_path / "SKILL.md"
            
            if skill_file.exists():
                with open(skill_file, encoding="utf-8") as f:
                    content = f.read()
                
                parsed = parse_skill_file(content)
                metadata = parsed["metadata"]
                body = parsed["content"]
                
                # Update the field
                # Fields that can be patched: description, when_to_use, when_not_to_use, 
                # procedure, pitfalls, verification, version, category, tags
                valid_fields = [
                    "description", "when_to_use", "when_not_to_use",
                    "procedure", "pitfalls", "verification", "version", "category"
                ]
                
                if field not in valid_fields:
                    return ToolOutput(
                        success=False,
                        result=None,
                        error=f"Invalid field '{field}'. Valid fields: {', '.join(valid_fields)}"
                    )
                
                # For nested fields in metadata
                if field in ["description", "version"]:
                    metadata[field] = new_content
                elif field in ["when_to_use", "when_not_to_use"]:
                    metadata[field] = new_content
                else:
                    # These go in the body
                    body = self._update_body_field(body, field, new_content)
                
                # Rebuild the skill file
                # Keep the original body structure and update only the specific field
                new_skill_content = self._rebuild_skill_content(metadata, body)
                
                with open(skill_file, "w", encoding="utf-8") as f:
                    f.write(new_skill_content)
                
                return ToolOutput(
                    success=True,
                    result=f"Patched skill '{name}' field '{field}'",
                    metadata={"name": name, "field": field}
                )
        
        return ToolOutput(
            success=False,
            result=None,
            error=f"Skill '{name}' not found"
        )

    def _update_body_field(self, body: str, field: str, new_content: str) -> str:
        """Update a field in the body content"""
        field_headers = {
            "procedure": "## Procedure",
            "pitfalls": "## Pitfalls",
            "verification": "## Verification"
        }
        
        header = field_headers.get(field, f"## {field.title()}")
        
        # Check if header exists in body
        if header in body:
            # Replace content under the header
            lines = body.split("\n")
            result = []
            in_field = False
            for line in lines:
                if line.startswith(header):
                    in_field = True
                    result.append(line)
                    result.append(new_content)
                elif in_field and line.startswith("## "):
                    in_field = False
                    result.append(line)
                elif not in_field:
                    result.append(line)
            return "\n".join(result)
        else:
            # Add new section
            return f"{body}\n\n{header}\n{new_content}"

    def _rebuild_skill_content(self, metadata: dict, body: str) -> str:
        """Rebuild full skill content from metadata and body"""
        # Keep certain metadata fields
        frontmatter = {
            "name": metadata.get("name", ""),
            "description": metadata.get("description", ""),
            "version": metadata.get("version", "1.0.0"),
            "platforms": metadata.get("platforms", ["macos", "linux", "windows"]),
            "metadata": metadata.get("metadata", {}),
            "when_to_use": metadata.get("when_to_use", ""),
            "when_not_to_use": metadata.get("when_not_to_use", "")
        }
        
        yaml_str = yaml.dump(frontmatter, default_flow_style=False, sort_keys=False)
        return f"---\n{yaml_str}---\n\n{body}"

    async def _edit_skill(self, name: str, new_content: str) -> ToolOutput:
        """Fully replace skill content"""
        # Check all skill directories
        for dir_path in DEFAULT_SKILL_DIRS:
            if not dir_path.exists():
                continue
            
            skill_path = dir_path / name
            skill_file = skill_path / "SKILL.md"
            
            if skill_file.exists():
                with open(skill_file, "w", encoding="utf-8") as f:
                    f.write(new_content)
                
                return ToolOutput(
                    success=True,
                    result=f"Edited skill '{name}'",
                    metadata={"name": name}
                )
        
        return ToolOutput(
            success=False,
            result=None,
            error=f"Skill '{name}' not found"
        )

    async def _delete_skill(self, name: str) -> ToolOutput:
        """Delete a skill"""
        # Check all skill directories
        for dir_path in DEFAULT_SKILL_DIRS:
            if not dir_path.exists():
                continue
            
            skill_path = dir_path / name
            
            if skill_path.exists() and skill_path.is_dir():
                import shutil
                shutil.rmtree(skill_path)
                return ToolOutput(
                    success=True,
                    result=f"Deleted skill '{name}'",
                    metadata={"name": name}
                )
        
        return ToolOutput(
            success=False,
            result=None,
            error=f"Skill '{name}' not found"
        )

    async def _activate_skill(self, name: str) -> ToolOutput:
        """Activate a skill for use in the current session"""
        try:
            from core.skills import SkillManager
            skill_manager = SkillManager()
            success, message, content = skill_manager.activate_skill(name)

            if not success:
                return ToolOutput(
                    success=False,
                    result=None,
                    error=message
                )

            # Store skill content in the tool registry's context for the agent to access
            if self.tool_registry and hasattr(self.tool_registry, 'active_skills'):
                self.tool_registry.active_skills[name] = content or ""

            return ToolOutput(
                success=True,
                result=message,
                metadata={"skill": name, "content_length": len(content) if content else 0}
            )

        except Exception as e:
            return ToolOutput(
                success=False,
                result=None,
                error=f"Failed to activate skill: {str(e)}"
            )