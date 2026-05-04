"""Windows tools for JARVIS.

These are native JARVIS tools that wrap the Windows automation functionality.
"""

from core.windows.tools import (
    app,
    clipboard,
    filesystem,
    input,
    multi,
    notification,
    process,
    registry,
    scrape,
    shell,
    snapshot,
)

__all__ = [
    "snapshot",
    "app",
    "input",
    "filesystem",
    "clipboard",
    "notification",
    "process",
    "registry",
    "scrape",
    "shell",
    "multi",
]