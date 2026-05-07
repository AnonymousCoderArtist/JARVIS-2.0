"""Heartbeat scheduler - Nanobot-style two-phase periodic awareness system"""

from __future__ import annotations

import asyncio
import logging
import re
from collections.abc import Callable
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Virtual heartbeat_ok tool for saving heartbeat results
_HEARTBEAT_RESULT_TOOL = [
    {
        "type": "function",
        "function": {
            "name": "heartbeat_result",
            "description": "Save heartbeat completion result and write to results file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "result": {
                        "type": "string",
                        "description": "The heartbeat task completion result to save",
                    },
                    "status": {
                        "type": "string",
                        "enum": ["completed", "error"],
                        "description": "Status of the heartbeat task",
                    },
                },
                "required": ["result", "status"],
            },
        },
    }
]

# Virtual heartbeat decision tool
_HEARTBEAT_TOOL = [
    {
        "type": "function",
        "function": {
            "name": "heartbeat",
            "description": "Report heartbeat decision after reviewing tasks.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["skip", "run"],
                        "description": "skip = nothing to do, run = has active tasks",
                    },
                    "tasks": {
                        "type": "string",
                        "description": "Natural-language summary of active tasks (required for run)",
                    },
                },
                "required": ["action"],
            },
        },
    }
]


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
        now = datetime.now(tz)
        current_time = now.strftime("%H:%M")
    except Exception:
        # Fallback: use naive datetime if timezone fails
        now = datetime.now()
        current_time = now.strftime("%H:%M")

    return start <= current_time <= end


def get_heartbeat_file() -> Path | None:
    """Get the HEARTBEAT.md file path from .jarvis directory"""
    cwd = Path.cwd()

    for parent in [cwd] + list(cwd.parents):
        heartbeat_file = parent / ".jarvis" / "HEARTBEAT.md"
        if heartbeat_file.exists():
            return heartbeat_file

    home_heartbeat = Path.home() / ".jarvis" / "HEARTBEAT.md"
    if home_heartbeat.exists():
        return home_heartbeat

    return None


def parse_heartbeat_file(content: str) -> dict[str, Any]:
    """Parse HEARTBEAT.md file and extract tasks"""
    tasks = []
    current_task: dict[str, Any] = {}
    in_tasks_block = False
    in_checklist_mode = True

    lines = content.split("\n")
    for line in lines:
        stripped_line = line.strip()

        # Check for tasks block (YAML format)
        if stripped_line.startswith("tasks:"):
            in_tasks_block = True
            in_checklist_mode = False
            continue

        if in_tasks_block:
            # Check for new task entry first
            if stripped_line.startswith("- name:"):
                # Save previous task before starting a new one
                if current_task:
                    tasks.append(current_task)
                current_task = {"name": stripped_line.split(":", 1)[1].strip()}
            elif current_task:  # Only process properties if we have a current task
                # Match "interval:" or "prompt:" with or without leading spaces
                if stripped_line.startswith("interval:"):
                    interval_val = stripped_line.split(":", 1)[1].strip()
                    current_task["interval"] = interval_val
                elif stripped_line.startswith("prompt:"):
                    prompt_val = stripped_line.split(":", 1)[1].strip().strip('"').strip("'")
                    current_task["prompt"] = prompt_val
                elif stripped_line.startswith("- [") or stripped_line.startswith("- [ ]"):
                    # Checklist mode mixed in
                    if current_task:
                        tasks.append(current_task)
                        current_task = {}
                    in_checklist_mode = True
                    task_text = re.sub(r"^-\s*\[\s*\]?\s*", "", stripped_line)
                    if task_text:
                        tasks.append({
                            "name": task_text[:50],
                            "prompt": task_text,
                            "type": "checklist"
                        })

        # Check for checklist mode (markdown checkbox)
        if stripped_line.startswith("- [") or stripped_line.startswith("- [ ]"):
            in_checklist_mode = True
            # Extract the task text after the checkbox
            task_text = re.sub(r"^-\s*\[\s*\]?\s*", "", stripped_line)
            if task_text:
                tasks.append({
                    "name": task_text[:50],
                    "prompt": task_text,
                    "type": "checklist"
                })

    # Don't forget the last task
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
    return result[:max_chars - 10] + "... [truncated]"


def save_heartbeat_result(result: str, status: str = "completed") -> Path:
    """Save heartbeat result to .jarvis/HEARTBEAT_RESULTS.md file."""
    heartbeat_file = get_heartbeat_file()
    if heartbeat_file:
        results_dir = heartbeat_file.parent
    else:
        results_dir = Path.cwd() / ".jarvis"

    results_dir.mkdir(parents=True, exist_ok=True)
    results_file = results_dir / "HEARTBEAT_RESULTS.md"

    timestamp = datetime.now().isoformat()

    # Format the result entry
    entry = f"\n## {timestamp} ({status})\n\n{result}\n"

    # Read existing content or create new
    if results_file.exists():
        existing = results_file.read_text(encoding="utf-8")
        # Keep last 50 entries to prevent file from growing too large
        content = entry + existing
    else:
        content = f"# Heartbeat Results\n\n{entry}"

    # Write the file
    results_file.write_text(content, encoding="utf-8")

    return results_file


def is_deliverable(response: str) -> bool:
    """
    Check if a heartbeat response is suitable for user delivery.
    
    Filters out:
    1. Finalization fallback - canned error messages when nothing to report
    2. Leaked internal reasoning - model meta-commentary instead of user-facing report
    """
    text = response.lower()

    # Runner finalization fallback
    if "couldn't produce a final answer" in text:
        return False

    # Leaked internal reasoning patterns
    leaked_patterns = [
        "heartbeat.md",
        "awareness.md",
        "judgment call:",
        "decision logic",
        "valid options are",
        "my instructions",
        "i am supposed to",
        "strict heartbeat interpretation",
    ]
    if any(pattern in text for pattern in leaked_patterns):
        return False

    return True


class HeartbeatScheduler:
    """
    Nanobot-style two-phase heartbeat scheduler for periodic agent awareness.
    
    Phase 1 (decision): Reads HEARTBEAT.md and asks the LLM -- via a virtual
    tool call -- whether there are active tasks. This avoids free-text parsing
    and the unreliable HEARTBEAT_OK token.
    
    Phase 2 (execution): Only triggered when Phase 1 returns 'run'. The
    on_execute callback runs the task through the full agent loop and
    returns the result to deliver.
    """

    def __init__(
        self,
        agent_executor: Callable[[str], Any],
        config: dict[str, Any] | None = None,
    ):
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

        # Evaluation callback (for post-run filtering)
        self._evaluator = self.config.get("evaluator")

        # Notification callback
        self._notifier = self.config.get("notifier")

        # Parse interval
        try:
            self.interval = parse_interval(self.interval_str)
        except ValueError as e:
            logger.warning(f"Invalid heartbeat interval '{self.interval_str}', using 30m: {e}")
            self.interval = timedelta(minutes=30)

    def update_config(self, config: dict[str, Any]) -> None:
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
        self._evaluator = config.get("evaluator", self._evaluator)
        self._notifier = config.get("notifier", self._notifier)

        active_hours = config.get("active_hours", {})
        self.active_start = active_hours.get("start", self.active_start)
        self.active_end = active_hours.get("end", self.active_end)
        self.active_timezone = active_hours.get("timezone", self.active_timezone)

        try:
            self.interval = parse_interval(self.interval_str)
        except ValueError:
            pass

    async def start(self) -> None:
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
        self._busy = busy

    async def _run_loop(self) -> None:
        while self._running:
            try:
                await asyncio.sleep(self.interval.total_seconds())
                if self._running:
                    await self._run_heartbeat()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Heartbeat error: {e}")
                await asyncio.sleep(self.interval.total_seconds())

    async def _decide(self, content: str) -> tuple[str, str]:
        """Phase 1: Ask LLM to decide skip/run via virtual tool call."""
        current_time = datetime.now().isoformat()

        # Build decision prompt
        decision_prompt = (
            f"Current Time: {current_time}\n\n"
            "Review the following HEARTBEAT.md and decide whether there are active tasks.\n\n"
            f"{content}"
        )

        try:
            response = await self.agent_executor(decision_prompt)

            # Handle response - check for tool_calls in response dict
            if isinstance(response, dict) and "tool_calls" in response:
                tool_calls = response.get("tool_calls", [])
                if tool_calls:
                    args = tool_calls[0].get("arguments", {})
                    return args.get("action", "skip"), args.get("tasks", "")

            # Fallback: parse response text for decision
            if isinstance(response, str):
                response_lower = response.lower()
                if "action" in response_lower:
                    if '"action": "run"' in response or '"action":"run"' in response:
                        return "run", response
                    if '"action": "skip"' in response or '"action":"skip"' in response:
                        return "skip", ""
                # HEARTBEAT_OK convention - check for explicit heartbeat ok
                if "heartbeat_ok" in response_lower:
                    return "skip", ""
                # Check for task indicators that suggest running
                task_indicators = ["task:", "todo:", "need to", "should", "must"]
                if any(ind in response.lower() for ind in task_indicators):
                    return "run", response

            return "skip", ""
        except Exception as e:
            logger.error(f"Heartbeat decision failed: {e}")
            return "skip", ""

    async def _run_heartbeat(self) -> str:
        """Run a single heartbeat check using two-phase approach."""
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

        if heartbeat_file:
            try:
                with open(heartbeat_file, encoding="utf-8") as f:
                    heartbeat_content = f.read()
                logger.info(f"Heartbeat: Found HEARTBEAT.md at {heartbeat_file}")
            except Exception as e:
                logger.warning(f"Failed to read HEARTBEAT.md: {e}")

        if not heartbeat_content:
            logger.debug("Heartbeat: no HEARTBEAT.md found")
            return "skipped: no heartbeat file"

        # Phase 1: Decision
        try:
            logger.info("Heartbeat: checking for tasks...")
            action, tasks = await self._decide(heartbeat_content)

            if action != "run":
                if self.show_ok:
                    logger.info("Heartbeat: OK (nothing to report)")
                return "HEARTBEAT_OK"

            logger.info("Heartbeat: tasks found, executing...")

            # Phase 2: Execution (only if decision was "run")
            if not self._notifier:
                logger.debug("Heartbeat: no notifier set, skipping execution")
                return "skipped: no notifier"

            response = await self.agent_executor(tasks)

            if not response:
                logger.info("Heartbeat: no response from execution")
                return "skipped: no response"

            if not is_deliverable(response):
                logger.info("Heartbeat: suppressed non-deliverable response")
                return "skipped: non-deliverable response"

            # Apply evaluator if available
            should_notify = True
            if self._evaluator:
                try:
                    should_notify = await self._evaluator(response, tasks)
                except Exception as e:
                    logger.warning(f"Evaluator failed: {e}")

            if should_notify and self._notifier:
                logger.info("Heartbeat: completed, delivering response")
                await self._notifier(response)

                # Save result to file
                try:
                    result_file = save_heartbeat_result(response, "completed")
                    logger.info(f"Heartbeat result saved to {result_file}")
                except Exception as e:
                    logger.warning(f"Failed to save heartbeat result: {e}")

                return format_heartbeat_result(response, self.ack_max_chars)
            else:
                logger.info("Heartbeat: silenced by post-run evaluation")
                return "HEARTBEAT_OK"

        except Exception as e:
            logger.error(f"Heartbeat execution failed: {e}")
            return f"heartbeat_error: {str(e)}"

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def last_run(self) -> datetime | None:
        return self._last_run

    @property
    def last_result(self) -> str | None:
        return self._last_result

    @property
    def next_run_time(self) -> datetime | None:
        if self._last_run and self._running:
            return self._last_run + self.interval
        return None
