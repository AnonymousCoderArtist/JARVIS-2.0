"""Cowork Agent configuration settings"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class CoworkConfig:
    """Configuration settings for the Cowork Agent"""

    max_iterations: int = 100
    timeout_per_action: int = 60
    sandbox_enabled: bool = True
    memory_retention_days: int = 7
    allowed_paths: list[str] = field(default_factory=list)
    auto_approve: bool = False

    # Task scheduling
    max_concurrent_tasks: int = 5
    task_timeout: int = 300

    # Memory settings
    max_memory_entries: int = 1000
    memory_cleanup_interval: int = 60

    # Skill settings
    skills_dir: str = "~/.jarvis/cowork/skills"
    auto_load_skills: bool = True

    # Sandbox settings
    sandbox_backend: str = "opensandbox"
    sandbox_base_url: str = "http://localhost:8080"

    @property
    def resolved_allowed_paths(self) -> list[Path]:
        """Resolve allowed paths to absolute Path objects"""
        return [Path(p).resolve() for p in self.allowed_paths]

    @property
    def resolved_skills_dir(self) -> Path:
        """Resolve skills directory to absolute Path"""
        path = Path(self.skills_dir).expanduser()
        if not path.is_absolute():
            path = Path.cwd() / path
        return path