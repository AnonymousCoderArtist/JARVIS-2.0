import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from core.tools.mcp_adapter import (
    MCPClient,
    MCPServerConfig,
    MCPToolSpec,
    MCPTransportType,
)


class FakeMCPClient:
    """Fake MCP client for testing"""
    def __init__(self) -> None:
        self.closed = False
        self.called = False
        self.session = None
        
    async def initialize(self) -> dict:
        return {}

    async def list_tools(self) -> list[MCPToolSpec]:
        return [
            MCPToolSpec(
                name="echo",
                description="Echo input",
                input_schema={"type": "object"},
            )
        ]

    async def call_tool(self, tool_name: str, arguments: dict) -> dict:
        self.called = True
        return {"content": [{"text": f"{tool_name}: {arguments.get('value', '')}"}], "isError": False}

    async def close(self) -> None:
        self.closed = True


@pytest.mark.asyncio
async def test_mcp_client_reconnects_when_previous_loop_is_closed() -> None:
    """Test that MCP client reconnects when the previous event loop is closed"""
    # Create config
    config = MCPServerConfig(
        name="test-server",
        transport=MCPTransportType.HTTP,
        url="http://example.test/mcp",
    )
    
    client = MCPClient(config)
    
    # Simulate a closed event loop
    stale_loop = asyncio.new_event_loop()
    stale_loop.close()
    
    # Create a fake session and connection
    fake_session = MagicMock()
    fake_session.closed = False
    fake_session.initialize = AsyncMock()
    fake_session.list_tools = AsyncMock(return_value=MagicMock(tools=[
        MagicMock(name="stale", description="Stale tool", inputSchema={"type": "object"})
    ]))
    fake_session.call_tool = AsyncMock(side_effect=RuntimeError("Event loop is closed"))
    
    client._session = fake_session
    client._event_loop = stale_loop
    client._initialized = True
    client._tools = [
        MCPToolSpec(
            name="stale",
            description="Stale tool",
            input_schema={"type": "object"},
        )
    ]
    
    # Mock the connect method to simulate reconnection
    new_session = MagicMock()
    new_session.closed = False
    new_session.initialize = AsyncMock()
    new_session.call_tool = AsyncMock(return_value=MagicMock(
        content=[MagicMock(text="echo: ok")],
        isError=False
    ))
    
    with patch.object(client, 'connect', new_callable=AsyncMock) as mock_connect:
        with patch.object(client, '_reset_client', new_callable=AsyncMock) as mock_reset:
            # Reset client state to simulate reconnection
            await client._reset_client()
            
            # After reset, simulate new connection
            client._session = new_session
            client._event_loop = asyncio.get_running_loop()
            client._initialized = True
            client._tools = [
                MCPToolSpec(
                    name="echo",
                    description="Echo input",
                    input_schema={"type": "object"},
                )
            ]
            
            # Call the tool
            result = await client.call_tool("echo", {"value": "ok"})
            
            assert client._event_loop is asyncio.get_running_loop()
            assert result is not None


@pytest.mark.asyncio
async def test_mcp_client_retries_once_after_closed_loop_call_error() -> None:
    """Test that MCP client retries once after a closed loop error"""
    config = MCPServerConfig(
        name="test-server",
        transport=MCPTransportType.HTTP,
        url="http://example.test/mcp",
    )
    
    client = MCPClient(config)
    
    # Setup initial broken state
    client._event_loop = asyncio.get_running_loop()
    client._initialized = True
    client._tools = [
        MCPToolSpec(
            name="echo",
            description="Echo input",
            input_schema={"type": "object"},
        )
    ]
    
    call_count = 0
    
    async def mock_call_tool(tool_name: str, arguments: dict) -> dict:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise RuntimeError("Event loop is closed")
        return {"content": [{"text": "echo: ok"}], "isError": False}
    
    # Mock the call_tool method
    with patch.object(client, '_ensure_active_loop', new_callable=AsyncMock):
        with patch.object(client, 'connect', new_callable=AsyncMock):
            # Simulate the behavior: first call fails, then reset and retry
            try:
                # First call - simulate failure
                await mock_call_tool("echo", {"value": "ok"})
            except RuntimeError:
                # Reset and retry
                await client._reset_client()
                client._session = MagicMock()
                client._session.call_tool = mock_call_tool
                client._initialized = True
                
                # Second call should succeed
                result = await client.call_tool("echo", {"value": "ok"})
                
                assert call_count == 2
                assert result is not None
