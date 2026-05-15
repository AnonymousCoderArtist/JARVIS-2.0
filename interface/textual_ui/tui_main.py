"""TUI entry point for JARVIS."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from core.agents.async_manager import AsyncAgentConfig, AsyncAgentManager
from core.agents.jarvis_v2 import JarvisV2 as CodingAgent
from core.llm.sdk_adapter import SDKAdapter
from core.llm_sdk.anthropic.sdk import AnthropicSDK
from core.llm_sdk.openai.sdk import OpenAISDK
from core.tools.agent_tool import AgentsTool
from core.tools.async_registry import AsyncToolRegistry
from core.tools.background_tools import ListBackgroundProcessesTool, ReadBackgroundOutputTool
from core.tools.code_tools import BashTool, RunTestsTool
from core.tools.file_edit_tool import EditTool
from core.tools.file_tools import FileReadTool, FileWriteTool, FindTool, LSTool
from core.tools.grep_tool import GrepSearchTool
from core.tools.memory_tool import ReadMemoryTool, SaveMemoryTool
from core.tools.repl_tool import REPLTool
from core.tools.web_tools import ExaWebSearchTool, WebFetchTool
from core.tools.worktree_tool import EnterWorktreeTool, ExitWorktreeTool
from interface.textual_ui.app import run_textual_ui

logger = logging.getLogger(__name__)


@dataclass
class ModelConfig:
    """Model configuration."""
    alias: str
    auto_compact_threshold: int = 16000
    thinking: str = "medium"


@dataclass
class ConnectorConfig:
    """Connector configuration."""
    name: str
    disabled: bool = False


@dataclass
class SessionLoggingConfig:
    """Session logging configuration."""
    enabled: bool = False


@dataclass
class Config:
    """Config for TUI with enhanced JARVIS integration."""
    model: str
    base_url: str | None
    api_key: str | None
    sdk: str

    # Additional config attributes
    active_model: str = field(init=False)
    enable_notifications: bool = False
    vibe_code_enabled: bool = False
    displayed_workdir: Path | None = field(init=False)
    file_watcher_for_autocomplete: bool = False
    bypass_tool_permissions: bool = False
    agent_paths: list[Path] = field(default_factory=list)
    enabled_agents: list[str] = field(default_factory=list)
    disabled_agents: list[str] = field(default_factory=list)
    mcp_servers: list = field(default_factory=list)
    session_logging: SessionLoggingConfig = field(default_factory=SessionLoggingConfig)
    api_timeout: float = 1800.0  # 30 minutes for long-running tool operations
    installed_agents: list = field(default_factory=list)
    enable_update_checks: bool = False
    enable_auto_update: bool = False
    autocopy_to_clipboard: bool = False
    connectors: list[ConnectorConfig] = field(default_factory=list)
    models: list[ModelConfig] = field(default_factory=list)
    max_output_bytes: int = 100000
    disable_welcome_banner_animation: bool = False

    def __post_init__(self):
        self.active_model = self.model
        self.models = [ModelConfig(alias=self.model)]
        self.displayed_workdir = Path.cwd()

    def is_active_model_mistral(self) -> bool:
        """Check if active model is mistral."""
        return "mistral" in self.active_model.lower()

    def get_active_model(self) -> ModelConfig:
        """Get active model config."""
        return self.models[0] if self.models else ModelConfig(alias=self.model)

    def set_thinking(self, level: str) -> None:
        """Set thinking level."""
        if self.models:
            self.models[0].thinking = level

    def get_active_transcribe_model(self) -> str:
        """Get active transcribe model."""
        return "whisper-1"

    def get_transcribe_provider_for_model(self, model: str) -> str:
        """Get transcribe provider for model."""
        return "openai"

    def get_active_provider(self) -> str:
        """Get active provider."""
        return self.sdk


def get_env_config() -> dict[str, str | None]:
    """Get configuration from environment variables."""
    return {
        "model": os.getenv("JARVIS_MODEL"),
        "base_url": os.getenv("JARVIS_BASE_URL"),
        "api_key": os.getenv("JARVIS_API_KEY"),
        "sdk": os.getenv("JARVIS_SDK", "openai"),
    }


def load_mcp_servers_from_config(config_path: Path | None = None) -> list[dict]:
    """Load MCP server configurations from .mcp.json file."""
    if config_path is None:
        # Default to .mcp.json in current directory or JARVIS config dir
        config_path = Path(".mcp.json")

        if not config_path.exists():
            # Try in JARVIS config directory
            jarvis_dir = Path.home() / ".jarvis"
            config_path = jarvis_dir / "mcp.json"

    if not config_path.exists():
        return []

    try:
        import json
        with open(config_path) as f:
            data = json.load(f)

        # Handle both formats:
        # {"mcpServers": {"name": {...}}} or [{"name": ..., ...}]
        if "mcpServers" in data:
            servers = []
            for name, config in data["mcpServers"].items():
                server = {
                    "name": name,
                    "command": config.get("command", ""),
                    "args": config.get("args", []),
                    "env": config.get("env", {}),
                    "transport": config.get("transport", ""),  # Empty string to allow auto-detection
                    "url": config.get("url", ""),
                }
                servers.append(server)
            return servers
        elif isinstance(data, list):
            return data
        else:
            return []
    except Exception as e:
        print(f"Warning: Failed to load MCP config from {config_path}: {e}")
        return []


async def connect_mcp_servers(tool_registry: AsyncToolRegistry, provider: Any, model: str) -> int:
    """Initialize MCP servers using lazy lifecycle model."""
    from core.tools.mcp_adapter import MCPRegistry, MCPServerConfig, MCPTransportType

    # Load MCP server configurations
    mcp_config_dicts = load_mcp_servers_from_config()

    if not mcp_config_dicts:
        return 0

    # Create MCP registry with proxy mode
    mcp_registry = MCPRegistry(tool_registry=tool_registry, use_proxy=True)

    # Convert config dicts to MCPServerConfig objects
    configs = []
    for config_dict in mcp_config_dicts:
        try:
            url = config_dict.get("url", "")
            transport = config_dict.get("transport", "")
            if url and not transport:
                transport = MCPTransportType.HTTP

            config = MCPServerConfig.from_dict({
                "name": config_dict.get("name", ""),
                "command": config_dict.get("command", ""),
                "args": config_dict.get("args", []),
                "env": config_dict.get("env", {}),
                "transport": transport or MCPTransportType.STDIO,
                "url": url,
                "timeout": config_dict.get("timeout", 30.0),
                "lifecycle": config_dict.get("lifecycle", "lazy"),
                "idleTimeout": config_dict.get("idleTimeout", config_dict.get("idle_timeout", 15.0)),
                "directTools": config_dict.get("directTools", config_dict.get("direct_tools", False)),
                "excludeTools": config_dict.get("excludeTools", config_dict.get("exclude_tools", [])),
            })
            configs.append(config)
        except Exception as e:
            print(f"Warning: Invalid MCP config for '{config_dict.get('name', 'unknown')}': {e}")

    if not configs:
        return 0

    # Initialize with lazy lifecycle
    results = await mcp_registry.initialize(
        configs=configs,
        llm_provider=provider,
        model=model,
    )

    connected = sum(1 for v in results.values() if v == "initialized")
    print(f"MCP: {connected}/{len(configs)} server(s) ready (lazy mode)")
    return connected


def create_tool_registry() -> AsyncToolRegistry:
    """Create and configure tool registry with all JARVIS tools."""
    tool_registry = AsyncToolRegistry()

    # Register file operations
    tool_registry.register(FileReadTool())
    tool_registry.register(FileWriteTool())
    tool_registry.register(EditTool())
    tool_registry.register(LSTool())
    tool_registry.register(FindTool())

    # Register code execution tools
    tool_registry.register(BashTool())
    tool_registry.register(REPLTool())
    tool_registry.register(RunTestsTool())

    # Register search tools
    tool_registry.register(GrepSearchTool())

    # Register background process tools
    tool_registry.register(ListBackgroundProcessesTool())
    tool_registry.register(ReadBackgroundOutputTool())

    # Register web tools
    tool_registry.register(WebFetchTool())
    tool_registry.register(ExaWebSearchTool())

    # Register memory tools
    tool_registry.register(SaveMemoryTool())
    tool_registry.register(ReadMemoryTool())

    # Register AskUserQuestion tool
    from core.tools.ask_user_question_tool import AskUserQuestionTool
    tool_registry.register(AskUserQuestionTool())

    # Register agent tools
    tool_registry.register(AgentsTool())
    # Register watcher status tool
    from core.tools.watcher_tool import WatcherStatusTool
    tool_registry.register(WatcherStatusTool())
    # Register skill tool
    from core.tools.skill_manage_tool import SkillTool
    tool_registry.register(SkillTool())

    # Register worktree tools
    tool_registry.register(EnterWorktreeTool())
    tool_registry.register(ExitWorktreeTool())

    # Register ToolSearch tool
    from core.tools.tool_search_tool import ToolSearchTool
    tool_registry.register(ToolSearchTool())

    return tool_registry


async def load_extensions(tool_registry, event_bus=None, hook_registry=None):
    """Discover and load extensions via the ExtensionRunner system."""
    from core.extensions import ExtensionRunner

    runner = ExtensionRunner()
    await runner.discover_and_load(project_dir=".")
    conflicts = await runner.bind(tool_registry, event_bus, hook_registry)
    if conflicts:
        for ext_name, tool_conflicts in conflicts.items():
            for c in tool_conflicts:
                logger.info("Extension '%s' overrode tool '%s'", ext_name, c["tool"])
    return runner


def create_sdk_instance(sdk: str, api_key: str | None, base_url: str | None) -> Any:
    """Create SDK instance based on configuration."""
    if sdk == "anthropic":
        return AnthropicSDK(api_key=api_key or "", base_url=base_url)
    else:
        return OpenAISDK(api_key=api_key or "", base_url=base_url)


def main(model: str = "gpt-4o", base_url: str | None = None, apikey: str | None = None, sdk: str = "openai", bypass: bool = False, resume_session: str | None = None) -> None:
    """Main TUI entry point with enhanced JARVIS core integration."""
    # Get environment config as fallback
    env_config = get_env_config()

    # Use CLI args, fall back to env vars
    model = model or env_config["model"] or "gpt-4o"
    base_url = base_url or env_config["base_url"]
    apikey = apikey or env_config["api_key"]
    sdk = sdk or env_config["sdk"] or "openai"

    # Warn if no API key is set
    if not apikey:
        print("WARNING: No API key provided. Set JARVIS_API_KEY environment variable or use --apikey flag.")
        print("The TUI will start but API calls will fail.")
        print()

    # Initialize tool registry with all JARVIS tools
    tool_registry = create_tool_registry()

    # Load extensions (custom tools, hooks, etc.)
    import asyncio
    extension_runner = asyncio.run(load_extensions(tool_registry))

    # Create SDK instance based on parameters
    sdk_instance = create_sdk_instance(sdk, apikey, base_url)

    # Create provider adapter
    provider = SDKAdapter(sdk_instance, "tui-provider")

    # Update tool registry with provider and model
    tool_registry.update_tool_providers(
        llm_provider=provider,
        model=model
    )
    logger.info("Tool registry provider set: provider=%r, model=%s", provider, model)

    # Connect to MCP servers and register their tools
    import asyncio
    mcp_count = asyncio.run(connect_mcp_servers(tool_registry, provider, model))
    if mcp_count > 0:
        print(f"Connected to {mcp_count} MCP server(s)")

    # Initialize agent manager for profile support
    from core.agents.manager import AgentManager
    from core.config.settings import Settings
    settings = Settings()
    agent_manager = AgentManager(
        config_getter=lambda: settings,
        initial_agent="default"
    )

    # Make the active profile configuration available to tools that need it
    # NOTE: always pass llm_provider and model so they are never cleared.
    tool_registry.update_tool_providers(
        llm_provider=provider,
        model=model,
        config_getter=lambda: agent_manager.config,
    )
    logger.info(
        "Tool registry after config_getter injection: registry.llm_provider=%r",
        tool_registry.llm_provider,
    )

    # Initialize async agent manager for concurrent operations (optional)
    async_config = AsyncAgentConfig(
        max_concurrent_agents=settings.max_concurrent_agents,
        max_concurrent_tools=settings.max_concurrent_tools,
        default_timeout=settings.default_timeout,
        enable_background_tasks=settings.enable_background_tasks,
        resource_monitoring=settings.resource_monitoring,
        progress_updates=settings.progress_updates
    )
    async_agent_manager = AsyncAgentManager(async_config)

    # Create JARVIS agent with full core integration, profile config getter, and concurrent tools enabled
    jarvis_agent = CodingAgent(
        provider,
        tool_registry,
        model=model,
        config_getter=lambda: agent_manager.config,
        use_concurrent_tools=True
    )

    # Rebuild system prompt with dynamic tool descriptions
    jarvis_agent.rebuild_system_prompt()

    # Create configuration with actual working directory
    config = Config(
        model=model,
        base_url=base_url,
        api_key=apikey,
        sdk=sdk,
    )

    # Create AgentLoop wrapper with enhanced core integration
    from interface.textual_ui.agent_loop import AgentLoop
    agent_loop = AgentLoop(
        agent=jarvis_agent,
        config=settings,
        tool_registry=tool_registry,
        agent_manager=agent_manager,
        resume_session=resume_session
    )

    # Launch textual UI
    run_textual_ui(agent_loop)


if __name__ == "__main__":
    main()
