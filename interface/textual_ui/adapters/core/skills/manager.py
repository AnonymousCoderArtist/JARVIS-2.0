"""Skills manager adapter."""

from typing import Any


class SkillManager:
    """Skills manager."""
    
    def __init__(self):
        self.available_skills = {}
    
    def parse_skill_command(self, command: str) -> Any:
        """Parse skill command."""
        return None
