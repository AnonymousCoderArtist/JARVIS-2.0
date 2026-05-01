"""Agent profile system with safety levels"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from enum import StrEnum, auto
from pathlib import Path
from typing import Any


class AgentSafety(StrEnum):
    """Safety levels for agent profiles"""
    SAFE = auto()
    NEUTRAL = auto()
    DESTRUCTIVE = auto()
    YOLO = auto()


class AgentType(StrEnum):
    """Types of agents"""
    AGENT = auto()
    SUBAGENT = auto()


@dataclass(frozen=True)
class AgentProfile:
    """Profile defining agent behavior and safety level"""

    name: str
    display_name: str
    description: str
    safety: AgentSafety
    agent_type: AgentType = AgentType.AGENT
    overrides: dict[str, Any] = field(default_factory=dict)

    def apply_to_config(self, base_config: dict) -> dict:
        """
        Apply profile overrides to base configuration

        Args:
            base_config: Base configuration dictionary

        Returns:
            Merged configuration dictionary
        """
        result = base_config.copy()

        # Deep merge overrides
        for key, value in self.overrides.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = {**result[key], **value}
            else:
                result[key] = value

        return result

    @classmethod
    def from_toml(cls, path: str) -> AgentProfile:
        """
        Load agent profile from TOML file

        Args:
            path: Path to TOML file

        Returns:
            AgentProfile instance
        """
        with Path(path).open("rb") as f:
            data = tomllib.load(f)

        return cls(
            name=Path(path).stem,
            display_name=data.pop("display_name", Path(path).stem.replace("-", " ").title()),
            description=data.pop("description", ""),
            safety=AgentSafety(data.pop("safety", AgentSafety.NEUTRAL)),
            agent_type=AgentType(data.pop("agent_type", AgentType.AGENT)),
            overrides=data,
        )
