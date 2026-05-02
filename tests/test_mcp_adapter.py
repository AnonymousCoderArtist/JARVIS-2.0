import asyncio

import pytest

from core.tools import mcp_adapter
from core.tools.mcp_adapter import (
    MCPClient,
    MCPServerConfig,
    MCPToolSpec,
    MCPTransport,
    MCPTransportType,
)


class FakeTransport(MCPTransport):
    def __init__(self) -> None:
        self.closed = False
        self.called = False

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
        return {"content": [{"text": f"{tool_name}: {arguments['value']}"}]}

    async def close(self) -> None:
        self.closed = True


class LoopClosedTransport(FakeTransport):
    async def call_tool(self, tool_name: str, arguments: dict) -> dict:
        raise RuntimeError("Event loop is closed")


@pytest.mark.asyncio
async def test_mcp_client_reconnects_when_previous_loop_is_closed(monkeypatch) -> None:
    transports: list[FakeTransport] = []

    def make_transport(*_args, **_kwargs) -> FakeTransport:
        transport = FakeTransport()
        transports.append(transport)
        return transport

    monkeypatch.setattr(mcp_adapter, "HTTPTransport", make_transport)

    client = MCPClient(
        MCPServerConfig(
            name="test-server",
            transport=MCPTransportType.HTTP,
            url="http://example.test/mcp",
        )
    )

    stale_loop = asyncio.new_event_loop()
    stale_loop.close()
    stale_transport = FakeTransport()

    client._event_loop = stale_loop
    client._transport = stale_transport
    client._initialized = True
    client._tools = [
        MCPToolSpec(
            name="stale",
            description="Stale tool",
            input_schema={"type": "object"},
        )
    ]

    result = await client.call_tool("echo", {"value": "ok"})

    assert stale_transport.closed is True
    assert transports
    assert transports[0].called is True
    assert client._transport is transports[0]
    assert client._event_loop is asyncio.get_running_loop()
    assert result == {"content": [{"text": "echo: ok"}]}


@pytest.mark.asyncio
async def test_mcp_client_retries_once_after_closed_loop_call_error(monkeypatch) -> None:
    transports: list[FakeTransport] = []

    def make_transport(*_args, **_kwargs) -> FakeTransport:
        transport = FakeTransport()
        transports.append(transport)
        return transport

    monkeypatch.setattr(mcp_adapter, "HTTPTransport", make_transport)

    client = MCPClient(
        MCPServerConfig(
            name="test-server",
            transport=MCPTransportType.HTTP,
            url="http://example.test/mcp",
        )
    )
    broken_transport = LoopClosedTransport()

    client._event_loop = asyncio.get_running_loop()
    client._transport = broken_transport
    client._initialized = True
    client._tools = [
        MCPToolSpec(
            name="echo",
            description="Echo input",
            input_schema={"type": "object"},
        )
    ]

    result = await client.call_tool("echo", {"value": "ok"})

    assert broken_transport.closed is True
    assert transports
    assert transports[0].called is True
    assert client._transport is transports[0]
    assert result == {"content": [{"text": "echo: ok"}]}
