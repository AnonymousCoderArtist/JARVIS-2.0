"""MCP Proxy Tool — single tool interface for all MCP servers.

Provides a token-efficient way for the LLM to discover, search, describe,
and call tools, read resources, and render prompts from any configured MCP server.
Instead of registering dozens of individual tools (~150-300 tokens each), only one
proxy tool is registered (~200 tokens total).

Modes (in precedence order):
1. call:     tool="tool_name" args='{"key":"val"}' [server="server_name"]
2. connect:  connect="server_name"
3. describe: describe="tool_name"
4. search:   search="query" [regex=true] [include_schemas=true] [server="name"]
5. list:     server="server_name"
6. resources: resources="server_name" — list resources for a server
7. read_resource: read_resource="uri" — read a resource
8. prompts: prompts="server_name" — list prompts for a server
9. get_prompt: get_prompt="name" args='{"key":"val"}' — render a prompt
10. status:  (no args)

Inspired by pi-mcp-adapter's mcp proxy tool.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

from .base import BaseTool, ToolInput, ToolOutput

if TYPE_CHECKING:
    from .mcp_adapter import MCPRegistry

logger = logging.getLogger(__name__)


class MCPProxyTool(BaseTool):
    """Single proxy tool for all MCP servers — token-efficient interface."""

    name = "mcp"
    description = (
        "MCP proxy — discover, search, describe, and call tools; read resources; "
        "render prompts from MCP servers. "
        "Modes (by precedence): "
        "call: tool='name' args='{...}' [server='name'] — execute a tool; "
        "connect: connect='server' — lazy-connect a server; "
        "describe: describe='tool' — show tool schema; "
        "search: search='query' [regex=true] [include_schemas=true] [server='name'] — find tools; "
        "list: server='name' — list tools for a server; "
        "resources: resources='server' — list resources; "
        "read_resource: read_resource='uri' — read a resource; "
        "prompts: prompts='server' — list prompts; "
        "get_prompt: get_prompt='name' args='{...}' — render a prompt; "
        "status: (no args) — show all servers and connection status."
    )

    input_schema = {
        "type": "object",
        "properties": {
            "tool": {
                "type": "string",
                "description": "Tool name to call (triggers call mode)",
            },
            "args": {
                "type": "string",
                "description": "JSON string of arguments for tool call or prompt arguments",
            },
            "server": {
                "type": "string",
                "description": "Server name to filter by or target",
            },
            "search": {
                "type": "string",
                "description": "Search query to find tools by name/description",
            },
            "regex": {
                "type": "boolean",
                "description": "Treat search query as regex (default: false)",
            },
            "describe": {
                "type": "string",
                "description": "Tool name to describe (shows parameters)",
            },
            "connect": {
                "type": "string",
                "description": "Server name to connect (lazy connect + metadata refresh)",
            },
            "include_schemas": {
                "type": "boolean",
                "description": "Include parameter schemas in search results (default: true)",
            },
            "resources": {
                "type": "string",
                "description": "Server name to list resources from (triggers resources mode)",
            },
            "read_resource": {
                "type": "string",
                "description": "Resource URI to read (triggers read_resource mode)",
            },
            "prompts": {
                "type": "string",
                "description": "Server name to list prompts from (triggers prompts mode)",
            },
            "get_prompt": {
                "type": "string",
                "description": "Prompt name to render (triggers get_prompt mode, use args for prompt arguments)",
            },
        },
    }

    def __init__(self, mcp_registry: MCPRegistry, **kwargs: Any):
        self._mcp_registry = mcp_registry
        # Set before super().__init__ since BaseTool requires name/description
        super().__init__(**kwargs)

    async def execute(self, input_data: ToolInput) -> ToolOutput:
        """Route to appropriate mode handler based on provided parameters."""
        try:
            # Mode precedence: tool (call) > connect > describe > search >
            # resources > read_resource > prompts > get_prompt > server (list) > status
            tool_name = getattr(input_data, "tool", None)
            connect = getattr(input_data, "connect", None)
            describe = getattr(input_data, "describe", None)
            search = getattr(input_data, "search", None)
            resources = getattr(input_data, "resources", None)
            read_resource = getattr(input_data, "read_resource", None)
            prompts = getattr(input_data, "prompts", None)
            get_prompt = getattr(input_data, "get_prompt", None)
            server = getattr(input_data, "server", None)

            if tool_name:
                return await self._execute_call(
                    tool_name=tool_name,
                    args_str=getattr(input_data, "args", "{}"),
                    server=server,
                )
            elif connect:
                return await self._execute_connect(connect)
            elif describe:
                return await self._execute_describe(describe, server)
            elif search:
                return await self._execute_search(
                    query=search,
                    regex=getattr(input_data, "regex", False) or False,
                    include_schemas=getattr(input_data, "include_schemas", True),
                    server=server,
                )
            elif resources:
                return await self._execute_resources(resources)
            elif read_resource:
                return await self._execute_read_resource(read_resource)
            elif prompts:
                return await self._execute_prompts(prompts)
            elif get_prompt:
                return await self._execute_get_prompt(
                    prompt_name=get_prompt,
                    args_str=getattr(input_data, "args", "{}"),
                )
            elif server:
                return await self._execute_list(server)
            else:
                return await self._execute_status()

        except Exception as e:
            logger.error(f"MCP proxy tool error: {e}")
            return ToolOutput(
                success=False,
                result=None,
                error=f"MCP proxy error: {e}",
            )

    async def _execute_status(self) -> ToolOutput:
        """Show status of all configured MCP servers."""
        registry = self._mcp_registry
        cache = registry._cache
        lifecycle = registry._lifecycle

        lines = ["## MCP Server Status\n"]

        for server_name in sorted(registry._configs.keys()):
            config = registry._configs[server_name]
            client = registry.get_client(server_name)
            connected = client.is_connected if client else False
            status_emoji = "🟢" if connected else "🔴"
            tool_count = 0
            resource_count = 0
            prompt_count = 0
            cached_smeta = cache.get_server(server_name)
            if cached_smeta:
                tool_count = len(cached_smeta.tools)
                resource_count = len(cached_smeta.resources)
                prompt_count = len(cached_smeta.prompts)
            elif client:
                tool_count = client.tool_count
                resource_count = client.resource_count
                prompt_count = client.prompt_count

            lifecycle_mode = config.lifecycle

            # Build capability badge
            caps_parts = []
            if tool_count:
                caps_parts.append(f"{tool_count}t")
            if resource_count:
                caps_parts.append(f"{resource_count}r")
            if prompt_count:
                caps_parts.append(f"{prompt_count}p")
            caps_badge = f"[{','.join(caps_parts)}]" if caps_parts else "[no capabilities]"

            # Auth indicator
            auth_badge = ""
            if config.auth and config.auth.is_configured:
                auth_badge = f" 🔒{config.auth.type}"

            lines.append(
                f"  {status_emoji} **{server_name}** {caps_badge}{auth_badge} — "
                f"{lifecycle_mode}, {'connected' if connected else 'disconnected'}"
            )

        total_cached = cache.total_tools
        total_resources = cache.total_resources
        total_prompts = cache.total_prompts
        connected_count = sum(
            1 for n in registry._configs
            if (c := registry.get_client(n)) and c.is_connected
        )
        summary_parts = [f"{total_cached} tools"]
        if total_resources:
            summary_parts.append(f"{total_resources} resources")
        if total_prompts:
            summary_parts.append(f"{total_prompts} prompts")
        lines.append(f"\n  Total: {len(registry._configs)} servers, {connected_count} connected, {', '.join(summary_parts)} in cache")

        return ToolOutput(
            success=True,
            result="\n".join(lines),
            metadata={
                "mode": "status",
                "total_servers": len(registry._configs),
                "connected": connected_count,
                "total_tools": total_cached,
                "total_resources": total_resources,
                "total_prompts": total_prompts,
            },
        )

    async def _execute_list(self, server: str) -> ToolOutput:
        """List tools for a specific server."""
        cache = self._mcp_registry._cache
        client = self._mcp_registry.get_client(server)

        # Try cache first
        cached_tools = cache.list_server_tools(server)
        if cached_tools:
            lines = [f"## Tools from '{server}'\n"]
            for tool in cached_tools:
                desc = tool.description[:80] + "..." if len(tool.description) > 80 else tool.description
                lines.append(f"  - **{tool.original_name}**: {desc}")
            lines.append(f"\n  {len(cached_tools)} tools")
            return ToolOutput(
                success=True,
                result="\n".join(lines),
                metadata={"mode": "list", "server": server, "count": len(cached_tools)},
            )

        # Try live client
        if client and client.is_connected:
            tools = await client.list_tools()
            lines = [f"## Tools from '{server}'\n"]
            for tool in tools:
                desc = tool.description[:80] + "..." if len(tool.description) > 80 else tool.description
                lines.append(f"  - **{tool.name}**: {desc}")
            lines.append(f"\n  {len(tools)} tools")
            return ToolOutput(
                success=True,
                result="\n".join(lines),
                metadata={"mode": "list", "server": server, "count": len(tools)},
            )

        return ToolOutput(
            success=False,
            result=None,
            error=f"Server '{server}' not found in cache or not connected. Use connect='{server}' first.",
        )

    async def _execute_search(
        self,
        query: str,
        regex: bool = False,
        include_schemas: bool = True,
        server: str | None = None,
    ) -> ToolOutput:
        """Search for tools by name/description."""
        cache = self._mcp_registry._cache
        matches = cache.search_tools(query, server=server, regex=regex)

        if not matches:
            return ToolOutput(
                success=True,
                result=f"No tools matching '{query}'",
                metadata={"mode": "search", "query": query, "count": 0},
            )

        lines = [f"## Search results for '{query}'\n"]
        for tool in matches:
            desc = tool.description[:100] + "..." if len(tool.description) > 100 else tool.description
            lines.append(f"  - **{tool.name}** (server: {tool.server_name}, original: {tool.original_name}): {desc}")
            if include_schemas and tool.input_schema:
                schema_str = json.dumps(tool.input_schema, indent=4)
                lines.append(f"    Schema: {schema_str}")

        lines.append(f"\n  {len(matches)} match(es)")
        return ToolOutput(
            success=True,
            result="\n".join(lines),
            metadata={"mode": "search", "query": query, "count": len(matches)},
        )

    async def _execute_describe(self, tool_name: str, server: str | None = None) -> ToolOutput:
        """Describe a specific tool with full schema."""
        cache = self._mcp_registry._cache

        # Try by prefixed name first, then by original name
        tool_meta = cache.get_tool_by_prefixed_name(tool_name)
        if not tool_meta and server:
            tool_meta = cache.get_tool(server, tool_name)

        if not tool_meta:
            # Try searching across all servers
            all_tools = cache.search_tools(tool_name)
            if all_tools:
                tool_meta = all_tools[0]

        if not tool_meta:
            return ToolOutput(
                success=False,
                result=None,
                error=f"Tool '{tool_name}' not found. Use search='{tool_name}' to find it.",
            )

        lines = [
            f"## Tool: {tool_meta.name}\n",
            f"  **Server**: {tool_meta.server_name}",
            f"  **Original name**: {tool_meta.original_name}",
            f"  **Description**: {tool_meta.description}",
            "\n  **Parameters**:",
        ]

        schema = tool_meta.input_schema
        if schema:
            props = schema.get("properties", {})
            required = schema.get("required", [])
            if props:
                for pname, pdef in props.items():
                    req_marker = " (required)" if pname in required else ""
                    ptype = pdef.get("type", "any")
                    pdesc = pdef.get("description", "")
                    lines.append(f"    - `{pname}` ({ptype}){req_marker}: {pdesc}")
            else:
                lines.append("    (no parameters)")
        else:
            lines.append("    (no schema available)")

        return ToolOutput(
            success=True,
            result="\n".join(lines),
            metadata={"mode": "describe", "tool": tool_meta.to_dict(), "server": tool_meta.server_name},
        )

    async def _execute_call(self, tool_name: str, args_str: str = "{}", server: str | None = None) -> ToolOutput:
        """Execute an MCP tool call via the proxy."""
        # Parse arguments
        try:
            args = json.loads(args_str) if isinstance(args_str, str) else args_str
        except json.JSONDecodeError as e:
            return ToolOutput(
                success=False,
                result=None,
                error=f"Invalid JSON args: {e}",
            )

        # Resolve server if not specified
        if not server:
            cache = self._mcp_registry._cache
            tool_meta = cache.get_tool_by_prefixed_name(tool_name)
            if tool_meta:
                server = tool_meta.server_name
                tool_name = tool_meta.original_name
            else:
                # Try to find by original name across servers
                for sname in self._mcp_registry._configs:
                    meta = cache.get_tool(sname, tool_name)
                    if meta:
                        server = sname
                        tool_name = meta.original_name
                        break

        if not server:
            return ToolOutput(
                success=False,
                result=None,
                error=f"Could not determine server for tool '{tool_name}'. Specify server='name'.",
            )

        # Ensure server is connected (lazy connect)
        try:
            client = await self._mcp_registry._lifecycle.ensure_connected(server)
        except Exception as e:
            return ToolOutput(
                success=False,
                result=None,
                error=f"Failed to connect to MCP server '{server}': {e}",
            )

        # Execute the tool call
        try:
            result = await client.call_tool(tool_name, args)

            # Notify lifecycle manager of tool activity
            await self._mcp_registry._lifecycle.on_tool_call(server)

            # Format the result
            content = result.get("content", [])
            is_error = result.get("isError", False)

            if isinstance(content, list):
                text_parts = []
                for item in content:
                    if isinstance(item, dict):
                        text_parts.append(item.get("text", str(item)))
                    else:
                        text_parts.append(str(item))
                text = "\n".join(text_parts)
            else:
                text = str(content) if content else ""

            return ToolOutput(
                success=not is_error,
                result=text,
                error=f"MCP tool error: {text}" if is_error else None,
                metadata={"mode": "call", "server": server, "tool": tool_name},
            )

        except Exception as e:
            return ToolOutput(
                success=False,
                result=None,
                error=f"MCP tool call failed: {e}",
            )

    async def _execute_connect(self, server: str) -> ToolOutput:
        """Explicitly connect to a lazy server and refresh its metadata."""
        try:
            client = await self._mcp_registry._lifecycle.ensure_connected(server)

            # Refresh metadata cache — tools, resources, and prompts in one pass
            tools = await client.list_tools()
            capabilities = client.get_capabilities()
            resources = await client.list_resources() if capabilities.resources else []
            prompts = await client.list_prompts() if capabilities.prompts else []
            self._mcp_registry._update_cache_for_server(
                server, tools, resources=resources, prompts=prompts
            )

            caps_info = []
            if capabilities.tools:
                caps_info.append(f"{client.tool_count} tools")
            if capabilities.resources:
                caps_info.append(f"{len(resources)} resources")
            if capabilities.prompts:
                caps_info.append(f"{len(prompts)} prompts")

            return ToolOutput(
                success=True,
                result=f"Connected to '{server}' with {', '.join(caps_info) or 'no capabilities'}",
                metadata={
                    "mode": "connect",
                    "server": server,
                    "tool_count": client.tool_count,
                    "resource_count": len(resources),
                    "prompt_count": len(prompts),
                },
            )
        except Exception as e:
            return ToolOutput(
                success=False,
                result=None,
                error=f"Failed to connect to MCP server '{server}': {e}",
            )

    # ========================================================================
    # RESOURCE MODES
    # ========================================================================

    async def _execute_resources(self, server: str) -> ToolOutput:
        """List resources for a specific server."""
        cache = self._mcp_registry._cache
        client = self._mcp_registry.get_client(server)

        # Try cache first
        cached_resources = cache.list_server_resources(server)
        if cached_resources:
            lines = [f"## Resources from '{server}'\n"]
            for resource in cached_resources:
                mime = f" ({resource.mime_type})" if resource.mime_type else ""
                lines.append(f"  - **{resource.name}** [{resource.uri}]{mime}: {resource.description}")
            lines.append(f"\n  {len(cached_resources)} resources")
            return ToolOutput(
                success=True,
                result="\n".join(lines),
                metadata={"mode": "resources", "server": server, "count": len(cached_resources)},
            )

        # Try live client
        if client and client.is_connected:
            try:
                resources = await client.list_resources()
                lines = [f"## Resources from '{server}'\n"]
                for resource in resources:
                    mime = f" ({resource.mime_type})" if resource.mime_type else ""
                    lines.append(f"  - **{resource.name}** [{resource.uri}]{mime}: {resource.description}")
                lines.append(f"\n  {len(resources)} resources")
                return ToolOutput(
                    success=True,
                    result="\n".join(lines),
                    metadata={"mode": "resources", "server": server, "count": len(resources)},
                )
            except Exception as e:
                return ToolOutput(
                    success=False,
                    result=None,
                    error=f"Failed to list resources from '{server}': {e}",
                )

        return ToolOutput(
            success=False,
            result=None,
            error=f"Server '{server}' not found in cache or not connected. Use connect='{server}' first.",
        )

    async def _execute_read_resource(self, uri: str) -> ToolOutput:
        """Read a resource by URI."""
        # Find which server has this resource
        cache = self._mcp_registry._cache
        server = None

        # Search cache for the resource
        for smeta_name in cache.server_names:
            for resource in cache.list_server_resources(smeta_name):
                if resource.uri == uri:
                    server = smeta_name
                    break
            if server:
                break

        if not server:
            return ToolOutput(
                success=False,
                result=None,
                error=f"Resource '{uri}' not found in any server cache. Use resources='server' to list available resources.",
            )

        # Connect and read
        try:
            client = await self._mcp_registry._lifecycle.ensure_connected(server)
            contents = await client.read_resource(uri)

            lines = [f"## Resource: {uri}\n"]
            for content in contents:
                if content.mime_type:
                    lines.append(f"  **MIME Type**: {content.mime_type}")
                if content.text:
                    lines.append(f"\n  {content.text}")
                elif content.blob is not None:
                    lines.append(f"\n  [Binary data: {len(content.blob)} bytes]")

            return ToolOutput(
                success=True,
                result="\n".join(lines),
                metadata={"mode": "read_resource", "uri": uri, "server": server},
            )
        except Exception as e:
            return ToolOutput(
                success=False,
                result=None,
                error=f"Failed to read resource '{uri}': {e}",
            )

    # ========================================================================
    # PROMPT MODES
    # ========================================================================

    async def _execute_prompts(self, server: str) -> ToolOutput:
        """List prompts for a specific server."""
        cache = self._mcp_registry._cache
        client = self._mcp_registry.get_client(server)

        # Try cache first
        cached_prompts = cache.list_server_prompts(server)
        if cached_prompts:
            lines = [f"## Prompts from '{server}'\n"]
            for prompt in cached_prompts:
                arg_desc = ""
                if prompt.arguments:
                    arg_names = [a.get("name", "?") for a in prompt.arguments]
                    arg_desc = f" (args: {', '.join(arg_names)})"
                lines.append(f"  - **{prompt.name}**{arg_desc}: {prompt.description}")
            lines.append(f"\n  {len(cached_prompts)} prompts")
            return ToolOutput(
                success=True,
                result="\n".join(lines),
                metadata={"mode": "prompts", "server": server, "count": len(cached_prompts)},
            )

        # Try live client
        if client and client.is_connected:
            try:
                prompts = await client.list_prompts()
                lines = [f"## Prompts from '{server}'\n"]
                for prompt in prompts:
                    arg_desc = ""
                    if prompt.arguments:
                        arg_names = [a.name for a in prompt.arguments]
                        arg_desc = f" (args: {', '.join(arg_names)})"
                    lines.append(f"  - **{prompt.name}**{arg_desc}: {prompt.description}")
                lines.append(f"\n  {len(prompts)} prompts")
                return ToolOutput(
                    success=True,
                    result="\n".join(lines),
                    metadata={"mode": "prompts", "server": server, "count": len(prompts)},
                )
            except Exception as e:
                return ToolOutput(
                    success=False,
                    result=None,
                    error=f"Failed to list prompts from '{server}': {e}",
                )

        return ToolOutput(
            success=False,
            result=None,
            error=f"Server '{server}' not found in cache or not connected. Use connect='{server}' first.",
        )

    async def _execute_get_prompt(self, prompt_name: str, args_str: str = "{}") -> ToolOutput:
        """Render a prompt by name."""
        # Parse arguments
        try:
            args = json.loads(args_str) if isinstance(args_str, str) else args_str
        except json.JSONDecodeError as e:
            return ToolOutput(
                success=False,
                result=None,
                error=f"Invalid JSON args: {e}",
            )

        # Find which server has this prompt
        cache = self._mcp_registry._cache
        server = None

        for smeta_name in cache.server_names:
            prompt = cache.get_prompt(smeta_name, prompt_name)
            if prompt:
                server = smeta_name
                break

        if not server:
            return ToolOutput(
                success=False,
                result=None,
                error=f"Prompt '{prompt_name}' not found. Use prompts='server' to list available prompts.",
            )

        # Connect and render
        try:
            client = await self._mcp_registry._lifecycle.ensure_connected(server)
            messages = await client.get_prompt(prompt_name, args)

            lines = [f"## Prompt: {prompt_name}\n"]
            for msg in messages:
                role_marker = "👤" if msg.role == "user" else "🤖"
                lines.append(f"  {role_marker} **{msg.role}**: {msg.content[:200]}{'...' if len(msg.content) > 200 else ''}")

            return ToolOutput(
                success=True,
                result="\n".join(lines),
                metadata={"mode": "get_prompt", "prompt": prompt_name, "server": server, "message_count": len(messages)},
            )
        except Exception as e:
            return ToolOutput(
                success=False,
                result=None,
                error=f"Failed to render prompt '{prompt_name}': {e}",
            )
