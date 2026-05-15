"""Disk usage monitor — alerts when disk space is low."""

import shutil
from core.watchers.base import BaseWatcher


class DiskMonitor(BaseWatcher):
    """Monitors disk usage and alerts when thresholds are exceeded."""

    name = "disk_monitor"
    description = "Watches disk usage and alerts when space is low"

    def __init__(self):
        super().__init__(interval=300)  # Check every 5 minutes
        self._last_alert_pct = 0
        self._warn_threshold = 85  # percent
        self._critical_threshold = 95  # percent

    async def watch(self):
        """Check disk usage and notify if thresholds are crossed."""
        try:
            usage = shutil.disk_usage("/")
            total = usage.total
            used = usage.used
            free = usage.free
            pct = (used / total) * 100

            data = {
                "total_gb": round(total / 1e9, 2),
                "used_gb": round(used / 1e9, 2),
                "free_gb": round(free / 1e9, 2),
                "percent_used": round(pct, 1),
            }

            # Always persist to COP
            self.update_cop(data)

            # Alert on threshold crossings (avoid repeated alerts for same range)
            if pct >= self._critical_threshold and self._last_alert_pct < self._critical_threshold:
                await self.notify(
                    "Disk Critical",
                    f"Disk is {pct:.1f}% full — only {data['free_gb']} GB remaining",
                    level="error",
                )
                self._last_alert_pct = pct
            elif pct >= self._warn_threshold and self._last_alert_pct < self._warn_threshold:
                await self.notify(
                    "Disk Warning",
                    f"Disk is {pct:.1f}% full — {data['free_gb']} GB remaining",
                    level="warning",
                )
                self._last_alert_pct = pct
            elif pct < self._warn_threshold and self._last_alert_pct >= self._warn_threshold:
                await self.notify(
                    "Disk Recovered",
                    f"Disk usage dropped to {pct:.1f}%",
                    level="info",
                )
                self._last_alert_pct = pct

        except Exception as e:
            # Non-Unix systems may not support shutil.disk_usage("/")
            pass
