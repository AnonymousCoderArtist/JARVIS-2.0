"""Configuration adapter compatible with vibe."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class VibeConfig:
    """Configuration class compatible with vibe."""
    model: str = "gpt-4o"
    base_url: str | None = None
    api_key: str | None = None
    sdk: str = "openai"
    
    # UI settings
    theme: str = "default"
    auto_scroll: bool = True
    show_thinking: bool = True
    
    # Feature flags
    voice_enabled: bool = False
    teleport_enabled: bool = False
    mcp_enabled: bool = False
    
    # Paths
    history_file: Path = field(default_factory=lambda: Path.home() / ".jarvis_history")
    data_dir: Path = field(default_factory=lambda: Path.home() / ".jarvis")
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get config value."""
        return getattr(self, key, default)
    
    def set(self, key: str, value: Any) -> None:
        """Set config value."""
        setattr(self, key, value)
