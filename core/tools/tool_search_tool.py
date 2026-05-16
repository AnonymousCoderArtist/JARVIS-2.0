"""ToolSearchTool for searching and discovering available tools

Inspired by openclaude's ToolSearchTool implementation.
Provides keyword search over tool names, descriptions, and search hints.
"""

from __future__ import annotations

import re
from typing import Any

from pydantic import Field

from core.tools.base import BaseTool, ToolInput, ToolOutput


class ToolSearchInput(ToolInput):
    """Input schema for ToolSearchTool"""

    query: str = Field(..., description="Query to find tools")
    max_results: int = Field(5, description="Maximum number of results to return")


class ToolSearchOutput(ToolOutput):
    """Output schema for ToolSearchTool"""

    matches: list[str] = []
    total_tools: int = 0
    pending_mcp_servers: list[str] | None = None


class ToolSearchTool(BaseTool):
    """Tool for searching and discovering available tools

    Supports:
    - Keyword search: "read file", "notebook"
    - Direct selection: "select:Read,Edit"
    - Required terms: "+slack send"
    - MCP tool prefix: "mcp__server"
    """

    name: str = "ToolSearch"
    description: str = (
        "Search for available tools by name, description, or keywords. "
        "Use 'select:Tool1,Tool2' for direct selection, or keywords like "
        "'read file' or '+slack message' to search."
    )
    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query or select:tool_name syntax",
            },
            "max_results": {
                "type": "integer",
                "default": 5,
                "description": "Maximum number of results",
            },
        },
        "required": ["query"],
    }

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._description_cache: dict[str, str] = {}

    async def execute(self, input_data: ToolInput) -> ToolOutput:
        """Execute the tool search"""
        if not self.tool_registry:
            return ToolSearchOutput(
                success=False,
                result=None,
                error="Tool registry not available",
                matches=[],
                total_tools=0,
            )

        tools = self.tool_registry.get_tools()
        all_tools = list(tools.values())

        # Get MCP server status
        pending_servers = self._get_pending_mcp_servers()

        # Parse input - ToolInput allows extra fields
        query = input_data.query or ""
        max_results = input_data.model_extra.get("max_results", 5) if input_data.model_extra else 5
        if not isinstance(max_results, int):
            max_results = 5

        # Check for select: prefix
        select_match = re.match(r"^select:(.+)$", query, re.IGNORECASE)
        if select_match:
            matches = await self._handle_select(select_match.group(1), all_tools)
            return ToolSearchOutput(
                success=True,
                result=None,
                matches=matches,
                total_tools=len(all_tools),
                pending_mcp_servers=pending_servers if pending_servers else None,
            )

        # Keyword search
        matches = await self._search_tools(query, all_tools, max_results)

        return ToolSearchOutput(
            success=True,
            result=None,
            matches=matches,
            total_tools=len(all_tools),
            pending_mcp_servers=pending_servers if pending_servers else None,
        )

    async def _handle_select(
        self, query: str, tools: list[BaseTool]
    ) -> list[str]:
        """Handle select: prefix for direct tool selection"""
        requested = [s.strip() for s in query.split(",") if s.strip()]
        found = []

        for tool_name in requested:
            matching = next(
                (t for t in tools if t.name.lower() == tool_name.lower()), None
            )
            if matching and matching.name not in found:
                found.append(matching.name)

        return found

    async def _search_tools(
        self, query: str, tools: list[BaseTool], max_results: int
    ) -> list[str]:
        """Keyword search over tools"""
        query_lower = query.lower().strip()

        # Fast path: exact match
        exact_match = next(
            (t for t in tools if t.name.lower() == query_lower), None
        )
        if exact_match:
            return [exact_match.name]

        # Parse query terms
        terms = query_lower.split()
        required_terms = [t[1:] for t in terms if t.startswith("+") and len(t) > 1]
        optional_terms = [t for t in terms if not t.startswith("+")]

        # Score tools
        scored = []
        for tool in tools:
            score = await self._score_tool(tool, required_terms, optional_terms)
            if score > 0:
                scored.append((tool.name, score))

        # Sort by score descending
        scored.sort(key=lambda x: x[1], reverse=True)
        return [name for name, _ in scored[:max_results]]

    async def _score_tool(
        self, tool: BaseTool, required_terms: list[str], optional_terms: list[str]
    ) -> int:
        """Score a tool based on search terms"""
        all_terms = required_terms + optional_terms
        if not all_terms:
            return 0

        score = 0
        name_lower = tool.name.lower()
        description = tool.description.lower()
        search_hint = getattr(tool, "search_hint", "") or ""
        hint_lower = search_hint.lower()

        # Parse tool name for MCP tools
        parsed = self._parse_tool_name(tool.name)

        for term in all_terms:
            # Name match (high weight)
            if term in parsed["parts"]:
                score += 10
            elif term in name_lower:
                score += 5

            # Description match (lower weight)
            if term in description:
                score += 2

            # Search hint match
            if term in hint_lower:
                score += 4

        # Check required terms are all present
        if required_terms:
            for req in required_terms:
                if req not in name_lower and req not in description:
                    return 0

        return score

    def _parse_tool_name(self, name: str) -> dict[str, Any]:
        """Parse tool name into searchable parts"""
        parts = []
        full = name.lower()

        # MCP tool format: mcp_server_action (note: uses single underscore, not double)
        if name.startswith("mcp_"):
            without_prefix = name[4:].lower()
            parts = [p for p in without_prefix.split("_") if p]
            full = without_prefix.replace("_", " ")
        else:
            # Regular tool: split by CamelCase and underscores
            split_name = re.sub(r"([a-z])([A-Z])", r"\1 \2", name)
            parts = [p for p in split_name.lower().split("_") if p]
            full = " ".join(parts)

        return {"parts": parts, "full": full}

    def _get_pending_mcp_servers(self) -> list[str]:
        """Get list of pending MCP server names"""
        pending = []
        if self.tool_registry:
            for tool in self.tool_registry.get_tools().values():
                if getattr(tool, "is_mcp", False):
                    status = getattr(tool, "mcp_status", None)
                    if status == "pending":
                        server_name = getattr(tool, "mcp_server_name", "")
                        if server_name and server_name not in pending:
                            pending.append(server_name)
        return pending


# Tool name constant for consistency
TOOL_SEARCH_TOOL_NAME = ToolSearchTool.name
