"""Skill manager for dynamic skill loading and execution"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from core.agents.cowork.config.settings import CoworkConfig


class SkillManager:
    """Manages loading and executing skills from .md and .json files"""

    def __init__(self, config: CoworkConfig | None = None):
        if config is None:
            config = CoworkConfig()
        self.config = config
        self._skills: dict[str, dict[str, Any]] = {}

    async def load_skills(self, directory: str | None = None) -> int:
        """
        Load all skills from the specified directory.

        Args:
            directory: Directory path to load skills from

        Returns:
            Number of skills loaded
        """
        target_dir = Path(directory or self.config.skills_dir).expanduser()
        if not target_dir.is_absolute():
            target_dir = Path.cwd() / target_dir

        if not target_dir.exists():
            target_dir.mkdir(parents=True, exist_ok=True)
            return 0

        count = 0
        for ext in ("*.md", "*.json"):
            for file_path in target_dir.glob(ext):
                try:
                    skill = await self._load_skill_file(file_path)
                    if skill:
                        self._skills[skill["name"]] = skill
                        count += 1
                except Exception:
                    continue

        return count

    async def _load_skill_file(self, file_path: Path) -> dict[str, Any] | None:
        """Load a single skill file (.md or .json)"""
        content = file_path.read_text(encoding="utf-8")

        if file_path.suffix == ".json":
            data = json.loads(content)
            return {
                "name": data.get("name", file_path.stem),
                "description": data.get("description", ""),
                "content": data.get("content", ""),
                "type": data.get("type", "custom"),
                "parameters": data.get("parameters", {}),
            }

        # Parse markdown skill files
        name = file_path.stem
        description = ""
        content = content

        lines = content.split("\n")
        if lines and lines[0].startswith("# "):
            name = lines[0][2:].strip()
            lines = lines[1:]

        if lines and lines[0].startswith("> "):
            description = lines[0][2:].strip()
            lines = lines[1:]

        return {
            "name": name,
            "description": description,
            "content": "\n".join(lines),
            "type": "markdown",
            "parameters": {},
        }

    def get_skill(self, name: str) -> dict[str, Any] | None:
        """Retrieve a skill by name"""
        return self._skills.get(name)

    def list_skills(self) -> list[dict[str, Any]]:
        """List all loaded skills"""
        return list(self._skills.values())

    async def execute_skill(
        self, name: str, context: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """
        Execute a skill by name with optional context.

        Args:
            name: Skill name to execute
            context: Optional context variables to pass to the skill

        Returns:
            Execution result dictionary
        """
        skill = self._skills.get(name)
        if not skill:
            return {
                "success": False,
                "error": f"Skill '{name}' not found",
            }

        try:
            # For now, return the skill content for LLM processing
            # Future: support actual code execution
            return {
                "success": True,
                "skill": skill,
                "context": context or {},
                "message": f"Skill '{name}' loaded successfully",
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }

    async def reload_skills(self) -> int:
        """Reload all skills from the skills directory"""
        self._skills.clear()
        return await self.load_skills()

    @property
    def skill_count(self) -> int:
        """Number of loaded skills"""
        return len(self._skills)