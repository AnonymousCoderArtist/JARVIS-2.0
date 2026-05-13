"""Weather connector - fetches weather data from OpenWeatherMap API"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Iterator, Optional

try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False

from ..base import BaseConnector, ConnectorConfig, Document, SyncStatus
from ..registry import ConnectorRegistry


DEFAULT_API_BASE = "https://api.openweathermap.org/data/2.5"
DEFAULT_CONFIG_DIR = Path.home() / ".jarvis" / "credentials"


def _weather_api_get(api_key: str, endpoint: str, params: Dict[str, str]) -> Dict[str, Any]:
    """Call OpenWeatherMap API"""
    if not HAS_HTTPX:
        raise ImportError("httpx is required for weather connector: pip install httpx")
    
    resp = httpx.get(
        f"{DEFAULT_API_BASE}/{endpoint}",
        params={**params, "appid": api_key},
        timeout=30.0,
    )
    resp.raise_for_status()
    return resp.json()


@ConnectorRegistry.register("weather")
class WeatherConnector(BaseConnector):
    """Fetch weather data from OpenWeatherMap"""
    
    connector_id = "weather"
    display_name = "OpenWeatherMap"
    auth_type = "api_key"
    
    def __init__(self, config: Optional[ConnectorConfig] = None):
        super().__init__(config)
        self._api_key = ""
        self._default_city = "London"
        self._status = SyncStatus()
        self._load_credentials()
    
    def _load_credentials(self):
        """Load API key from credentials"""
        creds = self._load_credentials()
        self._api_key = creds.get("api_key", "")
        
        # Also check config
        if not self._api_key:
            self._api_key = self.config.get_credential("api_key", "")
        
        # Get default city from config
        self._default_city = self.config.get_credential("city", "London")
    
    def is_connected(self) -> bool:
        """Check if we have a valid API key"""
        return bool(self._api_key)
    
    def disconnect(self) -> None:
        """Clear API key"""
        self._api_key = ""
    
    def sync(
        self, *, since: Optional[datetime] = None, cursor: Optional[str] = None
    ) -> Iterator[Document]:
        """Fetch current weather and forecast"""
        if not self.is_connected():
            return
        
        # Current weather
        try:
            current = _weather_api_get(
                self._api_key, 
                "weather",
                {"q": self._default_city, "units": "imperial"}
            )
            
            yield Document(
                doc_id=f"weather-current-{current.get('dt', '')}",
                source="weather",
                doc_type="current",
                content=json.dumps(current),
                title=f"Current weather in {self._default_city}",
                timestamp=datetime.fromtimestamp(current.get("dt", 0)),
                metadata={
                    "temp": current.get("main", {}).get("temp"),
                    "feels_like": current.get("main", {}).get("feels_like"),
                    "humidity": current.get("main", {}).get("humidity"),
                    "conditions": current.get("weather", [{}])[0].get("description"),
                    "icon": current.get("weather", [{}])[0].get("icon"),
                }
            )
        except Exception as e:
            self._status.error = str(e)
        
        # Forecast (next 5 days)
        try:
            forecast = _weather_api_get(
                self._api_key,
                "forecast",
                {"q": self._default_city, "units": "imperial", "cnt": 40}
            )
            
            for item in forecast.get("list", []):
                dt = item.get("dt", 0)
                yield Document(
                    doc_id=f"weather-forecast-{dt}",
                    source="weather",
                    doc_type="forecast",
                    content=json.dumps(item),
                    title=f"Forecast: {item.get('main', {}).get('temp')}°F",
                    timestamp=datetime.fromtimestamp(dt),
                    metadata={
                        "temp": item.get("main", {}).get("temp"),
                        "conditions": item.get("weather", [{}])[0].get("description"),
                    }
                )
        except Exception as e:
            self._status.error = str(e)
        
        self._status.state = "idle"
        self._status.last_sync = datetime.now()
    
    def sync_status(self) -> SyncStatus:
        return self._status
    
    # --- Legacy methods ---
    
    async def fetch(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        """Fetch weather data"""
        docs = list(self.sync())
        return [doc.to_dict() for doc in docs[:limit]]
    
    def supports_query_type(self, query_type: str) -> bool:
        return query_type in ["weather", "forecast"]
    
    def get_capabilities(self) -> list[str]:
        return ["current_weather", "forecast"]
    
    # --- Configuration ---
    
    def set_api_key(self, api_key: str, city: str = "London") -> None:
        """Set API key and default city"""
        self._api_key = api_key
        self._default_city = city
        self._save_credentials({
            "api_key": api_key,
            "city": city,
        })


# For backward compatibility
WeatherConnectorV2 = WeatherConnector