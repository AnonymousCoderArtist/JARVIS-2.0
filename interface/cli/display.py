"""Display module for JARVIS CLI - handles all UI rendering and rich components.

Visual effects (shimmer, typewriter, tool calls, sub-agent display) use raw ANSI
escape codes via console.file.write() for precise control. Static rendering
(banner, help, status, profiles, tools, skills, learn, patterns) still uses Rich.
"""

import asyncio
import json
import os
import sys
import time
from typing import Any

from rich.box import MINIMAL, ROUNDED
from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.rule import Rule
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text
from rich.theme import Theme as RichTheme

# ── Module-level console for helper functions ────────────────────────────────

console = Console(legacy_windows=False, color_system="auto", file=sys.stdout)

# ── ANSI helpers ─────────────────────────────────────────────────────────────

_I = "  "  # Indent prefix for all agent output (aligns under the `>` prompt)

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

        if is_reasoning:
            self._streaming_reasoning += chunk
            self._is_reasoning = True
        else:
            self._streaming_content += chunk
            self._is_reasoning = False

        if self._live:
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



