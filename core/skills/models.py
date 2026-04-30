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

    @classmethod
    def from_file(cls, path: Path) -> SkillProfile:
        """Load skill profile from a skill directory"""
        # Try to read SKILL.md file
        skill_file = path / "SKILL.md"
        if not skill_file.exists():
            raise FileNotFoundError(f"Skill file not found: {skill_file}")

        with open(skill_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # Extract metadata from content (you can enhance this with proper parsing)
        display_name = path.stem.replace("-", " ").title()
        description = content[:200] + "..." if len(content) > 200 else content

        return cls(
            name=path.stem,
            display_name=display_name,
            description=description,
            when_to_use="As specified in skill documentation",
            when_not_to_use="For general tasks not requiring this expertise",
            file_path=str(skill_file),
            metadata={"content_length": len(content)}
        )


# No built-in skills - all skills are loaded dynamically from file system
BUILTIN_SKILLS: dict[str, SkillProfile] = {}
