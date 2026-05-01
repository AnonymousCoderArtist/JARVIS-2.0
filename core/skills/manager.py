"""Skill manager for dynamic skill loading and management"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from .models import SkillProfile, BUILTIN_SKILLS


class SkillManager:
    """Manager for loading and managing skills dynamically"""

    def __init__(self):
        self._loaded_skills: dict[str, SkillProfile] = {}
        self._skill_content: dict[str, str] = {}
        self._skill_paths = [
            Path(os.path.expanduser("~/.claude/skills")),
            Path(os.path.expanduser("~/.agents/skills")),
            Path(".devin/skills"),
        ]

    def get_builtin_skills(self) -> dict[str, SkillProfile]:
        """Get all built-in skill profiles"""
        return BUILTIN_SKILLS.copy()

    def get_skill_profile(self, skill_name: str) -> SkillProfile | None:
        """Get a skill profile by name"""
        # Check built-in skills first
        if skill_name in BUILTIN_SKILLS:
            return BUILTIN_SKILLS[skill_name]

        # Check dynamically loaded skills
        if skill_name in self._loaded_skills:
            return self._loaded_skills[skill_name]

        # Try to load from file system
        return self._load_skill_from_filesystem(skill_name)

    def get_skill_content(self, skill_name: str) -> str | None:
        """Get the content of a skill"""
        if skill_name in self._skill_content:
            return self._skill_content[skill_name]

        # Try to load from file system
        skill_profile = self.get_skill_profile(skill_name)
        if skill_profile and skill_profile.file_path:
            try:
                with open(skill_profile.file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                self._skill_content[skill_name] = content
                return content
            except Exception:
                return None

        return None

    def get_all_available_skills(self) -> dict[str, SkillProfile]:
        """Get all available skills (built-in + dynamically loaded)"""
        skills = BUILTIN_SKILLS.copy()

        # Load skills from file system
        for skill_path in self._skill_paths:
            if skill_path.exists():
                for skill_dir in skill_path.iterdir():
                    if skill_dir.is_dir():
                        skill_name = skill_dir.name
                        if skill_name not in skills:
                            try:
                                profile = SkillProfile.from_file(skill_dir)
                                skills[skill_name] = profile
                                self._loaded_skills[skill_name] = profile
                            except Exception:
                                continue

        return skills

    def get_skill_descriptions_for_prompt(self) -> str:
        """Generate skill descriptions for system prompt"""
        skills = self.get_all_available_skills()
        if not skills:
            return ""

        sections = []
        for skill_name, profile in skills.items():
            section = f"""
### {profile.display_name} ({skill_name})
- **When to use**: {profile.when_to_use}
- **When NOT to use**: {profile.when_not_to_use}
- **Description**: {profile.description}
"""
            sections.append(section)

        return "## Available Skills\n\n" + "\n".join(sections)

    def _load_skill_from_filesystem(self, skill_name: str) -> SkillProfile | None:
        """Try to load a skill from the file system"""
        for skill_path in self._skill_paths:
            skill_dir = skill_path / skill_name
            if skill_dir.exists() and skill_dir.is_dir():
                try:
                    profile = SkillProfile.from_file(skill_dir)
                    self._loaded_skills[skill_name] = profile
                    return profile
                except Exception:
                    continue
        return None

    def is_skill_available(self, skill_name: str) -> bool:
        """Check if a skill is available"""
        return self.get_skill_profile(skill_name) is not None

    def activate_skill(self, skill_name: str) -> tuple[bool, str, str | None]:
        """
        Activate a skill and return (success, message, content)

        Returns:
            (success, message, content) tuple
        """
        profile = self.get_skill_profile(skill_name)
        if not profile:
            return False, f"Skill '{skill_name}' not found", None

        content = self.get_skill_content(skill_name)
        if not content:
            return False, f"Skill '{skill_name}' content could not be loaded", None

        self._skill_content[skill_name] = content
        return True, f"Activated skill: {profile.display_name}", content
