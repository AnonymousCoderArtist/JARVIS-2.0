"""Agent tree widget showing all background agents with rich metrics in chat."""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

from textual.containers import Horizontal, Vertical
from textual.timer import Timer
from textual.widgets import Static

from interface.textual_ui.widgets.no_markup_static import NoMarkupStatic
from interface.textual_ui.widgets.messages import NonSelectableStatic

from core.tools.consolidated_agent_tool import (
    list_background_agents,
    BackgroundAgentTask,
)


class AgentTreeWidget(Static):
    """Tree widget displaying all background agents with rich status.
    
    Displays in main chat:
    ● Agents
    ├─ ⠹ Agent  Refactor auth module · ⟳5≤30 · 5 tool uses · 33.8k token (62%) · 12.3s
    │    ⎿  editing 2 files…
    ├─ ⠹ Explore  Find auth files · ⟳3 · 3 tool uses · 12.4k token (8%) · 4.1s
    │    ⎿  searching…
    └─ 2 queued
    """
    
    BRANCH_MID = "├─"
    BRANCH_LAST = "└─"
    VERTICAL = "│"
    
    SPINNER_FRAMES = ("⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏")
    
    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._agents: list[BackgroundAgentTask] = []
        self._queued_count = 0
        self._spinner_index = 0
        self._refresh_timer: Timer | None = None
        self.add_class("agent-tree-widget")
    
    def on_mount(self) -> None:
        """Initial render and start periodic refresh."""
        self._refresh_display()
        self._refresh_timer = self.set_interval(0.8, self._refresh_display)
    
    def on_unmount(self) -> None:
        """Stop timer."""
        if self._refresh_timer:
            self._refresh_timer.stop()
            self._refresh_timer = None
    
    async def _refresh_display(self) -> None:
        """Refresh the display with current agent data."""
        self._agents = await list_background_agents()
        self._queued_count = sum(1 for a in self._agents if a.status == "pending")
        
        # Clear and rebuild
        self.remove_children()
        
        # Header
        self.mount(NoMarkupStatic("● Agents", classes="agent-tree-header"))
        
        if not self._agents:
            self.mount(NoMarkupStatic("  No background agents.", classes="agent-tree-empty"))
            return
        
        # Filter: show running + recent completed (last 5)
        running = [a for a in self._agents if a.status in ("pending", "running")]
        completed = sorted(
            [a for a in self._agents if a.status == "completed"],
            key=lambda a: a.completed_at or a.created_at,
            reverse=True
        )[:5]
        
        display_agents = running + completed
        
        # Agent entries
        for i, agent in enumerate(display_agents):
            is_last_agent = (i == len(display_agents) - 1) and self._queued_count == 0
            self._mount_agent_entry(agent, is_last_agent)
        
        # Queued count
        if self._queued_count > 0:
            self.mount(
                NonSelectableStatic(
                    f"{self.BRANCH_LAST} {self._queued_count} queued",
                    classes="agent-tree-queued"
                )
            )
    
    def _mount_agent_entry(self, agent: BackgroundAgentTask, is_last: bool) -> None:
        """Mount a single agent entry."""
        entry = Vertical(classes="agent-tree-entry")
        
        # Main line
        main_line = Horizontal(classes="agent-tree-main")
        
        # Branch
        branch = self.BRANCH_LAST if is_last else self.BRANCH_MID
        main_line.mount(NonSelectableStatic(branch, classes="agent-tree-branch"))
        
        # Status icon (spinning if running)
        icon = self._get_status_icon(agent)
        main_line.mount(
            NonSelectableStatic(icon, classes=f"agent-tree-icon agent-status-{agent.status}")
        )
        
        # Agent type badge
        agent_type = agent.agent_name.capitalize() if agent.agent_name else "Agent"
        main_line.mount(NoMarkupStatic(f" {agent_type} ", classes="agent-tree-type"))
        
        # Prompt (truncated)
        prompt = self._truncate(agent.prompt, 35)
        main_line.mount(NoMarkupStatic(f" {prompt} ", classes="agent-tree-prompt"))
        
        # Separator
        main_line.mount(NoMarkupStatic(" · ", classes="agent-tree-sep"))
        
        # Metrics
        metrics = self._get_metrics(agent)
        main_line.mount(NoMarkupStatic(metrics, classes="agent-tree-metrics"))
        
        entry.mount(main_line)
        
        # Activity line (if running or has activity)
        if agent.status == "running" or agent.current_activity:
            activity = self._get_activity_text(agent)
            if activity:
                activity_branch = " " if is_last else self.VERTICAL
                entry.mount(
                    NonSelectableStatic(
                        f"{activity_branch}    ⎿  {activity}",
                        classes="agent-tree-activity"
                    )
                )
        
        self.mount(entry)
    
    def _get_status_icon(self, agent: BackgroundAgentTask) -> str:
        """Get status icon for agent."""
        if agent.status == "running":
            icon = self.SPINNER_FRAMES[self._spinner_index % len(self.SPINNER_FRAMES)]
            self._spinner_index += 1
            return icon
        elif agent.status == "completed":
            return "●"
        elif agent.status == "failed":
            return "●"
        else:  # pending
            return "○"
    
    def _get_metrics(self, agent: BackgroundAgentTask) -> str:
        """Get formatted metrics string."""
        parts = []
        
        # Retry info
        retries = f"⟳{agent.retries}" if agent.retries > 0 else "⟳0"
        retries += f"≤{agent.max_retries}"
        parts.append(retries)
        
        # Tool uses
        tool_text = f"{agent.tool_uses} tool uses" if agent.tool_uses != 1 else "1 tool use"
        parts.append(tool_text)
        
        # Token usage
        if agent.max_tokens > 0:
            percentage = (agent.token_usage / agent.max_tokens * 100) if agent.max_tokens else 0
            token_text = f"{agent.token_usage/1000:.1f}k token ({percentage:.0f}%)"
        else:
            token_text = f"{agent.token_usage/1000:.1f}k token"
        parts.append(token_text)
        
        # Time elapsed
        if agent.status == "running" and agent.created_at:
            elapsed = (datetime.now() - agent.created_at).total_seconds()
        elif agent.completed_at and agent.created_at:
            elapsed = (agent.completed_at - agent.created_at).total_seconds()
        else:
            elapsed = 0
        
        time_str = self._format_time(elapsed)
        parts.append(time_str)
        
        return " · ".join(parts)
    
    def _get_activity_text(self, agent: BackgroundAgentTask) -> str:
        """Get activity description."""
        if agent.current_activity:
            activity = agent.current_activity
            # Make it more readable
            activity_map = {
                "read": "reading…",
                "grep": "searching…",
                "edit": "editing…",
                "write": "writing…",
                "ls": "listing…",
                "find": "finding…",
                "web_search": "searching web…",
                "fetch_webpage": "fetching…",
            }
            return activity_map.get(activity, f"{activity}…")
        elif agent.status == "running":
            return "running…"
        return ""
    
    def _format_time(self, seconds: float) -> str:
        """Format time as s, ms, or m:s."""
        if seconds < 60:
            return f"{seconds:.1f}s"
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes}m{secs:02d}s"
    
    def _truncate(self, text: str, max_len: int) -> str:
        """Truncate text with ellipsis."""
        if len(text) <= max_len:
            return text
        return text[:max_len-1] + "…"
