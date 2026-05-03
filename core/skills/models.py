"""Skill models and profiles for dynamic skill management"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class SkillProfile:
    """Profile for a skill with metadata and configuration"""
    name: str
    display_name: str
    description: str
    when_to_use: str
    when_not_to_use: str
    file_path: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    user_invocable: bool = True

    @classmethod
    def from_file(cls, path: Path) -> SkillProfile:
        """Load skill profile from a skill directory following agentskills.io standard"""
        import yaml
        import re

        # Try to read SKILL.md file
        skill_file = path / "SKILL.md"
        if not skill_file.exists():
            raise FileNotFoundError(f"Skill file not found: {skill_file}")

        with open(skill_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # Parse YAML frontmatter
        frontmatter = {}
        # Regex to find content between --- marks
        match = re.search(r'^---\s*\n(.*?)\n---\s*\n', content, re.DOTALL)
        if match:
            try:
                frontmatter = yaml.safe_load(match.group(1))
            except yaml.YAMLError:
                pass

        name = frontmatter.get("name", path.stem)
        display_name = frontmatter.get("display_name", name.replace("-", " ").title())
        description = frontmatter.get("description", "No description provided.")
        when_to_use = frontmatter.get("when_to_use", "As specified in skill documentation.")
        when_not_to_use = frontmatter.get("when_not_to_use", "For general tasks not requiring this expertise.")

        return cls(
            name=name,
            display_name=display_name,
            description=description,
            when_to_use=when_to_use,
            when_not_to_use=when_not_to_use,
            file_path=str(skill_file),
            metadata=frontmatter
        )


# No built-in skills - all skills are loaded dynamically from file system
BUILTIN_SKILLS: dict[str, SkillProfile] = {}
