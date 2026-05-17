"""Modern command-line interface for JARVIS with rich display and modular architecture."""

import asyncio
import json
import sys
from pathlib import Path
from typing import Any

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.history import FileHistory
from prompt_toolkit.output import DummyOutput
from prompt_toolkit.styles import Style

from core.agents.async_manager import AsyncAgentConfig, AsyncAgentManager
from core.agents.jarvis_v2 import JarvisV2 as CodingAgent
from core.agents.manager import AgentManager
from core.config.settings import Settings
from core.connectors import ConnectorConfig, ConnectorManager, FilesystemConnector
from core.events import EventBus, HookRegistry
from core.history import ConversationHistory
from core.learn import LearningConfig, LearningManager
from core.llm.sdk_adapter import SDKAdapter
from core.llm_sdk.anthropic.sdk import AnthropicSDK
from core.llm_sdk.openai.sdk import OpenAISDK
from core.skills.manager import SkillManager
from core.tools.agent_tool import AgentsTool
from core.tools.async_registry import AsyncToolRegistry
from core.tools.background_tools import ListBackgroundProcessesTool, ReadBackgroundOutputTool
from core.tools.code_tools import BashTool, RunTestsTool
from core.tools.file_edit_tool import EditTool
from core.tools.file_tools import FileReadTool, FileWriteTool, FindTool, LSTool
from core.tools.grep_tool import GrepSearchTool
from core.tools.memory_tool import ReadMemoryTool, SaveMemoryTool
from core.tools.repl_tool import REPLTool
from core.tools.tool_search_tool import ToolSearchTool
from core.tools.web_tools import ExaWebSearchTool, WebFetchTool
from core.tools.worktree_tool import EnterWorktreeTool, ExitWorktreeTool
from core.watchers.manager import WatcherManager

from .commands import CommandHandler
from .config import load_config
from .display import DisplayManager
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




class CLIInterface:
    """Modern CLI interface for JARVIS with rich display and modular architecture."""

    def __init__(self, model: str, base_url: str | None, apikey: str | None, sdk: str, bypass: bool = True, resume_session: str | None = None):
        self.model = model
        self.base_url = base_url
        self.apikey = apikey
        self.sdk = sdk
        self.bypass = bypass
        self.tool_registry = AsyncToolRegistry()
        self.jarvis_agent: CodingAgent | None = None
        self.extension_runner = None
        self.resume_session = resume_session

        # Shared event system and hook registry for the session
        self.event_bus = EventBus()
        self.hook_registry = HookRegistry()

        # Initialize conversation history
        from core.history import ConversationHistory
        if resume_session:
            # Resume existing session
            self.history = ConversationHistory(session_id=resume_session)
        else:
            # Create new session
            self.history = ConversationHistory()
        self._current_provider = None
        self.learning_manager: LearningManager | None = None
        self.connector_manager: ConnectorManager | None = None

        # Initialize modular components
        self.config_manager = load_config()
        self.display_manager = DisplayManager(
            theme=self.config_manager.config.display.theme,
            width=self.config_manager.config.display.width,
            custom_themes=self.config_manager.config.themes
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

        self._initialize_systems()

    def _initialize_systems(self):
        self._initialize_agents()  # Initialize provider first
        self._initialize_tools()   # Then register tools with provider available
        # Provider is already set on tools via update_tool_providers call in _initialize_agents
        if self._current_provider:
            self.tool_registry.update_tool_providers(
                llm_provider=self._current_provider,
                model=self.model
            )

    async def _initialize_systems_async(self):
        """Async initialization: load extensions and MCP servers."""
        await self._load_extensions()
        await self._initialize_mcp_servers_async()

    async def _initialize_mcp_servers_async(self):
        """Initialize MCP servers using lazy lifecycle model."""
        try:
            from core.tools.mcp_adapter import MCPRegistry

            # Load MCP server configurations
            mcp_config_dicts = self._load_mcp_configs()

            if not mcp_config_dicts:
                return

            # Create MCP registry with proxy mode
            mcp_registry = MCPRegistry(tool_registry=self.tool_registry, use_proxy=True)

            # Convert config dicts to MCPServerConfig objects
            configs = []
            for config_dict in mcp_config_dicts:
                try:
                    config = self._create_mcp_config(config_dict)
                    configs.append(config)
                except Exception as e:
                    print(f"Warning: Invalid MCP config for '{config_dict.get('name', 'unknown')}': {e}")

            if not configs:
                return

            # Initialize with lazy lifecycle (only eager/keep-alive connect immediately)
            results = await mcp_registry.initialize(
                configs=configs,
                llm_provider=self._current_provider,
                model=self.model,
            )

            connected = sum(1 for v in results.values() if v == "initialized")
            total = len(configs)
            print(f"MCP: {connected}/{total} server(s) ready (lazy mode)")

        except Exception as e:
            print(f"Warning: MCP server initialization failed: {e}")

    def _initialize_tools(self):
        """Register all tools with the tool registry."""
        self.tool_registry.register(FileReadTool())
        self.tool_registry.register(FileWriteTool())
        self.tool_registry.register(EditTool())
        self.tool_registry.register(LSTool())
        self.tool_registry.register(FindTool())
        self.tool_registry.register(BashTool())
        self.tool_registry.register(REPLTool())
        self.tool_registry.register(RunTestsTool())
        self.tool_registry.register(GrepSearchTool())
        self.tool_registry.register(ListBackgroundProcessesTool())
        self.tool_registry.register(ReadBackgroundOutputTool())
        self.tool_registry.register(WebFetchTool())
        self.tool_registry.register(ExaWebSearchTool())
        self.tool_registry.register(SaveMemoryTool())
        self.tool_registry.register(ReadMemoryTool())
        from core.tools import AskUserQuestionTool
        self.tool_registry.register(AskUserQuestionTool())
        self.tool_registry.register(AgentsTool())
        from core.tools import SkillTool
        self.tool_registry.register(SkillTool())
        # Register worktree tools
        self.tool_registry.register(EnterWorktreeTool())
        self.tool_registry.register(ExitWorktreeTool())
        # Register tool search tool
        self.tool_registry.register(ToolSearchTool())
        # Register watcher status tool
        from core.tools.watcher_tool import WatcherStatusTool
        self.tool_registry.register(WatcherStatusTool())

    async def _load_extensions(self):
        """Discover and load extensions via the ExtensionRunner system."""
        from core.extensions import ExtensionRunner

        runner = ExtensionRunner()
        await runner.discover_and_load(project_dir=".")
        conflicts = await runner.bind(
            self.tool_registry,
            self.event_bus,
            self.hook_registry,
        )
        if conflicts:
            for ext_name, tool_conflicts in conflicts.items():
                for c in tool_conflicts:
                    print(f"Extension '{ext_name}' overrode tool '{c['tool']}'")

        # Store runner for deferred hook binding after agent creation
        self.extension_runner = runner

    def _initialize_agents(self):
        # Create SDK instance based on CLI parameters
        if self.sdk == "anthropic":
            sdk = AnthropicSDK(api_key=self.apikey or "", base_url=self.base_url)
        else:
            sdk = OpenAISDK(api_key=self.apikey or "", base_url=self.base_url)

        provider = SDKAdapter(sdk, "cli-provider")

        # Store provider reference for tool registry
        self._current_provider = provider

        # Update tool registry with provider immediately so tools can be registered with it
        self.tool_registry.update_tool_providers(
            llm_provider=provider,
            model=self.model
        )

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

        # Create agent with profile config getter, concurrent tools enabled, and shared event system
        self.jarvis_agent = CodingAgent(
            provider,
            self.tool_registry,
            model=self.model,
            config_getter=lambda: self.agent_manager.config,
            bypass_tool_permissions=self.bypass,
            use_concurrent_tools=True,
            event_bus=self.event_bus,
            hook_registry=self.hook_registry,
        )

        # Wire extension hooks into the agent's HookRegistry
        if self.extension_runner:
            self.extension_runner.rebind_hooks(self.jarvis_agent.hook_registry)

        # Set bypass mode on agent
        if self.bypass:
            self.jarvis_agent.bypass_tool_permissions = True

        # Wire approval callback for interactive tool approvals
        self.jarvis_agent.set_approval_callback(self._handle_tool_approval)

        # Share conversation history with agent
        self.jarvis_agent.history = self.history

        # Initialize heartbeat system if enabled in config
        self.jarvis_agent.initialize_heartbeat(lambda: self.agent_manager.config)
        if self.jarvis_agent.heartbeat_scheduler:
            asyncio.create_task(self.jarvis_agent.start_heartbeat())

        # Load full history into agent memory if resuming a session
        if self.resume_session:
            messages = self.history.get_full_history(coalesce=True)
            for msg in messages:
                self.jarvis_agent.add_role_message(
                    role=msg.role,
                    content=str(msg.content or ""),
                    tool_calls=msg.tool_calls,
                    tool_call_id=msg.tool_call_id,
                )

        # Initialize learning manager (only if enabled in settings)
        settings = Settings()
        self.learning_manager = LearningManager(LearningConfig(enabled=settings.learning_enabled)) if settings.learning_enabled else None

        # Initialize WatcherManager and discover watchers
        self.watcher_manager = WatcherManager(
            config_getter=lambda: self.agent_manager.config,
            event_queue=None  # CLI doesn't use AgentLoop
        )
        self.watcher_manager.discover_watchers()

        # Initialize connector manager with filesystem connector
        self.connector_manager = ConnectorManager()
        fs_config = ConnectorConfig(
            name="filesystem",
            connector_type="filesystem",
            config={"root_dir": ".", "include_hidden": False}
        )
        self.connector_manager.register(FilesystemConnector(fs_config))

        # Update command handler with managers for new commands
        self.command_handler.set_managers(
            agent_manager=self.agent_manager,
            tool_registry=self.tool_registry,
            skill_manager=self.skill_manager,
            jarvis_agent=self.jarvis_agent,
            config_manager=self.config_manager,
            learning_manager=self.learning_manager,
            session_reset_callback=self.reset_session
        )

        # Update command handler with current status info
        self.command_handler.update_status_info(
            model=self.model,
            sdk=self.sdk,
            base_url=self.base_url or "",
            tool_count=len(self.tool_registry.list_tools())
        )

    def _load_mcp_configs(self) -> list[dict]:
        """Load MCP server configurations from .mcp.json file."""
        from pathlib import Path

        config_paths = [
            Path(".mcp.json"),
            Path.home() / ".jarvis" / "mcp.json"
        ]

        for config_path in config_paths:
            if config_path.exists():
                try:
                    with open(config_path) as f:
                        data = json.load(f)

                    # Handle both formats: {"mcpServers": {...}} or [...]
                    if "mcpServers" in data:
                        servers = []
                        for name, config in data["mcpServers"].items():
                            # Create a copy and ensure name is in the config dict
                            config_copy = config.copy()
                            config_copy["name"] = name
                            servers.append(config_copy)
                        return servers
                    else:
                        return data.get("mcpServers", []) if isinstance(data, dict) else data
                except Exception as e:
                    print(f"Warning: Failed to load MCP config from {config_path}: {e}")

        return []

    def _create_mcp_config(self, config_dict: dict):
        """Create MCPServerConfig from dictionary."""
        from core.tools.mcp_adapter import MCPServerConfig, MCPTransportType

        # Auto-detect transport based on URL presence
        transport = config_dict.get("transport", MCPTransportType.HTTP if "url" in config_dict else MCPTransportType.STDIO)

        return MCPServerConfig.from_dict({
            "name": config_dict["name"],
            "command": config_dict.get("command", ""),
            "args": config_dict.get("args", []),
            "env": config_dict.get("env", {}),
            "url": config_dict.get("url", ""),
            "transport": transport,
            "timeout": config_dict.get("timeout", 30.0),
            "disabled": config_dict.get("disabled", False),
            "disabled_tools": config_dict.get("disabled_tools", []),
            "lifecycle": config_dict.get("lifecycle", "lazy"),
            "idleTimeout": config_dict.get("idleTimeout", config_dict.get("idle_timeout", 15.0)),
            "directTools": config_dict.get("directTools", config_dict.get("direct_tools", False)),
            "excludeTools": config_dict.get("excludeTools", config_dict.get("exclude_tools", [])),
        })

    def _show_help(self):
        """Display available commands."""
        self.display_manager.show_help()

    async def _handle_tool_approval(self, tool_name: str, tool_args: dict[str, Any], tool_call_id: str, required_permissions: list[Any]):
        """Handle tool approval request from the agent.

        Displays the rich approval prompt and returns the user's decision.
        """
        from interface.cli.display import show_approval_prompt

        items = [{
            "tool_name": tool_name,
            "args": tool_args,
            "tool_call_id": tool_call_id,
            "permissions": required_permissions,
        }]

        # Stop any active streaming before showing approval prompt
        self.display_manager.stop_streaming()

        decisions = show_approval_prompt(
            self.display_manager.console,
            items,
            yolo_mode=self.bypass,
        )

        if decisions == "all" or (isinstance(decisions, list) and decisions and decisions[0]):
            return ("yes", "")
        return ("no", "User rejected the tool call")

    async def _handle_submit(self, text: str):
        """Process user input with streaming output."""
        # Handle commands and shell input first
        if await self.command_handler.handle_input(text):
            return

        if not self.jarvis_agent:
            self.display_manager.show_error("JARVIS agent not initialized.")
            return

        # Save user message to history
        from core.history import create_user_message
        self.history.append_message(create_user_message(text))

        # State tracking for chat responses
        in_tool_call = [False]
        self.display_manager.start_streaming()

        def stream_callback(chunk: str):
            if in_tool_call[0]:
                return
            self.display_manager.update_streaming(chunk, is_reasoning=False)

        def reasoning_callback(chunk: str):
            if in_tool_call[0]:
                return
            self.display_manager.update_streaming(chunk, is_reasoning=True)

        def reasoning_done_callback():
            # Reasoning is done, but we don't stop streaming yet as content might follow
            pass

        def tool_call_callback(tool_name: str, tool_args: dict[str, Any]):
            in_tool_call[0] = True
            # Stop streaming before showing tool call to avoid layout issues
            self.display_manager.stop_streaming()
            self.display_manager.show_tool_call(tool_name, tool_args)

        def tool_result_callback(tool_name: str, tool_args: dict[str, Any], result: Any):
            max_length = self.config_manager.config.behavior.max_response_length
            self.display_manager.show_tool_result(result, max_length)
            in_tool_call[0] = False
            # Restart streaming for subsequent assistant response
            self.display_manager.start_streaming()

        self.jarvis_agent.stream_callback = stream_callback
        self.jarvis_agent.reasoning_callback = reasoning_callback
        self.jarvis_agent.reasoning_done_callback = reasoning_done_callback
        self.jarvis_agent.tool_call_callback = tool_call_callback
        self.jarvis_agent.tool_result_callback = tool_result_callback

        try:
            await asyncio.wait_for(self.jarvis_agent.process(text), timeout=self.config_manager.config.behavior.timeout_seconds)

            # Assistant response is already persisted by jarvis_v2 via
            # add_role_message + self.history.append_message
        except asyncio.TimeoutError:
            self.display_manager.stop_streaming()
            self.display_manager.show_error("Task timed out.")
        except Exception as e:
            self.display_manager.stop_streaming()
            self.display_manager.show_error(f"Execution Error: {e}")
        finally:
            self.display_manager.stop_streaming()

    async def reset_session(self) -> str:
        """Reset the session by creating a new history and clearing agent memory."""
        old_session_id = self.history.session_id

        # Create new conversation history (new session)
        self.history = ConversationHistory()

        # Clear agent memory and update history reference
        if self.jarvis_agent:
            self.jarvis_agent.clear_memory()
            self.jarvis_agent.history = self.history
            self.jarvis_agent.rebuild_system_prompt()

        return old_session_id

    async def run(self):
        """Start the CLI loop using prompt_toolkit."""
        self.display_manager.clear_screen()
        self.display_manager.show_banner(
            model=self.model,
            sdk=self.sdk,
            base_url=self.base_url or "",
            tool_count=len(self.tool_registry.list_tools())
        )
        self._show_help()

        # Initialize MCP servers and extensions asynchronously
        await self._load_extensions()
        await self._initialize_mcp_servers_async()

        # Start background watchers
        if hasattr(self, 'watcher_manager'):
            await self.watcher_manager.start()

        while True:
            try:
                # Modern prompt styling
                prompt_text = HTML(
                    "<bold><style color='#78dcff'>></style></bold> "
                )

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
                self.display_manager.console.print("[success]Goodbye![/]")
                break
            except Exception as e:
                self.display_manager.show_error(f"Fatal Error: {e}")


async def main(launch_cli: bool = True, model: str = "gpt-4o", base_url: str | None = None, apikey: str | None = None, sdk: str = "openai", bypass: bool = True, resume_session: str | None = None):
    """Main CLI entry point."""
    if not launch_cli:
        print("Error: CLI mode not enabled. Use --cli flag.")
        sys.exit(1)

    cli = CLIInterface(model=model, base_url=base_url, apikey=apikey, sdk=sdk, bypass=bypass, resume_session=resume_session)
    await cli.run()


if __name__ == "__main__":
    asyncio.run(main())
