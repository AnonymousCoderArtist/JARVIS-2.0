"""Heartbeat scheduler for proactive periodic awareness system (OpenClaw-style)"""

from __future__ import annotations

import asyncio
import logging
import os
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger(__name__)


def parse_interval(interval_str: str) -> timedelta:
    """Parse interval string like '30m', '1h', '15s' into timedelta"""
    match = re.match(r"^(\d+)([smh])$", interval_str.lower())
    if not match:
        raise ValueError(f"Invalid interval format: {interval_str}")
    
    value, unit = int(match.group(1)), match.group(2)
    if unit == "s":
        return timedelta(seconds=value)
    elif unit == "m":
        return timedelta(minutes=value)
    elif unit == "h":
        return timedelta(hours=value)
    else:
        raise ValueError(f"Unknown time unit: {unit}")


def is_within_active_hours(start: str, end: str, timezone: str = "America/New_York") -> bool:
    """Check if current time is within active hours"""
    try:
        import zoneinfo
        tz = zoneinfo.ZoneInfo(timezone)
    except Exception:
        # Fallback to local timezone
        import time
        tz = None
    
    now = datetime.now(tz)
    current_time = now.strftime("%H:%M")
    
    # Simple comparison (handles same-day times only)
    return start <= current_time <= end


def get_heartbeat_file() -> Path | None:
    """Get the HEARTBEAT.md file path from .jarvis directory"""
    cwd = Path.cwd()
    
    # Look for .jarvis directory in current or parent directories
    for parent in [cwd] + list(cwd.parents):
        heartbeat_file = parent / ".jarvis" / "HEARTBEAT.md"
        if heartbeat_file.exists():
            return heartbeat_file
    
    # Check in home directory
    home_heartbeat = Path.home() / ".jarvis" / "HEARTBEAT.md"
    if home_heartbeat.exists():
        return home_heartbeat
    
    return None


def parse_heartbeat_file(content: str) -> dict[str, Any]:
    """Parse HEARTBEAT.md file and extract tasks"""
    tasks = []
    current_task = {}
    in_tasks_block = False
    in_checklist_mode = True
    
    lines = content.split("\n")
    for line in lines:
        line = line.strip()
        
        # Check for tasks block (YAML format)
        if line.startswith("tasks:"):
            in_tasks_block = True
            in_checklist_mode = False
            continue
        
        if in_tasks_block:
            # Parse YAML-like task definition
            if line.startswith("- name:"):
                if current_task:
                    tasks.append(current_task)
                current_task = {"name": line.split(":", 1)[1].strip()}
            elif line.startswith("  interval:") and current_task:
                current_task["interval"] = line.split(":", 1)[1].strip()
            elif line.startswith("  prompt:") and current_task:
                current_task["prompt"] = line.split(":", 1)[1].strip().strip('"')
        
        # Check for checklist mode (markdown checkbox)
        if line.startswith("- [") or line.startswith("- [ ]"):
            in_checklist_mode = True
            # Extract the task text after the checkbox
            task_text = re.sub(r"^-\s*\[\s*\]?\s*", "", line)
            if task_text:
                tasks.append({
                    "name": task_text[:50],
                    "prompt": task_text,
                    "type": "checklist"
                })
    
    if current_task and current_task not in tasks:
        tasks.append(current_task)
    
    return {
        "tasks": tasks,
        "mode": "checklist" if in_checklist_mode else "tasks_block"
    }


def format_heartbeat_result(result: str, max_chars: int = 300) -> str:
    """Format heartbeat result for delivery, truncating if needed"""
    if len(result) <= max_chars:
        return result
    
    # Truncate with indicator
    return result[:max_chars - 10] + "... [truncated]"


class HeartbeatScheduler:
    """
    Heartbeat scheduler for periodic agent awareness (OpenClaw-style)
    
    Runs periodic agent turns in the main session to allow the model to 
    surface attention-requiring items without spamming the user.
    """
    
    def __init__(
        self,
        agent_executor: Callable[[str], Any],
        config: dict[str, Any] | None = None,
    ):
        """
        Initialize heartbeat scheduler
        
        Args:
            agent_executor: Async function to execute agent with input
            config: Configuration dict with heartbeat settings
        """
        self.agent_executor = agent_executor
        self.config = config or {}
        
        # Configuration with defaults
        self.enabled = self.config.get("enabled", False)
        self.interval_str = self.config.get("every", "30m")
        self.target = self.config.get("target", "last")
        self.light_context = self.config.get("light_context", False)
        self.isolated_session = self.config.get("isolated_session", False)
        self.skip_when_busy = self.config.get("skip_when_busy", False)
        self.prompt = self.config.get(
            "prompt",
            "Read HEARTBEAT.md if exists. Follow strictly. If nothing needs attention, reply HEARTBEAT_OK."
        )
        self.ack_max_chars = self.config.get("ack_max_chars", 300)
        self.show_ok = self.config.get("show_ok", True)
        self.show_alerts = self.config.get("show_alerts", True)
        self.use_indicator = self.config.get("use_indicator", True)
        
        # Active hours
        active_hours = self.config.get("active_hours", {})
        self.active_start = active_hours.get("start", "08:00")
        self.active_end = active_hours.get("end", "22:00")
        self.active_timezone = active_hours.get("timezone", "America/New_York")
        
        # State
        self._running = False
        self._task: asyncio.Task | None = None
        self._last_run: datetime | None = None
        self._last_result: str | None = None
        self._busy = False
        self._manual_wake = False
        
        # Parse interval
        try:
            self.interval = parse_interval(self.interval_str)
        except ValueError as e:
            logger.warning(f"Invalid heartbeat interval '{self.interval_str}', using 30m: {e}")
            self.interval = timedelta(minutes=30)
    
    def update_config(self, config: dict[str, Any]) -> None:
        """Update heartbeat configuration dynamically"""
        self.config = config
        self.enabled = config.get("enabled", self.enabled)
        self.interval_str = config.get("every", self.interval_str)
        self.target = config.get("target", self.target)
        self.light_context = config.get("light_context", self.light_context)
        self.isolated_session = config.get("isolated_session", self.isolated_session)
        self.skip_when_busy = config.get("skip_when_busy", self.skip_when_busy)
        self.prompt = config.get("prompt", self.prompt)
        self.ack_max_chars = config.get("ack_max_chars", self.ack_max_chars)
        self.show_ok = config.get("show_ok", self.show_ok)
        self.show_alerts = config.get("show_alerts", self.show_alerts)
        self.use_indicator = config.get("use_indicator", self.use_indicator)
        
        active_hours = config.get("active_hours", {})
        self.active_start = active_hours.get("start", self.active_start)
        self.active_end = active_hours.get("end", self.active_end)
        self.active_timezone = active_hours.get("timezone", self.active_timezone)
        
        # Re-parse interval
        try:
            self.interval = parse_interval(self.interval_str)
        except ValueError:
            pass
    
    async def start(self) -> None:
        """Start the heartbeat scheduler"""
        if self._running:
            logger.warning("Heartbeat scheduler already running")
            return
        
        if not self.enabled:
            logger.info("Heartbeat scheduler disabled")
            return
        
        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info(f"Heartbeat scheduler started with interval: {self.interval_str}")
    
    async def stop(self) -> None:
        """Stop the heartbeat scheduler"""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("Heartbeat scheduler stopped")
    
    async def wake(self) -> str:
        """Manually trigger a heartbeat check (system event)"""
        self._manual_wake = True
        result = await self._run_heartbeat()
        self._manual_wake = False
        return result
    
    def set_busy(self, busy: bool) -> None:
        """Set busy state to skip heartbeat when agent is busy"""
        self._busy = busy
    
    async def _run_loop(self) -> None:
        """Main heartbeat loop"""
        while self._running:
            try:
                await self._run_heartbeat()
                
                # Sleep until next heartbeat
                await asyncio.sleep(self.interval.total_seconds())
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Heartbeat error: {e}")
                # Still sleep on error to avoid tight loop
                await asyncio.sleep(self.interval.total_seconds())
    
    async def _run_heartbeat(self) -> str:
        """Run a single heartbeat check"""
        # Check active hours (unless manual wake)
        if not self._manual_wake:
            if not is_within_active_hours(self.active_start, self.active_end, self.active_timezone):
                logger.debug("Outside active hours, skipping heartbeat")
                return "skipped: outside active hours"
        
        # Check busy state
        if self.skip_when_busy and self._busy:
            logger.debug("Agent busy, skipping heartbeat")
            return "skipped: agent busy"
        
        # Read HEARTBEAT.md if exists
        heartbeat_file = get_heartbeat_file()
        heartbeat_content = ""
        tasks_info = {}
        
        if heartbeat_file:
            try:
                with open(heartbeat_file, encoding="utf-8") as f:
                    heartbeat_content = f.read()
                tasks_info = parse_heartbeat_file(heartbeat_content)
                logger.info(f"Heartbeat: Found {len(tasks_info.get('tasks', []))} tasks in {heartbeat_file}")
            except Exception as e:
                logger.warning(f"Failed to read HEARTBEAT.md: {e}")
        
        # Build the heartbeat prompt
        prompt = self.prompt
        
        if heartbeat_content:
            # Prepend the heartbeat content for context
            prompt = f"{heartbeat_content}\n\n{self.prompt}"
        
        # Execute the agent with heartbeat prompt
        try:
            logger.info("Running heartbeat check...")
            result = await self.agent_executor(prompt)
            
            # Store result
            self._last_run = datetime.now()
            formatted_result = format_heartbeat_result(result, self.ack_max_chars)
            self._last_result = formatted_result
            
            # Handle HEARTBEAT_OK response
            if result.strip() == "HEARTBEAT_OK":
                if self.show_ok:
                    logger.info("Heartbeat: No issues detected")
                return "HEARTBEAT_OK"
            
            # Return result for delivery
            logger.info(f"Heartbeat result: {formatted_result[:100]}...")
            return formatted_result
            
        except Exception as e:
            logger.error(f"Heartbeat execution failed: {e}")
            return f"heartbeat_error: {str(e)}"
    
    @property
    def is_running(self) -> bool:
        """Check if heartbeat scheduler is running"""
        return self._running
    
    @property
    def last_run(self) -> datetime | None:
        """Get last heartbeat run time"""
        return self._last_run
    
    @property
    def last_result(self) -> str | None:
        """Get last heartbeat result"""
        return self._last_result
    
    @property
    def next_run_time(self) -> datetime | None:
        """Get approximate next run time"""
        if self._last_run and self._running:
            return self._last_run + self.interval
        return None