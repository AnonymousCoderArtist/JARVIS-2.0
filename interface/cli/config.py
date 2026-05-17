"""Configuration module for JARVIS CLI - handles settings, themes, and user preferences."""

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class ThemeConfig:
    """Theme configuration."""
    name: str = "dark"
    colors: dict[str, str] = field(default_factory=lambda: {
        "primary": "#ff8700",
        "secondary": "#666666",
        "success": "#00ff00",
        "error": "#ff0000",
        "warning": "#ffff00",
        "info": "#00ffff",
        "prompt": "#ff8700",
        "arrow": "#666666",
    })


@dataclass
class DisplayConfig:
    """Display configuration."""
    width: int = 80
    theme: str = "ml_intern"


@dataclass
class BehaviorConfig:
    """Behavior configuration."""
    auto_save_history: bool = True
    history_size: int = 1000
    confirm_on_exit: bool = False
    timeout_seconds: int = 1800  # 30 minutes default for LLM operations
    max_response_length: int = 2500
    show_tool_calls: bool = True
    show_reasoning: bool = True


@dataclass
class KeyBindingConfig:
    """Key binding configuration."""
    mode: str = "emacs"  # emacs, vi, or custom
    custom_bindings: dict[str, str] = field(default_factory=dict)


@dataclass
class CLIConfig:
    """Complete CLI configuration."""
    display: DisplayConfig = field(default_factory=DisplayConfig)
    behavior: BehaviorConfig = field(default_factory=BehaviorConfig)
    keybindings: KeyBindingConfig = field(default_factory=KeyBindingConfig)
    themes: dict[str, ThemeConfig] = field(default_factory=lambda: {
        "dark": ThemeConfig("dark"),
        "light": ThemeConfig("light", {
            "primary": "#ff6600",
            "secondary": "#888888",
            "success": "#00aa00",
            "error": "#cc0000",
            "warning": "#cc9900",
            "info": "#0099cc",
            "prompt": "#ff6600",
            "arrow": "#888888",
        }),
        "nord": ThemeConfig("nord", {
            "primary": "#81a1c1",
            "secondary": "#4c566a",
            "success": "#a3be8c",
            "error": "#bf616a",
            "warning": "#ebcb8b",
            "info": "#88c0d0",
            "prompt": "#81a1c1",
            "arrow": "#4c566a",
        }),
        "dracula": ThemeConfig("dracula", {
            "primary": "#bd93f9",
            "secondary": "#6272a4",
            "success": "#50fa7b",
            "error": "#ff5555",
            "warning": "#f1fa8c",
            "info": "#8be9fd",
            "prompt": "#bd93f9",
            "arrow": "#6272a4",
        }),
        "gruvbox": ThemeConfig("gruvbox", {
            "primary": "#fabd2f",
            "secondary": "#928374",
            "success": "#b8bb26",
            "error": "#fb4934",
            "warning": "#fabd2f",
            "info": "#83a598",
            "prompt": "#fabd2f",
            "arrow": "#928374",
        }),
        "catppuccin": ThemeConfig("catppuccin", {
            "primary": "#f5e0dc",
            "secondary": "#585b70",
            "success": "#a6e3a1",
            "error": "#f38ba8",
            "warning": "#f9e2af",
            "info": "#89dceb",
            "prompt": "#f5e0dc",
            "arrow": "#585b70",
        }),
        "ml_intern": ThemeConfig("ml_intern", {
            "primary": "#ffc850",        # warm gold
            "secondary": "#b48c28",      # dim gold
            "success": "#4ade80",        # dim green for tool success
            "error": "#f87171",          # dim red for tool failure
            "warning": "#ffc850",        # warm gold for warnings
            "info": "#78dcff",           # blue for links
            "prompt": "#78dcff",         # cyan for prompt
            "arrow": "#b48c28",          # dim gold for arrows
            "thinking_base": "#5a5a6e",  # thinking shimmer base
            "thinking_highlight": "#ffc850",  # thinking shimmer highlight
        }),
    })


class ConfigManager:
    """Manages CLI configuration loading, saving, and validation."""

    def __init__(self, config_dir: Path | None = None):
        self.config_dir = config_dir or self._get_default_config_dir()
        self.config_file = self.config_dir / "config.yaml"
        self.config = CLIConfig()
        self._ensure_config_dir()
        self._load_config()

    def _get_default_config_dir(self) -> Path:
        """Get default configuration directory."""
        home = Path.home()
        return home / ".jarvis" / "cli"

    def _ensure_config_dir(self):
        """Ensure configuration directory exists."""
        self.config_dir.mkdir(parents=True, exist_ok=True)

    def _load_config(self):
        """Load configuration from file."""
        # Load from environment variables first
        self._load_from_env()

        # Then load from config file if it exists
        if self.config_file.exists():
            try:
                with open(self.config_file) as f:
                    if self.config_file.suffix.lower() == '.json':
                        file_config = json.load(f)
                    else:
                        file_config = yaml.safe_load(f)

                self._update_config_from_dict(file_config)

            except Exception as e:
                print(f"Warning: Failed to load config file: {e}")

    def _load_from_env(self):
        """Load configuration from environment variables."""
        env_mappings = {
            "JARVIS_THEME": ("display", "theme"),
            "JARVIS_WIDTH": ("display", "width"),
            "JARVIS_TIMEOUT": ("behavior", "timeout_seconds"),
            "JARVIS_MAX_RESPONSE": ("behavior", "max_response_length"),
            "JARVIS_KEY_MODE": ("keybindings", "mode"),
        }

        for env_var, (section, key) in env_mappings.items():
            value = os.getenv(env_var)
            if value is not None:
                if key in ["width", "timeout_seconds", "max_response_length"]:
                    value = int(value)
                elif key in ["auto_save_history", "confirm_on_exit", "show_tool_calls", "show_reasoning"]:
                    value = value.lower() in ("true", "1", "yes", "on")

                setattr(getattr(self.config, section), key, value)

    def _update_config_from_dict(self, config_dict: dict[str, Any]):
        """Update configuration from dictionary."""
        if "display" in config_dict:
            self._update_section(self.config.display, config_dict["display"])

        if "behavior" in config_dict:
            self._update_section(self.config.behavior, config_dict["behavior"])

        if "keybindings" in config_dict:
            self._update_section(self.config.keybindings, config_dict["keybindings"])

        if "themes" in config_dict:
            for theme_name, theme_data in config_dict["themes"].items():
                if theme_name not in self.config.themes:
                    self.config.themes[theme_name] = ThemeConfig()
                self._update_section(self.config.themes[theme_name], theme_data)

    def _update_section(self, section_obj: Any, section_data: dict[str, Any]):
        """Update a configuration section from dictionary data."""
        for key, value in section_data.items():
            if hasattr(section_obj, key):
                setattr(section_obj, key, value)

    def save_config(self):
        """Save current configuration to file."""
        try:
            config_dict = asdict(self.config)

            with open(self.config_file, 'w') as f:
                if self.config_file.suffix.lower() == '.json':
                    json.dump(config_dict, f, indent=2)
                else:
                    yaml.dump(config_dict, f, default_flow_style=False, indent=2)

        except Exception as e:
            print(f"Error saving config: {e}")

    def get_theme_colors(self, theme_name: str | None = None) -> dict[str, str]:
        """Get color scheme for a theme."""
        theme_name = theme_name or self.config.display.theme
        if theme_name in self.config.themes:
            return self.config.themes[theme_name].colors
        else:
            return self.config.themes["dark"].colors

    def add_theme(self, name: str, colors: dict[str, str]):
        """Add a new theme."""
        self.config.themes[name] = ThemeConfig(name, colors)

    def set_theme(self, theme_name: str):
        """Set the active theme."""
        if theme_name in self.config.themes:
            self.config.display.theme = theme_name
        else:
            raise ValueError(f"Unknown theme: {theme_name}")

    def get_key_binding(self, action: str) -> str | None:
        """Get key binding for an action."""
        return self.config.keybindings.custom_bindings.get(action)

    def set_key_binding(self, action: str, key: str):
        """Set key binding for an action."""
        self.config.keybindings.custom_bindings[action] = key

    def reset_to_defaults(self):
        """Reset configuration to defaults."""
        self.config = CLIConfig()

    def export_config(self, format: str = "yaml") -> str:
        """Export configuration as string."""
        config_dict = asdict(self.config)

        if format.lower() == "json":
            return json.dumps(config_dict, indent=2)
        else:
            return yaml.dump(config_dict, default_flow_style=False, indent=2)

    def import_config(self, config_str: str, format: str = "yaml"):
        """Import configuration from string."""
        try:
            if format.lower() == "json":
                config_dict = json.loads(config_str)
            else:
                config_dict = yaml.safe_load(config_str)

            self._update_config_from_dict(config_dict)

        except Exception as e:
            raise ValueError(f"Failed to import config: {e}")


def create_default_config() -> CLIConfig:
    """Create a default configuration."""
    return CLIConfig()


def load_config(config_dir: Path | None = None) -> ConfigManager:
    """Load configuration from the specified directory."""
    return ConfigManager(config_dir)
