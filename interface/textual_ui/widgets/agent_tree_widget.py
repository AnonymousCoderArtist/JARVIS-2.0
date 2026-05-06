"""Agent tree widget - compact tree-style UI for displaying all agents.

Layout:
● Agents
 ├─ ⠹ Agent  Refactor auth module · ⟳5≤30 · 5 tool uses · 33.8k token (62%) · 12.3s
 │    ⎿  editing 2 files…
 ├─ ⠹ Explore  Find auth files · ⟳3 · 3 tool uses · 12.4k token (8%) · 4.1s
 │    ⎿  searching…
 ├─ ⠹ Agent  Long-running task · ⟳42 · 38 tool uses · 91.0k token (84% · ↻2) · 2m17s
 │    ⎿  reading…
 └─ 2 queued
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Static
from textual.reactive import reactive

from interface.textual_ui.widgets.no_markup_static import NoMarkupStatic


@dataclass
class AgentTreeItemData:
    """Data for a single agent in the tree."""
    task_id: str
    agent_name: str
    prompt: str
    status: str = "running"  # running, completed, failed
    start_time: float = field(default_factory=time.time)
    tool_uses: int = 0
    token_usage: int = 0
    token_limit: int = 200000  # Default, should be updated from model
    retries: int = 0
    max_retries: int = 30
    current_action: str = ""
    result: str = ""
    error: str | None = None
    queued: bool = False


class AgentTreeWidget(Static, can_focus=True):
    """Tree-style widget showing all agents in a compact format."""

    SPINNER_FRAMES = ("⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏")
    STATUS_ICONS = {
        "running": "⠹",
        "completed": "✓",
        "failed": "✗",
    }

    def __init__(self) -> None:
        super().__init__()
        self.agents: dict[str, AgentTreeItemData] = {}
        self.agent_order: list[str] = []
        self._is_spinning = False
        self._frame_index = 0
        self._container: Vertical | None = None
        self.add_class("agent-tree-widget")

    def compose(self) -> ComposeResult:
        """Render the agent tree."""
        self._container = Vertical(classes="agent-tree-container")
        yield self._container
        self._update_content()

    def _update_content(self) -> None:
        """Update the content of the container."""
        if not self._container:
            return

        # Clear existing children
        self._container.remove_children()

        # Header
        self._container.mount(NoMarkupStatic("● Agents", classes="agent-tree-header"))

        if not self.agent_order:
            self._container.mount(NoMarkupStatic("  (no agents)", classes="agent-tree-empty"))
            return

        active_agents = [tid for tid in self.agent_order if not self.agents[tid].queued]
        queued_agents = [tid for tid in self.agent_order if self.agents[tid].queued]

        for i, task_id in enumerate(active_agents):
            is_last = (i == len(active_agents) - 1) and len(queued_agents) == 0
            self._render_agent_to_container(task_id, is_last)

        # Queued count
        if queued_agents:
            if active_agents:
                self._container.mount(NoMarkupStatic("│   ", classes="agent-tree-branch"))
            self._container.mount(
                NoMarkupStatic(f"└─ {len(queued_agents)} queued", classes="agent-tree-queued")
            )

    def _render_agent_to_container(self, task_id: str, is_last: bool) -> None:
        """Render a single agent entry to the container."""
        if not self._container:
            return
        data = self.agents[task_id]
        branch = "└─" if is_last else "├─"
        status_icon = self._get_status_icon(data)

        # First line: status and metrics
        agent_type = data.agent_name.capitalize() if data.agent_name != "agent" else "Agent"
        prompt = self._truncate_prompt(data.prompt, 30)

        line = f"{branch} {status_icon} {agent_type}  {prompt}"

        # Add metrics
        metrics = []
        if data.retries > 0:
            metrics.append(f"⟳{data.retries}≤{data.max_retries}")
        if data.tool_uses > 0:
            metrics.append(f"{data.tool_uses} tool uses")
        if data.token_usage > 0:
            pct = (data.token_usage / data.token_limit * 100) if data.token_limit > 0 else 0
            token_str = self._format_tokens(data.token_usage)
            metrics.append(f"{token_str} token ({pct:.0f}%)")
        if data.status == "running":
            elapsed = time.time() - data.start_time
            metrics.append(self._format_time(elapsed))

        if metrics:
            line += " · " + " · ".join(metrics)

        self._container.mount(NoMarkupStatic(line, classes=f"agent-tree-item status-{data.status}"))

        # Second line: current action
        if data.current_action or data.status == "running":
            continuation = "│" if not is_last else " "
            action = data.current_action or "running…"
            self._container.mount(
                NoMarkupStatic(f"{continuation}    ⎿  {action}", classes="agent-tree-action")
            )

    def _get_status_icon(self, data: AgentTreeItemData) -> str:
        """Get the status icon, with spinning animation for running agents."""
        if data.status == "running" and self._is_spinning:
            return self.SPINNER_FRAMES[self._frame_index % len(self.SPINNER_FRAMES)]
        return self.STATUS_ICONS.get(data.status, "?")

    def _truncate_prompt(self, prompt: str, max_length: int = 30) -> str:
        """Truncate prompt for display."""
        if len(prompt) <= max_length:
            return prompt
        return prompt[:max_length-3] + "..."

    def _format_tokens(self, tokens: int) -> str:
        """Format token count (e.g., 33800 -> 33.8k)."""
        if tokens >= 1000:
            return f"{tokens/1000:.1f}k"
        return str(tokens)

    def _format_time(self, seconds: float) -> str:
        """Format time duration."""
        if seconds < 60:
            return f"{seconds:.1f}s"
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes}m{secs:02d}s"

    def on_mount(self) -> None:
        """Start spinner animation."""
        self._is_spinning = True
        self._frame_index = 0
        self.set_interval(0.3, self._update_spinner)

    def on_unmount(self) -> None:
        """Stop spinner animation."""
        self._is_spinning = False

    def _update_spinner(self) -> None:
        """Update spinner frames."""
        self._frame_index += 1
        # Only update if there are running agents
        if any(a.status == "running" for a in self.agents.values()):
            self._update_content()

    def add_agent(self, task_id: str, agent_name: str, prompt: str, queued: bool = False) -> None:
        """Add a new agent to the tree."""
        data = AgentTreeItemData(
            task_id=task_id,
            agent_name=agent_name,
            prompt=prompt,
            queued=queued,
        )
        self.agents[task_id] = data
        self.agent_order.append(task_id)
        self._update_content()

    def update_agent(self, task_id: str, **kwargs: Any) -> None:
        """Update agent data."""
        if task_id not in self.agents:
            return
        data = self.agents[task_id]
        for key, value in kwargs.items():
            if hasattr(data, key):
                setattr(data, key, value)
        self._update_content()

    def complete_agent(self, task_id: str, result: str = "", error: str | None = None) -> None:
        """Mark an agent as completed or failed."""
        if task_id not in self.agents:
            return
        data = self.agents[task_id]
        data.status = "completed" if not error else "failed"
        data.result = result
        data.error = error
        self._update_content()

    def remove_agent(self, task_id: str) -> None:
        """Remove an agent from the tree."""
        if task_id in self.agents:
            del self.agents[task_id]
            self.agent_order.remove(task_id)
            self._update_content()
