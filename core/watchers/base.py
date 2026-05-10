"""Base class for all watchers"""

from abc import ABC, abstractmethod
from typing import Any, Optional
from pathlib import Path
from datetime import datetime
import json
import logging

logger = logging.getLogger(__name__)

class BaseWatcher(ABC):
    """
    Base class for watchers.
    A watcher is a background task that periodically polls or monitors something.
    """
    name: str = "base_watcher"
    description: str = "A base watcher"
    
    def __init__(self, interval: int = 60, config: Optional[dict[str, Any]] = None):
        self.interval = interval
        self.config = config or {}
        self.enabled = True
        self._running = False
        self.event_queue = None
        
    def set_event_queue(self, queue: Any):
        """Set the event queue for TUI/CLI notifications."""
        self.event_queue = queue

    def notify(self, title: str, message: str, level: str = "info"):
        """Send a notification to the user interface and system toast."""
        # 1. Internal JARVIS Event Notification
        if self.event_queue:
            try:
                from interface.textual_ui.types import AssistantEvent
                # Push a heartbeat-style notification to the queue
                self.event_queue.put_nowait(AssistantEvent(
                    content=f"🔔 **[{self.name.upper()}] {title}**: {message}",
                    is_heartbeat=True
                ))
            except Exception as e:
                logger.debug(f"Watcher {self.name} failed to queue internal notification: {e}")
        
        # 2. System Toast Notification (matching TMP behavior)
        self._send_system_toast(title, message)
        
        # 3. Logging
        log_method = getattr(logger, level.lower(), logger.info)
        log_method(f"WATCHER ALERT [{self.name}]: {title} - {message}")

    def _send_system_toast(self, title: str, message: str):
        """Cross-platform system notification with PowerShell fallback for Windows."""
        clean_title = f"JARVIS: {title}"[:100]
        clean_message = message[:1000] # Increased from 200 to allow full messages

        # Try plyer first
        try:
            from plyer import notification
            notification.notify(
                title=clean_title,
                message=clean_message,
                app_name="JARVIS Watcher",
                timeout=10
            )
            return
        except Exception:
            pass

        # Fallback to PowerShell Toast (for Windows)
        if Path("C:/Windows/System32/WindowsPowerShell/v1.0/powershell.exe").exists():
            try:
                import subprocess
                t_esc = clean_title.replace('"', '`"').replace("'", "''")
                m_esc = clean_message.replace('"', '`"').replace("'", "''")
                
                ps_script = f'''
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null
$template = @"
<toast>
    <visual>
        <binding template="ToastGeneric">
            <text>{t_esc}</text>
            <text>{m_esc}</text>
        </binding>
    </visual>
</toast>
"@
$xml = New-Object Windows.Data.Xml.Dom.XmlDocument
$xml.load_xml($template)
$toast = New-Object Windows.UI.Notifications.ToastNotification $xml
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("JARVIS").Show($toast)
'''
                subprocess.run(["powershell", "-Command", ps_script], capture_output=True, timeout=5)
            except Exception:
                pass

    @abstractmethod
    async def watch(self) -> Any:
        """
        Perform the monitoring task.
        Returns the data or changes detected.
        """
        pass

    def update_cop(self, data: Any, key: Optional[str] = None):
        """
        Update the Common Operational Picture (COP).
        Automatically appends to ClassName.cop.jsonl with full data and timestamp.
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
            logger.error(f"Watcher {self.name} failed to update COP (JSONL): {e}")

    def append_cop(self, data: Any, key: Optional[str] = None):
        """Alias for update_cop to maintain backward compatibility."""
        self.update_cop(data, key)

    def get_cop(self, key: Optional[str] = None) -> Optional[list[dict[str, Any]]]:
        """Read the last 10 entries from the JSONL COP."""
        cop_dir = Path(".jarvis") / "status"
        file_id = key if key else self.__class__.__name__
        cop_file = cop_dir / f"{file_id}.cop.jsonl"
        
        if not cop_file.exists():
            return None
            
        try:
            entries = []
            with open(cop_file, "r", encoding="utf-8") as f:
                # Read lines and take last 10
                lines = f.readlines()
                for line in lines[-10:]:
                    if line.strip():
                        entries.append(json.loads(line))
            return entries
        except Exception as e:
            logger.error(f"Watcher {self.name} failed to read COP: {e}")
            return None
