"""Base class for all watchers"""

from abc import ABC, abstractmethod
from pathlib import Path
from datetime import datetime
import json
import logging

logger = logging.getLogger(__name__)


class BaseWatcher(ABC):
    """
    Base class for watchers.
    
    A watcher is a background plugin that runs continuously.
    Implement the `watch()` method to define your custom logic.
    
    Example:
        class MyWatcher(BaseWatcher):
            name = "my_watcher"
            
            def __init__(self):
                super().__init__(interval=60)
            
            async def watch(self):
                # Your custom logic here
                data = {"status": "ok"}
                self.update_cop(data)
    """
    name: str = "base_watcher"
    description: str = "A base watcher"
    
    def __init__(self, interval: int = 60):
        """
        Initialize the watcher.
        
        Args:
            interval: Seconds between each watch() call (default: 60)
        """
        self.interval = interval
        self._running = False
        self.event_queue = None
        
    @property
    def enabled(self) -> bool:
        """Check if watcher is enabled in config. Override to customize."""
        config = self.load_config()
        if config is None:
            return True
        return config.get("enabled", True)
    
    def load_config(self) -> dict:
        """
        Load watcher-specific config from settings.json.
        
        Config must be under: watcher.<watcher_name>
        
        Example in settings.json:
            "watcher": {
                "my_watcher": {
                    "enabled": true,
                    "any_setting": "value"
                }
            }
        
        Returns:
            dict: The watcher's config, or empty dict if not found.
        """
        settings_path = Path(".jarvis") / "settings.json"
        if settings_path.exists():
            try:
                with open(settings_path, encoding="utf-8") as f:
                    settings = json.load(f)
                    watcher_section = settings.get("watcher", {})
                    return watcher_section.get(self.name, {})
            except Exception as e:
                logger.debug(f"Watcher {self.name} failed to load config: {e}")
        return {}
    
    def set_event_queue(self, queue):
        """Set the event queue for communicating with JARVIS UI."""
        self.event_queue = queue
    
    async def notify(self, title: str, message: str, level: str = "info"):
        """
        [OPTIONAL] Send a notification to the JARVIS UI.
        
        Use this when you need to alert the user of important events.
        For persistent state, use `update_cop()` instead.
        
        Args:
            title: The title of the notification
            message: The message body
            level: Severity level ('info', 'warning', 'error')
        """
        if self.event_queue:
            try:
                # Lazy import to avoid circular dependencies
                from interface.textual_ui.types import AssistantEvent
                
                emoji = {"error": "🔴", "warning": "🟡", "info": "🔵"}.get(level.lower(), "📢")
                content = f"{emoji} **[{self.name.upper()}] {title}**: {message}"
                
                self.event_queue.put_nowait(AssistantEvent(
                    content=content,
                    is_heartbeat=True
                ))
            except Exception as e:
                logger.debug(f"Watcher {self.name} UI notification failed: {e}")
        
        # Also log it
        log_method = getattr(logger, level.lower(), logger.info)
        log_method(f"WATCHER [{self.name}]: {title} - {message}")

    def update_cop(self, data, key=None):
        """
        [REQUIRED] Store data in the Common Operational Picture (COP).
        
        This is the primary way to persist watcher state for agents.
        
        Appends to: .jarvis/status/<WatcherName>.cop.jsonl
        
        Args:
            data: The data to store (any JSON-serializable object)
            key: Optional custom key (defaults to class name)
        """
        cop_dir = Path(".jarvis") / "status"
        cop_dir.mkdir(parents=True, exist_ok=True)
        
        file_id = key if key else self.__class__.__name__
        cop_file = cop_dir / f"{file_id}.cop.jsonl"
        
        try:
            with open(cop_file, "a", encoding="utf-8") as f:
                entry = {
                    "timestamp": str(datetime.now()),
                    "watcher": self.name,
                    "class": self.__class__.__name__,
                    "data": data
                }
                f.write(json.dumps(entry, default=str) + "\n")
        except Exception as e:
            logger.error(f"Watcher {self.name} failed to update COP: {e}")
    
    def get_cop(self, key=None) -> list:
        """
        Read recent entries from COP.
        
        Args:
            key: Optional custom key (defaults to class name)
            
        Returns:
            List of recent entries (last 10)
        """
        cop_dir = Path(".jarvis") / "status"
        file_id = key if key else self.__class__.__name__
        cop_file = cop_dir / f"{file_id}.cop.jsonl"
        
        if not cop_file.exists():
            return []
        
        try:
            entries = []
            with open(cop_file, "r", encoding="utf-8") as f:
                for line in f.readlines()[-10:]:
                    if line.strip():
                        entries.append(json.loads(line))
            return entries
        except Exception as e:
            logger.error(f"Watcher {self.name} failed to read COP: {e}")
            return []
    
    @abstractmethod
    async def watch(self):
        """
        **Required.** The main logic that runs on each interval.
        
        This is the only method you MUST implement.
        Everything else is optional - customize as you need.
        
        Example:
            async def watch(self):
                # Fetch data from your API
                data = await self.fetch_data()
                
                # Store in COP
                self.update_cop(data)
                
                # Send notifications however you want
                if data.get("alert"):
                    await self.send_telegram(...)
        """
        pass
    
    async def start(self):
        """Called when watcher starts. Override for initialization."""
        pass
    
    async def stop(self):
        """Called when watcher stops. Override for cleanup."""
        pass