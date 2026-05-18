"""WorldMonitor API Client for Watchers"""

import httpx
import logging
import time
from typing import Any, Optional

try:
    from webscout import litagent
    HAS_LITAGENT = True
except ImportError:
    HAS_LITAGENT = False

logger = logging.getLogger(__name__)

class WorldMonitorClient:
    def __init__(self, base_url: str, user_agent: str):
        self.base_url = base_url
        self._default_ua = user_agent
        self._session_token = None
        self._token_exp = 0
        self._client = httpx.AsyncClient(
            base_url=base_url, 
            timeout=30.0
        )

    def _get_ua(self) -> str:
        if HAS_LITAGENT:
            try:
                # Get a random modern user agent
                return litagent.random()  # ty:ignore[unresolved-attribute]
            except Exception:
                return self._default_ua
        return self._default_ua

    async def close(self):
        await self._client.aclose()

    async def _create_session(self) -> Optional[str]:
        try:
            headers = {
                "Content-Type": "application/json",
                "User-Agent": self._get_ua()
            }
            response = await self._client.post(
                "/api/wm-session", 
                headers=headers
            )
            response.raise_for_status()
            data = response.json()
            self._session_token = data["token"]
            self._token_exp = data.get("exp", 0)
            return self._session_token
        except Exception as e:
            logger.error(f"WorldMonitor session creation failed: {e}")
            return None

    async def ensure_session(self) -> Optional[str]:
        # Check if token is expired or nearly expired (within 5 mins)
        now_ms = time.time() * 1000
        if not self._session_token or now_ms > (self._token_exp - 300000):
            return await self._create_session()
        return self._session_token

    async def fetch(self, path: str) -> Optional[dict[str, Any]]:
        token = await self.ensure_session()
        if not token:
            return None
            
        try:
            headers = {
                "X-WorldMonitor-Key": token,
                "Origin": "https://www.worldmonitor.app",
                "Referer": "https://www.worldmonitor.app/",
                "User-Agent": self._get_ua()
            }
            resp = await self._client.get(path, headers=headers)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.error(f"WorldMonitor fetch failed for {path}: {e}")
            # Reset session on potential auth errors
            if isinstance(e, httpx.HTTPStatusError) and e.response.status_code in (401, 403):
                self._session_token = None
            return None
