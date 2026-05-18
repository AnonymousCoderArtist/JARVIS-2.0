"""ExtensionRegistry — tracks all loaded extensions and their metadata."""

from __future__ import annotations

import logging
from typing import Any

from jarvis.core.extensions.types import ExtensionManifest

logger = logging.getLogger(__name__)


class ExtensionRegistry:
    """Central registry for tracking loaded extensions.

    Maintains a ``name → ExtensionManifest`` mapping and provides
    introspection for conflict detection and diagnostics.
    """

    def __init__(self) -> None:
        self._extensions: dict[str, ExtensionManifest] = {}
        self._agents: dict[str, Any] = {}
        # Maps extension_name -> {tool_name: tool_instance} for private tools
        self._private_tools: dict[str, dict[str, Any]] = {}
        # Maps agent_name -> extension_name for reverse lookup
        self._agent_owners: dict[str, str] = {}

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(self, manifest: ExtensionManifest) -> None:
        """Add or update an extension in the registry."""
        self._extensions[manifest.name] = manifest

    def unregister(self, name: str) -> None:
        """Remove an extension from the registry."""
        self._extensions.pop(name, None)
        self._private_tools.pop(name, None)

    def clear(self) -> None:
        """Remove ALL extensions.  Called during session teardown."""
        self._extensions.clear()
        self._agents.clear()
        self._private_tools.clear()
        self._agent_owners.clear()

    # ------------------------------------------------------------------
    # Private tools (extension-scoped, not in global ToolRegistry)
    # ------------------------------------------------------------------

    def register_private_tools(self, extension_name: str, tools: dict[str, Any]) -> None:
        """Store extension-private tools that are NOT registered globally.

        These tools are only visible to the extension's own agent(s).
        """
        self._private_tools[extension_name] = tools

    def get_private_tools(self, extension_name: str) -> dict[str, Any]:
        """Return extension-private tools for *extension_name*."""
        return self._private_tools.get(extension_name, {})

    def get_private_tools_for_agent(self, agent_name: str) -> dict[str, Any]:
        """Return private tools for the extension that owns *agent_name*."""
        owner = self._agent_owners.get(agent_name)
        if owner:
            return self.get_private_tools(owner)
        return {}

    # ------------------------------------------------------------------
    # Agent registration
    # ------------------------------------------------------------------

    def register_agent(self, extension_name: str, definition: Any) -> None:
        """Register an agent definition from an extension.

        Stores the agent under its name and tracks which extension owns it.
        """
        self._agents[definition.name] = definition
        self._agent_owners[definition.name] = extension_name

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
