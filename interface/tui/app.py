"""Textual TUI application for JARVIS."""

from typing import Any

from textual.app import App, ComposeResult
from textual.containers import Container
from textual.widgets import Header, Footer

from core.agents.base import BaseAgent
from interface.tui.widgets.banner import Banner
from interface.tui.widgets.chat_panel import ChatPanel
from interface.tui.widgets.status_bar import StatusBar

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


class JARVISApp(App):
    """JARVIS Textual User Interface application."""

    CSS_PATH = "tui.css"
    TITLE = "JARVIS 2.0"
    SUB_TITLE = "The professional AI engineering assistant"

    def __init__(self):
        super().__init__()
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

    def compose(self) -> ComposeResult:
        """Create child widgets for the app."""
        yield Header()
        yield Banner()
        yield ChatPanel(id="transcript-panel")
        yield Footer()
        yield StatusBar(id="status-bar")

    def on_mount(self) -> None:
        """Called when app is mounted."""
        # Set focus to the chat panel for input
        chat_panel = self.query_one("#transcript-panel", ChatPanel)
        chat_panel.focus()
