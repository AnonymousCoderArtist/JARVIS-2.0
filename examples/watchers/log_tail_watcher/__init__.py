"""Log tail watcher — monitors a log file for error patterns."""

import hashlib
import json
from pathlib import Path
from core.watchers.base import BaseWatcher


class LogTailWatcher(BaseWatcher):
    """Tails a log file and notifies when error patterns are detected."""

    name = "log_tail"
    description = "Monitors a log file for errors, warnings, and exceptions"

    def __init__(self):
        super().__init__(interval=10)  # Check every 10 seconds
        self._last_position = 0
        self._last_hash = None
        config = self.load_config()
        self._log_path = Path(config.get("log_path", "app.log"))
        self._patterns = config.get(
            "patterns",
            ["ERROR", "CRITICAL", "Exception", "Traceback", "FATAL"],
        )

    async def watch(self):
        """Read new lines from the log file and check for patterns."""
        if not self._log_path.exists():
            return

        try:
            file_size = self._log_path.stat().st_size

            # If file was truncated/rotated, reset position
            if file_size < self._last_position:
                self._last_position = 0

            # Read only new lines
            with open(self._log_path, "r", encoding="utf-8", errors="replace") as f:
                f.seek(self._last_position)
                new_lines = f.readlines()
                self._last_position = f.tell()

            if not new_lines:
                return

            # Check for error patterns
            matched = []
            for line in new_lines:
                line = line.strip()
                for pattern in self._patterns:
                    if pattern in line:
                        matched.append(line)
                        break

            if not matched:
                return

            # Hash to avoid spamming on repeated errors
            item_hash = hashlib.md5(
                json.dumps(matched[-5:], sort_keys=True).encode()
            ).hexdigest()

            if self._last_hash != item_hash:
                self._last_hash = item_hash

                data = {
                    "log_file": str(self._log_path),
                    "errors": matched[-10:],  # Keep last 10
                    "count": len(matched),
                }
                self.update_cop(data)

                await self.notify(
                    "Log Errors Detected",
                    f"Found {len(matched)} error line(s) in {self._log_path.name}",
                    level="warning",
                )

        except Exception as e:
            pass  # Silently skip on read errors
