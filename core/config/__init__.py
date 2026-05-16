"""Configuration Package — settings, themes, and keybindings."""

from core.config.keybindings import (
    Keybinding,
    Keybindings,
    format_keybinding_help,
    load_keybindings,
    resolve_action,
    save_keybindings,
)
from core.config.settings import Settings
from core.config.theme import (
    DEFAULT_THEME,
    LIGHT_THEME,
    Theme,
    discover_themes,
    get_theme,
    hex_to_ansi,
    hex_to_xterm256,
    load_theme_from_file,
    supports_256color,
    supports_truecolor,
)

__all__ = [
    "DEFAULT_THEME",
    "Keybinding",
    "Keybindings",
    "LIGHT_THEME",
    "Settings",
    "Theme",
    "discover_themes",
    "format_keybinding_help",
    "get_theme",
    "hex_to_ansi",
    "hex_to_xterm256",
    "load_keybindings",
    "load_theme_from_file",
    "resolve_action",
    "save_keybindings",
    "supports_256color",
    "supports_truecolor",
]

