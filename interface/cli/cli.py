"""Command-line interface for JARVIS"""

import asyncio
import shlex
import sys
from typing import Any

from rich.console import Console
from rich.markdown import Markdown
from rich.live import Live

from core.agents.base import BaseAgent
from core.agents.coding_agent import CodingAgent
from core.llm.sdk_adapter import SDKAdapter
from core.llm_sdk.anthropic.sdk import AnthropicSDK
from core.llm_sdk.openai.sdk import OpenAISDK
from core.tools.agent_tools import ActivateSkillTool, InvokeAgentTool
from core.tools.background_tools import ListBackgroundProcessesTool, ReadBackgroundOutputTool
from core.tools.code_tools import BashTool, RunTestsTool
from core.tools.file_edit_tool import EditTool
from core.tools.file_tools import FileReadTool, FileWriteTool, GlobTool, ListDirectoryTool
from core.tools.grep_tool import GrepSearchTool
from core.tools.memory_tool import SaveMemoryTool
from core.tools.registry import ToolRegistry
from core.tools.repl_tool import REPLTool
from core.tools.web_tools import WebFetchTool


class CLIInterface:
    """Enhanced CLI interface for JARVIS."""

    def __init__(self, model: str, base_url: str | None, apikey: str | None, sdk: str):
        self.console = Console(markup=True, emoji=False)
        self.model = model
        self.base_url = base_url
        self.apikey = apikey
        self.sdk = sdk
        self.tool_registry = ToolRegistry()
        self.jarvis_agent: CodingAgent | None = None
        self._current_provider = None

        self._initialize_systems()

    def _initialize_systems(self):
        self._initialize_tools()
        self._initialize_agents()
        # Update tool registry with provider after agent initialization
        if self._current_provider:
            self.tool_registry.llm_provider = self._current_provider
            self.tool_registry.model = self.model
            # Re-register tools to inject the provider references
            self._reinitialize_tools()

    def _initialize_tools(self):
        self.tool_registry.register(FileReadTool())
        self.tool_registry.register(FileWriteTool())
        self.tool_registry.register(EditTool())
        self.tool_registry.register(ListDirectoryTool())
        self.tool_registry.register(GlobTool())
        self.tool_registry.register(BashTool())
        self.tool_registry.register(REPLTool())
        self.tool_registry.register(RunTestsTool())
        self.tool_registry.register(GrepSearchTool())
        self.tool_registry.register(ListBackgroundProcessesTool())
        self.tool_registry.register(ReadBackgroundOutputTool())
        self.tool_registry.register(WebFetchTool())
        self.tool_registry.register(SaveMemoryTool())
        self.tool_registry.register(InvokeAgentTool())
        self.tool_registry.register(ActivateSkillTool())

    def _reinitialize_tools(self):
        """Re-register tools with provider references"""
        # Clear existing tools
        self.tool_registry._tools.clear()

        # Re-register with provider references
        self.tool_registry.register(FileReadTool())
        self.tool_registry.register(FileWriteTool())
        self.tool_registry.register(EditTool())
        self.tool_registry.register(ListDirectoryTool())
        self.tool_registry.register(GlobTool())
        self.tool_registry.register(BashTool())
        self.tool_registry.register(REPLTool())
        self.tool_registry.register(RunTestsTool())
        self.tool_registry.register(GrepSearchTool())
        self.tool_registry.register(ListBackgroundProcessesTool())
        self.tool_registry.register(ReadBackgroundOutputTool())
        self.tool_registry.register(WebFetchTool())
        self.tool_registry.register(SaveMemoryTool())
        self.tool_registry.register(InvokeAgentTool())
        self.tool_registry.register(ActivateSkillTool())

    def _initialize_agents(self):
        # Create SDK instance based on CLI parameters
        if self.sdk == "anthropic":
            sdk = AnthropicSDK(api_key=self.apikey or "", base_url=self.base_url)
        elif self.sdk == "openai":
            sdk = OpenAISDK(api_key=self.apikey or "", base_url=self.base_url)
        else:
            # Default to OpenAI SDK for standard mode
            sdk = OpenAISDK(api_key=self.apikey or "", base_url=self.base_url)

        provider = SDKAdapter(sdk, "cli-provider")

        # Store provider reference for tool registry
        self._current_provider = provider

        self.jarvis_agent = CodingAgent(provider, self.tool_registry, model=self.model)

    def _md(self, text: str):
        """Render markdown text."""
        self.console.print(Markdown(text))

    def _show_banner(self):
        """Display the welcome banner."""
        self.console.print()
        self.console.print("[bold cyan]JARVIS 2.0[/bold cyan]")
        self.console.print("[dim]The professional AI engineering assistant[/dim]")
        self.console.print()
        self.console.print(f"  [cyan]Model:[/cyan]    {self.model}")
        self.console.print(f"  [cyan]SDK:[/cyan]      {self.sdk}")
        self.console.print(f"  [cyan]Base URL:[/cyan] {self.base_url or 'default'}")
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

        # Streaming setup
        full_response = ""
        response_started = False
        live_ref = [None]  # Store Live reference in mutable container
        in_tool_call = [False]  # Track if we're in a tool call

        def stream_callback(chunk: str):
            nonlocal full_response, response_started, live_ref, in_tool_call
            # Don't accumulate during tool calls
            if in_tool_call[0]:
                return
            
            full_response += chunk
            if not response_started:
                response_started = True
            # Update the live display with the streaming content
            if live_ref[0] and full_response.strip():
                live_ref[0].update(Markdown(full_response))

        def tool_call_callback(tool_name: str, tool_args: dict[str, Any]):
            nonlocal full_response, live_ref, in_tool_call
            in_tool_call[0] = True
            
            # Print any accumulated response before tool call
            if full_response.strip():
                # Stop Live display temporarily
                if live_ref[0]:
                    live_ref[0].stop()
                    live_ref[0] = None
                self.console.print(Markdown(full_response))
                full_response = ""  # Reset after printing
            
            # Format tool call as multi-line function call
            args_lines = []
            for k, v in tool_args.items():
                args_lines.append(f'  {k}="{v}"')
            args_str = ",\n".join(args_lines)
            tool_call_str = f"{tool_name}(\n{args_str}\n)"
            
            # Display tool call in code block
            self.console.print()
            self.console.print(Markdown(f"```python\n{tool_call_str}\n```"))

        def tool_result_callback(tool_name: str, tool_args: dict[str, Any], result: Any):
            nonlocal in_tool_call
            # Display tool result with truncation
            if result and hasattr(result, 'success'):
                if result.success:
                    result_str = str(result.result) if result.result else "Success"
                else:
                    result_str = result.error if result.error else "Failed"
            else:
                result_str = str(result) if result else "No result"
            
            # Truncate result if too long
            max_length = 800
            if len(result_str) > max_length:
                result_str = result_str[:max_length] + "... (truncated)"
            
            # Display result as dim text outside code block
            self.console.print(f"[dim]{result_str}[/dim]")
            self.console.print()
            
            # Done with tool call
            in_tool_call[0] = False

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

        # Don't print remaining content - Live display already showed it during streaming
        # This prevents duplicate output
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
            self.console.print(f"  [cyan]Model:[/cyan]    {self.model}")
            self.console.print(f"  [cyan]SDK:[/cyan]      {self.sdk}")
            self.console.print(f"  [cyan]Base URL:[/cyan] {self.base_url or 'default'}")
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

def main(launch_cli: bool = True, model: str = "gpt-4o", base_url: str | None = None, apikey: str | None = None, sdk: str = "openai"):
    """Main CLI entry point."""
    if not launch_cli:
        print("Error: CLI mode not enabled. Use --cli flag.")
        sys.exit(1)
    
    cli = CLIInterface(model=model, base_url=base_url, apikey=apikey, sdk=sdk)
    asyncio.run(cli.run())

if __name__ == "__main__":
    main()
