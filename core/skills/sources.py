"""Skill source connectors for installing skills from various sources."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

import httpx


class SkillSource:
    """Base class for skill sources."""

    def __init__(self, name: str):
        self.name = name

    def install(self, skill_id: str, dest_dir: Path) -> tuple[bool, str, dict[str, Any]]:
        """Install a skill from this source.
        
        Returns:
            (success, message, metadata) tuple
        """
        raise NotImplementedError


class HermesSource(SkillSource):
    """Install skills from Hermes Agent catalog (hermes-agent/hermes)."""

    BASE_URL = "https://raw.githubusercontent.com/NousResearch/hermes-agent/main"

    def __init__(self):
        super().__init__("hermes")
        self._skill_index: dict[str, dict[str, Any]] | None = None

    def _fetch_index(self) -> dict[str, dict[str, Any]]:
        """Fetch the skill index from Hermes repository."""
        if self._skill_index is not None:
            return self._skill_index

        try:
            with httpx.Client(timeout=30.0) as client:
                resp = client.get(f"{self.BASE_URL}/skills/skills_index.json")
                if resp.status_code == 200:
                    self._skill_index = resp.json()
                    return self._skill_index
        except Exception:
            pass

        # Fallback: minimal index
        return {
            "code-explainer": {"file": "code_explainer"},
            "debug-helper": {"file": "debug_helper"},
            "refactor-assistant": {"file": "refactor_assistant"},
        }

    def install(self, skill_id: str, dest_dir: Path) -> tuple[bool, str, dict[str, Any]]:
        """Install a skill from Hermes catalog."""
        index = self._fetch_index()
        
        if skill_id not in index:
            return False, f"Skill '{skill_id}' not found in Hermes catalog", {}

        skill_info = index[skill_id]
        skill_file = skill_info.get("file", skill_id)
        
        try:
            with httpx.Client(timeout=30.0) as client:
                resp = client.get(f"{self.BASE_URL}/skills/{skill_file}.md")
                if resp.status_code != 200:
                    return False, f"Failed to fetch skill: HTTP {resp.status_code}", {}

                content = resp.text

            # Create skill directory
            skill_dir = dest_dir / skill_id
            skill_dir.mkdir(parents=True, exist_ok=True)

            # Write SKILL.md
            skill_file_path = skill_dir / "SKILL.md"
            skill_file_path.write_text(content)

            return True, f"Installed skill '{skill_id}' from Hermes", {
                "source": "hermes",
                "file": str(skill_file_path),
            }
        except Exception as e:
            return False, f"Failed to install skill: {e}", {}


class OpenClawSource(SkillSource):
    """Install skills from OpenClaw community catalog."""

    BASE_URL = "https://openclaw.github.io/skills"

    def __init__(self):
        super().__init__("openclaw")

    def install(self, skill_id: str, dest_dir: Path) -> tuple[bool, str, dict[str, Any]]:
        """Install a skill from OpenClaw catalog."""
        try:
            with httpx.Client(timeout=30.0) as client:
                # Try to get skill metadata
                resp = client.get(f"{self.BASE_URL}/api/skills/{skill_id}")
                if resp.status_code == 404:
                    return False, f"Skill '{skill_id}' not found in OpenClaw catalog", {}

                if resp.status_code != 200:
                    return False, f"API error: HTTP {resp.status_code}", {}

                skill_data = resp.json()

            # Create skill directory
            skill_dir = dest_dir / skill_id
            skill_dir.mkdir(parents=True, exist_ok=True)

            # Write SKILL.md
            content = skill_data.get("content", "# Skill not available")
            skill_file_path = skill_dir / "SKILL.md"
            skill_file_path.write_text(content)

            return True, f"Installed skill '{skill_id}' from OpenClaw", {
                "source": "openclaw",
                "file": str(skill_file_path),
            }
        except Exception as e:
            return False, f"Failed to install skill: {e}", {}


class GitHubSource(SkillSource):
    """Install skills from any GitHub repository."""

    def __init__(self):
        super().__init__("github")

    def install(self, skill_id: str, dest_dir: Path) -> tuple[bool, str, dict[str, Any]]:
        """Install a skill from a GitHub repository.
        
        skill_id format: owner/repo or owner/repo/path/to/skill
        """
        parts = skill_id.split("/")
        if len(parts) < 2:
            return False, "Invalid GitHub spec. Use: owner/repo or owner/repo/path", {}

        owner, repo = parts[0], parts[1]
        skill_path = "/".join(parts[2:]) if len(parts) > 2 else ""

        try:
            with httpx.Client(timeout=30.0) as client:
                # Get repo contents
                api_url = f"https://api.github.com/repos/{owner}/{repo}/contents"
                if skill_path:
                    api_url += f"/{skill_path}"
                
                resp = client.get(api_url)
                if resp.status_code == 404:
                    return False, f"Repository or path not found: {owner}/{repo}", {}

                if resp.status_code != 200:
                    return False, f"GitHub API error: HTTP {resp.status_code}", {}

                contents = resp.json()

            # Handle single file or directory
            if isinstance(contents, dict):
                # Single file
                skill_name = Path(skill_path).stem if skill_path else repo
                dest_skill_dir = dest_dir / skill_name
                dest_skill_dir.mkdir(parents=True, exist_ok=True)
                
                # Download the file
                download_url = contents.get("download_url") or contents.get("html_url")
                if download_url:
                    resp = client.get(download_url)
                    (dest_skill_dir / "SKILL.md").write_text(resp.text)
                    return True, f"Installed skill from {owner}/{repo}", {
                        "source": "github",
                        "file": str(dest_skill_dir / "SKILL.md"),
                    }
                return False, "Could not download file", {}

            else:
                # Directory - find SKILL.md files
                skill_name = skill_path or repo
                dest_skill_dir = dest_dir / skill_name
                dest_skill_dir.mkdir(parents=True, exist_ok=True)

                for item in contents:
                    if item["name"].endswith(".md"):
                        resp = client.get(item["download_url"])
                        (dest_skill_dir / item["name"]).write_text(resp.text)

                return True, f"Installed skills from {owner}/{repo}", {
                    "source": "github",
                    "directory": str(dest_skill_dir),
                }

        except Exception as e:
            return False, f"Failed to install from GitHub: {e}", {}


class LocalSource(SkillSource):
    """Install skills from local files or directories."""

    def __init__(self):
        super().__init__("local")

    def install(self, skill_id: str, dest_dir: Path) -> tuple[bool, str, dict[str, Any]]:
        """Install a skill from a local path."""
        src_path = Path(skill_id).expanduser().resolve()
        
        if not src_path.exists():
            return False, f"Local path not found: {skill_id}", {}

        try:
            if src_path.is_file():
                # Single file
                skill_name = src_path.stem
                dest_skill_dir = dest_dir / skill_name
                dest_skill_dir.mkdir(parents=True, exist_ok=True)
                (dest_skill_dir / "SKILL.md").write_text(src_path.read_text())
                return True, f"Installed skill from {skill_id}", {
                    "source": "local",
                    "file": str(dest_skill_dir / "SKILL.md"),
                }
            else:
                # Directory
                skill_name = src_path.name
                dest_skill_dir = dest_dir / skill_name
                dest_skill_dir.mkdir(parents=True, exist_ok=True)
                
                import shutil
                for item in src_path.iterdir():
                    if item.is_file():
                        shutil.copy2(item, dest_skill_dir / item.name)
                
                return True, f"Installed skill from {skill_id}", {
                    "source": "local",
                    "directory": str(dest_skill_dir),
                }
        except Exception as e:
            return False, f"Failed to install from local path: {e}", {}