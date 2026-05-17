"""Display module for JARVIS CLI - handles all UI rendering and rich components.

Visual effects (shimmer, typewriter, tool calls, sub-agent display) use raw ANSI
escape codes via console.file.write() for precise control. Static rendering
(banner, help, status, profiles, tools, skills, learn, patterns) still uses Rich.
"""

import asyncio
import io
import json
import os
import random
import re
import sys
import time
from typing import Any

from rich.box import MINIMAL, ROUNDED
from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.padding import Padding
from rich.rule import Rule
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text
from rich.theme import Theme as RichTheme

# ── Module-level console for helper functions ────────────────────────────────

console = Console(legacy_windows=False, color_system="auto", file=sys.stdout)

# ── ANSI helpers ─────────────────────────────────────────────────────────────

_I = "  "  # Indent prefix for all agent output (aligns under the `>` prompt)
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")


def _clip_to_width(s: str, width: int) -> str:
    """Truncate a string to *width* visible columns while preserving ANSI styles."""
    visible_len = 0
    out = []
    i = 0
    while i < len(s):
        if s[i] == "\x1b":
            # consume the whole escape sequence
            j = s.find("m", i)
            if j == -1:
                break
            out.append(s[i : j + 1])
            i = j + 1
            continue
        if visible_len >= width:
            break
        out.append(s[i])
        visible_len += 1
        i += 1
    out.append("\x1b[0m")
    return "".join(out)

# ── CRT Boot & Typewriter Helpers ──────────────────────────────────────────

GLITCH_CHARS = "█▓▒░"


def _glitch_text(text: str, intensity: float = 0.1) -> str:
    """Replace random characters with glitch characters based on intensity."""
    if intensity <= 0:
        return text
    result = []
    for ch in text:
        if ch == "\n":
            result.append(ch)
        elif random.random() < intensity:
            result.append(random.choice(GLITCH_CHARS))
        else:
            result.append(ch)
    return "".join(result)


def _type_text(console: Console, text: str, style: str = "", delay: float = 0.015):
    """Type text character-by-character to the Rich console with configurable delay."""
    for ch in text:
        console.print(ch, style=style, end="")
        console.file.flush()
        time.sleep(delay)
    console.print()


def _crt_line(console: Console, label: str, value: str, glitch_intensity: float = 0.3, delay: float = 0.015):
    """Print a single boot line with glitch effect that settles over time."""
    raw = f"  {label}: {value}"
    # Phase 1: heavily glitched version
    glitched = _glitch_text(raw, glitch_intensity)
    console.print(f"[dim]{glitched}[/]")
    time.sleep(delay * 8)
    # Phase 2: partially settled
    settled = _glitch_text(raw, glitch_intensity * 0.3)
    # Move cursor up one line, overwrite
    console.print(f"\033[1A\r[secondary]{settled}[/]")
    time.sleep(delay * 4)
    # Phase 3: fully resolved
    console.print(f"\033[1A\r[secondary]{raw}[/]")
    time.sleep(delay * 2)


def _boot_logo(console: Console):
    """Display a simple ASCII/Braille logo animation for the boot sequence."""
    frames = [
        "  ░░░░░░░░░░",
        "  ▒▒▒▒▒▒▒▒▒▒",
        "  ▓▓▓▓▓▓▓▓▓▓",
        "  ██████████",
        "  J A R V I S",
    ]
    for frame in frames:
        console.print(f"[primary]{frame}[/]")
        time.sleep(0.08)
    console.print()


def run_boot_sequence(console: Console, model: str, tools: list[str], config=None):
    """Run the CRT boot sequence. Only activates when config.display.enable_boot_animation is True."""
    # Check config — bail out if boot animation is disabled
    boot_enabled = False
    typewriter_speed = 0.015
    if config is not None:
        display_cfg = getattr(config, "display", None)
        if display_cfg is not None:
            boot_enabled = getattr(display_cfg, "enable_boot_animation", False)
            typewriter_speed = getattr(display_cfg, "typewriter_speed", 0.015)
    if not boot_enabled:
        return

    console.clear()

    # Phase 1: Logo animation
    _boot_logo(console)

    # Phase 2: CRT boot info lines
    username = os.getenv("USER", os.getenv("USERNAME", "user"))
    tool_count = len(tools)

    _crt_line(console, "User", username, glitch_intensity=0.4, delay=typewriter_speed)
    _crt_line(console, "Model", model, glitch_intensity=0.3, delay=typewriter_speed)
    _crt_line(console, "Tools", f"{tool_count} available", glitch_intensity=0.2, delay=typewriter_speed)

    console.print()
    console.print("[dim]─" * 40 + "[/dim]")
    console.print()


async def print_markdown(console: Console, text: str, cancel_event=None, instant: bool = False):
    """Render markdown to a StringIO buffer with force_terminal=True, then type character by character."""
    from rich.markdown import Markdown as RichMarkdown

    console.print()  # blank line before content

    # Render markdown to a string buffer so we can type it out
    buf = io.StringIO()
    buf_console = Console(
        file=buf,
        width=console.width,
        highlight=False,
        force_terminal=True,  # Important: preserve ANSI styles
        color_system="truecolor",
    )
    buf_console.print(Padding(RichMarkdown(text), (0, 0, 0, 2)))
    rendered = buf.getvalue()

    # Strip trailing whitespace from each line
    lines = rendered.split("\n")
    rendered = "\n".join(line.rstrip() for line in lines)

    f = console.file

    if instant:
        f.write(rendered)
        f.write("\n")
        f.flush()
        return

    # CRT typewriter effect — async so the event loop can service signal handlers
    rng = random.Random(42)
    cancelled = False
    for ch in rendered:
        if cancel_event is not None and cancel_event.is_set():
            cancelled = True
            break
        f.write(ch)
        f.flush()
        if ch == "\n":
            await asyncio.sleep(0.002)
        elif ch == " ":
            await asyncio.sleep(0.002)
        elif rng.random() < 0.03:
            await asyncio.sleep(0.015)
        else:
            await asyncio.sleep(0.004)
    f.write("\033[0m\n" if cancelled else "\n")
    f.flush()


# ── End CRT Boot & Typewriter Helpers ──────────────────────────────────────

# Text icons for different message types (modern UI indicators)
ICONS = {
    "user": "[user]",
    "assistant": "[jarvis]",
    "tool_call": "[tool]",
    "tool_result": "[result]",
    "reasoning": "[reasoning]",
    "error": "[error]",
    "success": "[success]",
    "warning": "[warning]",
    "info": "[info]",
    "prompt": ">",
    "arrow": "->",
    "loader": "-/|\\",  # Animated spinner frames
}

# Modern theme definitions
THEME_PRESETS = {
    "dark": {
        "primary": "#ff8700",
        "secondary": "#666666",
        "success": "#00ff00",
        "error": "#ff0000",
        "warning": "#ffff00",
        "info": "#00ffff",
        "prompt": "#ff8700",
        "user": "#5fafff",
        "jarvis": "#ff8700",
        "reasoning": "#888888",
        "tool_call": "#00afff",
        "tool_args": "#87d7ff",
        "tool_result": "#bcbcbc",
        "arrow": "#666666",
    },
    "light": {
        "primary": "#ff6600",
        "secondary": "#888888",
        "success": "#00aa00",
        "error": "#cc0000",
        "warning": "#cc9900",
        "info": "#0099cc",
        "prompt": "#ff6600",
        "user": "#005fdf",
        "jarvis": "#ff6600",
        "reasoning": "#666666",
        "tool_call": "#0087af",
        "tool_args": "#005f87",
        "tool_result": "#444444",
        "arrow": "#888888",
    },
    "nord": {
        "primary": "#81a1c1",
        "secondary": "#4c566a",
        "success": "#a3be8c",
        "error": "#bf616a",
        "warning": "#ebcb8b",
        "info": "#88c0d0",
        "prompt": "#81a1c1",
        "user": "#5e81ac",
        "jarvis": "#81a1c1",
        "reasoning": "#d8dee9",
        "tool_call": "#8fbcbb",
        "tool_args": "#8fbcbb",
        "tool_result": "#eceff4",
        "arrow": "#4c566a",
    },
    "dracula": {
        "primary": "#bd93f9",
        "secondary": "#6272a4",
        "success": "#50fa7b",
        "error": "#ff5555",
        "warning": "#f1fa8c",
        "info": "#8be9fd",
        "prompt": "#bd93f9",
        "user": "#50fa7b",
        "jarvis": "#bd93f9",
        "reasoning": "#f8f8f2",
        "tool_call": "#ff79c6",
        "tool_args": "#8be9fd",
        "tool_result": "#f8f8f2",
        "arrow": "#6272a4",
    },
    "gruvbox": {
        "primary": "#fabd2f",
        "secondary": "#928374",
        "success": "#b8bb26",
        "error": "#fb4934",
        "warning": "#fabd2f",
        "info": "#83a598",
        "prompt": "#fabd2f",
        "user": "#83a598",
        "jarvis": "#fabd2f",
        "reasoning": "#ebdbb2",
        "tool_call": "#fe8019",
        "tool_args": "#8ec07c",
        "tool_result": "#ebdbb2",
        "arrow": "#928374",
    },
    "catppuccin": {
        "primary": "#f5e0dc",
        "secondary": "#585b70",
        "success": "#a6e3a1",
        "error": "#f38ba8",
        "warning": "#f9e2af",
        "info": "#89dceb",
        "prompt": "#f5e0dc",
        "user": "#b4befe",
        "jarvis": "#f5e0dc",
        "reasoning": "#cdd6f4",
        "tool_call": "#f5c2e7",
        "tool_args": "#b4befe",
        "tool_result": "#cdd6f4",
        "arrow": "#585b70",
    },
    "ml_intern": {
        "primary": "#ffc850",
        "secondary": "#b48c28",
        "success": "#4ade80",
        "error": "#f87171",
        "warning": "#ffc850",
        "info": "#78dcff",
        "prompt": "#78dcff",
        "user": "#78dcff",
        "jarvis": "#ffc850",
        "reasoning": "#5a5a6e",
        "tool_call": "#ffc850",
        "tool_args": "#b48c28",
        "tool_result": "#b48c28",
        "arrow": "#b48c28",
    },
}


class Theme:
    """Color theme definitions for the CLI."""

    DARK_THEME = RichTheme({
        "primary": "bold #ff8700",
        "secondary": "#666666",
        "success": "bold #00ff00",
        "error": "bold #ff0000",
        "warning": "bold #ffff00",
        "info": "bold #00ffff",
        "prompt": "bold #ff8700",
        "user": "bold #5fafff",
        "jarvis": "bold #ff8700",
        "reasoning": "italic dim #888888",
        "tool_call": "bold #00afff",
        "tool_args": "#87d7ff",
        "tool_result": "#bcbcbc",
    })

    LIGHT_THEME = RichTheme({
        "primary": "bold #ff6600",
        "secondary": "#888888",
        "success": "bold #00aa00",
        "error": "bold #cc0000",
        "warning": "bold #cc9900",
        "info": "bold #0099cc",
        "prompt": "bold #ff6600",
        "user": "bold #005fdf",
        "jarvis": "bold #ff6600",
        "reasoning": "italic dim #666666",
        "tool_call": "bold #0087af",
        "tool_args": "#005f87",
        "tool_result": "#444444",
    })

    # New modern themes
    NORD_THEME = RichTheme({
        "primary": "bold #81a1c1",
        "secondary": "#4c566a",
        "success": "bold #a3be8c",
        "error": "bold #bf616a",
        "warning": "bold #ebcb8b",
        "info": "bold #88c0d0",
        "prompt": "bold #81a1c1",
        "user": "bold #5e81ac",
        "jarvis": "bold #81a1c1",
        "reasoning": "italic #d8dee9",
        "tool_call": "bold #8fbcbb",
        "tool_args": "#8fbcbb",
        "tool_result": "#eceff4",
    })

    DRACULA_THEME = RichTheme({
        "primary": "bold #bd93f9",
        "secondary": "#6272a4",
        "success": "bold #50fa7b",
        "error": "bold #ff5555",
        "warning": "bold #f1fa8c",
        "info": "bold #8be9fd",
        "prompt": "bold #bd93f9",
        "user": "bold #50fa7b",
        "jarvis": "bold #bd93f9",
        "reasoning": "italic #f8f8f2",
        "tool_call": "bold #ff79c6",
        "tool_args": "#8be9fd",
        "tool_result": "#f8f8f2",
    })

    GRUVBIX_THEME = RichTheme({
        "primary": "bold #fabd2f",
        "secondary": "#928374",
        "success": "bold #b8bb26",
        "error": "bold #fb4934",
        "warning": "bold #fabd2f",
        "info": "bold #83a598",
        "prompt": "bold #fabd2f",
        "user": "bold #83a598",
        "jarvis": "bold #fabd2f",
        "reasoning": "italic #ebdbb2",
        "tool_call": "bold #fe8019",
        "tool_args": "#8ec07c",
        "tool_result": "#ebdbb2",
    })

    CATPPUCCIN_THEME = RichTheme({
        "primary": "bold #f5e0dc",
        "secondary": "#585b70",
        "success": "bold #a6e3a1",
        "error": "bold #f38ba8",
        "warning": "bold #f9e2af",
        "info": "bold #89dceb",
        "prompt": "bold #f5e0dc",
        "user": "bold #b4befe",
        "jarvis": "bold #f5e0dc",
        "reasoning": "italic #cdd6f4",
        "tool_call": "bold #f5c2e7",
        "tool_args": "#b4befe",
        "tool_result": "#cdd6f4",
    })

    ML_INTERN_THEME = RichTheme({
        "tool.ok": "bold #4ade80",
        "tool.fail": "bold #f87171",
        "tool.name": "bold #ffc850",
        "thinking": "#5a5a6e",
        "prompt": "bold #78dcff",
        "primary": "bold #ffc850",
        "secondary": "#b48c28",
        "success": "bold #4ade80",
        "error": "bold #f87171",
        "warning": "bold #ffc850",
        "info": "bold #78dcff",
        "user": "bold #78dcff",
        "jarvis": "bold #ffc850",
        "reasoning": "italic #5a5a6e",
        "tool_call": "bold #ffc850",
        "tool_args": "#b48c28",
        "tool_result": "#b48c28",
        "arrow": "#b48c28",
    })


class _ThinkingShimmer:
    """Animated shiny/shimmer thinking indicator — a bright gradient sweeps across the text."""

    _BASE = (90, 90, 110)  # dim base color
    _HIGHLIGHT = (255, 200, 80)  # bright shimmer highlight (warm gold)
    _WIDTH = 5  # shimmer width in characters
    _FPS = 24

    def __init__(self, console: Console):
        self._console = console
        self._task = None
        self._running = False

    def start(self):
        if self._running:
            return
        self._running = True
        self._task = asyncio.ensure_future(self._animate())

    def stop(self):
        if not self._running:
            return
        self._running = False
        if self._task:
            self._task.cancel()
            self._task = None
        # Clear the shimmer line
        self._console.file.write("\r\033[K")
        self._console.file.flush()

    def _render_frame(self, text: str, offset: float) -> str:
        """Render one frame: a bright spot sweeps left-to-right across `text`."""
        out = []
        n = len(text)
        for i, ch in enumerate(text):
            dist = abs(i - offset)
            wrap_dist = abs(i - offset + n + self._WIDTH)
            dist = min(dist, wrap_dist, abs(i - offset - n - self._WIDTH))
            t = max(0.0, 1.0 - dist / self._WIDTH)
            t = t * t * (3 - 2 * t)  # smoothstep
            r = int(self._BASE[0] + (self._HIGHLIGHT[0] - self._BASE[0]) * t)
            g = int(self._BASE[1] + (self._HIGHLIGHT[1] - self._BASE[1]) * t)
            b = int(self._BASE[2] + (self._HIGHLIGHT[2] - self._BASE[2]) * t)
            out.append(f"\033[38;2;{r};{g};{b}m{ch}")
        out.append("\033[0m")
        return "".join(out)

    async def _animate(self):
        text = "Thinking..."
        n = len(text)
        speed = 0.45  # characters per frame
        pos = 0.0
        try:
            while self._running:
                frame = self._render_frame(text, pos)
                self._console.file.write(f"\r{_I}{frame}")
                self._console.file.flush()
                pos = (pos + speed) % (n + self._WIDTH)
                await asyncio.sleep(1.0 / self._FPS)
        except asyncio.CancelledError:
            pass


class DisplayManager:
    """Manages all display operations using rich console."""

    def __init__(self, theme: str = "dark", width: int | None = None, custom_themes: dict | None = None, config=None):
        self.theme_name = theme
        self.custom_themes = custom_themes or {}
        self._current_colors = self._get_theme_colors(theme)
        self.console = Console(
            width=width,
            theme=RichTheme(self._current_colors),
            legacy_windows=False,
            color_system="auto",
            file=sys.stdout
        )
        self._live: Live | None = None
        self._streaming_content = ""
        self._streaming_reasoning = ""
        self._is_reasoning = False
        self._config = config
        self._typewriter_buffer = ""
        self._last_typewriter_flush = 0
        self._thinking_shimmer: _ThinkingShimmer | None = None

    @property
    def theme(self) -> dict[str, str]:
        """Return the current theme colors for external components (e.g. prompt_toolkit)."""
        # Ensure hex codes start with # for prompt_toolkit compatibility
        return {k: f"#{v.split('#')[-1]}" if "#" in v else v for k, v in self._current_colors.items()}

    def _get_theme_colors(self, theme_name: str) -> dict[str, str]:
        """Calculate color definitions for a theme."""
        # Map theme names to their presets
        theme_map = {
            "dark": THEME_PRESETS["dark"],
            "light": THEME_PRESETS["light"],
            "nord": THEME_PRESETS["nord"],
            "dracula": THEME_PRESETS["dracula"],
            "gruvbox": THEME_PRESETS["gruvbox"],
            "catppuccin": THEME_PRESETS["catppuccin"],
            "ml_intern": THEME_PRESETS["ml_intern"],
        }

        # Get base colors from preset or use dark as fallback
        base_colors = theme_map.get(theme_name, theme_map["dark"])

        # Add formatting (bold/italic) for specific styles
        colors = {
            "primary": f"bold {base_colors['primary']}",
            "secondary": base_colors['secondary'],
            "success": f"bold {base_colors['success']}",
            "error": f"bold {base_colors['error']}",
            "warning": f"bold {base_colors['warning']}",
            "info": f"bold {base_colors['info']}",
            "prompt": f"bold {base_colors['prompt']}",
            "user": f"bold {base_colors['user']}",
            "jarvis": f"bold {base_colors['jarvis']}",
            "reasoning": f"italic dim {base_colors['reasoning']}",
            "tool_call": f"bold {base_colors['tool_call']}",
            "tool_args": base_colors['tool_args'],
            "tool_result": base_colors['tool_result'],
            "arrow": base_colors['arrow'],
        }

        # Override with custom theme if available
        if theme_name in self.custom_themes:
            theme_config = self.custom_themes[theme_name]
            theme_colors = getattr(theme_config, 'colors', theme_config)
            if isinstance(theme_colors, dict):
                for k, v in theme_colors.items():
                    if k in colors:
                        # Keep formatting (bold/italic) if it was there
                        prefix = colors[k].split("#")[0] if "#" in colors[k] else ""
                        colors[k] = f"{prefix}{v}"

        return colors

    def set_theme(self, theme_name: str):
        """Update the active theme at runtime."""
        self.theme_name = theme_name
        self._current_colors = self._get_theme_colors(theme_name)
        self.console.push_theme(RichTheme(self._current_colors))

    def cprint(self, text: str, style: str = "", end: str = "\n"):
        """Print with style using rich console."""
        self.console.print(text, style=style, end=end)

    def clear_screen(self):
        """Clear the terminal screen."""
        self.console.clear()

    def show_banner(self, model: str, sdk: str, base_url: str, tool_count: int):
        """Display the welcome banner with rich formatting and box-drawing characters."""
        self.console.print()
        self.console.print(
            "╭─────────────────── J A R V I S  2 . 0 ────────────────────╮"
        )
        self.console.print(
            "│                                                           │"
        )
        self.console.print(
            f"│     Model    {model:<45}│"
        )
        self.console.print(
            f"│       SDK    {sdk:<45}│"
        )
        self.console.print(
            f"│  Base URL    {(base_url or 'default'):<45}│"
        )
        self.console.print(
            f"│     Tools    {tool_count:<45}│"
        )
        self.console.print(
            "│                                                           │"
        )
        self.console.print(
            "╰───────────────────────────────────────────────────────────╯"
        )
        self.console.print()

    def show_help(self):
        """Display available commands using rich table with icons."""
        table = Table(
            show_header=True,
            header_style="primary",
            border_style="secondary",
            box=ROUNDED,
            padding=(0, 2)
        )
        table.add_column("Command", style="info")
        table.add_column("Description", style="white")

        commands = [
            ("/help", "Show this help message"),
            ("/status", "Show system status"),
            ("/profile", "Switch or list agent profiles"),
            ("/tools", "List available tools"),
            ("/skills", "List and manage skills"),
            ("/learn", "View learning system status"),
            ("/themes", "List and change themes"),
            ("/clear", "Clear the screen"),
            ("/exit", "Exit JARVIS"),
            ("! <cmd>", "Run shell command"),
        ]

        for cmd, desc in commands:
            table.add_row(cmd, desc)

        self.console.print(Panel(table, title="[primary]Available Commands[/]", border_style="secondary"))
        self.console.print("\n[dim]Tip: Just type your message and press Enter to chat with JARVIS.[/]\n")

    def start_streaming(self):
        """Initialize live display for streaming."""
        self._streaming_content = ""
        self._streaming_reasoning = ""
        self._is_reasoning = False
        self._typewriter_buffer = ""
        self._last_typewriter_flush = 0

        # Check if typewriter mode is enabled
        typewriter_enabled = False
        if self._config is not None:
            display_cfg = getattr(self._config, "display", None)
            if display_cfg is not None:
                typewriter_enabled = getattr(display_cfg, "enable_typewriter", False)

        if not typewriter_enabled:
            # Use standard Live display for instant rendering
            self._live = Live(
                Text(""),
                console=self.console,
                refresh_per_second=10,
                auto_refresh=True,
                vertical_overflow="visible"
            )
            self._live.start()

    def update_streaming(self, chunk: str, is_reasoning: bool = False):
        """Update the live display with a new chunk with smooth animation."""
        if not self._live:
            self.start_streaming()

        # Check if typewriter mode is enabled
        typewriter_enabled = False
        typewriter_speed = 0.015
        if self._config is not None:
            display_cfg = getattr(self._config, "display", None)
            if display_cfg is not None:
                typewriter_enabled = getattr(display_cfg, "enable_typewriter", False)
                typewriter_speed = getattr(display_cfg, "typewriter_speed", 0.015)

        if is_reasoning:
            self._streaming_reasoning += chunk
            self._is_reasoning = True
        else:
            self._streaming_content += chunk
            self._is_reasoning = False

        if typewriter_enabled and not is_reasoning:
            # Typewriter mode: type out new content character by character
            new_content = chunk
            for ch in new_content:
                if ch == "\n":
                    self.console.print()
                elif random.random() < 0.002:  # Occasional glitch
                    self.console.print(random.choice(GLITCH_CHARS), end="")
                    self.console.file.flush()
                else:
                    self.console.print(ch, end="")
                    self.console.file.flush()
                time.sleep(typewriter_speed)
        elif self._live:
            # Build the display object with improved styling
            parts = []
            if self._streaming_reasoning:
                reasoning_text = Text(self._streaming_reasoning, style="reasoning")
                parts.append(Panel(
                    reasoning_text,
                    title=f"{ICONS['reasoning']} Reasoning",
                    border_style="secondary",
                    padding=(0, 1),
                    box=MINIMAL
                ))

            if self._streaming_content:
                parts.append(Markdown(self._streaming_content))

            if parts:
                if len(parts) > 1:
                    from rich.console import Group
                    self._live.update(Group(*parts))
                else:
                    self._live.update(parts[0])

    def stop_streaming(self):
        """Finalize and stop live display."""
        if self._live:
            self._live.stop()
            self._live = None
        self.console.print()

    def show_thinking(self):
        """Start the thinking shimmer animation."""
        if self._thinking_shimmer is None:
            self._thinking_shimmer = _ThinkingShimmer(self.console)
        self._thinking_shimmer.start()

    def hide_thinking(self):
        """Stop the thinking shimmer animation."""
        if self._thinking_shimmer:
            self._thinking_shimmer.stop()
            self._thinking_shimmer = None

    def show_tool_call(self, tool_name: str, tool_args: dict[str, Any]):
        """Display tool call with gold typed name and dimmed arguments."""
        f = self.console.file
        gold = "\033[38;2;255;200;80m"
        reset = "\033[0m"

        # Build arguments string
        args_parts = []
        for key, value in tool_args.items():
            val_str = json.dumps(value) if isinstance(value, (dict, list)) else str(value)
            args_parts.append(f"{key}: {val_str}")
        args_str = "  ".join(args_parts)

        # CRT-style: type out tool name in warm gold
        f.write(f"{_I}{gold}▸ ")
        for ch in tool_name:
            f.write(ch)
            f.flush()
            time.sleep(0.015)
        f.write(f"{reset}  \033[2m{args_str}{reset}\n")
        f.flush()

    def show_tool_result(self, result: Any, max_length: int = 2500):
        """Display tool result with success/failure styling and line truncation."""
        if result and hasattr(result, 'success'):
            success = result.success
            res_str = str(result.result) if success else f"Error: {result.error}"
        else:
            success = result is not None and str(result) not in ("", "[]", "{}", "None")
            res_str = str(result) if result else "(no content)"

        if not res_str or res_str == "[]" or res_str == "{}":
            res_str = "(no content)"

        # Truncate to max 10 lines
        lines = res_str.split("\n")
        if len(lines) > 10:
            res_str = "\n".join(lines[:10]) + f"\n... ({len(lines) - 10} more lines truncated)"

        # Also truncate by character length
        if len(res_str) > max_length:
            res_str = res_str[:max_length] + f"\n... (large output truncated, {len(res_str)} total chars)"

        # Style based on success
        if success:
            icon = "✓"
            style = "tool.ok"
            # Try to detect JSON for syntax highlighting
            if res_str.strip().startswith(("{", "[")):
                try:
                    parsed = json.loads(res_str)
                    formatted = json.dumps(parsed, indent=2)
                    indented = "\n".join(f"{_I}  {line}" for line in formatted.split("\n"))
                    self.console.print(f"[{style}]{_I}{icon}[/] {Syntax(formatted, 'json', theme='monokai', background_color='default')}")
                    return
                except Exception:
                    pass
            indented = "\n".join(f"{_I}  {line}" for line in res_str.split("\n"))
            self.console.print(f"[{style}]{_I}{icon}[/] {res_str}")
        else:
            icon = "✗"
            style = "tool.fail"
            indented = "\n".join(f"{_I}  {line}" for line in res_str.split("\n"))
            self.console.print(f"[{style}]{_I}{icon}[/] {res_str}")

    def show_error(self, message: str, title: str = "Error"):
        """Display error message in a red panel."""
        self.console.print(Panel(message, title=title, border_style="error", padding=(0, 1)))

    def show_success(self, message: str, title: str = "Success"):
        """Display success message in a green panel."""
        self.console.print(Panel(message, title=title, border_style="success", padding=(0, 1)))

    def show_rule(self, title: str = "", style: str = "secondary"):
        """Display a horizontal rule."""
        self.console.print(Rule(title, style=style))

    def show_status(self, model: str, sdk: str, base_url: str, tool_count: int):
        """Display system status using rich panel."""
        status_table = Table.grid(padding=(0, 2))
        status_table.add_row("[secondary]Model:[/]", model)
        status_table.add_row("[secondary]SDK:[/]", sdk)
        status_table.add_row("[secondary]Base URL:[/]", base_url or "default")
        status_table.add_row("[secondary]Tools:[/]", str(tool_count))

        self.console.print(Panel(status_table, title="System Status", border_style="info"))

    def show_profiles(self, profiles: list, current: str):
        """Display available profiles."""
        table = Table(show_header=True, header_style="primary", box=None)
        table.add_column("Profile")
        table.add_column("Status")

        for profile in profiles:
            is_current = profile == current
            status = "[success]active[/]" if is_current else ""
            name = f"[info]{profile}[/]" if is_current else profile
            table.add_row(name, status)

        self.console.print(Panel(table, title="Agent Profiles", border_style="secondary"))

    def show_tools(self, tools: list):
        """Display available tools."""
        table = Table(show_header=True, header_style="primary", box=None)
        table.add_column("Tool", style="info")
        table.add_column("Description")

        for tool in tools:
            if isinstance(tool, dict):
                name = tool.get('name', 'unknown')
                desc = tool.get('description', '')
            else:
                name = getattr(tool, 'name', 'unknown')
                desc = getattr(tool, 'description', '')
            table.add_row(name, desc)

        self.console.print(Panel(table, title="Available Tools", border_style="secondary"))

    def show_skills(self, skills: dict):
        """Display available skills."""
        table = Table(show_header=True, header_style="primary", box=None)
        table.add_column("Skill", style="info")
        table.add_column("Description")

        for name, skill in skills.items():
            if hasattr(skill, 'description'):
                desc = skill.description
            elif isinstance(skill, dict):
                desc = skill.get('description', '')
            else:
                desc = "No description"
            table.add_row(name, desc)

        self.console.print(Panel(table, title="Available Skills", border_style="secondary"))

    def show_themes(self, themes: dict, current_theme: str):
        """Display available themes."""
        table = Table(show_header=True, header_style="primary", box=None)
        table.add_column("Theme")
        table.add_column("Status")

        for theme_name in themes:
            is_current = theme_name == current_theme
            status = "[success]active[/]" if is_current else ""
            name = f"[info]{theme_name}[/]" if is_current else theme_name
            table.add_row(name, status)

        self.console.print(Panel(table, title="Available Themes", border_style="secondary"))

    def show_learned_preferences(self, preferences):
        """Display learned preferences from the learning system."""
        if isinstance(preferences, dict):
            table = Table(show_header=True, header_style="primary", box=None)
            table.add_column("Setting", style="info")
            table.add_column("Value")

            table.add_row("Output Format", preferences.get("output_format", ""))
            table.add_row("Preferred Tools", ", ".join(preferences.get("preferred_tools", [])) or "none")
            table.add_row("Query Routing", str(len(preferences.get("query_routing", []))) + " rules")
            table.add_row("Last Updated", str(preferences.get("last_updated", ""))[:19])

            self.console.print(Panel(table, title="Learned Preferences", border_style="success"))
        else:
            self.console.print(Panel(str(preferences), title="Learned Preferences", border_style="success"))

    def show_learning_metrics(self, metrics):
        """Display learning metrics from trace analysis."""
        table = Table(show_header=True, header_style="primary", box=None)
        table.add_column("Metric", style="info")
        table.add_column("Value")

        table.add_row("Total Interactions", str(metrics.total_interactions))
        table.add_row("Tool Uses", str(metrics.tool_use_count))
        table.add_row("Errors", str(metrics.error_count))
        table.add_row("Avg Turns/Session", f"{metrics.avg_turns_per_session:.1f}")
        table.add_row("Success Rate", f"{metrics.successful_resolution_rate:.1%}")

        self.console.print(Panel(table, title="Learning Metrics", border_style="info"))

    def show_patterns(self, patterns):
        """Display detected patterns."""
        if not patterns:
            self.console.print(Panel("No patterns detected yet.", title="Patterns", border_style="secondary"))
            return

        if isinstance(patterns[0], str):
            # Simple string patterns from traces
            table = Table(show_header=True, header_style="primary", box=None)
            table.add_column("Recent User Inputs", style="info")
            for p in patterns[:10]:
                table.add_row(p[:80] + ("..." if len(p) > 80 else ""))
            self.console.print(Panel(table, title="Recent Traces", border_style="secondary"))
        else:
            # Dict or object patterns with name/category/confidence
            table = Table(show_header=True, header_style="primary", box=None)
            table.add_column("Pattern", style="info")
            table.add_column("Type")
            table.add_column("Confidence")
            table.add_column("Suggestion")

            for p in patterns[:10]:  # Show top 10
                name = p.get("name", p.name if hasattr(p, "name") else "unknown")
                category = p.get("category", p.category if hasattr(p, "category") else "unknown")
                confidence = p.get("confidence", p.confidence if hasattr(p, "confidence") else 0)
                suggestion = p.get("suggestion", p.suggestion if hasattr(p, "suggestion") else "")
                table.add_row(name, category, f"{confidence:.0%}", suggestion[:50] + ("..." if len(suggestion) > 50 else ""))

            self.console.print(Panel(table, title="Detected Patterns", border_style="secondary"))


class StreamingResponse:
    """Helper class to track streaming reasoning and response content."""

    def __init__(self):
        self.reasoning = ""
        self.content = ""
        self._start_time = time.time()

    @property
    def elapsed_time(self) -> float:
        return time.time() - self._start_time


# ── Approval Prompt UI ─────────────────────────────────────────────────────

def show_approval_prompt(console: Console, items: list[dict], yolo_mode: bool = False) -> list[bool] | str:
    """Display a rich approval prompt for pending tool calls.

    Args:
        console: Rich Console instance.
        items: List of dicts with keys: tool_name, args, tool_call_id, permissions.
        yolo_mode: If True, auto-approve all items.

    Returns:
        List of booleans (one per item) or "all" to approve everything.
    """
    count = len(items)
    if count == 0:
        return []

    if yolo_mode:
        console.print(Panel(
            f"[warning]yolo[/] → auto-approved [warning]{count}[/] item(s)",
            title="[warning]⚡ YOLO Mode[/]",
            border_style="warning",
            padding=(0, 1),
            box=ROUNDED,
        ))
        return [True] * count

    # Build numbered list of items
    lines = []
    for i, item in enumerate(items, 1):
        tool_name = item.get("tool_name", "unknown")
        tool_args = item.get("args", {})
        operation = _extract_operation(tool_name, tool_args)

        line = Text()
        line.append(f"  {i}. ", style="secondary")
        line.append(f"[{tool_name}]", style="bold tool_call")
        line.append(f"  {operation}", style="tool_result")
        lines.append(line)

        # Show additional details for complex tools
        if tool_name in ("bash", "edit", "file_write", "file_read"):
            detail = _format_tool_detail(tool_name, tool_args)
            if detail:
                lines.append(Text(f"     {detail}", style="dim secondary"))

    # Header
    header = f"[bold yellow]{count} tool call(s) require approval[/]"

    # Build panel content
    from rich.console import Group
    panel_content = Group(*lines)

    console.print(Panel(
        panel_content,
        title=header,
        border_style="warning",
        padding=(1, 1),
        box=ROUNDED,
    ))

    # Prompt user for input
    console.print()
    console.print("[secondary]Approve: [info]y[/] [secondary]| Reject: [error]n[/] [secondary]| Approve all: [info]a[/] [secondary]| Quit: [error]q[/][/]")

    try:
        response = console.input("[bold prompt]> [/]").strip().lower()
    except (EOFError, KeyboardInterrupt):
        console.print()
        return [False] * count

    if response in ("a", "all"):
        return "all"
    elif response in ("q", "quit"):
        return [False] * count
    elif response in ("y", "yes"):
        return [True] * count
    elif response in ("n", "no"):
        return [False] * count
    else:
        # Try to parse as number for individual approval
        try:
            idx = int(response) - 1
            decisions = [False] * count
            if 0 <= idx < count:
                decisions[idx] = True
            return decisions
        except ValueError:
            return [False] * count


def _extract_operation(tool_name: str, tool_args: dict) -> str:
    """Extract a human-readable operation description from tool call."""
    op_map = {
        "bash": lambda a: f"$ {a.get('command', '')[:80]}",
        "edit": lambda a: f"edit {a.get('file_path', a.get('path', 'unknown'))}",
        "file_write": lambda a: f"write {a.get('file_path', a.get('path', 'unknown'))}",
        "file_read": lambda a: f"read {a.get('file_path', a.get('path', 'unknown'))}",
        "find": lambda a: f"find {a.get('pattern', a.get('path', ''))}",
        "ls": lambda a: f"list {a.get('path', '.')}",
        "grep": lambda a: f"grep '{a.get('pattern', '')}'",
        "web_fetch": lambda a: f"fetch {a.get('url', '')[:60]}",
        "web_search": lambda a: f"search: {a.get('query', '')[:60]}",
    }
    extractor = op_map.get(tool_name)
    if extractor:
        return extractor(tool_args)
    # Generic: show first arg value
    if tool_args:
        first_key = next(iter(tool_args))
        val = str(tool_args[first_key])[:60]
        return f"{first_key}={val}"
    return ""


def _format_tool_detail(tool_name: str, tool_args: dict) -> str:
    """Format additional details for complex tools."""
    if tool_name == "bash":
        cmd = tool_args.get("command", "")
        return f"command: {cmd[:100]}"
    elif tool_name == "edit":
        return f"file: {tool_args.get('file_path', tool_args.get('path', ''))}"
    elif tool_name == "file_write":
        content = tool_args.get("content", "")
        return f"writing {len(content)} chars to {tool_args.get('file_path', tool_args.get('path', ''))}"
    elif tool_name == "web_fetch":
        return f"url: {tool_args.get('url', '')}"
    return ""


# ── Live-Updating Sub-Agent Dashboard ───────────────────────────────────────

class SubAgentDisplay:
    """Manages multiple concurrent sub-agent displays using raw ANSI escape codes."""

    _MAX_VISIBLE = 4  # tool-call lines shown per agent

    def __init__(self, console: Console | None = None):
        self._console = console or Console()
        self._agents: dict[str, dict] = {}
        self._lines_on_screen = 0

    def start(self, agent_id: str, label: str = "research"):
        import time
        self._agents[agent_id] = {
            "label": label,
            "calls": [],
            "tool_count": 0,
            "token_count": 0,
            "start_time": time.monotonic(),
        }
        self._redraw()

    def set_tokens(self, agent_id: str, tokens: int):
        if agent_id in self._agents:
            self._agents[agent_id]["token_count"] = tokens

    def set_tool_count(self, agent_id: str, count: int):
        if agent_id in self._agents:
            self._agents[agent_id]["tool_count"] = count

    def add_call(self, agent_id: str, tool_desc: str):
        if agent_id in self._agents:
            self._agents[agent_id]["calls"].append(tool_desc)
            self._redraw()

    def clear(self, agent_id: str):
        agent = self._agents.pop(agent_id, None)
        self._erase()
        if agent is not None:
            width = max(10, self._console.width or 80)
            line = _clip_to_width(self._render_completion_line(agent), width)
            self._console.file.write(line + "\n")
            self._console.file.flush()
        self._lines_on_screen = 0
        if self._agents:
            self._redraw()

    def _erase(self):
        if self._lines_on_screen > 0:
            f = self._console.file
            for _ in range(self._lines_on_screen):
                f.write("\033[A\033[K")
            f.flush()

    def _redraw(self):
        f = self._console.file
        self._erase()
        compact = len(self._agents) > 1
        width = max(10, self._console.width or 80)
        lines = []
        for agent in self._agents.values():
            for ln in self._render_agent_lines(agent, compact=compact):
                lines.append(_clip_to_width(ln, width))
        for line in lines:
            f.write(line + "\n")
        f.flush()
        self._lines_on_screen = len(lines)

    def _render_agent_lines(self, agent: dict, compact: bool = False) -> list[str]:
        """Render display lines for a single agent."""
        label = agent["label"]
        elapsed = time.monotonic() - agent["start_time"]
        tokens = agent["token_count"]
        tool_count = agent["tool_count"]
        calls = agent["calls"][-self._MAX_VISIBLE:]

        gold = "\033[38;2;255;200;80m"
        dim = "\033[2m"
        reset = "\033[0m"

        header = f"{_I}{gold}▸ {label}{reset}{dim}  {elapsed:.0f}s  {tokens:,} tokens  {tool_count} tools{reset}"
        lines = [header]
        for call in calls:
            lines.append(f"{_I}    {dim}{call}{reset}")
        return lines

    def _render_completion_line(self, agent: dict) -> str:
        """Render a single completion line for a finished agent."""
        label = agent["label"]
        elapsed = time.monotonic() - agent["start_time"]
        tokens = agent["token_count"]
        green = "\033[38;2;74;222;128m"
        dim = "\033[2m"
        reset = "\033[0m"
        return f"{_I}{green}✓ {label}{reset}{dim}  {elapsed:.0f}s  {tokens:,} tokens{reset}"


# ── Approval helpers ────────────────────────────────────────────────────────

def print_approval_header(count: int):
    """Display approval required header."""
    label = f"Approval required — {count} item{'s' if count != 1 else ''}"
    console.print()
    console.print(
        f"{_I}",
        Panel(f"[bold yellow]{label}[/bold yellow]", border_style="yellow", expand=False),
    )


def print_approval_item(index: int, total: int, tool_name: str, operation: str):
    """Display a single approval item."""
    console.print(f"\n{_I}[bold]\\[{index}/{total}][/bold]  [tool.name]{tool_name}[/tool.name]  {operation}")


def print_yolo_approve(count: int):
    """Display yolo auto-approve message."""
    console.print(f"{_I}[bold yellow]yolo →[/bold yellow] auto-approved {count} item(s)")


# ── Message helpers ─────────────────────────────────────────────────────────

def print_error(message: str):
    """Display an error message."""
    console.print(f"\n{_I}[bold red]Error:[/bold red] {message}")


def print_turn_complete():
    """No separator — clean output between turns."""
    pass


def print_interrupted():
    """Display interrupted message."""
    console.print(f"\n{_I}[dim italic]interrupted[/dim italic]")


def print_compacted(old_tokens: int, new_tokens: int):
    """Display context compaction message."""
    console.print(f"{_I}[dim]context compacted: {old_tokens:,} → {new_tokens:,} tokens[/dim]")


def print_init_done(tool_count: int = 0):
    """Display initialization complete message with tool count."""
    console.print(f"{_I}[dim]Ready with {tool_count} tools available.[/dim]")


def print_tool_call(tool_name: str, args_str: str):
    """Display a tool call being made."""
    gold = "\033[38;2;255;200;80m"
    reset = "\033[0m"
    dim = "\033[2m"
    console.file.write(f"{_I}{gold}▸ {tool_name}{reset}  {dim}{args_str}{reset}\n")
    console.file.flush()


def print_tool_output(output: str, success: bool = False, truncate: bool = True):
    """Display tool execution output."""
    if truncate and len(output) > 500:
        output = output[:500] + "\n... (truncated)"
    style = "tool.ok" if success else "tool.fail"
    icon = "✓" if success else "✗"
    indented = "\n".join(f"{_I}  {line}" for line in output.split("\n"))
    console.print(f"[{style}]{_I}{icon}[/] {indented}")


def print_tool_log(tool: str, log: str, agent_id: str = "", label: str = ""):
    """Display informational tool log message."""
    prefix = ""
    if label:
        prefix = f"[{label}] "
    elif agent_id:
        prefix = f"[{agent_id}] "
    console.print(f"{_I}[dim]{prefix}{tool}: {log}[/dim]")


def print_plan():
    """Display plan indicator (no-op for clean output)."""
    pass


def print_help():
    """Display available slash commands."""
    console.print()
    console.print(f"{_I}[bold]Available commands:[/bold]")
    console.print(f"{_I}  [info]/help[/]          Show this help message")
    console.print(f"{_I}  [info]/model[/]         Switch or list models")
    console.print(f"{_I}  [info]/yolo[/]          Toggle auto-approve mode")
    console.print(f"{_I}  [info]/status[/]        Show session status")
    console.print(f"{_I}  [info]/undo[/]          Undo last operation")
    console.print(f"{_I}  [info]/compact[/]       Compact context")
    console.print(f"{_I}  [info]/new[/]           Start new chat")
    console.print(f"{_I}  [info]/clear[/]         Start new chat and clear screen")
    console.print(f"{_I}  [info]/resume[/]        Resume a previous session")
    console.print(f"{_I}  [info]/effort[/]        Set reasoning effort level")
    console.print(f"{_I}  [info]/share-traces[/]  Manage trace visibility")
    console.print(f"{_I}  [info]/themes[/]        List and change UI themes")
    console.print(f"{_I}  [info]/tools[/]         List available tools")
    console.print(f"{_I}  [info]/skills[/]        List and manage skills")
    console.print(f"{_I}  [info]/learn[/]         View learning system status")
    console.print(f"{_I}  [info]/profile[/]       Switch or list agent profiles")
    console.print(f"{_I}  [info]/exit[/]          Exit JARVIS")
    console.print(f"{_I}  [info]! <cmd>[/]        Run shell command")
    console.print()
