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
from pygments.lexers import PythonLexer, BashLexer, MarkdownLexer

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
from core.tools.memory_tool import SaveMemoryTool, ReadMemoryTool
from core.tools.registry import ToolRegistry
from core.tools.repl_tool import REPLTool
from core.tools.web_tools import WebFetchTool

from .display import DisplayManager, StreamingResponse
from .commands import CommandHandler
from .config import ConfigManager, load_config
from .keybindings import create_key_bindings




class CLIInterface:
    """Modern CLI interface for JARVIS with rich display and modular architecture."""

    def __init__(self, model: str, base_url: str | None, apikey: str | None, sdk: str):
        self.model = model
        self.base_url = base_url
        self.apikey = apikey
        self.sdk = sdk
        self.tool_registry = ToolRegistry()
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
        self.session = PromptSession(history=FileHistory(str(history_path)))
        self.style = Style.from_dict({
            'prompt': f'bold {self.display_manager.theme["prompt"]}',
            'arrow': self.display_manager.theme["arrow"],
        })
        
        # Setup key bindings
        self.key_bindings = create_key_bindings(self.config_manager, self.display_manager)
        
        # Lexer for syntax highlighting
        self.lexer = None  # Will be set based on input context
        
        self._initialize_systems()

    def _detect_input_type(self, text: str) -> str:
        """Detect the type of input for appropriate lexer."""
        text_lower = text.lower().strip()
        
        if text_lower.startswith('python') or text_lower.startswith('def ') or text_lower.startswith('class '):
            return 'python'
        elif text_lower.startswith('!') or text_lower.startswith('cd ') or text_lower.startswith('ls '):
            return 'bash'
        elif '#' in text or '**' in text or '##' in text:
            return 'markdown'
        else:
            return 'text'

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

        # Initialize agent manager for profile support
        from core.agents.manager import AgentManager
        from core.config.settings import Settings
        settings = Settings()
        self.agent_manager = AgentManager(
            config_getter=lambda: settings,
            initial_agent="default"
        )

        # Create agent with profile config getter
        self.jarvis_agent = CodingAgent(
            provider,
            self.tool_registry,
            model=self.model,
            config_getter=lambda: self.agent_manager.config
        )
        
        # Update command handler with current status info
        self.command_handler.update_status_info(
            model=self.model,
            sdk=self.sdk,
            base_url=self.base_url,
            tool_count=len(self.tool_registry.list_tools())
        )

    def _show_banner(self):
        """Display the welcome banner."""
        self.display_manager.show_banner(
            model=self.model,
            sdk=self.sdk,
            base_url=self.base_url,
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
        response_state = StreamingResponse()
        in_tool_call = [False]

        def stream_callback(chunk: str):
            if in_tool_call[0]: return
            response_state.content += chunk
            # Update live markdown display
            self.display_manager.update_live_display(response_state.content)

        def reasoning_callback(chunk: str):
            if in_tool_call[0]: return
            response_state.reasoning += chunk

        def tool_call_callback(tool_name: str, tool_args: dict[str, Any]):
            in_tool_call[0] = True
            
            # Stop live display and clear current response buffer
            self.display_manager.stop_live_display()
            response_state.reasoning = ""
            response_state.content = ""
            
            # Show tool call
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
        
        # Stop live display
        self.display_manager.stop_live_display()
        
        # Show "(no response)" only if there was no content at all
        if not response_state.reasoning.strip() and not response_state.content.strip():
            self.display_manager.cprint("(no response)", style="dim")

        print()



    async def run(self):
        """Start the CLI loop using prompt_toolkit."""
        self.display_manager.clear_screen()
        self._show_banner()
        self._show_help()

        while True:
            try:
                # Use prompt_toolkit with advanced features
                prompt_msg = [
                    ('class:prompt', 'YOU '),
                    ('class:arrow', '> '),
                ]
                
                # Detect input type for syntax highlighting
                input_type = 'text'  # Default
                
                user_input = await self.session.prompt_async(
                    prompt_msg,
                    style=self.style,
                    multiline=False,
                    key_bindings=self.key_bindings,
                    lexer=self.lexer
                )

                if not user_input.strip():
                    continue

                await self._handle_submit(user_input)

            except (KeyboardInterrupt, EOFError):
                self.display_manager.cprint("\nGoodbye!", color="green")
                break
            except Exception as e:
                self.display_manager.show_error(f"Fatal Error: {e}")
                self.display_manager.stop_live_display()


def main(launch_cli: bool = True, model: str = "gpt-4o", base_url: str | None = None, apikey: str | None = None, sdk: str = "openai"):
    """Main CLI entry point."""
    if not launch_cli:
        print("Error: CLI mode not enabled. Use --cli flag.")
        sys.exit(1)
    
    cli = CLIInterface(model=model, base_url=base_url, apikey=apikey, sdk=sdk)
    asyncio.run(cli.run())


if __name__ == "__main__":
    main()
