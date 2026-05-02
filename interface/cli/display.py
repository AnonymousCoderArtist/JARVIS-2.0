"""Display module for JARVIS CLI - handles all UI rendering and rich components."""

import sys
import time
from typing import Any, Optional, Union
from rich.console import Console
from rich.markdown import Markdown
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
from rich.tree import Tree
from rich.columns import Columns
from rich.text import Text
from rich.align import Align
from rich.rule import Rule
from rich.syntax import Syntax
from rich.theme import Theme as RichTheme


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


class DisplayManager:
    """Manages all display operations using rich console."""

    def __init__(self, theme: str = "dark", width: Optional[int] = None, custom_themes: Optional[dict] = None):
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
        self._live: Optional[Live] = None
        self._streaming_content = ""
        self._streaming_reasoning = ""
        self._is_reasoning = False

    @property
    def theme(self) -> dict[str, str]:
        """Return the current theme colors for external components (e.g. prompt_toolkit)."""
        # Ensure hex codes start with # for prompt_toolkit compatibility
        return {k: f"#{v.split('#')[-1]}" if "#" in v else v for k, v in self._current_colors.items()}

    def _get_theme_colors(self, theme_name: str) -> dict[str, str]:
        """Calculate color definitions for a theme."""
        # Start with base theme colors
        colors = {
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
            "arrow": "#666666",
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
        """Display the welcome banner with rich formatting."""
        self.show_rule("JARVIS 2.0", style="primary")
        
        banner_table = Table.grid(padding=(0, 2))
        banner_table.add_column(style="secondary", justify="right")
        banner_table.add_column(style="info")
        
        banner_table.add_row("Model", model)
        banner_table.add_row("SDK", sdk)
        banner_table.add_row("Base URL", base_url or "default")
        banner_table.add_row("Tools", str(tool_count))
        
        self.console.print(Align.center(banner_table))
        self.show_rule(style="secondary")
        self.console.print()
    
    def show_help(self):
        """Display available commands using rich table."""
        table = Table(
            show_header=True, 
            header_style="primary", 
            border_style="secondary",
            box=None,
            padding=(0, 2)
        )
        table.add_column("Command", style="info")
        table.add_column("Description", style="white")

        commands = [
            ("/help", "Show this help"),
            ("/status", "Show system status"),
            ("/profile", "Switch or list agent profiles"),
            ("/tools", "List available tools"),
            ("/skills", "List and manage skills"),
            ("/learn", "View learning system status"),
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
        """Update the live display with a new chunk."""
        if not self._live:
            self.start_streaming()
        
        if is_reasoning:
            self._streaming_reasoning += chunk
            self._is_reasoning = True
        else:
            self._streaming_content += chunk
            self._is_reasoning = False

        # Build the display object
        parts = []
        if self._streaming_reasoning:
            reasoning_text = Text(self._streaming_reasoning, style="reasoning")
            parts.append(Panel(reasoning_text, title="Reasoning", border_style="secondary", padding=(0, 1)))
        
        if self._streaming_content:
            parts.append(Markdown(self._streaming_content))
        
        if parts:
            if len(parts) > 1:
                # Combine reasoning panel and content
                self._live.update(Columns(parts, equal=False, expand=True))
                # Actually, Columns might not be best for vertical stack
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

    def show_tool_call(self, tool_name: str, tool_args: dict[str, Any]):
        """Display tool call with rich formatting."""
        import json
        args_str = json.dumps(tool_args, indent=2)
        
        panel = Panel(
            Syntax(args_str, "json", theme="monokai", background_color="default"),
            title=f"Tool Call: [tool_call]{tool_name}[/]",
            title_align="left",
            border_style="tool_call",
            padding=(0, 1)
        )
        self.console.print(panel)
    
    def show_tool_result(self, result: Any, max_length: int = 2500):
        """Display tool result with truncation and syntax highlighting if needed."""
        if result and hasattr(result, 'success'):
            res_str = str(result.result) if result.success else f"Error: {result.error}"
            style = "success" if result.success else "error"
        else:
            res_str = str(result)
            style = "tool_result"
        
        if not res_str or res_str == "[]" or res_str == "{}":
            res_str = "(no content)"
        
        if len(res_str) > max_length:
            res_str = res_str[:max_length] + f"\n... (large output truncated, {len(res_str)} total chars)"
        
        # Try to detect if it's JSON or other code
        content_renderable = res_str
        if res_str.strip().startswith(("{", "[")):
            try:
                import json
                parsed = json.loads(res_str)
                content_renderable = Syntax(json.dumps(parsed, indent=2), "json", theme="monokai", background_color="default")
            except:
                pass
        
        panel = Panel(
            content_renderable,
            title="Tool Result",
            title_align="left",
            border_style=style,
            padding=(0, 1)
        )
        self.console.print(panel)
    
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
        from core.learn import LearnedPreferences
        if isinstance(preferences, LearnedPreferences):
            table = Table(show_header=True, header_style="primary", box=None)
            table.add_column("Setting", style="info")
            table.add_column("Value")

            table.add_row("Output Format", preferences.output_format)
            table.add_row("Preferred Tools", ", ".join(preferences.preferred_tools) or "none")
            table.add_row("Query Routing", str(len(preferences.query_routing)) + " rules")
            table.add_row("Last Updated", str(preferences.last_updated)[:19])

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

        table = Table(show_header=True, header_style="primary", box=None)
        table.add_column("Pattern", style="info")
        table.add_column("Type")
        table.add_column("Confidence")

        for p in patterns[:10]:  # Show top 10
            table.add_row(p.name, p.category, f"{p.confidence:.0%}")

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
