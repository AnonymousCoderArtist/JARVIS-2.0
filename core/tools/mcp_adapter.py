"""MCP (Model Context Protocol) Adapter for JARVIS

This module provides MCP client integration to connect to external MCP servers
and expose their tools as native JARVIS tools.

Based on the MCP specification: https://modelcontextprotocol.io/

Components:
- MCPClient: Client for connecting to MCP servers (stdio and HTTP transports)
- MCPToolAdapter: Wraps external MCP tools as JARVIS BaseTool instances
- MCPToolProvider: Discovers and registers tools from MCP servers
- MCPConfig: Configuration dataclass for MCP server setup
"""

import asyncio
import json
import logging
import os
import subprocess
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Awaitable, Callable

from .base import BaseTool, ToolInput, ToolOutput
from .registry import ToolRegistry
from .permissions import PermissionContext

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
# MCP TRANSPORT ABSTRACTION
# ============================================================================

class MCPTransport(ABC):
    """Abstract base class for MCP transports"""
    
    @abstractmethod
    async def initialize(self) -> dict[str, Any]:
        """Initialize the transport and return server capabilities"""
        pass
    
    @abstractmethod
    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Call a tool on the MCP server"""
        pass
    
    @abstractmethod
    async def list_tools(self) -> list[MCPToolSpec]:
        """List available tools from the MCP server"""
        pass
    
    @abstractmethod
    async def close(self) -> None:
        """Close the transport connection"""
        pass


class StdioTransport(MCPTransport):
    """MCP transport over stdio (for local MCP servers)"""
    
    def __init__(
        self,
        command: str,
        args: list[str],
        env: dict[str, str],
        timeout: float = 30.0,
    ):
        self.command = command
        self.args = args
        self.env = env
        self.timeout = timeout
        self._process: subprocess.Popen | None = None
        self._stdin: asyncio.StreamWriter | None = None
        self._stdout: asyncio.StreamReader | None = None
        self._request_id = 0
        self._lock = asyncio.Lock()
        self._initialized = False
        self._capabilities: dict[str, Any] = {}
    
    async def initialize(self) -> dict[str, Any]:
        """Start the MCP server process and initialize"""
        if self._initialized:
            return self._capabilities
        
        # Build environment
        full_env = os.environ.copy()
        full_env.update(self.env)
        
        # Start the process
        try:
            self._process = subprocess.Popen(
                [self.command] + self.args,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=full_env,
                text=True,
            )
        except Exception as e:
            raise RuntimeError(f"Failed to start MCP server: {e}")
        
        # Create async streams
        loop = asyncio.get_event_loop()
        self._stdin = await open_writer(self._process.stdin)
        self._stdout = await open_reader(self._process.stdout)
        
        # Send initialize request
        response = await self._send_request(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {
                    "name": "jarvis",
                    "version": "2.0.0"
                }
            }
        )
        
        self._capabilities = response.get("capabilities", {})
        self._initialized = True
        
        # Send initialized notification
        await self._send_notification("initialized", {})
        
        logger.info(f"MCP stdio transport initialized for {self.command}")
        return self._capabilities
    
    async def _send_request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        """Send a JSON-RPC request and wait for response"""
        async with self._lock:
            self._request_id += 1
            request = {
                "jsonrpc": "2.0",
                "id": self._request_id,
                "method": method,
                "params": params
            }
            
            # Write request
            request_json = json.dumps(request) + "\n"
            if self._stdin:
                self._stdin.write(request_json.encode())
                await self._stdin.drain()
            
            # Read response
            if not self._stdout:
                raise RuntimeError("MCP server stdout not available")
            response_line = await asyncio.wait_for(
                self._stdout.readline(),
                timeout=self.timeout
            )
            
            if not response_line:
                raise RuntimeError("MCP server closed connection")
            
            response = json.loads(response_line)
            
            if "error" in response:
                raise RuntimeError(f"MCP error: {response['error']}")
            
            return response.get("result", {})
    
    async def _send_notification(self, method: str, params: dict[str, Any]) -> None:
        """Send a JSON-RPC notification (no response)"""
        async with self._lock:
            notification = {
                "jsonrpc": "2.0",
                "method": method,
                "params": params
            }
            notification_json = json.dumps(notification) + "\n"
            if self._stdin:
                self._stdin.write(notification_json.encode())
                await self._stdin.drain()
    
    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Call a tool on the MCP server"""
        if not self._initialized:
            await self.initialize()
        
        return await self._send_request(
            "tools/call",
            {
                "name": tool_name,
                "arguments": arguments
            }
        )
    
    async def list_tools(self) -> list[MCPToolSpec]:
        """List available tools from the MCP server"""
        if not self._initialized:
            await self.initialize()
        
        response = await self._send_request("tools/list", {})
        tools = response.get("tools", [])
        
        return [
            MCPToolSpec(
                name=tool.get("name", ""),
                description=tool.get("description", ""),
                input_schema=tool.get("inputSchema", {}),
            )
            for tool in tools
        ]
    
    async def close(self) -> None:
        """Close the transport connection"""
        if self._process:
            self._process.terminate()
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()
            self._process = None
        logger.info("MCP stdio transport closed")


class HTTPTransport(MCPTransport):
    """MCP transport over HTTP/SSE"""
    
    def __init__(
        self,
        url: str,
        timeout: float = 30.0,
        headers: dict[str, str] | None = None,
    ):
        self.url = url
        self.timeout = timeout
        self.headers = headers or {}
        self._session: Any = None
        self._request_id = 0
        self._lock = asyncio.Lock()
        self._initialized = False
        self._capabilities: dict[str, Any] = {}
        self._aiohttp: Any = None  # type: ignore[assignment]
    
    def _import_aiohttp(self):
        """Import and return aiohttp module"""
        try:
            import aiohttp
            return aiohttp
        except ImportError:
            raise RuntimeError("aiohttp is required for HTTP transport. Install with: pip install aiohttp")
    
    async def initialize(self) -> dict[str, Any]:
        """Initialize HTTP transport"""
        if self._initialized:
            return self._capabilities
        
        # Import aiohttp
        self._aiohttp = self._import_aiohttp()
        
        # Create session
        self._session = self._aiohttp.ClientSession(
            headers={"Content-Type": "application/json", **self.headers}
        )
        
        # Send initialize request
        response = await self._send_request(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {
                    "name": "jarvis",
                    "version": "2.0.0"
                }
            }
        )
        
        self._capabilities = response.get("capabilities", {})
        self._initialized = True
        
        logger.info(f"MCP HTTP transport initialized at {self.url}")
        return self._capabilities
    
    async def _send_request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        """Send a JSON-RPC request"""
        # Ensure aiohttp is available
        if self._aiohttp is None:
            self._aiohttp = self._import_aiohttp()
        
        async with self._lock:
            self._request_id += 1
            request = {
                "jsonrpc": "2.0",
                "id": self._request_id,
                "method": method,
                "params": params
            }
            
            async with self._session.post(
                self.url,
                json=request,
                timeout=self._aiohttp.ClientTimeout(total=self.timeout)
            ) as response:
                if response.status != 200:
                    raise RuntimeError(f"MCP HTTP error: {response.status}")
                
                result = await response.json()
                
                if "error" in result:
                    raise RuntimeError(f"MCP error: {result['error']}")
                
                return result.get("result", {})
    
    async def _ensure_session(self) -> None:
        """Ensure the session is valid. Recreate if needed."""
        if self._session is None:
            await self.initialize()
            return
        
        # Check if session is closed by trying to make a simple request
        # If the session is invalid due to closed event loop, recreate it
        try:
            # Try to check if session is closed
            if self._session.closed:
                await self.initialize()
        except Exception:
            # If any error occurs (including event loop issues), reinitialize
            await self.initialize()
    
    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Call a tool on the MCP server"""
        # Ensure session is valid before calling
        await self._ensure_session()
        
        return await self._send_request(
            "tools/call",
            {
                "name": tool_name,
                "arguments": arguments
            }
        )
    
    async def list_tools(self) -> list[MCPToolSpec]:
        """List available tools from the MCP server"""
        if not self._initialized:
            await self.initialize()
        
        response = await self._send_request("tools/list", {})
        tools = response.get("tools", [])
        
        return [
            MCPToolSpec(
                name=tool.get("name", ""),
                description=tool.get("description", ""),
                input_schema=tool.get("inputSchema", {}),
            )
            for tool in tools
        ]
    
    async def close(self) -> None:
        """Close the HTTP session"""
        if self._session:
            await self._session.close()
            self._session = None
        logger.info("MCP HTTP transport closed")


# ============================================================================
# HELPER FUNCTIONS FOR STREAM I/O
# ============================================================================

async def open_reader(stream):
    """Create an async reader from a binary stream"""
    loop = asyncio.get_event_loop()
    reader = asyncio.StreamReader(loop=loop)
    protocol = asyncio.StreamReaderProtocol(reader, loop=loop)
    transport, _ = await loop.connect_read_pipe(lambda: protocol, stream)
    return reader


async def open_writer(stream):
    """Create an async writer from a binary stream"""
    # Use local import to avoid type checker issues with some configurations
    import asyncio as _asyncio
    import sys
    loop = _asyncio.get_event_loop()
    
    # Create a minimal stream writer that works across platforms
    reader = _asyncio.StreamReader(loop=loop)
    protocol = _asyncio.StreamReaderProtocol(reader, loop=loop)
    
    if sys.platform == "win32":
        # Windows doesn't support connect_write_pipe well for subprocess pipes
        transport = None
    else:
        try:
            import asyncio.streams as _streams
            transport, _ = await loop.connect_write_pipe(
                lambda: _streams.FlowControlDispatcher, stream  # type: ignore[attr-defined,call-arg]
            )
        except Exception:
            transport = None
    
    return _asyncio.StreamWriter(transport, protocol, stream, loop)  # type: ignore


# ============================================================================
# MCP CLIENT
# ============================================================================

class MCPClient:
    """Client for connecting to MCP servers"""
    
    def __init__(self, config: MCPServerConfig):
        self.config = config
        self._transport: MCPTransport | None = None
        self._tools: list[MCPToolSpec] = []
        self._initialized = False
    
    async def connect(self) -> None:
        """Connect to the MCP server"""
        if self._initialized:
            return
        
        # Create transport based on config
        if self.config.transport == MCPTransportType.STDIO:
            self._transport = StdioTransport(
                command=self.config.command,
                args=self.config.args,
                env=self.config.env,
                timeout=self.config.timeout,
            )
        elif self.config.transport in (MCPTransportType.HTTP, MCPTransportType.SSE):
            self._transport = HTTPTransport(
                url=self.config.url or f"http://localhost:8080/mcp",
                timeout=self.config.timeout,
            )
        else:
            raise ValueError(f"Unknown transport type: {self.config.transport}")
        
        # Initialize transport
        await self._transport.initialize()
        
        # List available tools
        self._tools = await self._transport.list_tools()
        
        self._initialized = True
        logger.info(f"Connected to MCP server '{self.config.name}' with {len(self._tools)} tools")
    
    async def disconnect(self) -> None:
        """Disconnect from the MCP server"""
        if self._transport:
            await self._transport.close()
            self._transport = None
        self._initialized = False
    
    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Call a tool on the MCP server"""
        if not self._initialized:
            await self.connect()
        
        if self._transport is None:
            raise RuntimeError("MCP transport not initialized")
        
        return await self._transport.call_tool(tool_name, arguments)
    
    async def list_tools(self) -> list[MCPToolSpec]:
        """List available tools from the MCP server"""
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
            logger.error(f"MCP tool execution failed: {e}")
            return ToolOutput(
                success=False,
                result=None,
                error=f"MCP tool execution failed: {str(e)}",
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
    
    # Handle both single server and list of servers
    if isinstance(data, dict):
        servers = data.get("mcp_servers", [data])
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
    "MCPTransport",
    "StdioTransport",
    "HTTPTransport",
    "MCPClient",
    "MCPToolAdapter",
    "MCPToolProvider",
    "MCPRegistry",
    "create_mcp_client_from_config",
    "load_mcp_config_from_file",
]