"""Configuration module for JARVIS CLI - handles settings, themes, and user preferences."""

import os
import json
import yaml
from pathlib import Path
from typing import Dict, Any, Optional, Union
from dataclasses import dataclass, asdict, field


@dataclass
class ThemeConfig:
    """Theme configuration."""
    name: str = "dark"
    colors: Dict[str, str] = field(default_factory=lambda: {
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
    theme: str = "dark"
    refresh_rate: int = 4
    show_timestamps: bool = False
    show_line_numbers: bool = True
    syntax_highlighting: bool = True
    auto_scroll: bool = True


@dataclass
class BehaviorConfig:
    """Behavior configuration."""
    auto_save_history: bool = True
    history_size: int = 1000
    confirm_on_exit: bool = False
    timeout_seconds: int = 600
    max_response_length: int = 2500
    show_tool_calls: bool = True
    show_reasoning: bool = True


@dataclass
class KeyBindingConfig:
    """Key binding configuration."""
    mode: str = "emacs"  # emacs, vi, or custom
    custom_bindings: Dict[str, str] = field(default_factory=dict)


@dataclass
class CLIConfig:
    """Complete CLI configuration."""
    display: DisplayConfig = field(default_factory=DisplayConfig)
    behavior: BehaviorConfig = field(default_factory=BehaviorConfig)
    keybindings: KeyBindingConfig = field(default_factory=KeyBindingConfig)
    themes: Dict[str, ThemeConfig] = field(default_factory=lambda: {
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
        })
    })


class ConfigManager:
    """Manages CLI configuration loading, saving, and validation."""
    
    def __init__(self, config_dir: Optional[Path] = None):
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
                with open(self.config_file, 'r') as f:
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
            "JARVIS_REFRESH_RATE": ("display", "refresh_rate"),
            "JARVIS_TIMEOUT": ("behavior", "timeout_seconds"),
            "JARVIS_MAX_RESPONSE": ("behavior", "max_response_length"),
            "JARVIS_KEY_MODE": ("keybindings", "mode"),
        }
        
        for env_var, (section, key) in env_mappings.items():
            value = os.getenv(env_var)
            if value is not None:
                # Type conversion based on key
                if key in ["width", "refresh_rate", "timeout_seconds", "max_response_length"]:
                    value = int(value)
                elif key in ["auto_save_history", "confirm_on_exit", "show_tool_calls", "show_reasoning"]:
                    value = value.lower() in ("true", "1", "yes", "on")
                
                setattr(getattr(self.config, section), key, value)
    
    def _update_config_from_dict(self, config_dict: Dict[str, Any]):
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
    
    def _update_section(self, section_obj: Any, section_data: Dict[str, Any]):
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
    
    def get_theme_colors(self, theme_name: Optional[str] = None) -> Dict[str, str]:
        """Get color scheme for a theme."""
        theme_name = theme_name or self.config.display.theme
        if theme_name in self.config.themes:
            return self.config.themes[theme_name].colors
        else:
            return self.config.themes["dark"].colors
    
    def add_theme(self, name: str, colors: Dict[str, str]):
        """Add a new theme."""
        self.config.themes[name] = ThemeConfig(name, colors)
    
    def set_theme(self, theme_name: str):
        """Set the active theme."""
        if theme_name in self.config.themes:
            self.config.display.theme = theme_name
        else:
            raise ValueError(f"Unknown theme: {theme_name}")
    
    def get_key_binding(self, action: str) -> Optional[str]:
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


def load_config(config_dir: Optional[Path] = None) -> ConfigManager:
    """Load configuration from the specified directory."""
    return ConfigManager(config_dir)
