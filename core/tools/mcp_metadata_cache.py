"""MCP Metadata Cache for lazy tool discovery.

Stores tool definitions from MCP servers in a local JSON cache so tools
can be discovered/searched without live server connections.

Inspired by pi-mcp-adapter's metadata caching system.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

CACHE_DIR = Path.home() / ".jarvis"
CACHE_FILE = CACHE_DIR / "mcp-cache.json"


@dataclass
class ToolMetadata:
    """Metadata for a single MCP tool."""

    name: str  # Prefixed name: "mcp_servername_toolname"
    original_name: str  # Original MCP tool name
    description: str
    input_schema: dict[str, Any]
    server_name: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ToolMetadata:
        return cls(
            name=data["name"],
            original_name=data["original_name"],
            description=data.get("description", ""),
            input_schema=data.get("input_schema", {}),
            server_name=data.get("server_name", ""),
        )


@dataclass
class ServerMetadata:
    """Metadata for an MCP server including its tools."""

    name: str
    tools: list[ToolMetadata]
    cached_at: float
    config_hash: str  # Hash of server config for validation

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "tools": [t.to_dict() for t in self.tools],
            "cached_at": self.cached_at,
            "config_hash": self.config_hash,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ServerMetadata:
        return cls(
            name=data["name"],
            tools=[ToolMetadata.from_dict(t) for t in data.get("tools", [])],
            cached_at=data.get("cached_at", 0.0),
            config_hash=data.get("config_hash", ""),
        )


def compute_config_hash(config_dict: dict[str, Any]) -> str:
    """Compute a hash of relevant server config fields for cache validation."""
    relevant_keys = ["command", "args", "url", "transport", "env"]
    relevant = {k: config_dict.get(k) for k in relevant_keys if k in config_dict}
    raw = json.dumps(relevant, sort_keys=True)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


class MCPMetadataCache:
    """Persistent cache of MCP tool metadata for discovery without live connections."""

    def __init__(self, cache_path: Path | None = None):
        self._cache_path = cache_path or CACHE_FILE
        self._servers: dict[str, ServerMetadata] = {}
        self._load()

    def _load(self) -> None:
        """Load cache from disk."""
        if not self._cache_path.exists():
            self._servers = {}
            return

        try:
            data = json.loads(self._cache_path.read_text(encoding="utf-8"))
            self._servers = {
                name: ServerMetadata.from_dict(sdata)
                for name, sdata in data.get("servers", {}).items()
            }
        except Exception as e:
            logger.warning(f"Failed to load MCP metadata cache: {e}")
            self._servers = {}

    def save(self) -> None:
        """Save cache to disk."""
        try:
            self._cache_path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "servers": {
                    name: smeta.to_dict() for name, smeta in self._servers.items()
                },
                "version": 1,
            }
            self._cache_path.write_text(
                json.dumps(data, indent=2), encoding="utf-8"
            )
        except Exception as e:
            logger.error(f"Failed to save MCP metadata cache: {e}")

    def get_server(self, name: str) -> ServerMetadata | None:
        """Get metadata for a server."""
        return self._servers.get(name)

    def get_tool(self, server: str, tool_name: str) -> ToolMetadata | None:
        """Get a specific tool's metadata."""
        smeta = self._servers.get(server)
        if not smeta:
            return None
        for tool in smeta.tools:
            if tool.original_name == tool_name or tool.name == tool_name:
                return tool
        return None

    def get_tool_by_prefixed_name(self, prefixed_name: str) -> ToolMetadata | None:
        """Get a tool by its prefixed name (e.g. 'mcp_server_tool')."""
        for smeta in self._servers.values():
            for tool in smeta.tools:
                if tool.name == prefixed_name:
                    return tool
        return None

    def search_tools(
        self,
        query: str,
        server: str | None = None,
        regex: bool = False,
        include_schemas: bool = True,
    ) -> list[ToolMetadata]:
        """Search for tools by name/description.

        Args:
            query: Search string.
            server: Optional server name to filter by.
            regex: If True, treat query as regex pattern.
            include_schemas: If True, include input schemas in results.

        Returns:
            List of matching ToolMetadata.
        """
        matches: list[ToolMetadata] = []
        servers_to_search = (
            {server: self._servers[server]} if server and server in self._servers else self._servers
        )

        if regex:
            try:
                pattern = re.compile(query, re.IGNORECASE)
            except re.error:
                pattern = re.compile(re.escape(query), re.IGNORECASE)
        else:
            pattern = re.compile(re.escape(query), re.IGNORECASE)

        for smeta in servers_to_search.values():
            for tool in smeta.tools:
                if pattern.search(tool.name) or pattern.search(tool.description) or pattern.search(tool.original_name):
                    matches.append(tool)

        return matches

    def list_server_tools(self, server: str) -> list[ToolMetadata]:
        """List all tools for a server."""
        smeta = self._servers.get(server)
        return smeta.tools if smeta else []

    def list_all_tools(self) -> list[ToolMetadata]:
        """List all tools across all servers."""
        tools: list[ToolMetadata] = []
        for smeta in self._servers.values():
            tools.extend(smeta.tools)
        return tools

    def is_valid(self, server_name: str, config_dict: dict[str, Any]) -> bool:
        """Check if cached metadata matches current server configuration."""
        smeta = self._servers.get(server_name)
        if not smeta:
            return False
        return smeta.config_hash == compute_config_hash(config_dict)

    def update_server(self, name: str, tools: list[ToolMetadata], config_dict: dict[str, Any]) -> None:
        """Update cache for a server with fresh tool metadata."""
        self._servers[name] = ServerMetadata(
            name=name,
            tools=tools,
            cached_at=time.time(),
            config_hash=compute_config_hash(config_dict),
        )
        self.save()

    def remove_server(self, name: str) -> None:
        """Remove a server's cache entry."""
        self._servers.pop(name, None)
        self.save()

    @property
    def server_names(self) -> list[str]:
        """Get all cached server names."""
        return list(self._servers.keys())

    @property
    def total_tools(self) -> int:
        """Get total number of cached tools."""
        return sum(len(s.tools) for s in self._servers.values())
