"""Simplified subagent viewer for monitoring background agents.

Provides read-only monitoring of background agent status without
launch/retrieve/clear functionality."""

from __future__ import annotations

from typing import Any, ClassVar
from enum import Enum, auto

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Container, Vertical
from textual.message import Message
from textual.widgets import OptionList, Static
from textual.widgets.option_list import Option

from interface.textual_ui.widgets.no_markup_static import NoMarkupStatic
from interface.textual_ui.types import AgentToolCallEvent, AgentToolResultEvent


class SubagentMode(Enum):
    """Available modes for subagent interaction."""
    MAIN_AGENT = auto()     # Default JARVIS main agent interface
    SUBAGENT_VIEW = auto()  # Full-screen read-only view of running subagent


class SubagentStatus(Enum):
    """Status indicators for background agents."""
    PENDING = ("⏳", "pending")      # Waiting to start
    RUNNING = ("◉", "running")      # Currently executing
    COMPLETED = ("✅", "completed")    # Finished successfully
    FAILED = ("❌", "failed")        # Failed with error
    UNKNOWN = ("❓", "unknown")      # Unknown status

    def __init__(self, icon: str, text: str):
        self.icon = icon
        self.text = text


def _build_agent_option_text(agent_name: str, display_name: str, status: SubagentStatus, is_current: bool) -> Text:
    """Build the option text for an agent in the list."""
    text = Text(no_wrap=True)
    marker = "▶ " if is_current else "  "
    style = "bold" if is_current else ""
    
    # Status icon
    status_icon, _ = status.icon, status.text
    text.append(f"{status_icon} ", style="green" if status == SubagentStatus.COMPLETED else "yellow" if status == SubagentStatus.RUNNING else "red" if status == SubagentStatus.FAILED else "")
    
    # Marker and name
    text.append(marker, style="green" if is_current else "")
    text.append(display_name, style=style)
    
    return text


class SubagentViewer(Container):
    """Simplified subagent viewer for monitoring background agents.
    
    Features:
    - Read-only monitoring of background agent status
    - Clean, organized agent management interface
    - Real-time updates via event system
    - No launch/retrieve/clear functionality (read-only)
    """

    can_focus_children = True

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape", "cancel", "Close", show=False),
        Binding("ctrl_w", "cancel", "Close", show=False),
        Binding("tab", "toggle_view", "Toggle View", show=True),
    ]

    class AgentSelected(Message):
        """Message sent when an agent is selected."""
        def __init__(self, agent_name: str):
            self.agent_name = agent_name
            super().__init__()

    class Cancelled(Message):
        """Message sent when the panel is cancelled/closed."""
        pass

    class ViewToggled(Message):
        """Message sent when view mode is toggled."""
        pass

    def __init__(
        self,
        agents: list[dict[str, str]],
        current_agent: str,
        background_agents: list[dict] | None = None,
        **kwargs: Any,
    ) -> None:
        """
        Initialize the subagent viewer.

        Args:
            agents: List of available agent dicts with 'name' and 'display_name' keys
            current_agent: Name of the currently active agent
            background_agents: List of active background agents with status info
        """
        super().__init__(id="subagent-viewer", **kwargs)
        self._agents = agents
        self._current_agent = current_agent
        self._background_agents = background_agents or []
        self._showing_background = False

    def compose(self) -> ComposeResult:
        """Compose the viewer contents."""
        if self._showing_background:
            self._compose_background_monitor()
        else:
            self._compose_agent_selector()

    def _compose_agent_selector(self) -> None:
        """Compose the agent selection interface."""
        options = []
        for agent in self._agents:
            agent_name = agent["name"]
            is_current = agent_name == self._current_agent
            options.append(
                Option(
                    _build_agent_option_text(
                        agent_name, 
                        agent["display_name"], 
                        SubagentStatus.UNKNOWN, 
                        is_current
                    ),
                    id=agent_name,
                )
            )
        
        with Vertical(id="subagent-content"):
            yield NoMarkupStatic("SUBAGENTS", classes="subagents-title")
            yield OptionList(*options, id="subagents-options")
            
            # Help text
            with Horizontal(id="subagents-help-container"):
                yield NoMarkupStatic("↑↓ Navigate", classes="subagents-help")
                yield NoMarkupStatic("  Enter Select", classes="subagents-help")
                yield NoMarkupStatic("  Tab Monitor", classes="subagents-help")
                yield NoMarkupStatic("  Esc Close", classes="subagents-help")

    def _compose_background_monitor(self) -> None:
        """Compose the background agent monitoring interface."""
        with Vertical(id="background-monitor-content"):
            # Header
            yield NoMarkupStatic("BACKGROUND AGENTS", classes="background-title")
            
            # Agent list
            if self._background_agents:
                for agent in self._background_agents:
                    status = SubagentStatus[agent.get("status", "UNKNOWN").upper()]
                    with Horizontal(classes="background-agent-item"):
                        yield Static(
                            self._build_agent_status_text(
                                agent["agent_name"], 
                                status, 
                                agent.get("task_id", "")
                            ),
                            classes="background-agent-status"
                        )
            else:
                yield NoMarkupStatic("No background agents running", classes="background-empty")
            
            # Help text
            with Horizontal(id="background-help-container"):
                yield NoMarkupStatic("Tab Agents", classes="background-help")
                yield NoMarkupStatic("  Esc Close", classes="background-help")

    def _build_agent_status_text(self, agent_name: str, status: SubagentStatus, task_id: str = "") -> Text:
        """Build formatted text for agent status display."""
        text = Text(no_wrap=True)
        
        # Status icon and name
        status_icon, status_text = status.icon, status.text
        text.append(f"{status_icon} ", style="bold")
        text.append(f"{agent_name}", style="bold")
        
        # Status and task ID
        if task_id:
            text.append(f" • {status_text}", style="dim")
            text.append(f" • {task_id[:8]}...", style="italic")
        else:
            text.append(f" • {status_text}", style="dim")
        
        return text

    def on_mount(self) -> None:
        """Focus the appropriate list on mount."""
        if self._showing_background:
            # Background monitor doesn't need focus
            pass
        else:
            option_list = self.query_one(OptionList)
            # Pre-select the current agent
            for i, agent in enumerate(self._agents):
                if agent["name"] == self._current_agent:
                    option_list.highlighted = i
                    break
            option_list.focus()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        """Handle agent selection."""
        if event.option.id:
            self.post_message(self.AgentSelected(event.option.id))

    def action_cancel(self) -> None:
        """Handle cancel/close."""
        self.post_message(self.Cancelled())
    
    def action_toggle_view(self) -> None:
        """Toggle between agent selector and background monitor."""
        self._showing_background = not self._showing_background
        # Recompose with new view
        self.remove_children()
        self.compose()
        self.post_message(self.ViewToggled())

    def update_background_agents(self, agents: list[dict]) -> None:
        """Update the list of background agents."""
        self._background_agents = agents
        if self._showing_background:
            # Refresh the background monitor view
            self.remove_children()
            self.compose()

    def handle_agent_event(self, event: AgentToolCallEvent | AgentToolResultEvent) -> None:
        """Handle agent events and update UI accordingly."""
        if isinstance(event, AgentToolCallEvent):
            # Agent launched - add to background list
            new_agent = {
                "agent_name": event.agent_name,
                "status": "running",
                "task_id": event.task_id,
                "prompt": event.prompt
            }
            self._background_agents.append(new_agent)
        elif isinstance(event, AgentToolResultEvent):
            # Agent completed - update status
            for i, agent in enumerate(self._background_agents):
                if agent.get("task_id") == event.task_id:
                    self._background_agents[i]["status"] = event.status
                    if event.status == "completed":
                        self._background_agents[i]["result"] = event.result
                    elif event.status == "failed":
                        self._background_agents[i]["error"] = event.error
                    break
        
        # Refresh if in background monitor view
        if self._showing_background:
            self.remove_children()
            self.compose()


class BackgroundAgentMonitor(Static):
    """Compact background agent monitor for status bar integration."""
    
    def __init__(self, **kwargs: Any):
        super().__init__(**kwargs)
        self.add_class("background-monitor")
        self._active_agents = 0
        self._completed_agents = 0
    
    def update_counts(self, active: int, completed: int) -> None:
        """Update agent counts."""
        self._active_agents = active
        self._completed_agents = completed
        self.update(self._get_display_text())
    
    def _get_display_text(self) -> str:
        """Get formatted display text."""
        parts = []
        if self._active_agents > 0:
            parts.append(f"🔄{self._active_agents}")
        if self._completed_agents > 0:
            parts.append(f"✅{self._completed_agents}")
        return " ".join(parts) if parts else "No agents"
    
    def on_mount(self) -> None:
        """Initialize display."""
        self.update(self._get_display_text())
