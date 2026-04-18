"""Command-line interface for JARVIS"""

import asyncio
import json
import shlex
import sys
from typing import Any

from rich.console import Console
from rich.markdown import Markdown

from core.agents.base import BaseAgent
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
        self.console = Console(markup=True, emoji=False)
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

        agents: dict[str, BaseAgent] = {
            "coding": CodingAgent(provider, self.tool_registry, model=active_model),
            "knowledge": KnowledgeAgent(provider, self.tool_registry, model=active_model),
        }

        self.agent_coordinator = AgentCoordinator(agents, self.tool_registry, model=active_model)
        self._current_provider_id = provider_id
        self._current_model_id = active_model

    def _md(self, text: str):
        """Render markdown text."""
        self.console.print(Markdown(text))

    def _sep(self, char: str = "-", style: str = "dim"):
        """Print a separator line."""
        width = self.console.width or 80
        self.console.print(f"[{style}]{char * width}[/{style}]")

    def _show_banner(self):
        """Display the welcome banner."""
        self.console.print()
        self.console.print("[bold cyan]JARVIS 2.0[/bold cyan]")
        self.console.print("[dim]The professional AI engineering assistant[/dim]")
        self.console.print()
        self.console.print(f"  [cyan]Provider:[/cyan] {self._current_provider_id or 'not configured'}")
        self.console.print(f"  [cyan]Model:[/cyan]    {self._current_model_id or 'not configured'}")
        self.console.print(f"  [cyan]Tools:[/cyan]    {len(self.tool_registry.list_tools())}")
        self._sep()
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

    def _tool_call_md(self, tool_name: str, tool_args: dict[str, Any]) -> str:
        """Build markdown for a tool call."""
        args_lines = []
        for k, v in tool_args.items():
            if isinstance(v, str):
                display_v = v[:100] + "..." if len(v) > 100 else v
                args_lines.append(f'  {k}="{display_v}"')
            else:
                args_lines.append(f"  {k}={v!r}")

        if args_lines:
            args_text = ",\n".join(args_lines)
            return f"**tool call:** `{tool_name}({args_text})`"
        return f"**tool call:** `{tool_name}()`"

    def _tool_result_md(self, tool_name: str, result: Any) -> str:
        """Build markdown for a tool result."""
        success = getattr(result, "success", True)
        error = getattr(result, "error", None)

        if not success:
            return f"**error:** {error or 'Tool failed'}"

        payload = getattr(result, "result", "")
        metadata = getattr(result, "metadata", None) or {}

        # Check for diff
        if isinstance(payload, str) and payload.strip().startswith("diff --git"):
            return f"**{tool_name}:**\n\n```diff\n{payload}\n```"

        results = metadata.get("results") if isinstance(metadata, dict) else None
        if isinstance(results, list) and results:
            diff_text = results[0].get("unified_diff") or results[0].get("diff")
            if isinstance(diff_text, str) and diff_text:
                return f"**{tool_name}:**\n\n```diff\n{diff_text}\n```"

        # Truncate long output
        if isinstance(payload, str) and len(payload) > 500:
            payload = payload[:500] + "\n... (truncated)"

        # Detect language
        if isinstance(payload, str):
            stripped = payload.strip()
            if stripped.startswith("{") or stripped.startswith("["):
                try:
                    json.loads(stripped)
                    return f"**{tool_name}:**\n\n```json\n{payload}\n```"
                except (json.JSONDecodeError, ValueError):
                    pass

            if any(kw in payload for kw in ["def ", "import ", "class "]) and "\n" in payload:
                return f"**{tool_name}:**\n\n```python\n{payload}\n```"

        if isinstance(payload, str) and ("#" in payload or "**" in payload or "`" in payload):
            return f"**{tool_name}:**\n\n{payload}"

        return f"**{tool_name}:** {payload or 'Done'}"

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

        # User message
        self.console.print()
        self._sep("-", "orange1")
        self.console.print("[bold orange1]You[/bold orange1]")
        self._md(text)
        self.console.print()

        # JARVIS header
        self._sep("-", "cyan")
        self.console.print("[bold cyan]JARVIS[/bold cyan]")
        self.console.print()

        full_response = ""
        response_started = False

        def stream_callback(chunk: str):
            nonlocal full_response, response_started
            full_response += chunk
            # Print a dot to show progress during streaming
            if not response_started:
                self.console.print("[dim]...[/dim]", end="")
                response_started = True

        def tool_call_callback(tool_name: str, tool_args: dict[str, Any]):
            nonlocal full_response
            # Render accumulated response before tool call
            if full_response.strip():
                self.console.print()
                self._md(full_response)
                full_response = ""
            self.console.print()
            self._md(self._tool_call_md(tool_name, tool_args))
            self.console.print()

        def tool_result_callback(tool_name: str, tool_args: dict[str, Any], result: Any):
            self._md(self._tool_result_md(tool_name, result))
            self.console.print()

        self.agent_coordinator.stream_callback = stream_callback
        self.agent_coordinator.tool_call_callback = tool_call_callback
        self.agent_coordinator.tool_result_callback = tool_result_callback

        try:
            await self.agent_coordinator.execute_task(text)
            # Render final response as markdown
            if full_response.strip():
                self.console.print()
                self._md(full_response)
            elif not response_started:
                self.console.print("[dim](no response)[/dim]")
        except Exception as e:
            self.console.print(f"\n[red]Error: {e}[/red]")

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
            self._sep()
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
        self._sep("-", "dim")
        self.console.print(f"[dim]shell[/dim]")
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
                user_input = self.console.input("[bold orange1]YOU[/bold orange1] [dim]>[/dim] ")
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
