import logging
from collections.abc import AsyncGenerator
from typing import Any

import httpx
from curl_cffi.requests import AsyncSession
from curl_cffi.requests import Headers as CurlHeaders

logger = logging.getLogger(__name__)

# Default timeout for HTTP requests (30 minutes for long-running LLM operations)
DEFAULT_TIMEOUT = 1800.0

class HTTPClient:
    """
    Custom HTTP Client using httpx for simple requests and
    curl_cffi for LLM interactions to handle TLS fingerprints.
    """

    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.httpx_client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(DEFAULT_TIMEOUT, connect=30.0)
        )
        self.curl_session = AsyncSession(
            impersonate="chrome110",
            timeout=DEFAULT_TIMEOUT
        )

    async def fetch_models(self, endpoint: str, headers: dict[str, str]) -> dict[str, Any]:
        """Fetch models using httpx as requested."""
        try:
            response = await self.httpx_client.get(endpoint, headers=headers)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error fetching models from {endpoint}: {e}")
            raise

    async def post(self, endpoint: str, json_data: dict[str, Any], headers: dict[str, str]) -> dict[str, Any]:
        """Post request using curl_cffi."""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        response = await self.curl_session.post(
            url,
            json=json_data,
            headers=headers,
            timeout=DEFAULT_TIMEOUT
        )
        if response.status_code >= 400:
            raise Exception(f"HTTP {response.status_code}: {response.text}")
        return response.json()

    async def stream(self, endpoint: str, json_data: dict[str, Any], headers: dict[str, str]) -> AsyncGenerator[str, None]:
        """Streaming post request using curl_cffi."""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"

        # curl_cffi stream handling
        response = await self.curl_session.post(
            url,
            json=json_data,
            headers=headers,
            stream=True,
            timeout=DEFAULT_TIMEOUT
        )
        if response.status_code >= 400:
            raise Exception(f"HTTP {response.status_code}: {response.text}")

        try:
            async for line in response.aiter_lines():
                if line:
                    # Handle both bytes and string responses
                    if isinstance(line, bytes):
                        yield line.decode("utf-8")
                    else:
                        yield line
        except Exception as e:
            logger.error(f"Error during streaming: {e}")
            raise

    async def close(self):
        """Close both httpx and curl_cffi sessions."""
        try:
            await self.httpx_client.aclose()
        except Exception as e:
            logger.debug(f"Error closing httpx client: {e}")

        try:
            # curl_cffi AsyncSession doesn't have aclose but close
            await self.curl_session.close()
        except Exception as e:
            logger.debug(f"Error closing curl session: {e}")

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
