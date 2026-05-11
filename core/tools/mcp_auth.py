"""MCP Authentication Manager for JARVIS.

Provides OAuth2, bearer token, and API key authentication for MCP servers.

Uses the MCP Python SDK's OAuthClientProvider for full OAuth2 flows:
- Authorization Code Flow with PKCE
- Automatic client registration
- Token refresh
- Protected resource metadata discovery

Also supports simpler auth mechanisms:
- Bearer tokens (static Authorization header)
- API keys (configurable header name)
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

from mcp.shared.auth import OAuthClientInformationFull, OAuthClientMetadata, OAuthToken
from mcp.client.auth.oauth2 import OAuthClientProvider, TokenStorage

logger = logging.getLogger(__name__)

AUTH_DIR = Path.home() / ".jarvis" / "auth"


# ============================================================================
# FILE-BASED TOKEN STORAGE
# ============================================================================


class FileTokenStorage:
    """File-based token storage for OAuth2 tokens.

    Stores tokens in ~/.jarvis/auth/<server_name>.json
    """

    def __init__(self, server_name: str, auth_dir: Path | None = None):
        self._server_name = server_name
        self._auth_dir = auth_dir or AUTH_DIR
        self._token_path = self._auth_dir / f"{server_name}.json"

    async def get_tokens(self) -> OAuthToken | None:
        """Get stored tokens."""
        if not self._token_path.exists():
            return None

        try:
            data = json.loads(self._token_path.read_text(encoding="utf-8"))
            token_data = data.get("tokens")
            if not token_data:
                return None
            return OAuthToken.model_validate(token_data)
        except Exception as e:
            logger.warning(f"Failed to load tokens for '{self._server_name}': {e}")
            return None

    async def set_tokens(self, tokens: OAuthToken) -> None:
        """Store tokens."""
        try:
            self._auth_dir.mkdir(parents=True, exist_ok=True)
            data = self._load_file()
            data["tokens"] = tokens.model_dump(mode="json")
            data["updated_at"] = time.time()
            self._token_path.write_text(
                json.dumps(data, indent=2), encoding="utf-8"
            )
        except Exception as e:
            logger.error(f"Failed to save tokens for '{self._server_name}': {e}")

    async def get_client_info(self) -> OAuthClientInformationFull | None:
        """Get stored client information."""
        if not self._token_path.exists():
            return None

        try:
            data = json.loads(self._token_path.read_text(encoding="utf-8"))
            client_data = data.get("client_info")
            if not client_data:
                return None
            return OAuthClientInformationFull.model_validate(client_data)
        except Exception as e:
            logger.warning(f"Failed to load client info for '{self._server_name}': {e}")
            return None

    async def set_client_info(self, client_info: OAuthClientInformationFull) -> None:
        """Store client information."""
        try:
            self._auth_dir.mkdir(parents=True, exist_ok=True)
            data = self._load_file()
            # Use model_dump with mode='json' to handle AnyUrl and other
            # non-standard types that aren't directly JSON serializable
            data["client_info"] = client_info.model_dump(mode="json")
            data["updated_at"] = time.time()
            self._token_path.write_text(
                json.dumps(data, indent=2), encoding="utf-8"
            )
        except Exception as e:
            logger.error(f"Failed to save client info for '{self._server_name}': {e}")

    def _load_file(self) -> dict[str, Any]:
        """Load the auth file as a dict."""
        if self._token_path.exists():
            try:
                return json.loads(self._token_path.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {}


# ============================================================================
# OAUTH CLIENT CREATION
# ============================================================================


async def create_oauth_client(config: Any) -> Any:
    """Create an authenticated httpx.AsyncClient for an OAuth2-protected MCP server.

    Args:
        config: MCPServerConfig with auth.type="oauth"

    Returns:
        httpx.AsyncClient with OAuth2 authentication
    """
    import httpx

    auth_config = config.auth
    if not auth_config:
        raise ValueError(f"No auth config for server '{config.name}'")

    server_url = config.url
    if not server_url:
        raise ValueError(f"No URL configured for OAuth MCP server '{config.name}'")

    # Build client metadata
    client_metadata = OAuthClientMetadata(
        client_name=f"JARVIS-{config.name}",
        redirect_uris=[auth_config.redirect_uri or "http://localhost:8765/callback"],
        grant_types=["authorization_code"],
        response_types=["code"],
        token_endpoint_auth_method="client_secret_post",
        scope=auth_config.scope or "openid profile email",
    )

    # Create token storage
    storage = FileTokenStorage(config.name)

    # Create redirect handler — opens browser for user authorization
    async def redirect_handler(authorization_url: str) -> None:
        """Open the authorization URL in the user's browser."""
        import webbrowser

        logger.info(f"Opening browser for OAuth authorization: {authorization_url}")
        print(f"\n🔐 OAuth Authorization Required for '{config.name}'")
        print(f"   Opening browser: {authorization_url}")
        print(f"   Waiting for authorization...\n")

        webbrowser.open(authorization_url)

    # Create callback handler — starts local server to receive callback
    async def callback_handler() -> tuple[str, str | None]:
        """Start a local server to receive the OAuth callback."""
        from http.server import HTTPServer, BaseHTTPRequestHandler
        from urllib.parse import urlparse, parse_qs
        import threading

        code: str | None = None
        state: str | None = None
        received = threading.Event()

        class CallbackHandler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                nonlocal code, state
                parsed = urlparse(self.path)
                params = parse_qs(parsed.query)

                if "code" in params:
                    code = params["code"][0]
                if "state" in params:
                    state = params["state"][0]

                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(
                    b"<html><body><h1>Authorization successful!</h1>"
                    b"<p>You can close this tab.</p></body></html>"
                )
                received.set()

            def log_message(self, format, *args) -> None:
                pass  # Suppress log output

        redirect_uri = auth_config.redirect_uri or "http://localhost:8765/callback"
        parsed_redirect = urlparse(redirect_uri)
        port = parsed_redirect.port or 8765

        server = HTTPServer(("localhost", port), CallbackHandler)
        server.timeout = 300  # 5 minute timeout

        # Run server in thread
        server_thread = threading.Thread(target=server.handle_request)
        server_thread.daemon = True
        server_thread.start()

        # Wait for callback
        received.wait(timeout=300)
        server.server_close()

        if not code:
            raise RuntimeError("OAuth authorization failed: no code received")

        return code, state

    # Create the OAuth provider
    oauth_provider = OAuthClientProvider(
        server_url=server_url,
        client_metadata=client_metadata,
        storage=storage,
        redirect_handler=redirect_handler,
        callback_handler=callback_handler,
        timeout=300.0,
        client_metadata_url=auth_config.client_metadata_url or None,
    )

    # Create httpx client with the OAuth provider as auth
    client = httpx.AsyncClient(auth=oauth_provider, timeout=30.0)

    logger.info(f"Created OAuth2 client for '{config.name}'")
    return client


# ============================================================================
# TOKEN STATUS HELPERS
# ============================================================================


def get_token_status(server_name: str) -> dict[str, Any]:
    """Get token status for a server.

    Returns dict with:
    - has_tokens: bool
    - is_expired: bool
    - auth_type: str
    - expires_at: float | None
    """
    token_path = AUTH_DIR / f"{server_name}.json"
    if not token_path.exists():
        return {"has_tokens": False, "is_expired": True, "auth_type": "none", "expires_at": None}

    try:
        data = json.loads(token_path.read_text(encoding="utf-8"))
        tokens = data.get("tokens", {})
        auth_type = data.get("auth_type", "oauth")

        expires_at = tokens.get("expires_at")
        is_expired = False
        if expires_at:
            is_expired = time.time() > expires_at

        return {
            "has_tokens": bool(tokens.get("access_token")),
            "is_expired": is_expired,
            "auth_type": auth_type,
            "expires_at": expires_at,
        }
    except Exception as e:
        logger.warning(f"Failed to get token status for '{server_name}': {e}")
        return {"has_tokens": False, "is_expired": True, "auth_type": "none", "expires_at": None}
