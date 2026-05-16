"""MCP Capability Negotiation & Data Models.

Defines capability tracking, resource/prompt/sampling specs, and auth config
for JARVIS's MCP integration. Uses the MCP Python SDK v1.26+ types.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from mcp.types import (
    Prompt,
    Resource,
    ResourceTemplate,
    ServerCapabilities,
)

# ============================================================================
# SERVER CAPABILITIES TRACKING
# ============================================================================


@dataclass
class MCPServerCapabilities:
    """Structured representation of what an MCP server supports.

    Populated after initialize() by inspecting the server's advertised capabilities.
    """

    tools: bool = False
    resources: bool = False
    prompts: bool = False
    sampling: bool = False
    logging: bool = False
    completions: bool = False
    tasks: bool = False

    @classmethod
    def from_server_capabilities(cls, caps: ServerCapabilities | None) -> MCPServerCapabilities:
        """Create from the SDK's ServerCapabilities object."""
        if caps is None:
            return cls()

        return cls(
            tools=caps.tools is not None,
            resources=caps.resources is not None,
            prompts=caps.prompts is not None,
            logging=caps.logging is not None,
            completions=caps.completions is not None if hasattr(caps, "completions") else False,
            tasks=caps.tasks is not None if hasattr(caps, "tasks") else False,
            # Sampling is a *client* capability — we track whether the server
            # might request sampling (i.e., if we advertised SamplingCapability).
            sampling=False,
        )

    def to_dict(self) -> dict[str, bool]:
        return {
            "tools": self.tools,
            "resources": self.resources,
            "prompts": self.prompts,
            "sampling": self.sampling,
            "logging": self.logging,
            "completions": self.completions,
            "tasks": self.tasks,
        }


# ============================================================================
# RESOURCE DATA MODELS
# ============================================================================


@dataclass
class MCPResourceSpec:
    """Specification for an MCP resource."""

    uri: str
    name: str
    description: str = ""
    mime_type: str = ""
    server_name: str = ""

    @classmethod
    def from_sdk(cls, resource: Resource, server_name: str = "") -> MCPResourceSpec:
        """Create from the SDK's Resource object."""
        return cls(
            uri=str(resource.uri),
            name=resource.name or "",
            description=resource.description or "",
            mime_type=resource.mimeType or "",
            server_name=server_name,
        )


@dataclass
class MCPResourceTemplateSpec:
    """Specification for an MCP resource template."""

    uri_template: str
    name: str
    description: str = ""
    mime_type: str = ""
    server_name: str = ""

    @classmethod
    def from_sdk(cls, template: ResourceTemplate, server_name: str = "") -> MCPResourceTemplateSpec:
        """Create from the SDK's ResourceTemplate object."""
        return cls(
            uri_template=str(template.uriTemplate),
            name=template.name or "",
            description=template.description or "",
            mime_type=template.mimeType or "",
            server_name=server_name,
        )


@dataclass
class MCPResourceContent:
    """Content returned by reading an MCP resource."""

    uri: str
    mime_type: str = ""
    text: str = ""
    blob: bytes | None = None

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {"uri": self.uri, "mimeType": self.mime_type}
        if self.text:
            result["text"] = self.text
        if self.blob is not None:
            import base64

            result["blob"] = base64.b64encode(self.blob).decode()
        return result


# ============================================================================
# PROMPT DATA MODELS
# ============================================================================


@dataclass
class MCPPromptArgument:
    """Argument for an MCP prompt template."""

    name: str
    description: str = ""
    required: bool = False


@dataclass
class MCPPromptSpec:
    """Specification for an MCP prompt template."""

    name: str
    description: str = ""
    arguments: list[MCPPromptArgument] = field(default_factory=list)
    server_name: str = ""

    @classmethod
    def from_sdk(cls, prompt: Prompt, server_name: str = "") -> MCPPromptSpec:
        """Create from the SDK's Prompt object."""
        args = []
        if prompt.arguments:
            for arg in prompt.arguments:
                args.append(
                    MCPPromptArgument(
                        name=arg.name or "",
                        description=arg.description or "",
                        required=arg.required or False,
                    )
                )
        return cls(
            name=prompt.name,
            description=prompt.description or "",
            arguments=args,
            server_name=server_name,
        )


@dataclass
class MCPPromptMessage:
    """A single message in a rendered MCP prompt."""

    role: str  # "user" | "assistant"
    content: str

    def to_dict(self) -> dict[str, str]:
        return {"role": self.role, "content": self.content}


# ============================================================================
# AUTH CONFIG
# ============================================================================


@dataclass
class MCPAuthConfig:
    """Authentication configuration for an MCP server.

    Supported types:
    - "oauth": Full OAuth2 authorization code flow with PKCE
    - "bearer": Static bearer token in Authorization header
    - "api_key": API key in a configurable header or query parameter
    """

    type: str = ""  # "oauth" | "bearer" | "api_key" | ""

    # OAuth fields
    client_id: str = ""
    client_secret: str = ""
    scope: str = ""
    redirect_uri: str = ""

    # Bearer/API key fields
    token: str = ""
    header_name: str = "Authorization"
    header_prefix: str = "Bearer"

    # Token source — read token from environment variable
    token_env_var: str = ""

    # Client metadata URL for OAuth (URL-based client ID)
    client_metadata_url: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MCPAuthConfig:
        """Create from a dictionary."""
        return cls(
            type=data.get("type", ""),
            client_id=data.get("clientId", data.get("client_id", "")),
            client_secret=data.get("clientSecret", data.get("client_secret", "")),
            scope=data.get("scope", ""),
            redirect_uri=data.get("redirectUri", data.get("redirect_uri", "")),
            token=data.get("token", ""),
            header_name=data.get("headerName", data.get("header_name", "Authorization")),
            header_prefix=data.get("headerPrefix", data.get("header_prefix", "Bearer")),
            token_env_var=data.get("tokenEnvVar", data.get("token_env_var", "")),
            client_metadata_url=data.get(
                "clientMetadataUrl", data.get("client_metadata_url", "")
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "scope": self.scope,
            "redirect_uri": self.redirect_uri,
            "token": self.token,
            "header_name": self.header_name,
            "header_prefix": self.header_prefix,
            "token_env_var": self.token_env_var,
            "client_metadata_url": self.client_metadata_url,
        }

    def get_token(self) -> str:
        """Resolve the token from config or environment variable."""
        import os

        if self.token_env_var:
            env_token = os.environ.get(self.token_env_var, "")
            if env_token:
                return env_token
        return self.token

    @property
    def is_configured(self) -> bool:
        """Check if auth is configured."""
        return bool(self.type)
