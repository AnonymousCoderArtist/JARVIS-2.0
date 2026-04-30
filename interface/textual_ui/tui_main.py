"""TUI entry point for JARVIS."""

from __future__ import annotations

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

from interface.textual_ui.adapters.core.agent_loop import AgentLoop
from interface.textual_ui.adapters.core.config import VibeConfig
from interface.textual_ui.app import run_textual_ui


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
    config = VibeConfig(
        model=model,
        base_url=base_url,
        api_key=apikey,
        sdk=sdk,
    )
    
    # Create AgentLoop adapter
    agent_loop = AgentLoop(
        agent=jarvis_agent,
        config=config,
        tool_registry=tool_registry,
    )
    
    # Launch textual UI
    run_textual_ui(agent_loop)


if __name__ == "__main__":
    main()
