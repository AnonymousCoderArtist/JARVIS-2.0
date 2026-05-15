"""Resource Loader — discovers skills, prompts, context files, and themes across multiple tiers.

Tier precedence (lower number = higher priority)
--------------------------------------------------
0. Project explicit (paths from ``.jarvis/settings.json``)
1. Project auto-discovered (``.jarvis/`` directory)
2. User explicit (paths from ``~/.jarvis/settings.json``)
3. User auto-discovered (``~/.jarvis/`` directory)
4. Bundled/package resources

When resources with the same name exist in multiple tiers, the higher
priority one wins.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from core.prompts import PromptTemplate, load_template_from_file, load_templates_from_dir

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Context file names (case-insensitive)
CONTEXT_FILE_NAMES = {"AGENTS.md", "CLAUDE.md", "SYSTEM.md", "APPEND_SYSTEM.md"}

# Default discovery paths
USER_DIR = Path.home() / ".jarvis"
PROJECT_DIR_NAME = ".jarvis"


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class Resource:
    """A discovered resource with its tier/precedence info."""
    name: str
    type: str  # "skill", "prompt", "theme", "context_file"
    file_path: str
    tier: int  # 0-4 (lower = higher priority)
    source: str = ""  # Human-readable description, e.g. "project auto-detected"


@dataclass
class DiscoveredResources:
    """All resources discovered for a session."""
    templates: list[PromptTemplate] = field(default_factory=list)
    context_files: list[Resource] = field(default_factory=list)
    skills: list[Resource] = field(default_factory=list)
    themes: list[Resource] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Resource discovery
# ---------------------------------------------------------------------------


def discover_prompt_templates(project_dir: str | Path | None = None) -> list[PromptTemplate]:
    """Discover prompt templates from all tiers.

    Templates found in project dir override user-global ones with the same name.
    """
    seen: set[str] = set()
    templates: list[PromptTemplate] = []

    # Tier 1: Project auto-discovered (highest)
    if project_dir is not None:
        proj_prompts = Path(project_dir) / PROJECT_DIR_NAME / "prompts"
        for tpl in load_templates_from_dir(proj_prompts):
            if tpl.name not in seen:
                seen.add(tpl.name)
                templates.append(tpl)

    # Tier 3: User auto-discovered
    user_prompts = USER_DIR / "prompts"
    for tpl in load_templates_from_dir(user_prompts):
        if tpl.name not in seen:
            seen.add(tpl.name)
            templates.append(tpl)

    return templates


def discover_context_files(project_dir: str | Path | None = None) -> list[Resource]:
    """Walk up from *project_dir* to find context files (AGENTS.md, etc.).

    Returns them in order from most specific (closest to cwd) to most general
    (farthest up the tree).
    """
    resources: list[Resource] = []
    seen_paths: set[str] = set()

    if project_dir is None:
        project_dir = Path.cwd()

    # Walk up directories from project_dir to filesystem root
    current = Path(project_dir).resolve()
    while True:
        for fname in CONTEXT_FILE_NAMES:
            for actual in (current / fname, current / fname.lower()):
                if actual.exists() and actual.is_file():
                    resolved = str(actual.resolve())
                    if resolved not in seen_paths:
                        seen_paths.add(resolved)
                        resources.append(Resource(
                            name=actual.name,
                            type="context_file",
                            file_path=resolved,
                            tier=1,  # Project-level
                            source=f"discovered from {current}",
                        ))

        # Move to parent
        if current.parent == current:
            break
        current = current.parent

    # Also check user-global context files
    user_system = USER_DIR / "SYSTEM.md"
    if user_system.exists():
        resolved = str(user_system.resolve())
        if resolved not in seen_paths:
            seen_paths.add(resolved)
            resources.append(Resource(
                name="USER_SYSTEM.md",
                type="context_file",
                file_path=resolved,
                tier=3,  # User-level
                source="user global SYSTEM.md",
            ))

    return resources


def discover_skills(project_dir: str | Path | None = None) -> list[Resource]:
    """Discover skill directories from all tiers."""
    seen: set[str] = set()
    resources: list[Resource] = []

    skill_search_dirs = []
    if project_dir is not None:
        skill_search_dirs.append((Path(project_dir) / PROJECT_DIR_NAME / "skills", 1))
    skill_search_dirs.append((USER_DIR / "skills", 3))
    skill_search_dirs.append((Path.home() / ".agents" / "skills", 3))

    for dir_path, tier in skill_search_dirs:
        if not dir_path.exists():
            continue
        for item in dir_path.iterdir():
            if item.is_dir() and item.name not in seen:
                skill_file = item / "SKILL.md"
                if skill_file.exists():
                    seen.add(item.name)
                    resources.append(Resource(
                        name=item.name,
                        type="skill",
                        file_path=str(skill_file.resolve()),
                        tier=tier,
                    ))

    return resources


def discover_all(
    project_dir: str | Path | None = None,
) -> DiscoveredResources:
    """Discover all resources (skills, prompts, context files) in one call."""
    return DiscoveredResources(
        templates=discover_prompt_templates(project_dir),
        context_files=discover_context_files(project_dir),
        skills=discover_skills(project_dir),
    )


# ---------------------------------------------------------------------------
# Context file reading
# ---------------------------------------------------------------------------


def read_context_files(resources: list[Resource]) -> str:
    """Read all context file resources and return them as a formatted string."""
    if not resources:
        return ""

    sections: list[str] = []
    for res in resources:
        try:
            content = Path(res.file_path).read_text(encoding="utf-8")
            sections.append(f"<context name=\"{res.name}\" source=\"{res.source}\">\n{content}\n</context>")
        except Exception:
            logger.warning("Failed to read context file %s", res.file_path)

    if sections:
        return "\n\n".join(sections)
    return ""
