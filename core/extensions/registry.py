"""ExtensionRegistry — tracks all loaded extensions and their metadata."""

from __future__ import annotations

import logging
from typing import Any

from core.extensions.types import ExtensionManifest

logger = logging.getLogger(__name__)


class ExtensionRegistry:
    """Central registry for tracking loaded extensions.

    Maintains a ``name → ExtensionManifest`` mapping and provides
    introspection for conflict detection and diagnostics.
    """

    def __init__(self) -> None:
        self._extensions: dict[str, ExtensionManifest] = {}
        self._agents: dict[str, Any] = {}

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(self, manifest: ExtensionManifest) -> None:
        """Add or update an extension in the registry."""
        self._extensions[manifest.name] = manifest

    def unregister(self, name: str) -> None:
        """Remove an extension from the registry."""
        self._extensions.pop(name, None)

    def clear(self) -> None:
        """Remove ALL extensions.  Called during session teardown."""
        self._extensions.clear()
        self._agents.clear()

    # ------------------------------------------------------------------
    # Agent registration
    # ------------------------------------------------------------------

    def register_agent(self, definition: Any) -> None:
        """Register an agent definition from an extension."""
        self._agents[definition.name] = definition

    def get_agents(self) -> dict[str, Any]:
        """Return all registered agent definitions."""
        return self._agents.copy()

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def get(self, name: str) -> ExtensionManifest | None:
        return self._extensions.get(name)

    def list_extensions(self) -> list[ExtensionManifest]:
        return list(self._extensions.values())

    def has_extension(self, name: str) -> bool:
        return name in self._extensions

    @property
    def count(self) -> int:
        return len(self._extensions)

    def get_tool_origin(self, tool_name: str) -> str | None:
        """Return the extension name that provides *tool_name*, or ``None``."""
        for manifest in self._extensions.values():
            if tool_name in manifest.tools:
                return manifest.name
        return None

    def check_conflicts(self, tool_name: str) -> list[str]:
        """Return names of all extensions that register *tool_name*."""
        return [
            name for name, m in self._extensions.items()
            if tool_name in m.tools
        ]
