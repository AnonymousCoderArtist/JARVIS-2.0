"""Command-line interface for JARVIS"""

import asyncio
import sys
from typing import Optional
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.markdown import Markdown
from rich.prompt import Prompt
from rich.text import Text
from core.config.settings import Settings
from core.llm_sdk.provider_registry import provider_registry
from core.llm_sdk.base.sdk import Message, GenerationConfig
from core.tools.registry import ToolRegistry
from core.tools.file_tools import FileReadTool, FileWriteTool, ListDirectoryTool, GlobTool
from core.tools.code_tools import BashTool, RunTestsTool
from core.tools.document_tools import ReadPDFTool
from core.tools.file_edit_tool import ReplaceTool
from core.tools.grep_tool import GrepSearchTool
from core.tools.powershell_tool import PowerShellTool
from core.tools.repl_tool import REPLTool
from core.tools.background_tools import ListBackgroundProcessesTool, ReadBackgroundOutputTool
from core.tools.web_tools import WebFetchTool
from core.tools.memory_tool import SaveMemoryTool
from core.tools.agent_tools import InvokeAgentTool, ActivateSkillTool
from core.agents.coding_agent import CodingAgent
from core.agents.knowledge_agent import KnowledgeAgent
from core.agents.coordinator import AgentCoordinator


class CLIInterface:
    """Command-line interface for JARVIS"""

    def __init__(self):
        self.console = Console()
        self.settings = Settings()
        self.provider_registry = provider_registry
        self.tool_registry = ToolRegistry()
        self.agent_coordinator = None
        self._initialize_providers()
        self._initialize_tools()
        self._initialize_agents()

    def _initialize_providers(self):
        """Initialize LLM providers from configuration using SDK registry"""
        providers_configured = 0

        # Get all known providers
        from core.llm_sdk.known_providers import KnownProviders

        for provider_id in KnownProviders.keys():
            api_key = self.settings.get_provider_api_key(provider_id)
            enabled = self.settings.is_provider_enabled(provider_id)

            if enabled and api_key:
                provider_config = self.provider_registry.get_provider_config(provider_id)
                if provider_config:
                    self.console.print(f"[green]✓[/green] {provider_id.capitalize()} provider registered")
                    providers_configured += 1

        # Check if any providers are configured
        if providers_configured == 0:
            self.console.print("[yellow]⚠[/yellow] Warning: No LLM providers configured. Please set API keys in config.toml")

    def _initialize_tools(self):
        """Initialize default tools"""
        # File tools
        self.tool_registry.register(FileReadTool())
        self.tool_registry.register(FileWriteTool())
        self.tool_registry.register(ReplaceTool())
        self.tool_registry.register(ListDirectoryTool())
        self.tool_registry.register(GlobTool())

        # Code tools
        self.tool_registry.register(BashTool())
        self.tool_registry.register(PowerShellTool())
        self.tool_registry.register(REPLTool())
        self.tool_registry.register(RunTestsTool())

        # Search tools
        self.tool_registry.register(GrepSearchTool())

        # Background tools
        self.tool_registry.register(ListBackgroundProcessesTool())
        self.tool_registry.register(ReadBackgroundOutputTool())

        # Web tools
        self.tool_registry.register(WebFetchTool())

        # Memory tools
        self.tool_registry.register(SaveMemoryTool())

        # Agent tools
        self.tool_registry.register(InvokeAgentTool())
        self.tool_registry.register(ActivateSkillTool())

        # Document tools
        self.tool_registry.register(ReadPDFTool())

        self.console.print(f"[green]✓[/green] {len(self.tool_registry.list_tools())} tools registered")

    def _initialize_agents(self):
        """Initialize agents with coordinator using SDK"""
        # Get selected provider
        default_provider_name = self.settings.selected_provider_id

        if not default_provider_name:
            self.console.print("[yellow]⚠[/yellow] Warning: No provider selected, skipping agent initialization")
            return

        # Get API key for selected provider
        api_key = self.settings.get_provider_api_key(default_provider_name)

        if not api_key:
            self.console.print(f"[yellow]⚠[/yellow] Warning: No API key configured for provider '{default_provider_name}'")
            return

        if not self.settings.is_provider_enabled(default_provider_name):
            self.console.print(f"[yellow]⚠[/yellow] Warning: Provider '{default_provider_name}' is not enabled")
            return

        default_sdk = self.provider_registry.get_sdk_instance(
            default_provider_name,
            api_key
        )

        if not default_sdk:
            self.console.print(f"[yellow]⚠[/yellow] Warning: Failed to get SDK instance for provider '{default_provider_name}'")
            return

        # Create adapter for SDK to work with existing agents
        from core.llm.sdk_adapter import SDKAdapter
        default_provider = SDKAdapter(default_sdk, default_provider_name)

        # Initialize agents
        agents = {}

        # Get selected model from config
        selected_model = self.settings.selected_model_id

        # Coding agent
        try:
            coding_agent = CodingAgent(default_provider, self.tool_registry, model=selected_model)
            agents["coding"] = coding_agent
            self.console.print("[green]✓[/green] Coding agent initialized")
        except Exception as e:
            self.console.print(f"[yellow]⚠[/yellow] Failed to initialize coding agent: {str(e)}")

        # Knowledge agent
        try:
            knowledge_agent = KnowledgeAgent(default_provider, self.tool_registry, model=selected_model)
            agents["knowledge"] = knowledge_agent
            self.console.print("[green]✓[/green] Knowledge agent initialized")
        except Exception as e:
            self.console.print(f"[yellow]⚠[/yellow] Failed to initialize knowledge agent: {str(e)}")

        # Initialize coordinator
        if agents:
            self.agent_coordinator = AgentCoordinator(agents, self.tool_registry)
            self.console.print("[green]✓[/green] Agent coordinator initialized")

    def _show_banner(self):
        """Display the application banner"""
        self.console.print(f"[bold cyan]JARVIS 2.0[/bold cyan] - [dim]v{self.settings.app_version}[/dim]\n")

    def _show_help(self):
        """Display help information"""
        self.console.print("[bold]Commands:[/bold]")
        self.console.print("  [cyan]help[/cyan] - Show this help")
        self.console.print("  [cyan]status[/cyan] - Show system status")
        self.console.print("  [cyan]providers[/cyan] - List configured LLM providers")
        self.console.print("  [cyan]tools[/cyan] - List available tools")
        self.console.print("  [cyan]exit/quit[/cyan] - Exit JARVIS")
        self.console.print()

    def _show_status(self):
        """Display system status"""
        self.console.print(f"[bold]Version:[/bold] {self.settings.app_version}")
        self.console.print(f"[bold]Provider:[/bold] {self.settings.selected_provider_id or 'None'}")
        self.console.print(f"[bold]Tools:[/bold] {len(self.tool_registry.list_tools())}")
        self.console.print()

    def _show_providers(self):
        """Display configured providers"""
        from core.config.provider_config import ProviderConfig
        provider_config = ProviderConfig(self.settings)
        enabled_providers = provider_config.list_enabled_providers()

        if not enabled_providers:
            self.console.print("[yellow]No providers configured[/yellow]\n")
            return

        for provider_id in enabled_providers:
            config = provider_config.get_provider_config(provider_id)
            if config:
                self.console.print(f"  [cyan]{config.get('display_name', provider_id)}[/cyan] ({provider_id})")
        self.console.print()

    def _show_tools(self):
        """Display available tools"""
        tools = self.tool_registry.list_tools()

        if not tools:
            self.console.print("[yellow]No tools registered[/yellow]\n")
            return

        for tool in tools:
            self.console.print(f"  [cyan]{tool['name']}[/cyan] - {tool['description']}")
        self.console.print()

    async def _process_command(self, user_input: str) -> Optional[str]:
        """Process a user command"""
        user_input = user_input.strip().lower()

        if user_input in ["exit", "quit"]:
            return "EXIT"
        elif user_input == "help":
            self._show_help()
        elif user_input == "status":
            self._show_status()
        elif user_input == "providers":
            self._show_providers()
        elif user_input == "tools":
            self._show_tools()
        else:
            # Process as a normal request
            return await self._process_request(user_input)

        return None

    async def _process_request(self, user_input: str) -> str:
        """Process a normal user request using the agent coordinator with streaming"""
        if not self.agent_coordinator:
            return "Error: Agent coordinator not initialized. Please configure an LLM provider."

        # Set up callbacks for streaming and tool calls
        full_response = ""

        def stream_callback(chunk: str):
            """Callback for streaming content"""
            nonlocal full_response
            full_response += chunk
            self.console.print(chunk, end="")

        def tool_call_callback(tool_name: str, tool_args: dict):
            """Callback for tool calls"""
            import json
            args_str = json.dumps(tool_args, indent=2)
            self.console.print()
            self.console.print(f"> {tool_name}({args_str})", style="cyan")
            self.console.print("... (tool output) ...", style="dim")
            self.console.print()

        # Set callbacks on coordinator
        self.agent_coordinator.stream_callback = stream_callback
        self.agent_coordinator.tool_call_callback = tool_call_callback

        try:
            response = await self.agent_coordinator.execute_task(user_input)
            return response
        except Exception as e:
            return f"Error processing request: {str(e)}"

    async def run(self):
        """Run the CLI interface"""
        self._show_banner()
        self._show_help()

        while True:
            try:
                user_input = Prompt.ask(
                    f"[bold cyan]JARVIS[/bold cyan] [dim]›[/dim]",
                    console=self.console
                )

                if not user_input.strip():
                    continue

                result = await self._process_command(user_input)

                if result == "EXIT":
                    self.console.print("\n[green]Goodbye! 👋[/green]\n")
                    break
                elif result:
                    # Only display response if it wasn't streamed
                    if not self.agent_coordinator.stream_callback:
                        self._display_response(result)
                    else:
                        self.console.print()  # Add newline after streaming

            except KeyboardInterrupt:
                self.console.print("\n\n[yellow]Interrupted. Type 'exit' to quit.[/yellow]")
            except Exception as e:
                self.console.print(f"\n[red]Error: {str(e)}[/red]\n")

    def _display_response(self, response: str):
        """Display response with markdown rendering and rich formatting"""
        # Check if response contains code blocks
        if "```" in response:
            # Render as markdown
            md = Markdown(response)
            response_panel = Panel(
                md,
                title="[bold]Response[/bold]",
                border_style="green",
                padding=(1, 2)
            )
            self.console.print(response_panel)
        else:
            # Display as text with panel
            response_panel = Panel(
                Text(response, style="green"),
                title="[bold]Response[/bold]",
                border_style="green",
                padding=(1, 2)
            )
            self.console.print(response_panel)
        self.console.print()


def main():
    """Main entry point"""
    cli = CLIInterface()
    asyncio.run(cli.run())


if __name__ == "__main__":
    main()
