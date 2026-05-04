"""Windows automation module for JARVIS.

This module provides Windows desktop automation capabilities including:
- Desktop state capture and UI element inspection
- Mouse and keyboard automation
- Application management
- Process management
- System integration

Data is persisted in ~/.jarvis/windows for session tracking.
"""

from core.windows.desktop.service import Desktop
from core.windows.watchdog.service import WatchDog
from core.windows.paths import WINDOWS_DATA_DIR

__all__ = ["Desktop", "WatchDog", "WINDOWS_DATA_DIR"]