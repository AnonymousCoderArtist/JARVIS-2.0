"""AgentLoop adapter that wraps JARVIS's CodingAgent."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator, Callable
from dataclasses import dataclass, field
from typing import Any

from core.agents.coding_agent import CodingAgent
from core.tools.registry import ToolRegistry

from .config import VibeConfig
from .skills.manager import SkillManager
from .types import AgentStats, ApprovalResponse, BaseEvent


@dataclass
class AgentProfile:
    """Agent profile."""
    display_name: str = "JARVIS"
    safety: str = "standard"


@dataclass
class TelemetryClient:
    """Stub telemetry client."""
    def send_telemetry_event(self, event: str, data: dict[str, Any] | None = None) -> None:
        """Send telemetry event."""
        pass
    
    def send_user_rating_feedback(self, rating: int, comment: str | None = None) -> None:
        """Send user rating feedback."""
        pass
    
    def send_slash_command_used(self, command: str, command_type: str) -> None:
        """Send slash command used."""
        pass


@dataclass
class Stats:
    """Statistics tracker."""
    context_tokens: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_cost: float = 0.0
    _listeners: dict[str, list[Callable]] = field(default_factory=dict)
    
    def add_listener(self, metric: str, callback: Callable) -> None:
        """Add listener for metric changes."""
        if metric not in self._listeners:
            self._listeners[metric] = []
        self._listeners[metric].append(callback)
    
    def trigger_listeners(self) -> None:
        """Trigger all listeners."""
        for callbacks in self._listeners.values():
            for callback in callbacks:
                try:
                    callback(self.context_tokens)
                except Exception:
                    pass


class AgentLoop:
    """AgentLoop adapter that wraps JARVIS's CodingAgent."""
    
    def __init__(
        self,
        agent: CodingAgent,
        config: VibeConfig,
        tool_registry: ToolRegistry,
    ):
        self.agent = agent
        self.config = config
        self.base_config = config
        self.tool_registry = tool_registry
        self.agent_profile = AgentProfile()
        self.stats = Stats()
        self.telemetry_client = TelemetryClient()
        self.is_initialized = True
        self.skill_manager = SkillManager()
        self.mcp_registry = None
        self.connector_registry = None
        self.hook_config_issues = []
        
        self._approval_callback: Callable[[str, list[str]], ApprovalResponse] | None = None
        self._user_input_callback: Callable[[str], str] | None = None
        self._event_queue: asyncio.Queue[BaseEvent] = asyncio.Queue()
    
    async def wait_until_ready(self) -> None:
        """Wait until agent is ready."""
        # JARVIS agent is ready immediately
        pass
    
    def set_approval_callback(self, callback: Callable[[str, list[str]], ApprovalResponse]) -> None:
        """Set approval callback."""
        self._approval_callback = callback
    
    def set_user_input_callback(self, callback: Callable[[str], str]) -> None:
        """Set user input callback."""
        self._user_input_callback = callback
    
    def approve_always(self, tool_name: str, permissions: list[str]) -> None:
        """Approve tool always."""
        pass
    
    def emit_new_session_telemetry(self) -> None:
        """Emit new session telemetry."""
        pass
    
    def refresh_config(self) -> None:
        """Refresh configuration."""
        pass
    
    async def refresh_system_prompt(self) -> None:
        """Refresh system prompt."""
        self.agent.rebuild_system_prompt()
    
    async def inject_user_context(self, context: str) -> None:
        """Inject user context."""
        self.agent.update_context({"user_context": context})
    
    async def process_message(self, message: str) -> AsyncGenerator[str, None]:
        """Process a message and stream response."""
        if self._user_input_callback:
            # If UI is handling input, just yield the message
            yield message
            return
        
        # Otherwise, process through agent
        response = await self.agent.process(message)
        yield response
    
    async def run(self) -> None:
        """Run the agent loop."""
        pass
