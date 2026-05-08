"""MCP (Model Context Protocol) Adapter for JARVIS

This module provides MCP client integration to connect to external MCP servers
and expose their tools as native JARVIS tools.

Uses the official MCP Python SDK: https://github.com/modelcontextprotocol/python-sdk

Components:
- MCPClient: Client for connecting to MCP servers (stdio and HTTP transports)
- MCPToolAdapter: Wraps external MCP tools as JARVIS BaseTool instances
- MCPToolProvider: Discovers and registers tools from MCP servers
- MCPConfig: Configuration dataclass for MCP server setup
"""

import asyncio
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamable_http_client

from .base import BaseTool, ToolInput, ToolOutput
from .registry import ToolRegistry

logger = logging.getLogger(__name__)


# ============================================================================
# MCP CONFIGURATION
# ============================================================================

class MCPTransportType(str):
    """MCP transport types"""
    STDIO = "stdio"
    HTTP = "http"
    SSE = "sse"


@dataclass
class MCPServerConfig:
    """Configuration for an MCP server"""
    name: str
    command: str = ""
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    transport: str = MCPTransportType.STDIO  # "stdio", "http", "sse"
    url: str = ""  # For HTTP/SSE transport
    timeout: float = 30.0
    disabled: bool = False
    disabled_tools: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> "MCPServerConfig":
        """Create config from dictionary"""
        return cls(
            name=data.get("name", ""),
            command=data.get("command", ""),
            args=data.get("args", []),
            env=data.get("env", {}),
            transport=data.get("transport", MCPTransportType.STDIO),
            url=data.get("url", ""),
            timeout=data.get("timeout", 30.0),
            disabled=data.get("disabled", False),
            disabled_tools=data.get("disabled_tools", []),
        )


@dataclass
class MCPToolSpec:
    """Specification for an MCP tool"""
    name: str
    description: str
    input_schema: dict[str, Any]
    server_name: str = ""
    remote_name: str = ""


# ============================================================================
# MCP CLIENT (Using official MCP SDK)
# ============================================================================

class MCPClient:
    """Client for connecting to MCP servers using the official MCP SDK"""

    def __init__(self, config: MCPServerConfig):
        self.config = config
        self._session: ClientSession | None = None
        self._tools: list[MCPToolSpec] = []
        self._initialized = False
        self._lock = asyncio.Lock()
        self._event_loop: asyncio.AbstractEventLoop | None = None
        self._run_task: asyncio.Task | None = None
        self._stop_event: asyncio.Event | None = None
        self._ready_event: asyncio.Event | None = None
        self._connect_error: Exception | None = None
        # Status tracking
        self._connect_time: float = 0.0
        self._last_error: str | None = None
        self._last_tool_call: float = 0.0

    async def _reset_client(self) -> None:
        """Reset the client state when event loop changes"""
        if self._stop_event:
            self._stop_event.set()

        if self._run_task and not self._run_task.done():
            try:
                # Wait for the task to finish cleanup
                await asyncio.wait_for(asyncio.shield(self._run_task), timeout=5.0)
            except Exception as e:
                logger.warning(f"Error waiting for MCP client task shutdown: {e}")
                self._run_task.cancel()

        self._run_task = None
        self._stop_event = None
        self._ready_event = None
        self._session = None
        self._tools = []
        self._initialized = False
        self._event_loop = None
        self._connect_error = None
        self._last_error = None

    async def _ensure_active_loop(self) -> None:
        """Reset state if this client was initialized on another event loop."""
        current_loop = asyncio.get_running_loop()

        if self._event_loop is None:
            self._event_loop = current_loop
            return

        stored_loop_closed = self._event_loop.is_closed()
        if self._event_loop is not current_loop or stored_loop_closed:
            logger.info(
                "MCP client event loop changed or closed; resetting client "
                "for server '%s'",
                self.config.name,
            )
            await self._reset_client()
            self._event_loop = current_loop

    async def connect(self) -> None:
        """Connect to the MCP server"""
        await self._ensure_active_loop()

        if self._initialized:
            return

        try:
            self._stop_event = asyncio.Event()
            self._ready_event = asyncio.Event()
            self._connect_error = None

            # Start background task to manage the context managers
            self._run_task = asyncio.create_task(self._run_client_task())

            # Wait for it to be ready or fail
            await self._ready_event.wait()

            if self._connect_error:
                raise self._connect_error

            # List available tools
            await self._list_tools()

            self._initialized = True
            logger.info(f"Connected to MCP server '{self.config.name}' with {len(self._tools)} tools")

        except Exception as e:
            logger.error(f"Failed to connect to MCP server '{self.config.name}': {e}")
            await self._reset_client()
            raise

    async def _run_client_task(self) -> None:
        """Background task that keeps the MCP context managers open in a single task scope"""
        try:
            from contextlib import AsyncExitStack
            async with AsyncExitStack() as stack:
                if self.config.transport == MCPTransportType.STDIO:
                    # Build environment
                    import os
                    full_env = os.environ.copy()
                    full_env.update(self.config.env)

                    # Create server parameters
                    server_params = StdioServerParameters(
                        command=self.config.command,
                        args=self.config.args,
                        env=full_env,
                    )

                    logger.info(f"Connecting to MCP server via stdio: {self.config.command} {self.config.args}")
                    ctx = stdio_client(server_params)
                    streams = await stack.enter_async_context(ctx)
                    read_stream, write_stream = streams

                elif self.config.transport in (MCPTransportType.HTTP, MCPTransportType.SSE):
                    if not self.config.url:
                        raise ValueError(f"No URL configured for HTTP MCP server '{self.config.name}'")

                    logger.info(f"Connecting to MCP server via HTTP: {self.config.url}")
                    ctx = streamable_http_client(self.config.url)
                    streams = await stack.enter_async_context(ctx)
                    # HTTP stream client returns (read, write, session_id) or similar depending on MCP sdk version
                    if len(streams) == 3:
                        read_stream, write_stream, _ = streams
                    else:
                        read_stream, write_stream = streams
                else:
                    raise ValueError(f"Unknown transport: {self.config.transport}")

                # Create session
                session_ctx = ClientSession(read_stream, write_stream)
                self._session = await stack.enter_async_context(session_ctx)

                # Initialize the session
                await self._session.initialize()

                logger.info(f"MCP transport initialized for {self.config.name}")

                # Record connection time
                import time
                self._connect_time = time.time()

                # Signal ready
                if self._ready_event:
                    self._ready_event.set()

                # Wait until stopped
                if self._stop_event:
                    await self._stop_event.wait()

        except Exception as e:
            self._connect_error = e
            self._last_error = str(e)
            if self._ready_event and not self._ready_event.is_set():
                self._ready_event.set()
            logger.debug(f"MCP client task for {self.config.name} ended with exception: {e}")


    async def _list_tools(self) -> None:
        """List available tools from the MCP server"""
        if not self._session:
            raise RuntimeError("MCP session not initialized")

        response = await self._session.list_tools()
        tools = response.tools if hasattr(response, 'tools') else []

        self._tools = [
            MCPToolSpec(
                name=tool.name,
                description=tool.description or "",
                input_schema=tool.inputSchema if hasattr(tool, 'inputSchema') else {},
                server_name=self.config.name,
                remote_name=tool.name,
            )
            for tool in tools
        ]

    async def disconnect(self) -> None:
        """Disconnect from the MCP server"""
        await self._reset_client()
        self._event_loop = None

    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Call a tool on the MCP server"""
        await self._ensure_active_loop()

        if not self._initialized:
            await self.connect()

        if not self._session:
            raise RuntimeError("MCP session not initialized")

        try:
            async with self._lock:
                result = await self._session.call_tool(tool_name, arguments)

                # Convert MCP result to our format
                content = []
                is_error = False

                if hasattr(result, 'content'):
                    for item in result.content:
                        if hasattr(item, 'text'):
                            content.append({"type": "text", "text": item.text})
                        elif hasattr(item, 'data'):
                            # Handle image/audio resources
                            mime_type = getattr(item, 'mimeType', 'application/octet-stream')
                            content.append({"type": "image", "data": item.data, "mimeType": mime_type})

                if hasattr(result, 'isError'):
                    is_error = result.isError

                return {
                    "content": content,
                    "isError": is_error,
                }

        except Exception as e:
            logger.error(f"MCP tool call failed: {e}")
            raise

    async def list_tools(self) -> list[MCPToolSpec]:
        """List available tools from the MCP server"""
        await self._ensure_active_loop()

        if not self._initialized:
            await self.connect()

        return self._tools

    @property
    def is_connected(self) -> bool:
        """Check if connected to MCP server"""
        return self._initialized

    @property
    def server_name(self) -> str:
        """Get the server name"""
        return self.config.name

    @property
    def tool_count(self) -> int:
        """Get the number of available tools"""
        return len(self._tools)

    @property
    def uptime_seconds(self) -> float:
        """Get connection uptime in seconds"""
        if not self._initialized or self._connect_time == 0:
            return 0.0
        import time
        return time.time() - self._connect_time

    @property
    def last_error(self) -> str | None:
        """Get the last connection error"""
        return self._last_error

    @property
    def transport_type(self) -> str:
        """Get the transport type"""
        return self.config.transport


# ============================================================================
# MCP TOOL ADAPTER
# ============================================================================

class MCPToolAdapter(BaseTool):
    """Adapter that wraps an MCP tool as a JARVIS BaseTool"""

    def __init__(
        self,
        mcp_client: MCPClient,
        tool_spec: MCPToolSpec,
        tool_registry: ToolRegistry | None = None,
        llm_provider: Any = None,
        model: str | None = None,
    ):
        self._mcp_client = mcp_client
        self._tool_spec = tool_spec

        # Build input schema from MCP tool spec
        input_schema = self._build_input_schema(tool_spec)

        # Set tool properties BEFORE init (required by BaseTool)
        self.name = f"mcp_{tool_spec.server_name}_{tool_spec.name}"
        self.description = tool_spec.description or f"MCP tool: {tool_spec.name}"
        self.input_schema = input_schema

        # MCP tool markers
        self.is_mcp = True
        self.mcp_server_name = tool_spec.server_name
        self.mcp_status = "connected"

        # Initialize base class
        super().__init__(
            tool_registry=tool_registry,
            llm_provider=llm_provider,
            model=model,
        )

    def _build_input_schema(self, tool_spec: MCPToolSpec) -> dict[str, Any]:
        """Build JARVIS input schema from MCP tool spec"""
        mcp_schema = tool_spec.input_schema

        # Start with basic structure
        schema = {
            "type": "object",
            "properties": {},
            "required": [],
        }

        # Copy properties from MCP schema
        if "properties" in mcp_schema:
            schema["properties"] = mcp_schema["properties"]

        if "required" in mcp_schema:
            schema["required"] = mcp_schema["required"]

        # Add the tool spec name as a required parameter if no properties
        if not schema["properties"]:
            schema["properties"] = {
                "input": {
                    "type": "string",
                    "description": f"Input for {tool_spec.name}"
                }
            }
            schema["required"] = ["input"]

        return schema

    async def execute(self, input_data: ToolInput) -> ToolOutput:
        """Execute the MCP tool"""
        try:
            # Convert ToolInput to dict
            args = input_data.model_dump(exclude_none=True)

            # Call the MCP tool
            result = await self._mcp_client.call_tool(
                self._tool_spec.name,
                args
            )

            # Parse the result
            content = result.get("content", [])

            # Extract text from content
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

            is_error = result.get("isError", False)

            return ToolOutput(
                success=not is_error,
                result=text,
                error=f"MCP tool error: {text}" if is_error else None,
                metadata={
                    "mcp_server": self._mcp_client.server_name,
                    "mcp_tool": self._tool_spec.name,
                    "tool_type": "mcp",
                },
            )

        except Exception as e:
            error_msg = str(e)
            logger.error(f"MCP tool execution failed: {e}")

            return ToolOutput(
                success=False,
                result=None,
                error=error_msg,
            )

    def get_remote_name(self) -> str:
        """Get the remote MCP tool name"""
        return self._tool_spec.name

    @property
    def server_name(self) -> str:
        """Get the MCP server name"""
        return self._mcp_client.server_name


# ============================================================================
# MCP TOOL PROVIDER
# ============================================================================

class MCPToolProvider:
    """Discovers tools from MCP servers and provides them as JARVIS tools"""

    def __init__(self, config: MCPServerConfig):
        self.config = config
        self._client: MCPClient | None = None

    async def connect(self) -> MCPClient:
        """Connect to the MCP server and return the client"""
        if self._client is None:
            self._client = MCPClient(self.config)
            await self._client.connect()
        return self._client

    async def disconnect(self) -> None:
        """Disconnect from the MCP server"""
        if self._client:
            await self._client.disconnect()
            self._client = None

    async def discover_tools(
        self,
        tool_registry: ToolRegistry | None = None,
        llm_provider: Any = None,
        model: str | None = None,
    ) -> list[MCPToolAdapter]:
        """Discover available tools and return them as JARVIS tool adapters"""
        client = await self.connect()
        tool_specs = await client.list_tools()

        adapters = []
        for spec in tool_specs:
            # Check if tool is disabled
            if spec.name in self.config.disabled_tools:
                logger.info(f"Skipping disabled tool: {spec.name}")
                continue

            # Create adapter with server name
            spec.server_name = self.config.name
            spec.remote_name = spec.name

            adapter = MCPToolAdapter(
                mcp_client=client,
                tool_spec=spec,
                tool_registry=tool_registry,
                llm_provider=llm_provider,
                model=model,
            )
            adapters.append(adapter)

        logger.info(f"Discovered {len(adapters)} tools from MCP server '{self.config.name}'")
        return adapters

    @property
    def is_connected(self) -> bool:
        """Check if connected to MCP server"""
        return self._client is not None and self._client.is_connected

    @property
    def server_name(self) -> str:
        """Get the server name"""
        return self.config.name


# ============================================================================
# MCP REGISTRY (MANAGES MULTIPLE SERVERS)
# ============================================================================

class MCPRegistry:
    """Registry for managing multiple MCP servers and their tools"""

    def __init__(self, tool_registry: ToolRegistry | None = None):
        self._tool_registry = tool_registry
        self._providers: dict[str, MCPToolProvider] = {}
        self._clients: dict[str, MCPClient] = {}
        self._adapters: dict[str, MCPToolAdapter] = {}

    async def add_server(
        self,
        config: MCPServerConfig,
        llm_provider: Any = None,
        model: str | None = None,
    ) -> MCPToolProvider | None:
        """Add and connect to an MCP server"""
        if config.disabled:
            logger.info(f"MCP server '{config.name}' is disabled, skipping")
            return None

        provider = MCPToolProvider(config)

        try:
            # Connect and discover tools
            adapters = await provider.discover_tools(
                tool_registry=self._tool_registry,
                llm_provider=llm_provider,
                model=model,
            )

            # Register adapters
            self._providers[config.name] = provider
            self._clients[config.name] = await provider.connect()

            for adapter in adapters:
                tool_name = adapter.name
                self._adapters[tool_name] = adapter

                # Register with tool registry if available
                if self._tool_registry:
                    self._tool_registry.register(adapter)

            logger.info(f"Registered {len(adapters)} tools from MCP server '{config.name}'")
            return provider

        except Exception as e:
            logger.error(f"Failed to connect to MCP server '{config.name}': {e}")
            raise

    async def remove_server(self, server_name: str) -> None:
        """Remove an MCP server and its tools"""
        if server_name in self._providers:
            await self._providers[server_name].disconnect()
            del self._providers[server_name]

        if server_name in self._clients:
            await self._clients[server_name].disconnect()
            del self._clients[server_name]

        # Remove adapters for this server
        to_remove = [k for k in self._adapters if k.startswith(f"mcp_{server_name}_")]
        for key in to_remove:
            del self._adapters[key]

    async def connect_all(
        self,
        configs: list[MCPServerConfig],
        llm_provider: Any = None,
        model: str | None = None,
    ) -> dict[str, list[str]]:
        """Connect to multiple MCP servers"""
        results = {}

        for config in configs:
            try:
                await self.add_server(config, llm_provider, model)
                results[config.name] = ["connected"]
            except Exception as e:
                results[config.name] = [f"error: {str(e)}"]

        return results

    async def disconnect_all(self) -> None:
        """Disconnect from all MCP servers"""
        for provider in self._providers.values():
            await provider.disconnect()

        self._providers.clear()
        self._clients.clear()
        self._adapters.clear()

    def get_tool(self, tool_name: str) -> MCPToolAdapter | None:
        """Get an MCP tool adapter by name"""
        return self._adapters.get(tool_name)

    def list_servers(self) -> list[str]:
        """List connected MCP server names"""
        return list(self._providers.keys())

    def list_tools(self) -> list[dict[str, Any]]:
        """List all MCP tools"""
        return [
            {
                "name": adapter.name,
                "description": adapter.description,
                "server": adapter.server_name,
                "remote_name": adapter.get_remote_name(),
            }
            for adapter in self._adapters.values()
        ]

    @property
    def connected_servers(self) -> int:
        """Get the number of connected servers"""
        return len(self._clients)

    @property
    def total_tools(self) -> int:
        """Get the total number of MCP tools"""
        return len(self._adapters)


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

async def create_mcp_client_from_config(config_dict: dict) -> MCPClient:
    """Create an MCP client from a configuration dictionary"""
    config = MCPServerConfig.from_dict(config_dict)
    client = MCPClient(config)
    await client.connect()
    return client


def load_mcp_config_from_file(config_path: str) -> list[MCPServerConfig]:
    """Load MCP server configurations from a JSON/YAML file"""
    path = Path(config_path)

    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    content = path.read_text()

    if path.suffix == ".json":
        import json
        data = json.loads(content)
    elif path.suffix in (".yaml", ".yml"):
        try:
            import yaml
            data = yaml.safe_load(content)
        except ImportError:
            raise RuntimeError("PyYAML is required for YAML config files")
    else:
        raise ValueError(f"Unsupported config file format: {path.suffix}")

    # Handle different config formats
    if isinstance(data, dict):
        # Check for "mcpServers" key (Claude Code style)
        if "mcpServers" in data:
            servers = list(data["mcpServers"].values())
        # Check for "mcp_servers" key
        elif "mcp_servers" in data:
            servers = data["mcp_servers"]
        # Single server config
        else:
            servers = [data]
    else:
        servers = data

    return [MCPServerConfig.from_dict(s) for s in servers]


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    "MCPTransportType",
    "MCPServerConfig",
    "MCPToolSpec",
    "MCPClient",
    "MCPToolAdapter",
    "MCPToolProvider",
    "MCPRegistry",
    "create_mcp_client_from_config",
    "load_mcp_config_from_file",
]
