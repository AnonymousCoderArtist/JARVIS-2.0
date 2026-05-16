"""HTTP connector - fetch data from arbitrary HTTP endpoints"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional
from urllib.parse import urlparse

try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False

logger = logging.getLogger(__name__)

from .base import BaseConnector, ConnectorConfig, Document, SyncStatus
from .registry import ConnectorRegistry


DEFAULT_CONFIG_DIR = Path.home() / ".jarvis" / "credentials"


@ConnectorRegistry.register("http")
class HTTPConnector(BaseConnector):
    """Fetch data from arbitrary HTTP endpoints - useful for webhooks and APIs"""
    
    connector_id = "http"
    display_name = "HTTP Endpoint"
    auth_type = "none"  # Can be configured with auth
    
    def __init__(self, config: Optional[ConnectorConfig] = None):
        super().__init__(config)
        self._default_headers = {}
        self._timeout = 30.0
        self._status = SyncStatus()
    
    def is_connected(self) -> bool:
        """HTTP connector is always "connected" (can make requests)"""
        return True
    
    def disconnect(self) -> None:
        """Nothing to disconnect"""
        pass
    
    def sync(
        self, *, since: Optional[datetime] = None, cursor: Optional[str] = None
    ) -> Iterator[Document]:
        """Fetch from configured HTTP endpoints
        
        This connector can be configured with multiple endpoints in config.
        Example config:
            "endpoints": [
                {"url": "https://api.example.com/data", "method": "GET"},
                {"url": "https://api.example.com/webhook", "method": "POST"}
            ]
        """
        endpoints = self.config.get_credential("endpoints", [])
        
        if not endpoints:
            # Try to get from config directly
            endpoints = self.config.config.get("endpoints", [])
        
        if not endpoints:
            # Use a single default endpoint from config
            url = self.config.get_credential("url", "")
            if url:
                endpoints = [{"url": url, "method": "GET"}]
        
        if not isinstance(endpoints, list):
            endpoints = []
        
        for endpoint in endpoints[:10]:  # Limit to 10 endpoints
            if not isinstance(endpoint, dict):
                continue
            url = endpoint.get("url", "")
            method = str(endpoint.get("method", "GET")).upper()
            
            if not url:
                continue
            
            try:
                if not HAS_HTTPX:
                    logger.warning("httpx required for HTTP connector")
                    continue
                
                headers = {**self._default_headers}
                extra_headers = endpoint.get("headers", {})
                if isinstance(extra_headers, dict):
                    headers.update(extra_headers)
                
                response = httpx.request(
                    method=method,
                    url=url,
                    headers=headers,
                    timeout=self._timeout,
                )
                response.raise_for_status()
                
                # Try to parse JSON, fallback to text
                try:
                    data = response.json()
                    content = json.dumps(data)
                except:
                    content = response.text
                
                yield Document(
                    doc_id=f"http-{hash(url)}-{datetime.now().timestamp()}",
                    source="http",
                    doc_type=endpoint.get("doc_type", "http_response"),
                    content=content[:5000],  # Limit content size
                    title=f"Response from {url}",
                    timestamp=datetime.now(),
                    url=url,
                    metadata={
                        "status_code": response.status_code,
                        "method": method,
                        "url": url,
                    }
                )
                
            except Exception as e:
                logger.debug(f"HTTP request failed for {url}: {e}")
                continue
        
        self._status.state = "idle"
        self._status.last_sync = datetime.now()
    
    def sync_status(self) -> SyncStatus:
        return self._status
    
    # --- Direct fetch method for tools ---
    
    def fetch_url(
        self, 
        url: str, 
        method: str = "GET",
        headers: Optional[Dict[str, str]] = None,
        data: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Directly fetch a URL - useful for tools"""
        if not HAS_HTTPX:
            raise ImportError("httpx is required for HTTP connector")
        
        request_headers = {**self._default_headers}
        if headers:
            request_headers.update(headers)
        
        kwargs: Dict[str, Any] = {"url": url, "headers": request_headers, "timeout": self._timeout}
        
        if method == "POST" and data:
            kwargs["json"] = data
        
        response = httpx.request(method, **kwargs)
        response.raise_for_status()
        
        return {
            "status_code": response.status_code,
            "content": response.text,
            "json": response.json() if response.headers.get("content-type", "").startswith("application/json") else None,
        }
    
    # --- Legacy methods ---
    
    async def fetch(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        # For legacy support, treat query as URL
        try:
            result = self.fetch_url(query)
            return [{
                "id": f"http-{hash(query)}",
                "title": f"Response from {query}",
                "content": result.get("content", ""),
                "source": "http",
                "metadata": {"status": result.get("status_code")},
            }]
        except Exception as e:
            return [{"error": str(e)}]
    
    def supports_query_type(self, query_type: str) -> bool:
        return query_type in ["http", "web", "api", "url"]
    
    def get_capabilities(self) -> list[str]:
        return ["http_get", "http_post", "web_fetch"]
    
    # --- Configuration ---
    
    def set_default_headers(self, headers: Dict[str, str]) -> None:
        """Set default headers for all requests"""
        self._default_headers = headers
    
    def set_timeout(self, timeout: float) -> None:
        """Set request timeout in seconds"""
        self._timeout = timeout


# For backward compatibility
HTTPConnectorV2 = HTTPConnector