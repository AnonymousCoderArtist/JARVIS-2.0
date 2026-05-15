"""Theme system for JARVIS — color tokens, truecolor/256 detection, hot-reload.

Themes are JSON files with 51 color tokens covering:
- Core UI (accent, border, success, error)
- Messages (user message bg, tool output, custom message labels)
- Markdown (headings, code blocks, links)
- Syntax highlighting (keywords, strings, functions)
- Thinking levels (border colors per reasoning intensity)
"""

from __future__ import annotations

import json
import logging
import os
from copy import deepcopy
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Default dark theme (matches JARVIS TUI default)
# ---------------------------------------------------------------------------

DEFAULT_DARK_THEME: dict[str, str] = {
    # Core UI
    "accent": "#00aaff",
    "border": "#404040",
    "success": "#00cc66",
    "error": "#ff4444",
    "warning": "#ffaa00",
    "muted": "#808080",
    "dim": "#606060",
    "text": "#e0e0e0",
    "background": "#1a1a2e",
    "surface": "#16213e",
    "selection": "#0f3460",
    "thinkingText": "#888888",
    # Messages
    "userMessageBg": "#1e3a5f",
    "assistantMessageBg": "#1a1a2e",
    "toolOutput": "#2d2d2d",
    "toolSuccessBg": "#1a3a2a",
    "toolErrorBg": "#3a1a1a",
    "customMessageLabel": "#ffaa00",
    "compactionSummaryBg": "#2a2a1a",
    # Markdown
    "mdHeading": "#00aaff",
    "mdCodeBlock": "#2d2d2d",
    "mdCodeText": "#e0e0e0",
    "mdLink": "#66ccff",
    "mdLinkHover": "#99ddff",
    "mdListBullet": "#00cc66",
    "mdBlockquote": "#808080",
    "mdInlineCode": "#ff9966",
    # Syntax highlighting
    "syntaxKeyword": "#cc66ff",
    "syntaxString": "#00cc66",
    "syntaxFunction": "#66ccff",
    "syntaxOperator": "#ff9966",
    "syntaxComment": "#808080",
    "syntaxNumber": "#ff9966",
    "syntaxType": "#00aaff",
    "syntaxVariable": "#e0e0e0",
    # Thinking level border colors
    "thinkingOff": "#404040",
    "thinkingMinimal": "#666666",
    "thinkingLow": "#888888",
    "thinkingMedium": "#ffaa00",
    "thinkingHigh": "#ff6600",
    "thinkingXhigh": "#ff4444",
    # UI elements
    "footerBg": "#0d1b2a",
    "footerText": "#808080",
    "headerBg": "#0d1b2a",
    "statusBarBg": "#1b2838",
    "progressBar": "#00aaff",
    "scrollbar": "#404040",
    "scrollbarHover": "#606060",
    "dialogBg": "#1a1a2e",
    "dialogBorder": "#404040",
    "inputBg": "#0d1b2a",
    "inputBorder": "#404040",
    "inputFocus": "#00aaff",
}

DEFAULT_LIGHT_THEME: dict[str, str] = {
    "accent": "#0066cc", "border": "#cccccc", "success": "#008800", "error": "#cc0000",
    "warning": "#cc8800", "muted": "#999999", "dim": "#bbbbbb", "text": "#333333",
    "background": "#ffffff", "surface": "#f5f5f5", "selection": "#ddeeff",
    "thinkingText": "#999999",
    "userMessageBg": "#e8f0fe", "assistantMessageBg": "#ffffff",
    "toolOutput": "#f0f0f0", "toolSuccessBg": "#e8f5e9", "toolErrorBg": "#fce4ec",
    "customMessageLabel": "#cc8800", "compactionSummaryBg": "#f9fbe7",
    "mdHeading": "#0066cc", "mdCodeBlock": "#f0f0f0", "mdCodeText": "#333333",
    "mdLink": "#0066cc", "mdLinkHover": "#004499", "mdListBullet": "#008800",
    "mdBlockquote": "#999999", "mdInlineCode": "#cc6600",
    "syntaxKeyword": "#8800cc", "syntaxString": "#008800", "syntaxFunction": "#0066cc",
    "syntaxOperator": "#cc6600", "syntaxComment": "#999999", "syntaxNumber": "#cc6600",
    "syntaxType": "#0066cc", "syntaxVariable": "#333333",
    "thinkingOff": "#cccccc", "thinkingMinimal": "#bbbbbb", "thinkingLow": "#999999",
    "thinkingMedium": "#cc8800", "thinkingHigh": "#cc6600", "thinkingXhigh": "#cc0000",
    "footerBg": "#eeeeee", "footerText": "#999999", "headerBg": "#eeeeee",
    "statusBarBg": "#f5f5f5", "progressBar": "#0066cc", "scrollbar": "#cccccc",
    "scrollbarHover": "#bbbbbb", "dialogBg": "#ffffff", "dialogBorder": "#cccccc",
    "inputBg": "#f5f5f5", "inputBorder": "#cccccc", "inputFocus": "#0066cc",
}

REQUIRED_TOKENS = set(DEFAULT_DARK_THEME.keys())

THEME_DIRS = [
    Path.home() / ".jarvis" / "themes",
    Path(".jarvis") / "themes",
]


class Theme:
    """Represents a loaded theme with all 51 color tokens.

    Supports both ``truecolor`` (hex) and ``256-color`` (closest match) modes.
    """

    def __init__(self, name: str, colors: dict[str, str], is_dark: bool = True) -> None:
        self.name = name
        self._colors = deepcopy(colors)
        self.is_dark = is_dark

    def get(self, token: str, default: str = "#000000") -> str:
        """Get the hex color for *token*."""
        return self._colors.get(token, default)

    def as_dict(self) -> dict[str, str]:
        return dict(self._colors)

    def __getitem__(self, token: str) -> str:
        return self._colors[token]

    def __contains__(self, token: str) -> bool:
        return token in self._colors


# ---------------------------------------------------------------------------
# Theme loading
# ---------------------------------------------------------------------------


def load_theme_from_file(path: str | Path) -> Theme | None:
    """Load a theme from a JSON file.

    Missing tokens are filled from the dark default.
    """
    p = Path(path)
    if not p.exists():
        return None

    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        logger.warning("Failed to parse theme file %s", path)
        return None

    if not isinstance(data, dict):
        return None

    # Merge with defaults — fill any missing tokens
    merged = dict(DEFAULT_DARK_THEME)
    merged.update(data)

    name = data.get("name", p.stem)
    is_dark = data.get("is_dark", True)

    # Validate that all required tokens are present
    missing = REQUIRED_TOKENS - set(merged.keys())
    if missing:
        logger.warning("Theme '%s' missing tokens: %s", name, ", ".join(sorted(missing)))

    return Theme(name=name, colors=merged, is_dark=is_dark)


def discover_themes() -> list[Theme]:
    """Discover all theme JSON files from global and project directories."""
    themes: list[Theme] = []
    seen_names: set[str] = set()

    for theme_dir in THEME_DIRS:
        if not theme_dir.exists():
            continue
        for f in sorted(theme_dir.glob("*.json")):
            theme = load_theme_from_file(f)
            if theme is not None and theme.name not in seen_names:
                seen_names.add(theme.name)
                themes.append(theme)

    return themes


def get_theme(name: str | None = None) -> Theme:
    """Get a theme by name, or the default dark theme."""
    if name:
        for theme_dir in THEME_DIRS:
            for f in theme_dir.glob(f"{name}.json"):
                theme = load_theme_from_file(f)
                if theme is not None:
                    return theme

    return DEFAULT_THEME


# Default themes (always available)
DEFAULT_THEME = Theme("dark", dict(DEFAULT_DARK_THEME))
LIGHT_THEME = Theme("light", dict(DEFAULT_LIGHT_THEME), is_dark=False)


# ---------------------------------------------------------------------------
# Color mode detection
# ---------------------------------------------------------------------------


def supports_truecolor() -> bool:
    """Detect if the terminal supports 24-bit truecolor."""
    colorterm = os.environ.get("COLORTERM", "")
    if colorterm in ("truecolor", "24bit"):
        return True

    term = os.environ.get("TERM", "")
    if "truecolor" in term or "24bit" in term:
        return True

    # Modern terminals known to support truecolor
    term_program = os.environ.get("TERM_PROGRAM", "")
    if term_program in ("kitty", "ghostty", "wezterm", "vscode", "warp-terminal"):
        return True

    return False


def supports_256color() -> bool:
    """Detect if the terminal supports 256-color mode."""
    term = os.environ.get("TERM", "")
    if "256" in term:
        return True
    if os.environ.get("TERM_PROGRAM", "") in ("iTerm.app", "Apple_Terminal"):
        return True
    return False


def hex_to_ansi(hex_color: str) -> tuple[int, int, int]:
    """Convert a hex color string like ``#ff8800`` to ``(r, g, b)``."""
    h = hex_color.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def hex_to_xterm256(hex_color: str) -> int:
    """Find the closest xterm-256 color index for a hex color."""
    r, g, b = hex_to_ansi(hex_color)

    def _distance(idx: int) -> int:
        # Simplified cube-based xterm color mapping
        if idx < 16:
            # Standard ANSI colors
            std = [
                (0, 0, 0), (128, 0, 0), (0, 128, 0), (128, 128, 0),
                (0, 0, 128), (128, 0, 128), (0, 128, 128), (192, 192, 192),
                (128, 128, 128), (255, 0, 0), (0, 255, 0), (255, 255, 0),
                (0, 0, 255), (255, 0, 255), (0, 255, 255), (255, 255, 255),
            ]
            sr, sg, sb = std[idx]
        elif idx < 232:
            # 6x6x6 color cube
            idx2 = idx - 16
            sr = (idx2 // 36) * 51
            sg = ((idx2 // 6) % 6) * 51
            sb = (idx2 % 6) * 51
        else:
            # Grayscale ramp
            gray = (idx - 232) * 10 + 8
            sr = sg = sb = gray

        return (r - sr) ** 2 + (g - sg) ** 2 + (b - sb) ** 2

    return min(range(256), key=_distance)
