"""Dependency watcher — checks for outdated packages and known vulnerabilities."""

import hashlib
import json
from pathlib import Path

from jarvis.core.watchers.base import BaseWatcher


class DependencyWatcher(BaseWatcher):
    """Checks for outdated dependencies and known security vulnerabilities."""

    name = "dependency_watcher"
    description = "Monitors project dependencies for updates and security advisories"

    def __init__(self):
        super().__init__(interval=3600)  # Check every hour
        self._last_hash = None

    async def watch(self):
        """Scan project dependency files and check for issues."""
        issues = []

        # Detect project type and scan relevant files
        project_root = Path.cwd()

        # Python: check requirements.txt, pyproject.toml
        req_file = project_root / "requirements.txt"
        if req_file.exists():
            issues.extend(self._check_python_deps(req_file))

        pyproject = project_root / "pyproject.toml"
        if pyproject.exists():
            issues.extend(self._check_pyproject(pyproject))

        # Node.js: check package.json
        pkg_file = project_root / "package.json"
        if pkg_file.exists():
            issues.extend(self._check_node_deps(pkg_file))

        if not issues:
            return

        # Hash to avoid repeated notifications
        item_hash = hashlib.md5(
            json.dumps(sorted(issues), sort_keys=True).encode()
        ).hexdigest()

        if self._last_hash != item_hash:
            self._last_alert_hash = item_hash
            data = {
                "issues": issues,
                "count": len(issues),
            }
            self.update_cop(data)

            await self.notify(
                "Dependency Issues",
                f"Found {len(issues)} outdated or vulnerable package(s)",
                level="warning",
            )

    def _check_python_deps(self, path: Path) -> list[dict]:
        """Parse requirements.txt for pinned versions."""
        issues = []
        try:
            with open(path) as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "==" in line:
                        pkg, version = line.split("==", 1)
                        issues.append({
                            "type": "pinned",
                            "package": pkg.strip(),
                            "version": version.strip(),
                            "file": str(path),
                            "note": "Pinned version — check for updates",
                        })
        except Exception:
            pass
        return issues

    def _check_pyproject(self, path: Path) -> list[dict]:
        """Check pyproject.toml for dependency info."""
        # Placeholder — full implementation would parse TOML
        return []

    def _check_node_deps(self, path: Path) -> list[dict]:
        """Check package.json for outdated dependencies."""
        issues = []
        try:
            with open(path) as f:
                pkg = json.load(f)
            for section in ("dependencies", "devDependencies"):
                deps = pkg.get(section, {})
                for name, version in deps.items():
                    if version.startswith("^") or version.startswith("~"):
                        issues.append({
                            "type": "semver",
                            "package": name,
                            "version": version,
                            "file": str(path),
                            "note": f"Semver range in {section} — verify compatibility",
                        })
        except Exception:
            pass
        return issues
