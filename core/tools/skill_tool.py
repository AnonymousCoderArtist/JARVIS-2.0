"""Tool for activating and using skills."""

from __future__ import annotations

from typing import Any

from core.tools.base import BaseTool, ToolInput, ToolOutput
from core.skills import SkillManager


class SkillTool(BaseTool):
    """Tool for activating and using skills in the agent."""

    name: str = "activate_skill"
    description: str = "Activate a skill to enhance the agent's capabilities. Skills provide specialized knowledge and capabilities for specific tasks."
    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "skill_name": {
                "type": "string",
                "description": "Name of the skill to activate (e.g., 'code-explainer', 'debug-helper')",
            },
        },
        "required": ["skill_name"],
    }

    def __init__(self, skill_manager: SkillManager | None = None):
        super().__init__()
        self.skill_manager = skill_manager or SkillManager()

    async def execute(self, input_data: ToolInput) -> ToolOutput:
        """Activate a skill and return its content."""
        skill_name = getattr(input_data, "skill_name", None)

        if not skill_name:
            return ToolOutput(
                success=False,
                result=None,
                error="skill_name is required",
            )

        # Check if skill is available
        profile = self.skill_manager.get_skill_profile(skill_name)
        if not profile:
            available = list(self.skill_manager.get_builtin_skills().keys())
            return ToolOutput(
                success=False,
                result=None,
                error=f"Skill '{skill_name}' not found. Available: {available}",
            )

        # Activate the skill
        success, message, content = self.skill_manager.activate_skill(skill_name)

        if not success:
            return ToolOutput(
                success=False,
                result={"skill": skill_name, "message": message},
                error=message,
            )

        # Return skill content for the agent to use
        return ToolOutput(
            success=True,
            result={
                "skill": skill_name,
                "display_name": profile.display_name,
                "description": profile.description,
                "content": content,
                "message": message,
            },
        )

    def resolve_permission(self, args: dict[str, Any]) -> Any:
        """Skills are user-invoked, no special permission needed."""
        return None