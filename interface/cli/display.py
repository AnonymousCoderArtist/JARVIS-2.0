"""Display module for JARVIS CLI - handles all UI rendering and rich components."""

import re
from typing import Any, Optional
from rich.console import Console, ConsoleOptions, RenderResult
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


class Colors:
    """ANSI color codes for fallback rendering."""
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"


class Theme:
    """Color theme definitions for the CLI."""
    
    DARK_THEME = {
        "primary": "#ff8700",
        "secondary": "#666666",
        "success": "#00ff00",
        "error": "#ff0000",
        "warning": "#ffff00",
        "info": "#00ffff",
        "prompt": "#ff8700",
        "arrow": "#666666",
    }
    
    LIGHT_THEME = {
        "primary": "#ff6600",
        "secondary": "#888888",
        "success": "#00aa00",
        "error": "#cc0000",
        "warning": "#cc9900",
        "info": "#0099cc",
        "prompt": "#ff6600",
        "arrow": "#888888",
    }


class DisplayManager:
    """Manages all display operations using rich console."""
    
    def __init__(self, theme: str = "dark", width: int = 80):
        self.theme_name = theme
        self.theme = Theme.DARK_THEME if theme == "dark" else Theme.LIGHT_THEME
        self.console = Console(
            width=width, 
            legacy_windows=False,
            color_system="auto"
        )
        self._live_display: Optional[Live] = None
        self._current_content = ""
    
    def cprint(self, text: str, color: str = "", style: str = "", end: str = "\n"):
        """Print with color and style using rich console."""
        if color or style:
            rich_style = ""
            if style:
                rich_style += style + " "
            if color:
                rich_style += color
            self.console.print(text, style=rich_style.strip(), end=end)
        else:
            self.console.print(text, end=end)
    
    def clear_screen(self):
        """Clear the terminal screen."""
        import os
        os.system('cls' if os.name == 'nt' else 'clear')
    
    def render_markdown(self, md: str) -> str:
        """Render markdown using rich console and return as string."""
        with self.console.capture() as capture:
            self.console.print(Markdown(md))
        return capture.get()
    
    def update_live_display(self, content: str):
        """Update the live markdown display with new content."""
        if content.strip():
            try:
                markdown = Markdown(content)
                if self._live_display is None:
                    self._live_display = Live(
                        markdown, 
                        console=self.console, 
                        refresh_per_second=4,
                        transient=False
                    )
                    self._live_display.start()
                else:
                    self._live_display.update(markdown)
                self._current_content = content
            except Exception:
                # Fallback to regular print if markdown parsing fails
                self.console.print(content, end="")
    
    def stop_live_display(self):
        """Stop the live display if it's active."""
        if self._live_display is not None:
            try:
                self._live_display.stop()
            except Exception:
                pass
            finally:
                self._live_display = None
    
    def show_banner(self, model: str, sdk: str, base_url: str, tool_count: int):
        """Display the welcome banner with rich formatting."""
        banner_content = [
            ("JARVIS 2.0", "bold cyan"),
            ("The professional AI engineering assistant", "dim"),
            ("", ""),
            (f"  Model:    {model}", "cyan"),
            (f"  SDK:      {sdk}", "cyan"),
            (f"  Base URL: {base_url or 'default'}", "cyan"),
            (f"  Tools:    {tool_count}", "cyan"),
            ("", "")
        ]
        
        for text, style in banner_content:
            self.console.print(text, style=style)
    
    def show_help(self):
        """Display available commands using rich table."""
        table = Table(title="Commands", show_header=True, header_style="bold cyan")
        table.add_column("Command", style="cyan", width=15)
        table.add_column("Description", style="white", width=40)
        
        commands = [
            ("/help", "Show this help"),
            ("/status", "Show system status"),
            ("/clear", "Clear the screen"),
            ("/exit", "Exit JARVIS"),
            ("! <cmd>", "Run shell command"),
        ]
        
        for cmd, desc in commands:
            table.add_row(cmd, desc)
        
        self.console.print(table)
        self.console.print("\nJust type your message and press Enter to chat with JARVIS.\n")
    
    def show_status(self, model: str, sdk: str, base_url: str, tool_count: int):
        """Display system status using rich panel."""
        status_text = f"""
Model:    {model}
SDK:      {sdk}
Base URL: {base_url or 'default'}
Tools:    {tool_count}
        """.strip()
        
        panel = Panel(
            status_text,
            title="Status",
            title_align="left",
            border_style="cyan"
        )
        self.console.print(panel)
    
    def show_tool_call(self, tool_name: str, tool_args: dict[str, Any]):
        """Display tool call with rich formatting."""
        import json
        
        try:
            args_json = json.dumps(tool_args, indent=2)
            panel = Panel(
                args_json,
                title=f"{tool_name}()",
                title_align="left",
                border_style="cyan bold",
                padding=(0, 1)
            )
            self.console.print(panel)
        except Exception:
            self.console.print(f"{tool_name}({tool_args})", style="cyan bold")
    
    def show_tool_result(self, result: Any, max_length: int = 2500):
        """Display tool result with truncation for large outputs."""
        if result and hasattr(result, 'success'):
            res_str = str(result.result) if result.success else f"Error: {result.error}"
        else:
            res_str = str(result)
        
        # Handle empty results
        if not res_str or res_str == "[]" or res_str == "{}":
            res_str = "(no content)"
        
        # Truncate large results
        if len(res_str) > max_length:
            res_str = res_str[:max_length] + f"\n... (large output truncated, {len(res_str)} total chars)"
        
        self.console.print(res_str, style="dim")
    
    def show_error(self, message: str, title: str = "Error"):
        """Display error message in a red panel."""
        panel = Panel(
            message,
            title=title,
            title_align="left",
            border_style="red bold",
            padding=(0, 1)
        )
        self.console.print(panel)
    
    def show_success(self, message: str, title: str = "Success"):
        """Display success message in a green panel."""
        panel = Panel(
            message,
            title=title,
            title_align="left",
            border_style="green bold",
            padding=(0, 1)
        )
        self.console.print(panel)
    
    def create_progress(self) -> Progress:
        """Create a rich progress bar."""
        return Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeElapsedColumn(),
            console=self.console
        )
    
    def create_tree(self, title: str) -> Tree:
        """Create a rich tree for hierarchical data."""
        return Tree(f"[bold cyan]{title}[/bold cyan]")
    
    def create_columns(self, *panels, equal: bool = True, expand: bool = True):
        """Create columns layout for multiple panels."""
        return Columns(list(panels), equal=equal, expand=expand)
    
    def show_rule(self, title: str = "", style: str = "cyan"):
        """Display a horizontal rule with optional title."""
        self.console.print(Rule(title, style=style))
    
    def show_separator(self):
        """Display a visual separator."""
        self.console.print()


class StreamingResponse:
    """Helper class to track streaming reasoning and response content."""
    
    def __init__(self):
        self.reasoning = ""
        self.content = ""
    
    def to_plain_text(self, display_manager: DisplayManager) -> str:
        """Return combined text representation using display manager."""
        parts = []
        if self.reasoning.strip():
            parts.append(f"[dim]{self.reasoning}[/dim]")
        if self.content.strip():
            if self.reasoning.strip():
                parts.append("")
            parts.append(display_manager.render_markdown(self.content))
        return "\n".join(parts) if parts else ""
