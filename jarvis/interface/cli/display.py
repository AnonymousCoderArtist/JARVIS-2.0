"""Display module for JARVIS CLI — raw ANSI escape codes, no Rich."""

import asyncio
import json
import os
import sys
import time
from typing import Any

_I = "  "
_RESET = "\033[0m"
_BOLD = "\033[1m"
_DIM = "\033[2m"
_ITALIC = "\033[3m"
_BOLD_DIM = "\033[1;2m"
_BOLD_ITALIC = "\033[1;3m"
_CLEAR_LINE = "\033[K"
_CURSOR_UP = "\033[A"
_HIDE_CURSOR = "\033[?25l"
_SHOW_CURSOR = "\033[?25h"

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
    "loader": "-/|\\",
}

THEME_PRESETS = {
    "dark": {"primary": "#ff8700", "secondary": "#666666", "success": "#00ff00", "error": "#ff0000", "warning": "#ffff00", "info": "#00ffff", "prompt": "#ff8700", "user": "#5fafff", "jarvis": "#ff8700", "reasoning": "#888888", "tool_call": "#00afff", "tool_args": "#87d7ff", "tool_result": "#bcbcbc", "arrow": "#666666"},
    "light": {"primary": "#ff6600", "secondary": "#888888", "success": "#00aa00", "error": "#cc0000", "warning": "#cc9900", "info": "#0099cc", "prompt": "#ff6600", "user": "#005fdf", "jarvis": "#ff6600", "reasoning": "#666666", "tool_call": "#0087af", "tool_args": "#005f87", "tool_result": "#444444", "arrow": "#888888"},
    "nord": {"primary": "#81a1c1", "secondary": "#4c566a", "success": "#a3be8c", "error": "#bf616a", "warning": "#ebcb8b", "info": "#88c0d0", "prompt": "#81a1c1", "user": "#5e81ac", "jarvis": "#81a1c1", "reasoning": "#d8dee9", "tool_call": "#8fbcbb", "tool_args": "#8fbcbb", "tool_result": "#eceff4", "arrow": "#4c566a"},
    "dracula": {"primary": "#bd93f9", "secondary": "#6272a4", "success": "#50fa7b", "error": "#ff5555", "warning": "#f1fa8c", "info": "#8be9fd", "prompt": "#bd93f9", "user": "#50fa7b", "jarvis": "#bd93f9", "reasoning": "#f8f8f2", "tool_call": "#ff79c6", "tool_args": "#8be9fd", "tool_result": "#f8f8f2", "arrow": "#6272a4"},
    "gruvbox": {"primary": "#fabd2f", "secondary": "#928374", "success": "#b8bb26", "error": "#fb4934", "warning": "#fabd2f", "info": "#83a598", "prompt": "#fabd2f", "user": "#83a598", "jarvis": "#fabd2f", "reasoning": "#ebdbb2", "tool_call": "#fe8019", "tool_args": "#8ec07c", "tool_result": "#ebdbb2", "arrow": "#928374"},
    "catppuccin": {"primary": "#f5e0dc", "secondary": "#585b70", "success": "#a6e3a1", "error": "#f38ba8", "warning": "#f9e2af", "info": "#89dceb", "prompt": "#f5e0dc", "user": "#b4befe", "jarvis": "#f5e0dc", "reasoning": "#cdd6f4", "tool_call": "#f5c2e7", "tool_args": "#b4befe", "tool_result": "#cdd6f4", "arrow": "#585b70"},
    "ml_intern": {"primary": "#ffc850", "secondary": "#b48c28", "success": "#4ade80", "error": "#f87171", "warning": "#ffc850", "info": "#78dcff", "prompt": "#78dcff", "user": "#78dcff", "jarvis": "#ffc850", "reasoning": "#5a5a6e", "tool_call": "#ffc850", "tool_args": "#b48c28", "tool_result": "#b48c28", "arrow": "#b48c28"},
}

# ── ANSI colour helpers ─────────────────────────────────────────────────────


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    h = hex_color.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _fg(hex_color: str) -> str:
    r, g, b = _hex_to_rgb(hex_color)
    return f"\033[38;2;{r};{g};{b}m"


def _style(color_map: dict[str, str], key: str, text: str, bold: bool = False, dim: bool = False, italic: bool = False) -> str:
    hex_color = color_map.get(key, "#ffffff")
    parts = [_fg(hex_color)]
    if bold:
        parts.append(_BOLD)
    if dim:
        parts.append(_DIM)
    if italic:
        parts.append(_ITALIC)
    parts.append(text)
    parts.append(_RESET)
    return "".join(parts)


def _panel_box(lines: list[str], title: str = "", border_color: str = "\033[38;2;102;102;102m") -> str:
    """Draw a simple box around lines."""
    if not lines:
        return ""
    width = max(len(_strip_ansi(line)) for line in lines)
    title_str = ""
    if title:
        title_str = f" {title} "
        if len(title_str) > width:
            width = len(_strip_ansi(title_str))
    inner_w = width + 2
    top = f"{border_color}╭{'─' * (inner_w - 2)}╮{_RESET}"
    bottom = f"{border_color}╰{'─' * (inner_w - 2)}╯{_RESET}"
    out = [top]
    if title:
        pad_left = (inner_w - 2 - len(_strip_ansi(title_str))) // 2
        pad_right = inner_w - 2 - len(_strip_ansi(title_str)) - pad_left
        out.append(f"{border_color}│{' ' * pad_left}{title_str}{' ' * pad_right}│{_RESET}")
    for line in lines:
        visible_len = len(_strip_ansi(line))
        pad = inner_w - 2 - visible_len
        out.append(f"{border_color}│{_RESET} {line}{' ' * pad}{border_color}│{_RESET}")
    out.append(bottom)
    return "\n".join(out)


def _strip_ansi(text: str) -> str:
    import re
    return re.sub(r"\033\[[0-9;]*[a-zA-Z]", "", text)


# ── Thinking shimmer ────────────────────────────────────────────────────────


class _ThinkingShimmer:
    _BASE = (90, 90, 110)
    _HIGHLIGHT = (255, 200, 80)
    _WIDTH = 5
    _FPS = 24

    def __init__(self, out):
        self._out = out
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
        self._out.write("\r\033[K")
        self._out.flush()

    def _render_frame(self, text: str, offset: float) -> str:
        out = []
        n = len(text)
        for i, ch in enumerate(text):
            dist = abs(i - offset)
            wrap_dist = abs(i - offset + n + self._WIDTH)
            dist = min(dist, wrap_dist, abs(i - offset - n - self._WIDTH))
            t = max(0.0, 1.0 - dist / self._WIDTH)
            t = t * t * (3 - 2 * t)
            r = int(self._BASE[0] + (self._HIGHLIGHT[0] - self._BASE[0]) * t)
            g = int(self._BASE[1] + (self._HIGHLIGHT[1] - self._BASE[1]) * t)
            b = int(self._BASE[2] + (self._HIGHLIGHT[2] - self._BASE[2]) * t)
            out.append(f"\033[38;2;{r};{g};{b}m{ch}")
        out.append("\033[0m")
        return "".join(out)

    async def _animate(self):
        text = "Thinking..."
        n = len(text)
        speed = 0.45
        pos = 0.0
        try:
            while self._running:
                frame = self._render_frame(text, pos)
                self._out.write(f"\r{_I}{frame}")
                self._out.flush()
                pos = (pos + speed) % (n + self._WIDTH)
                await asyncio.sleep(1.0 / self._FPS)
        except asyncio.CancelledError:
            pass


# ── DisplayManager ──────────────────────────────────────────────────────────


class DisplayManager:
    def __init__(self, theme: str = "dark", width: int | None = None, custom_themes: dict | None = None, config=None):
        self.theme_name = theme
        self.custom_themes = custom_themes or {}
        self._width = width or (os.get_terminal_size().columns if sys.stdout.isatty() else 80)
        self._current_colors = self._get_theme_colors(theme)
        self._config = config
        self._thinking_shimmer: _ThinkingShimmer | None = None
        self._streaming_content = ""
        self._streaming_reasoning = ""
        self._is_reasoning = False
        self._streaming_active = False
        self._stream_start_line = 0
        self._lines_written = 0
        self._out = sys.stdout

    @property
    def console(self):
        """Compatibility shim — return self for code that expects .console."""
        return self

    def write(self, text: str):
        self._out.write(text)
        self._out.flush()

    def print(self, text: str = "", end: str = "\n"):
        self._out.write(text + end)
        self._out.flush()

    @property
    def theme(self) -> dict[str, str]:
        return {k: f"#{v.split('#')[-1]}" if "#" in v else v for k, v in self._current_colors.items()}

    def _get_theme_colors(self, theme_name: str) -> dict[str, str]:
        theme_map = {
            "dark": THEME_PRESETS["dark"], "light": THEME_PRESETS["light"],
            "nord": THEME_PRESETS["nord"], "dracula": THEME_PRESETS["dracula"],
            "gruvbox": THEME_PRESETS["gruvbox"], "catppuccin": THEME_PRESETS["catppuccin"],
            "ml_intern": THEME_PRESETS["ml_intern"],
        }
        base = theme_map.get(theme_name, theme_map["dark"])
        colors = {
            "primary": base["primary"], "secondary": base["secondary"],
            "success": base["success"], "error": base["error"],
            "warning": base["warning"], "info": base["info"],
            "prompt": base["prompt"], "user": base["user"],
            "jarvis": base["jarvis"], "reasoning": base["reasoning"],
            "tool_call": base["tool_call"], "tool_args": base["tool_args"],
            "tool_result": base["tool_result"], "arrow": base["arrow"],
        }
        if theme_name in self.custom_themes:
            tc = self.custom_themes[theme_name]
            tc_colors = getattr(tc, "colors", tc)
            if isinstance(tc_colors, dict):
                for k, v in tc_colors.items():
                    if k in colors:
                        colors[k] = v
        return colors

    def set_theme(self, theme_name: str):
        self.theme_name = theme_name
        self._current_colors = self._get_theme_colors(theme_name)

    def cprint(self, text: str, style: str = "", end: str = "\n"):
        if style in self._current_colors:
            self.print(_style(self._current_colors, style, text, bold=True), end=end)
        else:
            self.print(text, end=end)

    def clear_screen(self):
        self._out.write("\033[2J\033[H")
        self._out.flush()

    def show_banner(self, model: str, sdk: str, base_url: str, tool_count: int):
        c = self._current_colors
        lines = [
            f"{_style(c, 'jarvis', 'J A R V I S  2 . 0', bold=True)}",
            "",
            f"  Model     {_style(c, 'secondary', model)}",
            f"  SDK       {_style(c, 'secondary', sdk)}",
            f"  Base URL  {_style(c, 'secondary', base_url or 'default')}",
            f"  Tools     {_style(c, 'secondary', str(tool_count))}",
        ]
        self.print(_panel_box(lines, border_color=_fg(c["jarvis"])))
        self.print()

    def show_help(self):
        c = self._current_colors
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
        lines = []
        for cmd, desc in commands:
            lines.append(f"  {_style(c, 'info', cmd, bold=True)}  {_style(c, 'secondary', desc)}")
        self.print(_panel_box(lines, title="Available Commands", border_color=_fg(c["info"])))
        self.print()
        self.print(f"{_I}{_style(c, 'secondary', 'Tip: Just type your message and press Enter to chat with JARVIS.', italic=True)}")
        self.print()

    # ── Streaming ───────────────────────────────────────────────────────────

    def start_streaming(self):
        self._streaming_content = ""
        self._streaming_reasoning = ""
        self._is_reasoning = False
        self._streaming_active = True
        self._lines_written = 0

    def update_streaming(self, chunk: str, is_reasoning: bool = False):
        if is_reasoning:
            self._streaming_reasoning += chunk
            self._is_reasoning = True
        else:
            self._streaming_content += chunk
            self._is_reasoning = False
        self._redraw_stream()

    def stop_streaming(self):
        self._streaming_active = False
        self.print()

    def _redraw_stream(self):
        """Erase previously drawn streaming lines and redraw."""
        if not self._streaming_active:
            return
        c = self._current_colors
        if self._lines_written > 0:
            for _ in range(self._lines_written):
                self._out.write(f"\r{_CLEAR_LINE}{_CURSOR_UP}")
            self._out.write(f"\r{_CLEAR_LINE}")
            self._out.flush()

        parts = []
        if self._streaming_reasoning:
            reasoning_block = f"{_style(c, 'reasoning', ICONS['reasoning'] + ' Reasoning', bold=True)}\n{_I}{_style(c, 'reasoning', self._streaming_reasoning, italic=True)}"
            parts.append(reasoning_block)
        if self._streaming_content:
            parts.append(self._streaming_content)

        output = "\n\n".join(parts)
        lines = output.split("\n")
        self._lines_written = len(lines)
        for line in lines:
            self.print(line)

    # ── Tool display ────────────────────────────────────────────────────────

    def show_thinking(self):
        if self._thinking_shimmer is None:
            self._thinking_shimmer = _ThinkingShimmer(self._out)
        self._thinking_shimmer.start()

    def hide_thinking(self):
        if self._thinking_shimmer:
            self._thinking_shimmer.stop()
            self._thinking_shimmer = None

    def show_tool_call(self, tool_name: str, tool_args: dict[str, Any]):
        c = self._current_colors
        args_parts = []
        for key, value in tool_args.items():
            val_str = json.dumps(value) if isinstance(value, (dict, list)) else str(value)
            args_parts.append(f"{key}: {val_str}")
        args_str = "  ".join(args_parts)
        gold = _fg(c.get("tool_call", "#ffc850"))
        self._out.write(f"{_I}{gold}▸ ")
        for ch in tool_name:
            self._out.write(ch)
            self._out.flush()
            time.sleep(0.015)
        self._out.write(f"{_RESET}  {_DIM}{args_str}{_RESET}\n")
        self._out.flush()

    def show_tool_result(self, result: Any, max_length: int = 2500):
        c = self._current_colors
        if result and hasattr(result, "success"):
            success = result.success
            res_str = str(result.result) if success else f"Error: {result.error}"
        else:
            success = result is not None and str(result) not in ("", "[]", "{}", "None")
            res_str = str(result) if result else "(no content)"

        if not res_str or res_str in ("[]", "{}"):
            res_str = "(no content)"

        lines = res_str.split("\n")
        if len(lines) > 10:
            res_str = "\n".join(lines[:10]) + f"\n... ({len(lines) - 10} more lines truncated)"
        if len(res_str) > max_length:
            res_str = res_str[:max_length] + f"\n... (large output truncated, {len(res_str)} total chars)"

        icon = "✓" if success else "✗"
        style_key = "success" if success else "error"
        indented = "\n".join(f"{_I}  {line}" for line in res_str.split("\n"))
        if res_str.strip().startswith(("{", "[")):
            try:
                parsed = json.loads(res_str)
                formatted = json.dumps(parsed, indent=2)
                indented = "\n".join(f"{_I}  {line}" for line in formatted.split("\n"))
            except Exception:
                pass
        self.print(f"{_style(c, style_key, f'{_I}{icon}', bold=True)} {indented}")

    # ── Panels ──────────────────────────────────────────────────────────────

    def show_error(self, message: str, title: str = "Error"):
        c = self._current_colors
        lines = [f"{_style(c, 'error', message)}"]
        self.print(_panel_box(lines, title=title, border_color=_fg(c["error"])))

    def show_success(self, message: str, title: str = "Success"):
        c = self._current_colors
        lines = [f"{_style(c, 'success', message)}"]
        self.print(_panel_box(lines, title=title, border_color=_fg(c["success"])))

    def show_rule(self, title: str = "", style: str = "secondary"):
        c = self._current_colors
        color = _fg(c.get(style, "#666666"))
        width = self._width - 4
        if title:
            half = (width - len(title) - 2) // 2
            self.print(f"{_I}{color}{'─' * half} {title} {'─' * (width - half - len(title) - 1)}{_RESET}")
        else:
            self.print(f"{_I}{color}{'─' * width}{_RESET}")

    # ── Tables ──────────────────────────────────────────────────────────────

    def _simple_table(self, headers: list[str], rows: list[list[str]], col_styles: list[str] | None = None) -> str:
        c = self._current_colors
        col_count = len(headers)
        widths = [len(h) for h in headers]
        for row in rows:
            for i, cell in enumerate(row):
                if i < col_count:
                    w = len(_strip_ansi(cell))
                    if w > widths[i]:
                        widths[i] = w

        header_line = "  "
        for i, h in enumerate(headers):
            style = col_styles[i] if col_styles and i < len(col_styles) else "secondary"
            header_line += _style(c, style, h.ljust(widths[i] + 2), bold=True)
        lines = [header_line, f"  {'─' * (sum(widths) + 2 * col_count)}"]
        for row in rows:
            line = "  "
            for i, cell in enumerate(row):
                pad = widths[i] - len(_strip_ansi(cell)) + 2 if i < len(widths) else 0
                line += cell + " " * pad
            lines.append(line)
        return "\n".join(lines)

    def show_status(self, model: str, sdk: str, base_url: str, tool_count: int):
        c = self._current_colors
        rows = [
            [f"{_style(c, 'secondary', 'Model:')} ", model],
            [f"{_style(c, 'secondary', 'SDK:')} ", sdk],
            [f"{_style(c, 'secondary', 'Base URL:')} ", base_url or "default"],
            [f"{_style(c, 'secondary', 'Tools:')} ", str(tool_count)],
        ]
        self.print(_panel_box([r[0] + r[1] for r in rows], title="System Status", border_color=_fg(c["info"])))

    def show_profiles(self, profiles: list, current: str):
        c = self._current_colors
        rows = []
        for profile in profiles:
            is_current = profile == current
            if is_current:
                rows.append([_style(c, "info", profile, bold=True), _style(c, "success", "active", bold=True)])
            else:
                rows.append([profile, ""])
        self.print(_panel_box(
            [self._simple_table(["Profile", "Status"], rows, ["info", "success"])],
            title="Agent Profiles",
            border_color=_fg(c["secondary"]),
        ))

    def show_tools(self, tools: list):
        c = self._current_colors
        rows = []
        for tool in tools:
            if isinstance(tool, dict):
                name = tool.get("name", "unknown")
                desc = tool.get("description", "")
            else:
                name = getattr(tool, "name", "unknown")
                desc = getattr(tool, "description", "")
            rows.append([_style(c, "info", name), desc])
        self.print(_panel_box(
            [self._simple_table(["Tool", "Description"], rows, ["info"])],
            title="Available Tools",
            border_color=_fg(c["secondary"]),
        ))

    def show_skills(self, skills: dict):
        c = self._current_colors
        rows = []
        for name, skill in skills.items():
            if hasattr(skill, "description"):
                desc = skill.description
            elif isinstance(skill, dict):
                desc = skill.get("description", "")
            else:
                desc = "No description"
            rows.append([_style(c, "info", name), desc])
        self.print(_panel_box(
            [self._simple_table(["Skill", "Description"], rows, ["info"])],
            title="Available Skills",
            border_color=_fg(c["secondary"]),
        ))

    def show_themes(self, themes: dict, current_theme: str):
        c = self._current_colors
        rows = []
        for theme_name in themes:
            is_current = theme_name == current_theme
            if is_current:
                rows.append([_style(c, "info", theme_name, bold=True), _style(c, "success", "active", bold=True)])
            else:
                rows.append([theme_name, ""])
        self.print(_panel_box(
            [self._simple_table(["Theme", "Status"], rows, ["info", "success"])],
            title="Available Themes",
            border_color=_fg(c["secondary"]),
        ))

    def show_learned_preferences(self, preferences):
        c = self._current_colors
        if isinstance(preferences, dict):
            rows = [
                ["Output Format", preferences.get("output_format", "")],
                ["Preferred Tools", ", ".join(preferences.get("preferred_tools", [])) or "none"],
                ["Query Routing", str(len(preferences.get("query_routing", []))) + " rules"],
                ["Last Updated", str(preferences.get("last_updated", ""))[:19]],
            ]
            self.print(_panel_box(
                [self._simple_table(["Setting", "Value"], rows, ["info"])],
                title="Learned Preferences",
                border_color=_fg(c["success"]),
            ))
        else:
            self.print(_panel_box([str(preferences)], title="Learned Preferences", border_color=_fg(c["success"])))

    def show_learning_metrics(self, metrics):
        c = self._current_colors
        rows = [
            ["Total Interactions", str(metrics.total_interactions)],
            ["Tool Uses", str(metrics.tool_use_count)],
            ["Errors", str(metrics.error_count)],
            ["Avg Turns/Session", f"{metrics.avg_turns_per_session:.1f}"],
            ["Success Rate", f"{metrics.successful_resolution_rate:.1%}"],
        ]
        self.print(_panel_box(
            [self._simple_table(["Metric", "Value"], rows, ["info"])],
            title="Learning Metrics",
            border_color=_fg(c["info"]),
        ))

    def show_patterns(self, patterns):
        c = self._current_colors
        if not patterns:
            self.print(_panel_box(["No patterns detected yet."], title="Patterns", border_color=_fg(c["secondary"])))
            return
        if isinstance(patterns[0], str):
            rows = [[p[:80] + ("..." if len(p) > 80 else "")] for p in patterns[:10]]
            self.print(_panel_box(
                [self._simple_table(["Recent User Inputs"], rows, ["info"])],
                title="Recent Traces",
                border_color=_fg(c["secondary"]),
            ))
        else:
            rows = []
            for p in patterns[:10]:
                name = p.get("name", p.name if hasattr(p, "name") else "unknown")
                category = p.get("category", p.category if hasattr(p, "category") else "unknown")
                confidence = p.get("confidence", p.confidence if hasattr(p, "confidence") else 0)
                suggestion = p.get("suggestion", p.suggestion if hasattr(p, "suggestion") else "")
                rows.append([_style(c, "info", name), category, f"{confidence:.0%}", suggestion[:50] + ("..." if len(suggestion) > 50 else "")])
            self.print(_panel_box(
                [self._simple_table(["Pattern", "Type", "Confidence", "Suggestion"], rows, ["info"])],
                title="Detected Patterns",
                border_color=_fg(c["secondary"]),
            ))


# ── StreamingResponse ───────────────────────────────────────────────────────


class StreamingResponse:
    def __init__(self):
        self.reasoning = ""
        self.content = ""
        self._start_time = time.time()

    @property
    def elapsed_time(self) -> float:
        return time.time() - self._start_time


# ── Approval Prompt ─────────────────────────────────────────────────────────


def show_approval_prompt(out, items: list[dict], yolo_mode: bool = False) -> list[bool] | str:
    c_colors = None
    # Try to get theme colors from DisplayManager if passed
    if hasattr(out, "_current_colors"):
        c_colors = out._current_colors
    else:
        c_colors = THEME_PRESETS["ml_intern"]

    count = len(items)
    if count == 0:
        return []

    if yolo_mode:
        lines = [f"{_style(c_colors, 'warning', 'yolo', bold=True)} → auto-approved {_style(c_colors, 'warning', str(count), bold=True)} item(s)"]
        out.write(_panel_box(lines, title="⚡ YOLO Mode", border_color=_fg(c_colors["warning"])) + "\n")
        out.flush()
        return [True] * count

    lines = []
    for i, item in enumerate(items, 1):
        tool_name = item.get("tool_name", "unknown")
        tool_args = item.get("args", {})
        operation = _extract_operation(tool_name, tool_args)
        line = f"  {_style(c_colors, 'secondary', f'{i}.')} {_style(c_colors, 'tool_call', f'[{tool_name}]', bold=True)}  {_style(c_colors, 'tool_result', operation)}"
        lines.append(line)
        if tool_name in ("bash", "edit", "file_write", "file_read"):
            detail = _format_tool_detail(tool_name, tool_args)
            if detail:
                lines.append(f"     {_style(c_colors, 'secondary', detail, dim=True)}")

    header = f"{_style(c_colors, 'warning', f'{count} tool call(s) require approval', bold=True)}"
    out.write(_panel_box(lines, title=header, border_color=_fg(c_colors["warning"])) + "\n")
    out.flush()

    out.write(f"\n{_I}{_style(c_colors, 'secondary', 'Approve: ')}{_style(c_colors, 'info', 'y', bold=True)}{_style(c_colors, 'secondary', ' | Reject: ')}{_style(c_colors, 'error', 'n', bold=True)}{_style(c_colors, 'secondary', ' | Approve all: ')}{_style(c_colors, 'info', 'a', bold=True)}{_style(c_colors, 'secondary', ' | Quit: ')}{_style(c_colors, 'error', 'q', bold=True)}\n")
    out.write(f"{_I}{_style(c_colors, 'prompt', '> ', bold=True)}")
    out.flush()

    try:
        response = sys.stdin.readline().strip().lower()
    except (EOFError, KeyboardInterrupt):
        out.write("\n")
        out.flush()
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
        try:
            idx = int(response) - 1
            decisions = [False] * count
            if 0 <= idx < count:
                decisions[idx] = True
            return decisions
        except ValueError:
            return [False] * count


def _extract_operation(tool_name: str, tool_args: dict) -> str:
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
    if tool_args:
        first_key = next(iter(tool_args))
        val = str(tool_args[first_key])[:60]
        return f"{first_key}={val}"
    return ""


def _format_tool_detail(tool_name: str, tool_args: dict) -> str:
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
