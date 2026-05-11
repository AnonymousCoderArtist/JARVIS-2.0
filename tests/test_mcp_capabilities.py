"""Tests for MCP capability negotiation and data models."""

import pytest

from core.tools.mcp_capabilities import (
    MCPAuthConfig,
    MCPPromptArgument,
    MCPPromptMessage,
    MCPPromptSpec,
    MCPResourceContent,
    MCPResourceSpec,
    MCPResourceTemplateSpec,
    MCPServerCapabilities,
)
from mcp.types import Prompt, Resource, ResourceTemplate, ServerCapabilities


class TestMCPServerCapabilities:
    """Tests for MCPServerCapabilities data model."""

    def test_defaults(self):
        caps = MCPServerCapabilities()
        assert caps.tools is False
        assert caps.resources is False
        assert caps.prompts is False
        assert caps.sampling is False
        assert caps.logging is False

    def test_from_server_capabilities_none(self):
        caps = MCPServerCapabilities.from_server_capabilities(None)
        assert caps.tools is False
        assert caps.resources is False

    def test_from_server_capabilities_with_tools(self):
        sdk_caps = ServerCapabilities(tools={})
        caps = MCPServerCapabilities.from_server_capabilities(sdk_caps)
        assert caps.tools is True
        assert caps.resources is False

    def test_from_server_capabilities_with_resources(self):
        sdk_caps = ServerCapabilities(resources={})
        caps = MCPServerCapabilities.from_server_capabilities(sdk_caps)
        assert caps.resources is True

    def test_from_server_capabilities_with_prompts(self):
        sdk_caps = ServerCapabilities(prompts={})
        caps = MCPServerCapabilities.from_server_capabilities(sdk_caps)
        assert caps.prompts is True

    def test_from_server_capabilities_with_all(self):
        sdk_caps = ServerCapabilities(
            tools={}, resources={}, prompts={}, logging={}
        )
        caps = MCPServerCapabilities.from_server_capabilities(sdk_caps)
        assert caps.tools is True
        assert caps.resources is True
        assert caps.prompts is True
        assert caps.logging is True
        # sampling is client capability, always False from server caps
        assert caps.sampling is False

    def test_to_dict(self):
        caps = MCPServerCapabilities(tools=True, resources=True)
        d = caps.to_dict()
        assert d["tools"] is True
        assert d["resources"] is True
        assert d["prompts"] is False
        assert d["sampling"] is False


class TestMCPResourceSpec:
    """Tests for MCPResourceSpec data model."""

    def test_defaults(self):
        spec = MCPResourceSpec(uri="file:///test.txt", name="test")
        assert spec.uri == "file:///test.txt"
        assert spec.name == "test"
        assert spec.description == ""
        assert spec.mime_type == ""
        assert spec.server_name == ""

    def test_from_sdk(self):
        sdk_resource = Resource(uri="file:///data.json", name="data", mimeType="application/json")
        spec = MCPResourceSpec.from_sdk(sdk_resource, server_name="myserver")
        assert spec.uri == "file:///data.json"
        assert spec.name == "data"
        assert spec.mime_type == "application/json"
        assert spec.server_name == "myserver"

    def test_from_sdk_missing_fields(self):
        sdk_resource = Resource(uri="file:///x", name="x")
        spec = MCPResourceSpec.from_sdk(sdk_resource)
        assert spec.mime_type == ""
        assert spec.description == ""


class TestMCPResourceTemplateSpec:
    """Tests for MCPResourceTemplateSpec data model."""

    def test_from_sdk(self):
        sdk_template = ResourceTemplate(
            uriTemplate="file:///{category}/data", name="category_data", mimeType="text/plain"
        )
        spec = MCPResourceTemplateSpec.from_sdk(sdk_template, server_name="test")
        assert spec.uri_template == "file:///{category}/data"
        assert spec.name == "category_data"
        assert spec.mime_type == "text/plain"
        assert spec.server_name == "test"


class TestMCPResourceContent:
    """Tests for MCPResourceContent data model."""

    def test_text_content(self):
        content = MCPResourceContent(uri="file:///test.txt", text="hello world")
        d = content.to_dict()
        assert d["uri"] == "file:///test.txt"
        assert d["text"] == "hello world"
        assert "blob" not in d

    def test_blob_content(self):
        content = MCPResourceContent(uri="file:///image.png", blob=b"\x89PNG")
        d = content.to_dict()
        assert "blob" in d
        import base64
        assert base64.b64decode(d["blob"]) == b"\x89PNG"

    def test_empty_content(self):
        content = MCPResourceContent(uri="file:///empty")
        d = content.to_dict()
        assert d["uri"] == "file:///empty"
        assert "text" not in d
        assert "blob" not in d


class TestMCPPromptSpec:
    """Tests for MCPPromptSpec data model."""

    def test_from_sdk(self):
        from mcp.types import PromptArgument
        sdk_prompt = Prompt(
            name="code_review",
            description="Review code",
            arguments=[
                PromptArgument(name="code", description="Code to review", required=True),
                PromptArgument(name="language", description="Programming language"),
            ],
        )
        spec = MCPPromptSpec.from_sdk(sdk_prompt, server_name="reviewer")
        assert spec.name == "code_review"
        assert spec.description == "Review code"
        assert len(spec.arguments) == 2
        assert spec.arguments[0].name == "code"
        assert spec.arguments[0].required is True
        assert spec.arguments[1].name == "language"
        assert spec.arguments[1].required is False
        assert spec.server_name == "reviewer"

    def test_from_sdk_no_arguments(self):
        sdk_prompt = Prompt(name="hello", description="Say hello")
        spec = MCPPromptSpec.from_sdk(sdk_prompt)
        assert spec.arguments == []


class TestMCPPromptMessage:
    """Tests for MCPPromptMessage data model."""

    def test_to_dict(self):
        msg = MCPPromptMessage(role="user", content="Review this code")
        d = msg.to_dict()
        assert d["role"] == "user"
        assert d["content"] == "Review this code"


class TestMCPAuthConfig:
    """Tests for MCPAuthConfig data model."""

    def test_defaults(self):
        auth = MCPAuthConfig()
        assert auth.type == ""
        assert auth.is_configured is False

    def test_bearer_from_dict(self):
        auth = MCPAuthConfig.from_dict({
            "type": "bearer",
            "token": "my-secret-token",
        })
        assert auth.type == "bearer"
        assert auth.token == "my-secret-token"
        assert auth.is_configured is True

    def test_api_key_from_dict(self):
        auth = MCPAuthConfig.from_dict({
            "type": "api_key",
            "token": "key123",
            "headerName": "X-API-Key",
        })
        assert auth.type == "api_key"
        assert auth.header_name == "X-API-Key"

    def test_oauth_from_dict(self):
        auth = MCPAuthConfig.from_dict({
            "type": "oauth",
            "clientId": "my-client",
            "scope": "openid profile",
        })
        assert auth.type == "oauth"
        assert auth.client_id == "my-client"
        assert auth.scope == "openid profile"

    def test_token_env_var(self):
        import os
        os.environ["TEST_MCP_TOKEN"] = "env-token-123"
        try:
            auth = MCPAuthConfig(token_env_var="TEST_MCP_TOKEN")
            assert auth.get_token() == "env-token-123"
        finally:
            del os.environ["TEST_MCP_TOKEN"]

    def test_token_env_var_missing(self):
        auth = MCPAuthConfig(token_env_var="NONEXISTENT_VAR_12345", token="fallback")
        assert auth.get_token() == "fallback"

    def test_to_dict(self):
        auth = MCPAuthConfig(type="bearer", token="abc")
        d = auth.to_dict()
        assert d["type"] == "bearer"
        assert d["token"] == "abc"
        # token_env_var is also included but empty
        assert "token_env_var" in d

    def test_from_dict_legacy_names(self):
        auth = MCPAuthConfig.from_dict({
            "type": "oauth",
            "client_id": "legacy-id",
            "client_secret": "legacy-secret",
            "redirect_uri": "http://localhost:9999/callback",
        })
        assert auth.client_id == "legacy-id"
        assert auth.client_secret == "legacy-secret"
        assert auth.redirect_uri == "http://localhost:9999/callback"
