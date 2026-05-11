"""Tests for MCP auth module — OAuth2, bearer, API key, token storage."""

import json
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.tools.mcp_auth import AUTH_DIR, FileTokenStorage, get_token_status
from core.tools.mcp_capabilities import MCPAuthConfig


class TestFileTokenStorage:
    """Tests for FileTokenStorage."""

    def test_init(self, tmp_path: Path):
        storage = FileTokenStorage("test-server", auth_dir=tmp_path)
        assert storage._server_name == "test-server"
        assert storage._token_path == tmp_path / "test-server.json"

    @pytest.mark.asyncio
    async def test_get_tokens_empty(self, tmp_path: Path):
        storage = FileTokenStorage("test-server", auth_dir=tmp_path)
        tokens = await storage.get_tokens()
        assert tokens is None

    @pytest.mark.asyncio
    async def test_set_and_get_tokens(self, tmp_path: Path):
        from mcp.shared.auth import OAuthToken

        storage = FileTokenStorage("test-server", auth_dir=tmp_path)
        token = OAuthToken(
            access_token="test-access-token",
            token_type="Bearer",
            expires_in=3600,
            scope="openid profile",
        )
        await storage.set_tokens(token)

        # Verify file was created
        assert storage._token_path.exists()

        # Verify we can read it back
        loaded = await storage.get_tokens()
        assert loaded is not None
        assert loaded.access_token == "test-access-token"

    @pytest.mark.asyncio
    async def test_get_client_info_empty(self, tmp_path: Path):
        storage = FileTokenStorage("test-server", auth_dir=tmp_path)
        info = await storage.get_client_info()
        assert info is None

    @pytest.mark.asyncio
    async def test_set_and_get_client_info(self, tmp_path: Path):
        from mcp.shared.auth import OAuthClientInformationFull

        storage = FileTokenStorage("test-server", auth_dir=tmp_path)
        client_info = OAuthClientInformationFull(
            client_id="test-client-id",
            client_secret="test-secret",
            redirect_uris=["http://localhost:8765/callback"],
        )
        await storage.set_client_info(client_info)

        loaded = await storage.get_client_info()
        assert loaded is not None
        assert loaded.client_id == "test-client-id"

    @pytest.mark.asyncio
    async def test_creates_auth_dir(self, tmp_path: Path):
        nested = tmp_path / "sub" / "dir"
        storage = FileTokenStorage("test-server", auth_dir=nested)
        from mcp.shared.auth import OAuthToken

        token = OAuthToken(access_token="abc", token_type="Bearer")
        await storage.set_tokens(token)
        assert nested.exists()
        assert (nested / "test-server.json").exists()

    @pytest.mark.asyncio
    async def test_corrupted_file_returns_none(self, tmp_path: Path):
        storage = FileTokenStorage("test-server", auth_dir=tmp_path)
        # Write corrupted data
        storage._token_path.parent.mkdir(parents=True, exist_ok=True)
        storage._token_path.write_text("not valid json{{{{", encoding="utf-8")

        tokens = await storage.get_tokens()
        assert tokens is None


class TestGetTokenStatus:
    """Tests for get_token_status helper."""

    def test_no_token_file(self, tmp_path: Path):
        with patch("core.tools.mcp_auth.AUTH_DIR", tmp_path):
            status = get_token_status("nonexistent")
            assert status["has_tokens"] is False
            assert status["is_expired"] is True
            assert status["auth_type"] == "none"

    def test_valid_token(self, tmp_path: Path):
        with patch("core.tools.mcp_auth.AUTH_DIR", tmp_path):
            token_path = tmp_path / "test-server.json"
            token_path.parent.mkdir(parents=True, exist_ok=True)
            token_path.write_text(json.dumps({
                "tokens": {"access_token": "abc", "expires_at": time.time() + 3600},
                "auth_type": "bearer",
            }), encoding="utf-8")

            status = get_token_status("test-server")
            assert status["has_tokens"] is True
            assert status["is_expired"] is False
            assert status["auth_type"] == "bearer"

    def test_expired_token(self, tmp_path: Path):
        with patch("core.tools.mcp_auth.AUTH_DIR", tmp_path):
            token_path = tmp_path / "test-server.json"
            token_path.parent.mkdir(parents=True, exist_ok=True)
            token_path.write_text(json.dumps({
                "tokens": {"access_token": "abc", "expires_at": time.time() - 100},
                "auth_type": "oauth",
            }), encoding="utf-8")

            status = get_token_status("test-server")
            assert status["has_tokens"] is True
            assert status["is_expired"] is True
            assert status["auth_type"] == "oauth"

    def test_corrupted_file(self, tmp_path: Path):
        with patch("core.tools.mcp_auth.AUTH_DIR", tmp_path):
            token_path = tmp_path / "test-server.json"
            token_path.parent.mkdir(parents=True, exist_ok=True)
            token_path.write_text("not json{{", encoding="utf-8")

            status = get_token_status("test-server")
            assert status["has_tokens"] is False
            assert status["is_expired"] is True


class TestMCPAuthConfigIntegration:
    """Tests for MCPAuthConfig with the auth system."""

    def test_bearer_auth_config(self):
        auth = MCPAuthConfig.from_dict({
            "type": "bearer",
            "token": "my-token",
        })
        assert auth.type == "bearer"
        assert auth.get_token() == "my-token"
        assert auth.is_configured is True

    def test_api_key_auth_config(self):
        auth = MCPAuthConfig.from_dict({
            "type": "api_key",
            "token": "key-123",
            "headerName": "X-API-Key",
        })
        assert auth.type == "api_key"
        assert auth.header_name == "X-API-Key"
        assert auth.get_token() == "key-123"

    def test_env_var_token_resolution(self):
        import os
        os.environ["TEST_JARVIS_TOKEN"] = "from-env"
        try:
            auth = MCPAuthConfig(token_env_var="TEST_JARVIS_TOKEN", token="fallback")
            assert auth.get_token() == "from-env"
        finally:
            del os.environ["TEST_JARVIS_TOKEN"]

    def test_env_var_missing_falls_back_to_token(self):
        auth = MCPAuthConfig(token_env_var="NONEXISTENT_JARVIS_VAR", token="fallback")
        assert auth.get_token() == "fallback"

    def test_server_config_with_auth(self):
        from core.tools.mcp_adapter import MCPServerConfig

        config = MCPServerConfig.from_dict({
            "name": "protected-server",
            "url": "https://api.example.com/mcp",
            "transport": "http",
            "auth": {
                "type": "bearer",
                "token": "secret-token",
            },
        })
        assert config.auth is not None
        assert config.auth.type == "bearer"
        assert config.auth.token == "secret-token"

    def test_server_config_without_auth(self):
        from core.tools.mcp_adapter import MCPServerConfig

        config = MCPServerConfig.from_dict({
            "name": "open-server",
            "command": "npx",
            "args": ["mcp-server"],
        })
        assert config.auth is None

    def test_server_config_oauth(self):
        from core.tools.mcp_adapter import MCPServerConfig

        config = MCPServerConfig.from_dict({
            "name": "oauth-server",
            "url": "https://api.example.com/mcp",
            "transport": "http",
            "auth": {
                "type": "oauth",
                "clientId": "jarvis-client",
                "scope": "openid profile email",
                "redirectUri": "http://localhost:8765/callback",
            },
        })
        assert config.auth is not None
        assert config.auth.type == "oauth"
        assert config.auth.client_id == "jarvis-client"
