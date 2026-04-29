"""Command-line interface for JARVIS"""

import asyncio
import json
import shlex
import sys
from typing import Any

from rich.console import Console
from rich.markdown import Markdown
from rich.live import Live

from core.agents.base import BaseAgent
from core.agents.coding_agent import CodingAgent
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
        self.console = Console(markup=True, emoji=False)
        self.settings = Settings()
        self.provider_registry = provider_registry
        self.tool_registry = ToolRegistry()
        self.jarvis_agent: CodingAgent | None = None
        self._current_provider_id: str | None = None
        self._current_model_id: str | None = None

        self._initialize_systems()

    def _initialize_systems(self):
        self._initialize_tools()
        self._initialize_agents()

    def _initialize_tools(self):
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
        provider_id = self.settings.selected_provider_id
        if not provider_id or not self.settings.is_provider_enabled(provider_id):
            return

        api_key = self.settings.get_provider_api_key(provider_id)
        sdk = self.provider_registry.get_sdk_instance(provider_id, api_key)
        if not sdk:
            return

        active_model = self.settings.selected_model_id or "gpt-4o"
        provider = SDKAdapter(sdk, provider_id)

        self.jarvis_agent = CodingAgent(provider, self.tool_registry, model=active_model)
        
        # Rebuild agent prompt with dynamic tool descriptions
        self.jarvis_agent.rebuild_system_prompt()
        
        self._current_provider_id = provider_id
        self._current_model_id = active_model

    def _md(self, text: str):
        """Render markdown text."""
        self.console.print(Markdown(text))

    def _show_banner(self):
        """Display the welcome banner."""
        self.console.print()
        self.console.print("[bold cyan]JARVIS 2.0[/bold cyan]")
        self.console.print("[dim]The professional AI engineering assistant[/dim]")
        self.console.print()
        self.console.print(f"  [cyan]Provider:[/cyan] {self._current_provider_id or 'not configured'}")
        self.console.print(f"  [cyan]Model:[/cyan]    {self._current_model_id or 'not configured'}")
        self.console.print(f"  [cyan]Tools:[/cyan]    {len(self.tool_registry.list_tools())}")
        self.console.print()

    def _show_help(self):
        """Display available commands."""
        self._md(
            "### Commands\n"
            "- `/help` - Show this help\n"
            "- `/status` - Show system status\n"
            "- `/clear` - Clear the screen\n"
            "- `/exit` - Exit JARVIS\n"
            "- `! <cmd>` - Run shell command\n\n"
            "Just type your message and press Enter to chat with JARVIS."
        )
        self.console.print()



    async def _handle_submit(self, text: str):
        """Process user input."""
        if text.startswith("/"):
            await self._handle_command(text)
            return

        if text.startswith("!"):
            await self._run_shell_command(text[1:].strip())
            return

        if not self.jarvis_agent:
            self.console.print("[red]Error: JARVIS agent not initialized.[/red]")
            return

        # User message (prompt already shows 'YOU >')
        # Do not re-print the user's input to avoid echoing it in the transcript.
        self.console.print()
        self.console.print()

        # Streaming setup
        full_response = ""
        response_started = False
        live_ref = [None]  # Store Live reference in mutable container

        def stream_callback(chunk: str):
            nonlocal full_response, response_started, live_ref
            full_response += chunk
            if not response_started:
                response_started = True
            # Update the live display with the streaming content
            if live_ref[0] and full_response.strip():
                live_ref[0].update(Markdown(full_response))

        def tool_call_callback(tool_name: str, tool_args: dict[str, Any]):
            nonlocal full_response
            # No-op - don't display tool calls

        def tool_result_callback(tool_name: str, tool_args: dict[str, Any], result: Any):
            # No-op - don't display tool results
            pass

        self.jarvis_agent.stream_callback = stream_callback
        self.jarvis_agent.tool_call_callback = tool_call_callback
        self.jarvis_agent.tool_result_callback = tool_result_callback

        # Use Live display for streaming (without spinner)
        with Live("", refresh_per_second=10) as live:
            live_ref[0] = live
            try:
                await self.jarvis_agent.process(text)
            except Exception as e:
                self.console.print(f"\n[red]Error: {e}[/red]")
                return

        # Response already displayed via Live streaming
        # Just add spacing after the response
        if not response_started:
            self.console.print("[dim](no response)[/dim]")

        self.console.print()

    async def _handle_command(self, text: str):
        parts = shlex.split(text)
        cmd = parts[0].lstrip("/").lower()

        if cmd == "help":
            self._show_help()
        elif cmd == "clear":
            self.console.clear()
            self._show_banner()
            self._show_help()
        elif cmd == "status":
            tool_count = len(self.tool_registry.list_tools())
            self.console.print()
            self.console.print("[bold cyan]Status[/bold cyan]")
            self.console.print(f"  [cyan]Provider:[/cyan] {self._current_provider_id or 'none'}")
            self.console.print(f"  [cyan]Model:[/cyan]    {self._current_model_id or 'none'}")
            self.console.print(f"  [cyan]Tools:[/cyan]    {tool_count}")
            self.console.print()
        elif cmd in ["exit", "quit"]:
            self.console.print("[green]Goodbye![/green]")
            sys.exit(0)
        else:
            self.console.print(f"[red]Unknown command: {cmd}[/red]")

    async def _run_shell_command(self, command: str):
        if not command:
            return
        self.console.print()
        self.console.print("[dim]shell[/dim]")
        self.console.print(f"[dim]$ {command}[/dim]")
        self.console.print()
        process = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        if stdout:
            output = stdout.decode()
            if output.strip():
                self.console.print(output)
        if stderr:
            self.console.print()
            self.console.print("[bold red]stderr[/bold red]")
            self.console.print(f"[red]{stderr.decode()}[/red]")
        self.console.print()

    async def run(self):
        """Start the CLI loop."""
        self.console.clear()
        self._show_banner()
        self._show_help()

        while True:
            try:
                # Print prompt separately to avoid double-printing
                self.console.print("[bold orange1]YOU[/bold orange1] [dim]>[/dim] ", end="")
                user_input = input()
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
