"""Modern command-line interface for JARVIS with rich display and modular architecture."""

import asyncio
import json
import sys
from pathlib import Path
from typing import Any, Optional

from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.styles import Style
from prompt_toolkit.lexers import PygmentsLexer
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.output import DummyOutput
from prompt_toolkit.application import get_app
from prompt_toolkit.formatted_text import HTML
from pygments.lexers.python import PythonLexer
from pygments.lexers.shell import BashLexer
from pygments.lexers.markup import MarkdownLexer
from rich.markdown import Markdown

from core.agents.coding_agent import CodingAgent
from core.agents.manager import AgentManager
from core.agents.async_manager import AsyncAgentManager, AsyncAgentConfig
from core.config.settings import Settings
from core.llm.sdk_adapter import SDKAdapter
from core.llm_sdk.anthropic.sdk import AnthropicSDK
from core.llm_sdk.openai.sdk import OpenAISDK
from core.skills.manager import SkillManager
from core.tools.agent_tools import ActivateSkillTool, InvokeAgentTool
from core.tools.background_tools import ListBackgroundProcessesTool, ReadBackgroundOutputTool
from core.tools.code_tools import BashTool, RunTestsTool
from core.tools.file_edit_tool import EditTool
from core.tools.file_tools import FileReadTool, FileWriteTool, GlobTool, ListDirectoryTool
from core.tools.grep_tool import GrepSearchTool
from core.tools.memory_tool import SaveMemoryTool, ReadMemoryTool
from core.tools.registry import ToolRegistry
from core.tools.async_registry import AsyncToolRegistry
from core.tools.repl_tool import REPLTool
from core.tools.web_tools import WebFetchTool

from .display import DisplayManager, StreamingResponse
from .commands import CommandHandler
from .config import ConfigManager, load_config
from .keybindings import create_key_bindings


class CommandCompleter(Completer):
    """Completer for CLI commands and file paths."""

    def __init__(self, command_handler: CommandHandler, tool_registry=None):
        self.command_handler = command_handler
        self.tool_registry = tool_registry

    def get_completions(self, document, complete_event):
        text = document.get_word_before_cursor()

        # Command completion (slash commands)
        if text.startswith('/'):
            for cmd_name, cmd in self.command_handler.command_registry.commands.items():
                if cmd_name.startswith(text[1:]):
                    yield Completion(f'/{cmd_name}', start_position=-len(text[1:]))
        # File path completion (after certain triggers)
        elif text.startswith('~') or '/' in text or '\\' in text:
            import os
            base_path = text
            if '/' in text:
                base_path = text[:text.rfind('/') + 1]
                prefix = text[text.rfind('/') + 1:]
            else:
                base_path = './'
                prefix = text

            try:
                for item in os.listdir(base_path):
                    if item.startswith(prefix):
                        yield Completion(item, start_position=-len(prefix))
            except (FileNotFoundError, PermissionError):
                pass




class DynamicLexer:
    """Dynamic lexer that switches based on input type."""

    def __init__(self, command_handler: CommandHandler):
        self.command_handler = command_handler

    def _get_lexer_for_text(self, text: str):
        """Determine which lexer to use based on text content."""
        text_lower = text.lower().strip()

        if text_lower.startswith('python') or 'def ' in text or 'class ' in text:
            return PygmentsLexer(PythonLexer)
        elif text_lower.startswith('!') or 'cd ' in text or 'ls ' in text or 'bash ' in text:
            return PygmentsLexer(BashLexer)
        elif '#' in text or '**' in text or '##' in text:
            return PygmentsLexer(MarkdownLexer)
        return None

    def lex_document(self, document):
        """Return a function that lexes a document."""
        lexer = self._get_lexer_for_text(document.text)
        if lexer:
            return lexer.lex_document(document)
        # Return a no-op lexer function
        return lambda i: []

    def __call__(self, document, _):
        """Make this callable for compatibility."""
        return self._get_lexer_for_text(document.text)


class CLIInterface:
    """Modern CLI interface for JARVIS with rich display and modular architecture."""

    def __init__(self, model: str, base_url: str | None, apikey: str | None, sdk: str, bypass: bool = True):
        self.model = model
        self.base_url = base_url
        self.apikey = apikey
        self.sdk = sdk
        self.bypass = bypass
        self.tool_registry = AsyncToolRegistry()
        self.jarvis_agent: CodingAgent | None = None
        self._current_provider = None

        # Initialize modular components
        self.config_manager = load_config()
        self.display_manager = DisplayManager(
            theme=self.config_manager.config.display.theme,
            width=self.config_manager.config.display.width
        )
        self.command_handler = CommandHandler(self.display_manager)

        # Prompt toolkit setup
        history_path = Path.home() / ".jarvis_history"

        # Handle terminal compatibility
        output = None
        try:
            import os
            if 'xterm' in os.environ.get('TERM', '') or 'WSL' in os.environ.get('OSTYPE', ''):
                output = DummyOutput()
        except Exception:
            pass

        self.session = PromptSession(history=FileHistory(str(history_path)), output=output)
        self.style = Style.from_dict({
            'prompt': f'bold {self.display_manager.theme["prompt"]}',
            'arrow': self.display_manager.theme["arrow"],
        })

        # Setup key bindings
        self.key_bindings = create_key_bindings(self.config_manager, self.display_manager)

        # Completer for tab completion
        self.completer = CommandCompleter(self.command_handler, self.tool_registry)

        # Dynamic lexer for syntax highlighting
        self.dynamic_lexer = DynamicLexer(self.command_handler)

        self._initialize_systems()

    def _initialize_systems(self):
        self._initialize_tools()
        self._initialize_agents()
        # Update tool registry with provider after agent initialization
        if self._current_provider:
            self.tool_registry.update_tool_providers(
                llm_provider=self._current_provider,
                model=self.model
            )

    def _initialize_tools(self):
        """Register all tools with the tool registry."""
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
        self.tool_registry.register(ReadMemoryTool())
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

        # Initialize settings and managers
        settings = Settings()
        self.agent_manager = AgentManager(
            config_getter=lambda: settings,
            initial_agent="default"
        )
        self.skill_manager = SkillManager()

        # Initialize async agent manager for concurrent operations (optional)
        settings = Settings()
        async_config = AsyncAgentConfig(
            max_concurrent_agents=settings.max_concurrent_agents,
            max_concurrent_tools=settings.max_concurrent_tools,
            default_timeout=settings.default_timeout,
            enable_background_tasks=settings.enable_background_tasks,
            resource_monitoring=settings.resource_monitoring,
            progress_updates=settings.progress_updates
        )
        self.async_agent_manager = AsyncAgentManager(async_config)

        # Create agent with profile config getter and concurrent tools enabled
        self.jarvis_agent = CodingAgent(
            provider,
            self.tool_registry,
            model=self.model,
            config_getter=lambda: self.agent_manager.config,
            bypass_tool_permissions=self.bypass,
            use_concurrent_tools=True
        )

        # Set bypass mode on agent
        if self.bypass:
            self.jarvis_agent.bypass_tool_permissions = True

        # Update command handler with managers for new commands
        self.command_handler.set_managers(
            agent_manager=self.agent_manager,
            tool_registry=self.tool_registry,
            skill_manager=self.skill_manager,
            jarvis_agent=self.jarvis_agent
        )

        # Update command handler with current status info
        self.command_handler.update_status_info(
            model=self.model,
            sdk=self.sdk,
            base_url=self.base_url or "",
            tool_count=len(self.tool_registry.list_tools())
        )

    def _show_banner(self):
        """Display the welcome banner."""
        self.display_manager.show_banner(
            model=self.model,
            sdk=self.sdk,
            base_url=self.base_url or "",
            tool_count=len(self.tool_registry.list_tools())
        )
    
    def _show_help(self):
        """Display available commands."""
        self.display_manager.show_help()

    async def _handle_submit(self, text: str):
        """Process user input with streaming output."""
        # Handle commands and shell input first
        if await self.command_handler.handle_input(text):
            return

        if not self.jarvis_agent:
            self.display_manager.show_error("JARVIS agent not initialized.")
            return

        print()

        # State tracking for chat responses
        in_tool_call = [False]

        def stream_callback(chunk: str):
            if in_tool_call[0]:
                return
            # Stream content in real-time for immediate feedback
            # Write directly to stdout to avoid Rich's processing which may add newlines
            import sys
            sys.stdout.write(chunk)
            sys.stdout.flush()

        def reasoning_callback(chunk: str):
            if in_tool_call[0]:
                return
            # Stream reasoning in real-time
            import sys
            sys.stdout.write(chunk)
            sys.stdout.flush()

        def tool_call_callback(tool_name: str, tool_args: dict[str, Any]):
            in_tool_call[0] = True
            # Add newline before tool call for better separation
            print()
            # Show tool call using Rich
            self.display_manager.show_tool_call(tool_name, tool_args)

        def tool_result_callback(tool_name: str, tool_args: dict[str, Any], result: Any):
            max_length = self.config_manager.config.behavior.max_response_length
            self.display_manager.show_tool_result(result, max_length)
            print()
            in_tool_call[0] = False

        self.jarvis_agent.stream_callback = stream_callback
        self.jarvis_agent.reasoning_callback = reasoning_callback
        self.jarvis_agent.tool_call_callback = tool_call_callback
        self.jarvis_agent.tool_result_callback = tool_result_callback

        try:
            await asyncio.wait_for(self.jarvis_agent.process(text), timeout=600)
        except asyncio.TimeoutError:
            self.display_manager.show_error("Task timed out.")
        except Exception as e:
            self.display_manager.show_error(f"Execution Error: {e}")

        print()



    async def run(self):
        """Start the CLI loop using prompt_toolkit."""
        self.display_manager.clear_screen()
        self._show_banner()
        self._show_help()

        while True:
            try:
                # Use prompt_toolkit with advanced features
                from rich.text import Text
                prompt_text = Text()
                prompt_text.append("YOU", style="bold cyan")
                prompt_text.append(" > ", style="bold green")

                # Use completer (removed lexer to fix display issues)
                user_input = await self.session.prompt_async(
                    prompt_text,
                    style=self.style,
                    multiline=False,
                    key_bindings=self.key_bindings,
                    completer=self.completer,
                    complete_while_typing=True
                )

                if not user_input.strip():
                    continue

                await self._handle_submit(user_input)

            except (KeyboardInterrupt, EOFError):
                self.display_manager.console.print()
                self.display_manager.console.print("[bold green]Goodbye![/bold green]")
                break
            except Exception as e:
                self.display_manager.show_error(f"Fatal Error: {e}")
                self.display_manager.stop_live_display()


async def main(launch_cli: bool = True, model: str = "gpt-4o", base_url: str | None = None, apikey: str | None = None, sdk: str = "openai", bypass: bool = True):
    """Main CLI entry point."""
    if not launch_cli:
        print("Error: CLI mode not enabled. Use --cli flag.")
        sys.exit(1)

    cli = CLIInterface(model=model, base_url=base_url, apikey=apikey, sdk=sdk, bypass=bypass)
    await cli.run()


if __name__ == "__main__":
    asyncio.run(main())
