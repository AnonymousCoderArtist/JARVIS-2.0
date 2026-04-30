"""TUI entry point for JARVIS."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

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

from interface.textual_ui.app import run_textual_ui


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
    """Config for TUI."""
    model: str
    base_url: str | None
    api_key: str | None
    sdk: str
    
    # Additional config attributes
    active_model: str = field(init=False)
    enable_notifications: bool = False
    vibe_code_enabled: bool = False
    displayed_workdir: Path | None = None
    file_watcher_for_autocomplete: bool = False
    bypass_tool_permissions: bool = False
    mcp_servers: list = field(default_factory=list)
    session_logging: SessionLoggingConfig = field(default_factory=SessionLoggingConfig)
    api_timeout: float = 30.0
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


def main(model: str = "gpt-4o", base_url: str | None = None, apikey: str | None = None, sdk: str = "openai") -> None:
    """Main TUI entry point."""
    # Initialize tool registry
    tool_registry = ToolRegistry()
    
    # Register all tools
    tool_registry.register(FileReadTool())
    tool_registry.register(FileWriteTool())
    tool_registry.register(EditTool())
    tool_registry.register(ListDirectoryTool())
    tool_registry.register(GlobTool())
    tool_registry.register(BashTool())
    tool_registry.register(REPLTool())
    tool_registry.register(RunTestsTool())
    tool_registry.register(GrepSearchTool())
    tool_registry.register(ListBackgroundProcessesTool())
    tool_registry.register(ReadBackgroundOutputTool())
    tool_registry.register(WebFetchTool())
    tool_registry.register(SaveMemoryTool())
    tool_registry.register(InvokeAgentTool())
    tool_registry.register(ActivateSkillTool())
    
    # Create SDK instance based on parameters
    if sdk == "anthropic":
        sdk_instance = AnthropicSDK(api_key=apikey or "", base_url=base_url)
    elif sdk == "openai":
        sdk_instance = OpenAISDK(api_key=apikey or "", base_url=base_url)
    else:
        # Default to OpenAI SDK for standard mode
        sdk_instance = OpenAISDK(api_key=apikey or "", base_url=base_url)
    
    provider = SDKAdapter(sdk_instance, "tui-provider")
    
    # Update tool registry with provider
    tool_registry.update_tool_providers(
        llm_provider=provider,
        model=model
    )
    
    # Create JARVIS agent
    jarvis_agent = CodingAgent(provider, tool_registry, model=model)
    jarvis_agent.rebuild_system_prompt()
    
    # Create configuration
    config = Config(
        model=model,
        base_url=base_url,
        api_key=apikey,
        sdk=sdk,
    )
    
    # Create AgentLoop wrapper
    from interface.textual_ui.agent_loop import AgentLoop
    agent_loop = AgentLoop(
        agent=jarvis_agent,
        config=config,
        tool_registry=tool_registry,
    )
    
    # Launch textual UI
    run_textual_ui(agent_loop)


if __name__ == "__main__":
    main()
