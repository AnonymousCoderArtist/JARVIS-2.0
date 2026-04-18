"""Command-line interface for JARVIS"""

import asyncio
import shlex
import sys
from typing import Any, Optional

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.text import Text
from rich.live import Live

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
        self.agent_coordinator: Optional[AgentCoordinator] = None
        self._current_provider_id: Optional[str] = None
        self._current_model_id: Optional[str] = None
        
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
        self.console.print()
        self.console.print(f"[bold cyan]JARVIS 2.0[/bold cyan] [dim]— The professional AI engineering assistant[/dim]")
        self.console.print(f"[dim]Provider:[/dim] [bold cyan]{self._current_provider_id or 'None'}[/bold cyan]   [dim]Model:[/dim] [bold cyan]{self._current_model_id or 'None'}[/bold cyan]   [dim]Tools:[/dim] [bold cyan]{len(self.tool_registry.list_tools())}[/bold cyan]")
        self.console.print()

    def _show_help(self):
        """Display available commands."""
        self.console.print("[dim]Commands: /help, /status, /clear, /exit, !<cmd>[/dim]")

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

        # Show user input
        self.console.print()
        self.console.print(f"[bold orange1]❯[/bold orange1] {text}")
        
        full_response = ""
        thinking = True
        response_started = False
        
        def stream_callback(chunk: str):
            nonlocal full_response, thinking, response_started
            if thinking:
                thinking = False
                self.console.print()  # End thinking line
            if not response_started:
                response_started = True
                self.console.print(f"[bold cyan]🤖[/bold cyan] ", end="")
            full_response += chunk
            self.console.print(chunk, end="")

        def tool_call_callback(tool_name: str, tool_args: dict):
            nonlocal thinking, response_started
            if thinking:
                thinking = False
                self.console.print()  # End thinking line
            if response_started:
                self.console.print()  # New line before tool call
            # Format tool args for display
            args_str = ", ".join(f"{k}={repr(v)}" for k, v in tool_args.items())
            self.console.print(f"[bold cyan]>[/bold cyan] [dim]{tool_name}({args_str})[/dim]")

        def tool_result_callback(tool_name: str, tool_args: dict, result: Any):
            if hasattr(result, "success") and not result.success:
                self.console.print(f"[red]❌ Tool Error: {result.error}[/red]")
            else:
                pass  # Success is implicit in the result

        self.agent_coordinator.stream_callback = stream_callback
        self.agent_coordinator.tool_call_callback = tool_call_callback
        self.agent_coordinator.tool_result_callback = tool_result_callback

        try:
            # Show thinking indicator
            self.console.print("[bold cyan]>[/bold cyan] [dim]Thinking...[/dim]", end="")
            
            await self.agent_coordinator.execute_task(text)
            
            # Ensure final newline if response was printed
            if response_started:
                self.console.print()
            elif thinking:
                # If still thinking, no response was generated
                self.console.print()
                
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
        if not command: return
        self.console.print(f"[dim]> {command}[/dim]")
        process = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        if stdout: self.console.print(stdout.decode())
        if stderr: self.console.print(stderr.decode(), style="red")

    async def run(self):
        """Start the CLI loop."""
        self._show_banner()
        self._show_help()
        
        while True:
            try:
                # Use standard input for now, could be upgraded to prompt_toolkit
                user_input = self.console.input("\n[bold orange1]❯[/bold orange1] ")
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
