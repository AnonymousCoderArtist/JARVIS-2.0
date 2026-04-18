"""Command-line interface for JARVIS"""

import asyncio
import shlex
import sys
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from core.agents.coding_agent import CodingAgent
from core.agents.coordinator import AgentCoordinator
from core.agents.knowledge_agent import KnowledgeAgent
from core.config.settings import Settings
from core.llm.sdk_adapter import SDKAdapter
from core.llm_sdk.provider_registry import provider_registry
from core.tools.agent_tools import ActivateSkillTool, InvokeAgentTool
from core.tools.background_tools import ListBackgroundProcessesTool, ReadBackgroundOutputTool
from core.tools.code_tools import BashTool, RunTestsTool
from core.tools.document_tools import ReadPDFTool
from core.tools.file_edit_tool import ReplaceTool
from core.tools.file_tools import FileReadTool, FileWriteTool, GlobTool, ListDirectoryTool
from core.tools.grep_tool import GrepSearchTool
from core.tools.memory_tool import SaveMemoryTool
from core.tools.powershell_tool import PowerShellTool
from core.tools.registry import ToolRegistry
from core.tools.repl_tool import REPLTool
from core.tools.web_tools import WebFetchTool


class CLIInterface:
    """Enhanced CLI interface for JARVIS."""

    def __init__(self):
        self.console = Console()
        self.settings = Settings()
        self.provider_registry = provider_registry
        self.tool_registry = ToolRegistry()
        self.agent_coordinator: AgentCoordinator | None = None
        self._current_provider_id: str | None = None
        self._current_model_id: str | None = None

        self._initialize_systems()

    def _initialize_systems(self):
        """Initialize all components."""
        self._initialize_tools()
        self._initialize_agents()

    def _initialize_tools(self):
        """Register all available tools."""
        self.tool_registry.register(FileReadTool())
        self.tool_registry.register(FileWriteTool())
        self.tool_registry.register(ReplaceTool())
        self.tool_registry.register(ListDirectoryTool())
        self.tool_registry.register(GlobTool())
        self.tool_registry.register(BashTool())
        self.tool_registry.register(PowerShellTool())
        self.tool_registry.register(REPLTool())
        self.tool_registry.register(RunTestsTool())
        self.tool_registry.register(GrepSearchTool())
        self.tool_registry.register(ListBackgroundProcessesTool())
        self.tool_registry.register(ReadBackgroundOutputTool())
        self.tool_registry.register(WebFetchTool())
        self.tool_registry.register(SaveMemoryTool())
        self.tool_registry.register(InvokeAgentTool())
        self.tool_registry.register(ActivateSkillTool())
        self.tool_registry.register(ReadPDFTool())

    def _initialize_agents(self):
        """Initialize LLM providers and agents."""
        provider_id = self.settings.selected_provider_id
        if not provider_id or not self.settings.is_provider_enabled(provider_id):
            return

        api_key = self.settings.get_provider_api_key(provider_id)
        sdk = self.provider_registry.get_sdk_instance(provider_id, api_key)
        if not sdk:
            return

        active_model = self.settings.selected_model_id or "gpt-4o"
        provider = SDKAdapter(sdk, provider_id)

        agents = {
            "coding": CodingAgent(provider, self.tool_registry, model=active_model),
            "knowledge": KnowledgeAgent(provider, self.tool_registry, model=active_model),
        }

        self.agent_coordinator = AgentCoordinator(agents, self.tool_registry, model=active_model)
        self._current_provider_id = provider_id
        self._current_model_id = active_model

    def _show_banner(self):
        """Display the welcome banner."""
        self.console.print(Panel(
            Text.from_markup(f"[bold cyan]JARVIS 2.0[/bold cyan]\n[dim]The professional AI engineering assistant[/dim]\n\n[cyan]Provider:[/cyan] {self._current_provider_id or 'None'}\n[cyan]Model:[/cyan] {self._current_model_id or 'None'}\n[cyan]Tools:[/cyan] {len(self.tool_registry.list_tools())}"),
            border_style="cyan",
            padding=(1, 2)
        ))

    def _show_help(self):
        """Display available commands."""
        help_text = """
[bold cyan]Commands:[/bold cyan]
  [bold white]/help[/bold white]       - Show this help
  [bold white]/status[/bold white]     - Show system status
  [bold white]/clear[/bold white]      - Clear the screen
  [bold white]/exit[/bold white]       - Exit JARVIS
  [bold white]! <cmd>[/bold white]     - Run shell command
"""
        self.console.print(help_text)

    async def _handle_submit(self, text: str):
        """Process user input."""
        if text.startswith("/"):
            await self._handle_command(text)
            return

        if text.startswith("!"):
            await self._run_shell_command(text[1:].strip())
            return

        if not self.agent_coordinator:
            self.console.print("[red]Error: Agent coordinator not initialized.[/red]")
            return

        # Set up callbacks for streaming
        self.console.print("\n[bold cyan]JARVIS[/bold cyan] › ", end="")

        full_response = ""

        def stream_callback(chunk: str):
            nonlocal full_response
            full_response += chunk
            self.console.print(chunk, end="")

        def tool_call_callback(tool_name: str, tool_args: dict):
            # Format tool call like: grep(pattern="TODO", path=".")
            args_str = ", ".join(f'{k}="{v}"' if isinstance(v, str) else f'{k}={v}' for k, v in tool_args.items())
            self.console.print(f"\n[dim]{tool_name}({args_str})[/dim]")

        def tool_result_callback(tool_name: str, tool_args: dict, result: Any):
            if hasattr(result, "success") and not result.success:
                self.console.print(f"[red]❌ Tool Error: {result.error}[/red]")
            else:
                self.console.print("[green]✅ Success[/green]")

        self.agent_coordinator.stream_callback = stream_callback
        self.agent_coordinator.tool_call_callback = tool_call_callback
        self.agent_coordinator.tool_result_callback = tool_result_callback

        try:
            await self.agent_coordinator.execute_task(text)
            self.console.print() # Final newline
        except Exception as e:
            self.console.print(f"\n[red]Error: {e}[/red]")

    async def _handle_command(self, text: str):
        parts = shlex.split(text)
        cmd = parts[0].lstrip("/").lower()

        if cmd == "help":
            self._show_help()
        elif cmd == "clear":
            self.console.clear()
            self._show_banner()
        elif cmd == "status":
            self.console.print(f"[cyan]Provider:[/cyan] {self._current_provider_id}")
            self.console.print(f"[cyan]Model:[/cyan] {self._current_model_id}")
        elif cmd in ["exit", "quit"]:
            self.console.print("[green]Goodbye![/green]")
            sys.exit(0)
        else:
            self.console.print(f"[red]Unknown command: {cmd}[/red]")

    async def _run_shell_command(self, command: str):
        if not command:
            return
        self.console.print(f"[dim]> {command}[/dim]")
        process = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        if stdout:
            self.console.print(stdout.decode())
        if stderr:
            self.console.print(stderr.decode(), style="red")

    async def run(self):
        """Start the CLI loop."""
        self.console.clear()
        self._show_banner()
        self._show_help()

        while True:
            try:
                # Use standard input for now, could be upgraded to prompt_toolkit
                user_input = self.console.input("\n[bold orange1]YOU[/bold orange1] [dim]›[/dim] ")
                if not user_input.strip():
                    continue
                await self._handle_submit(user_input)
            except (KeyboardInterrupt, EOFError):
                self.console.print("\n[green]Goodbye![/green]")
                break
            except Exception as e:
                self.console.print(f"\n[red]Fatal Error: {e}[/red]")

def main():
    cli = CLIInterface()
    asyncio.run(cli.run())

if __name__ == "__main__":
    main()
