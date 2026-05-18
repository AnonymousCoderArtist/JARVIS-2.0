"""Weather Watcher - Monitors local weather and sends notifications"""

import asyncio
import json
import logging
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional

import aiohttp

from jarvis.core.watchers.base import BaseWatcher

# Suppress ALL terminal output for this watcher - prevents干扰 jarvis --cli
class QuietLogger:
    """Null logger that suppresses all output"""
    def __init__(self):
        pass
    def debug(self, *args, **kwargs): pass
    def info(self, *args, **kwargs): pass
    def warning(self, *args, **kwargs): pass
    def error(self, *args, **kwargs): pass
    def critical(self, *args, **kwargs): pass
    def log(self, level, *args, **kwargs): pass

# Create a quiet logger that goes nowhere
logger = QuietLogger()

# User agent for HTTP requests (same style as world_monitor)
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"


class WeatherWatcher(BaseWatcher):
    """
    Monitors local weather conditions and sends Windows notifications.
    
    Config (in .jarvis/settings.json):
        "watcher": {
            "weather": {
                "enabled": true,
                "latitude": 40.7128,      # Optional: your latitude
                "longitude": -74.0060,   # Optional: your longitude
                "notifications": true,    # Enable Windows notifications
                "interval": 3600          # Check every 1 hour (3600 seconds)
            }
        }
    
    If latitude/longitude not provided, will try to detect from IP address.
    """
    name = "weather"
    description = "Monitors local weather and sends notifications"
    
    def __init__(self):
        super().__init__(interval=3600)  # Default: 1 hour
        
        self._last_weather = None
        self._last_notification_time = None
        
    @property
    def config(self) -> dict:
        """Load watcher-specific config from settings.json."""
        return self.load_config()
    
    def _get_location(self) -> Optional[tuple[float, float]]:
        """Get location from config or detect from IP."""
        # Check config first
        config = self.config
        lat = config.get("latitude")
        lon = config.get("longitude")
        
        if lat is not None and lon is not None:
            logger.info(f"Using configured location: {lat}, {lon}")
            return (float(lat), float(lon))
        
        # Try to detect from IP
        try:
            return self._detect_location_from_ip()
        except Exception as e:
            logger.warning(f"Could not detect location from IP: {e}")
            return None
    
    def _detect_location_from_ip(self) -> Optional[tuple[float, float]]:
        """Detect location from IP address using free IP APIs (tries multiple)."""
        import requests
        
        # Try ipapi.co first
        try:
            response = requests.get(
                "https://ipapi.co/json/",
                timeout=5,
                headers={"User-Agent": USER_AGENT}
            )
            if response.status_code == 200:
                data = response.json()
                lat = data.get("latitude")
                lon = data.get("longitude")
                city = data.get("city", "Unknown")
                if lat and lon:
                    logger.info(f"Detected location from IP: {city} ({lat}, {lon})")
                    return (float(lat), float(lon))
        except Exception as e:
            logger.debug(f"ipapi.co failed: {e}")
        
        # Try ipinfo.io fallback
        try:
            response = requests.get(
                "https://ipinfo.io/json",
                timeout=5,
                headers={"User-Agent": USER_AGENT}
            )
            if response.status_code == 200:
                data = response.json()
                loc = data.get("loc", "")
                if loc:
                    lat, lon = loc.split(",")
                    city = data.get("city", "Unknown")
                    logger.info(f"Detected location from IP: {city} ({lat}, {lon})")
                    return (float(lat), float(lon))
        except Exception as e:
            logger.debug(f"ipinfo.io failed: {e}")
        
        # Try ip-api.com fallback
        try:
            response = requests.get(
                "http://ip-api.com/json/?fields=lat,lon,city",
                timeout=5,
                headers={"User-Agent": USER_AGENT}
            )
            if response.status_code == 200:
                data = response.json()
                lat = data.get("lat")
                lon = data.get("lon")
                city = data.get("city", "Unknown")
                if lat and lon:
                    logger.info(f"Detected location from IP: {city} ({lat}, {lon})")
                    return (float(lat), float(lon))
        except Exception as e:
            logger.debug(f"ip-api.com failed: {e}")
        
        return None
    
    async def _fetch_weather(self, lat: float, lon: float) -> Optional[dict]:
        """Fetch weather data from Open-Meteo API."""
        try:
            url = "https://api.open-meteo.com/v1/forecast"
            params = {
                "latitude": lat,
                "longitude": lon,
                "current": "temperature_2m,relative_humidity_2m,apparent_temperature,weather_code,wind_speed_10m",
                "timezone": "auto"
            }
            
            async with aiohttp.ClientSession(headers={"User-Agent": USER_AGENT}) as session:
                async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    if response.status == 200:
                        data = await response.json()
                        return self._parse_weather_data(data)
                    else:
                        logger.error(f"Weather API returned status: {response.status}")
                        return None
        except Exception as e:
            logger.error(f"Failed to fetch weather: {e}")
            return None
    
    def _parse_weather_data(self, data: dict) -> dict:
        """Parse Open-Meteo response into useful format."""
        current = data.get("current_weather", {}) or data.get("current", {})
        
        # Weather code to description mapping
        weather_codes = {
            0: "Clear sky",
            1: "Mainly clear",
            2: "Partly cloudy",
            3: "Overcast",
            45: "Fog",
            48: "Depositing rime fog",
            51: "Light drizzle",
            53: "Moderate drizzle",
            55: "Dense drizzle",
            61: "Slight rain",
            63: "Moderate rain",
            65: "Heavy rain",
            71: "Slight snow",
            73: "Moderate snow",
            75: "Heavy snow",
            80: "Slight rain showers",
            81: "Moderate rain showers",
            82: "Violent rain showers",
            95: "Thunderstorm",
            96: "Thunderstorm with slight hail",
            99: "Thunderstorm with heavy hail"
        }
        
        weather_code = current.get("weather_code", 0)
        weather_desc = weather_codes.get(weather_code, "Unknown")
        
        return {
            "temperature": current.get("temperature_2m"),
            "feels_like": current.get("apparent_temperature"),
            "humidity": current.get("relative_humidity_2m"),
            "wind_speed": current.get("wind_speed_10m"),
            "weather_code": weather_code,
            "weather_description": weather_desc,
            "timestamp": datetime.now().isoformat()
        }
    
    def _send_windows_notification(self, title: str, message: str):
        """Send Windows toast notification using PowerShell."""
        import sys
        if sys.platform != "win32":
            return
        try:
            # Try using Windows.UI.Notifications (Windows 10+)
            ps_command = f'''
            [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
            $xml = @'
            <toast>
                <visual>
                    <binding template="ToastText02">
                        <text id="1">{title}</text>
                        <text id="2">{message}</text>
                    </binding>
                </visual>
            </toast>
'@
            $doc = New-Object Windows.Data.Xml.Dom.XmlDocument
            $doc.LoadXml($xml)
            $toast = New-Object Windows.UI.Notifications.ToastNotification $doc
            [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("JARVIS").Show($toast)
            '''
            
            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps_command],
                capture_output=True,
                timeout=5
            )
            
            if result.returncode == 0:
                return
            
            # Fallback: Use Windows Forms MessageBox (always available)
            fallback_cmd = f'Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.MessageBox]::Show("{message}", "{title}", "OK", "Information")'
            subprocess.run(
                ["powershell", "-NoProfile", "-Command", fallback_cmd],
                capture_output=True,
                timeout=5
            )
                
        except FileNotFoundError:
            pass  # PowerShell not available
        except Exception as e:
            logger.debug(f"Notification error: {e}")
    
    def _should_notify(self, weather: dict) -> bool:
        """Decide whether to send a notification based on weather conditions."""
        config = self.config
        if not config.get("notifications", True):
            return False
        
        # Check if there's a meaningful change in weather
        if self._last_weather is None:
            return True
        
        # Notify on significant weather changes
        last_desc = self._last_weather.get("weather_description", "")
        current_desc = weather.get("weather_description", "")
        
        if last_desc != current_desc:
            return True
        
        # Notify if temperature changed significantly (>10°C)
        last_temp = self._last_weather.get("temperature", 0)
        current_temp = weather.get("temperature", 0)
        if abs(current_temp - last_temp) > 10:
            return True
        
        # Check interval - only notify once per hour max
        if self._last_notification_time:
            import time
            time_since_last = time.time() - self._last_notification_time
            if time_since_last < 3600:  # 1 hour
                return False
        
        return True
    
    async def watch(self):
        """Main watch loop - fetch weather and send notifications."""
        # Get location
        location = self._get_location()
        if not location:
            logger.warning("WeatherWatcher: No location available")
            return
        
        lat, lon = location
        
        # Fetch weather
        weather = await self._fetch_weather(lat, lon)
        if not weather:
            logger.warning("WeatherWatcher: Failed to fetch weather data")
            return
        
        # Store location info in weather data
        weather["location"] = {"latitude": lat, "longitude": lon}
        
        # Update COP with weather data (will auto-use class name: WeatherWatcher.cop.jsonl)
        self.update_cop(weather)
        
        # Send notification if conditions met
        if self._should_notify(weather):
            temp = weather.get("temperature", "N/A")
            desc = weather.get("weather_description", "Unknown")
            feels_like = weather.get("feels_like", temp)
            
            title = f"🌤️ JARVIS Weather Update"
            message = f"Current: {temp}°C (feels like {feels_like}°C)\n{desc}"
            
            self._send_windows_notification(title, message)
            
            # Update last notification time
            import time
            self._last_notification_time = time.time()
        
        # Store last weather for comparison
        self._last_weather = weather
        
        logger.info(f"WeatherWatcher: Updated - {weather.get('temperature')}°C, {weather.get('weather_description')}")


if __name__ == "__main__":
    """Test the weather watcher by running this file directly."""
    import asyncio
    import sys
    import traceback
    from pathlib import Path
    
    # Add parent dir to path so we can import jarvis.core.watchers
    sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
    
    print("[TEST] WeatherWatcher...")
    print("-" * 40)
    
    watcher = WeatherWatcher()
    
    # Get location
    print("[GEO] Detecting location from IP...")
    location = watcher._get_location()
    if location is None:
        # Debug: show what happened
        print("   Trying IP detection...")
        try:
            loc = watcher._detect_location_from_ip()
            if loc:
                location = loc
                print(f"   [OK] Detected: {loc}")
            else:
                print("   [FAIL] IP detection returned None")
        except Exception as e:
            print(f"   [ERROR] IP detection error: {e}")
            traceback.print_exc()
        
        if location is None:
            print("\n[FAIL] Could not detect location.")
            print("   Option 1: Check internet connection")
            print("   Option 2: Set latitude/longitude manually in .jarvis/settings.json")
            sys.exit(1)
    
    lat, lon = location
    print(f"   Location: {lat}, {lon}")
    
    # Fetch weather
    print("\n[WEATHER] Fetching weather data...")
    weather = asyncio.run(watcher._fetch_weather(lat, lon))
    if not weather:
        print("[FAIL] Failed to fetch weather data")
        sys.exit(1)
    
    print(f"   Temperature: {weather.get('temperature')}°C")
    print(f"   Feels like: {weather.get('feels_like')}°C")
    print(f"   Humidity: {weather.get('humidity')}%")
    print(f"   Wind: {weather.get('wind_speed')} km/h")
    print(f"   Condition: {weather.get('weather_description')}")
    
    # Update COP
    print("\n[COP] Updating COP...")
    weather["location"] = {"latitude": lat, "longitude": lon}
    watcher.update_cop(weather)
    print(f"   [OK] Saved to .jarvis/status/WeatherWatcher.cop.jsonl")
    
    # Send notification
    print("\n[NOTIFY] Sending Windows notification...")
    temp = weather.get("temperature", "N/A")
    desc = weather.get("weather_description", "Unknown")
    feels_like = weather.get("feels_like", temp)
    title = f"[JARVIS] Weather Update"
    message = f"Current: {temp}°C (feels like {feels_like}°C)\n{desc}"
    watcher._send_windows_notification(title, message)
    print("   [OK] Notification sent!")
    
    print("\n" + "=" * 40)
    print("[DONE] WeatherWatcher test complete!")