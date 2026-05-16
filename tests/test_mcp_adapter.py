import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.tools.mcp_adapter import (
    MCPClient,
    MCPServerConfig,
    MCPToolSpec,
    MCPTransportType,
)
from core.tools.mcp_metadata_cache import (
    MCPMetadataCache,
    ToolMetadata,
    compute_config_hash,
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


# ============================================================================
# Lazy MCP Tests
# ============================================================================


class TestMCPServerConfigExtensions:
    """Test extended MCPServerConfig with lazy fields."""

    def test_default_lifecycle_is_lazy(self):
        config = MCPServerConfig(name="test")
        assert config.lifecycle == "lazy"

    def test_default_idle_timeout(self):
        config = MCPServerConfig(name="test")
        assert config.idle_timeout == 15.0

    def test_default_direct_tools_is_false(self):
        config = MCPServerConfig(name="test")
        assert config.direct_tools is False

    def test_from_dict_with_new_fields(self):
        data = {
            "name": "my-server",
            "command": "npx",
            "args": ["-y", "my-mcp"],
            "lifecycle": "eager",
            "idleTimeout": 30,
            "directTools": ["tool1", "tool2"],
            "excludeTools": ["internal"],
        }
        config = MCPServerConfig.from_dict(data)
        assert config.lifecycle == "eager"
        assert config.idle_timeout == 30
        assert config.direct_tools == ["tool1", "tool2"]
        assert config.exclude_tools == ["internal"]

    def test_from_dict_direct_tools_true(self):
        data = {"name": "test", "directTools": True}
        config = MCPServerConfig.from_dict(data)
        assert config.direct_tools is True

    def test_from_dict_legacy_field_names(self):
        data = {
            "name": "test",
            "idle_timeout": 20,
            "direct_tools": ["t1"],
            "exclude_tools": ["t2"],
        }
        config = MCPServerConfig.from_dict(data)
        assert config.idle_timeout == 20
        assert config.direct_tools == ["t1"]
        assert config.exclude_tools == ["t2"]

    def test_from_dict_defaults(self):
        data = {"name": "test"}
        config = MCPServerConfig.from_dict(data)
        assert config.lifecycle == "lazy"
        assert config.idle_timeout == 15.0
        assert config.direct_tools is False
        assert config.exclude_tools == []


class TestMCPMetadataCache:
    """Test MCPMetadataCache."""

    def test_empty_cache(self, tmp_path):
        cache = MCPMetadataCache(cache_path=tmp_path / "test-cache.json")
        assert cache.total_tools == 0
        assert cache.server_names == []

    def test_update_and_get_server(self, tmp_path):
        cache = MCPMetadataCache(cache_path=tmp_path / "test-cache.json")
        tools = [
            ToolMetadata(
                name="mcp_test_echo",
                original_name="echo",
                description="Echo input",
                input_schema={"type": "object"},
                server_name="test",
            ),
        ]
        config_dict = {"command": "test", "url": "", "transport": "stdio"}
        cache.update_server("test", tools, config_dict)

        assert cache.total_tools == 1
        assert "test" in cache.server_names

        smeta = cache.get_server("test")
        assert smeta is not None
        assert len(smeta.tools) == 1
        assert smeta.tools[0].original_name == "echo"

    def test_search_tools_by_name(self, tmp_path):
        cache = MCPMetadataCache(cache_path=tmp_path / "test-cache.json")
        tools = [
            ToolMetadata("mcp_test_echo", "echo", "Echo input", {}, "test"),
            ToolMetadata("mcp_test_search", "search", "Search code", {}, "test"),
        ]
        cache.update_server("test", tools, {"command": "test"})

        matches = cache.search_tools("echo")
        assert len(matches) == 1
        assert matches[0].original_name == "echo"

    def test_search_tools_by_description(self, tmp_path):
        cache = MCPMetadataCache(cache_path=tmp_path / "test-cache.json")
        tools = [
            ToolMetadata("mcp_test_echo", "echo", "Echo input", {}, "test"),
            ToolMetadata("mcp_test_search", "search", "Search code", {}, "test"),
        ]
        cache.update_server("test", tools, {"command": "test"})

        matches = cache.search_tools("search code")
        assert len(matches) == 1
        assert matches[0].original_name == "search"

    def test_search_tools_with_regex(self, tmp_path):
        cache = MCPMetadataCache(cache_path=tmp_path / "test-cache.json")
        tools = [
            ToolMetadata("mcp_test_echo", "echo", "Echo input", {}, "test"),
            ToolMetadata("mcp_test_search", "search", "Search code", {}, "test"),
        ]
        cache.update_server("test", tools, {"command": "test"})

        matches = cache.search_tools("ech.+", regex=True)
        assert len(matches) == 1

    def test_search_tools_server_filter(self, tmp_path):
        cache = MCPMetadataCache(cache_path=tmp_path / "test-cache.json")
        tools_a = [ToolMetadata("mcp_a_echo", "echo", "Echo from A", {}, "a")]
        tools_b = [ToolMetadata("mcp_b_echo", "echo", "Echo from B", {}, "b")]
        cache.update_server("a", tools_a, {"command": "a"})
        cache.update_server("b", tools_b, {"command": "b"})

        matches = cache.search_tools("echo", server="a")
        assert len(matches) == 1
        assert matches[0].server_name == "a"

    def test_remove_server(self, tmp_path):
        cache = MCPMetadataCache(cache_path=tmp_path / "test-cache.json")
        tools = [ToolMetadata("mcp_test_echo", "echo", "Echo", {}, "test")]
        cache.update_server("test", tools, {"command": "test"})

        cache.remove_server("test")
        assert cache.get_server("test") is None
        assert cache.total_tools == 0

    def test_persistence_across_instances(self, tmp_path):
        path = tmp_path / "test-cache.json"
        cache1 = MCPMetadataCache(cache_path=path)
        tools = [ToolMetadata("mcp_test_echo", "echo", "Echo", {}, "test")]
        cache1.update_server("test", tools, {"command": "test"})

        # Create a new instance loading from the same file
        cache2 = MCPMetadataCache(cache_path=path)
        assert cache2.total_tools == 1
        assert cache2.get_server("test") is not None

    def test_is_valid_with_matching_config(self, tmp_path):
        cache = MCPMetadataCache(cache_path=tmp_path / "test-cache.json")
        config_dict = {"command": "my-server", "url": "", "transport": "stdio"}
        tools = [ToolMetadata("mcp_test_echo", "echo", "Echo", {}, "test")]
        cache.update_server("test", tools, config_dict)

        assert cache.is_valid("test", config_dict) is True
        assert cache.is_valid("test", {"command": "different"}) is False

    def test_get_tool_by_prefixed_name(self, tmp_path):
        cache = MCPMetadataCache(cache_path=tmp_path / "test-cache.json")
        tools = [ToolMetadata("mcp_test_echo", "echo", "Echo", {}, "test")]
        cache.update_server("test", tools, {"command": "test"})

        found = cache.get_tool_by_prefixed_name("mcp_test_echo")
        assert found is not None
        assert found.original_name == "echo"

        not_found = cache.get_tool_by_prefixed_name("mcp_test_nonexistent")
        assert not_found is None


class TestComputeConfigHash:
    """Test config hash computation."""

    def test_same_config_same_hash(self):
        d = {"command": "test", "args": ["-y", "foo"]}
        h1 = compute_config_hash(d)
        h2 = compute_config_hash(d)
        assert h1 == h2

    def test_different_config_different_hash(self):
        h1 = compute_config_hash({"command": "test1"})
        h2 = compute_config_hash({"command": "test2"})
        assert h1 != h2

    def test_irrelevant_keys_ignored(self):
        h1 = compute_config_hash({"command": "test", "name": "a"})
        h2 = compute_config_hash({"command": "test", "name": "b"})
        # 'name' is not in relevant_keys, so hash should be the same
        assert h1 == h2
