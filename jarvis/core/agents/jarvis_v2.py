"""Jarvis V2 Agent - Main agent for all tasks"""

import asyncio
import time
from collections import defaultdict
from pathlib import Path
from typing import TYPE_CHECKING, Any

from jarvis.core.connectors import ConnectorManager
from jarvis.core.learn import LearningConfig, LearningManager
from jarvis.core.tools.skill_manage_tool import create_skill_markdown, get_skill_dir

from .base import BaseAgent
from .heartbeat_scheduler import HeartbeatScheduler
from .system_prompts import (
    FORK_SYSTEM_PROMPT,
    GENERAL_PURPOSE_SYSTEM_PROMPT,
    JARVIS_V2_SYSTEM_PROMPT,
    get_agent_prompt,
)
from .task_scheduler import TaskScheduler

if TYPE_CHECKING:
    pass


# Mapping from system_prompt_id to system prompts (loaded lazily)
def _get_system_prompt(agent_type: str) -> str:
    return get_agent_prompt(agent_type)


SYSTEM_PROMPT_MAP = {
    "jarvis": JARVIS_V2_SYSTEM_PROMPT,
    "explore": lambda: get_agent_prompt("explore"),
    "plan": lambda: get_agent_prompt("plan"),
    "jarvis-help": lambda: get_agent_prompt("jarvis-help"),
    "statusline-setup": lambda: get_agent_prompt("statusline-setup"),
    "verification": lambda: get_agent_prompt("verification"),
    "rubber-duck": lambda: get_agent_prompt("rubber-duck"),
    "general-purpose": GENERAL_PURPOSE_SYSTEM_PROMPT,
    "fork": FORK_SYSTEM_PROMPT,
}


class JarvisV2(BaseAgent):
    """JARVIS V2 - Single agent for all tasks"""

    SYSTEM_PROMPT = JARVIS_V2_SYSTEM_PROMPT

    def __init__(
        self,
        llm_provider,
        tool_registry,
        model: str | None = None,
        config_getter=None,
        bypass_tool_permissions: bool = False,
        use_concurrent_tools: bool = True,
        system_prompt: str | None = None,
        connector_manager: ConnectorManager | None = None,
        event_bus=None,
        hook_registry=None,
    ):
        # Use provided system_prompt or default to JARVIS_V2_SYSTEM_PROMPT
        effective_prompt = system_prompt if system_prompt else self.SYSTEM_PROMPT
        super().__init__(
            llm_provider, tool_registry, effective_prompt, model, config_getter,
            bypass_tool_permissions, use_concurrent_tools,
            event_bus=event_bus, hook_registry=hook_registry,
        )
        # Rebuild system prompt with tool descriptions
        self.rebuild_system_prompt()

        # Initialize learning system (lazy, reads from settings)
        self._learning_manager: LearningManager | None = None
        self._interactions_since_learning: int = 0
        self._last_response_text: str = ""
        self.connector_manager = connector_manager

        # Initialize heartbeat system (disabled by default, can be enabled via config)
        self._heartbeat_scheduler: HeartbeatScheduler | None = None
        self._tool_call_count: int = 0
        self._skill_creation_threshold: int = 5
        self._self_evaluation_interval: int = 15

    @property
    def learning_manager(self) -> LearningManager | None:
        """Lazy initialization of learning manager, reads enabled from settings."""
        if self._learning_manager is None:
            # Check if learning is enabled in settings
            settings = self._config_getter() if self._config_getter else None
            enabled = settings.learning_enabled if settings else False
            if enabled:
                self._learning_manager = LearningManager(LearningConfig(enabled=True))
        return self._learning_manager

    @property
    def heartbeat_scheduler(self) -> HeartbeatScheduler | None:
        """Get the heartbeat scheduler instance"""
        return self._heartbeat_scheduler

    def initialize_heartbeat(self, config_getter=None, notifier=None, evaluator=None) -> None:
        """Initialize the heartbeat scheduler with configuration
        
        Args:
            config_getter: Function returning settings (optional)
            notifier: Callback for delivering heartbeat results (async function)
            evaluator: Optional callback to evaluate if response should be delivered
        """
        settings = config_getter() if config_getter else None
        if not settings:
            return

        # Check if heartbeat is enabled in config
        if not settings.heartbeat_enabled:
            return

        # Get heartbeat config from settings properties
        heartbeat_config = {
            "enabled": settings.heartbeat_enabled,
            "every": settings.heartbeat_interval,
            "target": settings.heartbeat_target,
            "light_context": settings.heartbeat_light_context,
            "isolated_session": settings.heartbeat_isolated_session,
            "skip_when_busy": settings.heartbeat_skip_when_busy,
            "prompt": settings.heartbeat_prompt,
            "active_hours": settings.heartbeat_active_hours,
            "show_ok": settings.heartbeat_show_ok,
            "show_alerts": settings.heartbeat_show_alerts,
            "use_indicator": settings.heartbeat_use_indicator,
            "evaluator": evaluator,
            "notifier": notifier,
        }

        # Create agent executor for heartbeat (Phase 1 decision)
        async def agent_executor(prompt: str) -> str:
            return await self.process(prompt, {"heartbeat": True})

        self._heartbeat_scheduler = HeartbeatScheduler(
            agent_executor=agent_executor,
            config=heartbeat_config
        )

        # Set skill creation and evaluation thresholds from learning config
        self._skill_creation_threshold = getattr(settings, 'skill_creation_threshold', 5)
        self._self_evaluation_interval = getattr(settings, 'self_evaluation_interval', 15)

        # Initialize tool tracking attributes
        self._last_tool_name: str = ""
        self._tool_usage_history: list[str] = []

        # Set up tool call tracking via callback
        self.tool_call_callback = self._on_tool_call

    async def start_heartbeat(self) -> None:
        """Start the heartbeat scheduler"""
        if self._heartbeat_scheduler:
            await self._heartbeat_scheduler.start()

    async def stop_heartbeat(self) -> None:
        """Stop the heartbeat scheduler"""
        if self._heartbeat_scheduler:
            await self._heartbeat_scheduler.stop()

    async def trigger_heartbeat(self) -> str:
        """Manually trigger a heartbeat check"""
        if self._heartbeat_scheduler:
            return await self._heartbeat_scheduler.wake()
        return "Heartbeat not initialized"

    def set_busy(self, busy: bool) -> None:
        """Set busy state for heartbeat skip_when_busy feature"""
        if self._heartbeat_scheduler:
            self._heartbeat_scheduler.set_busy(busy)

    def track_tool_call(self) -> None:
        """Track a tool call for learning loop purposes"""
        self._tool_call_count += 1

        # Track tool usage patterns for learning
        if not hasattr(self, '_tool_usage_history'):
            self._tool_usage_history: list[str] = []
        self._tool_usage_history.append(self._last_tool_name or "unknown")
        if len(self._tool_usage_history) > 100:
            self._tool_usage_history = self._tool_usage_history[-100:]

        # Check if we should trigger skill creation
        if self._tool_call_count >= self._skill_creation_threshold:
            asyncio.create_task(self._create_skill_from_patterns())
            self._skill_creation_threshold = self._tool_call_count + 5  # Reset threshold

        # Check if we should trigger self-evaluation
        if self._tool_call_count >= self._self_evaluation_interval:
            asyncio.create_task(self._perform_self_evaluation())
            self._self_evaluation_interval = self._tool_call_count + 15  # Reset interval

    async def _create_skill_from_patterns(self) -> str | None:
        """Analyze tool usage patterns and create a skill if a pattern emerges"""
        if not self._tool_usage_history or len(self._tool_usage_history) < 3:
            return None

        recent_tools = self._tool_usage_history[-10:]

        # Check for repeated patterns
        tool_counts = defaultdict(int, {t: recent_tools.count(t) for t in set(recent_tools)})

        # Find most used tools
        most_used = [(t, c) for t, c in tool_counts.items() if c >= 2]
        if not most_used:
            return None

        # Create skill name and description
        top_tool = most_used[0][0]
        skill_name = f"tool-{top_tool.replace('_', '-')}-helper"
        skill_dir = get_skill_dir()
        skill_file = skill_dir / f"{skill_name}.md"

        # Create skill markdown
        skill_content = create_skill_markdown(
            name=f"Tool {top_tool} Helper",
            description=f"Automatically generated skill for using the {top_tool} tool effectively",
            when_to_use=f"When the user needs to use {top_tool} or similar operations",
            when_not_to_use="When other tools would be more appropriate",
            procedure=f"1. Identify the user's intent\n2. Use {top_tool} with appropriate parameters\n3. Verify the result\n4. Report back to user",
            pitfalls="Ensure parameters are correctly formatted",
            verification="Check that the tool executed successfully"
        )

        # Write skill file
        skill_file.write_text(skill_content)
        return str(skill_file)

    async def _perform_self_evaluation(self) -> dict[str, Any]:
        """Perform self-evaluation checkpoint and potentially improve skills"""
        evaluation = {
            "tool_call_count": self._tool_call_count,
            "last_10_tools": self._tool_usage_history[-10:] if hasattr(self, '_tool_usage_history') else [],
            "improvements_made": []
        }

        # Analyze recent performance
        if hasattr(self, '_tool_usage_history') and len(self._tool_usage_history) >= 5:
            recent = self._tool_usage_history[-5:]
            tool_counts = defaultdict(int)
            for tool in recent:
                tool_counts[tool] += 1

            # If a tool is used frequently, ensure skill exists
            for tool, count in tool_counts.items():
                if count >= 2:
                    skill_name = f"tool-{tool.replace('_', '-')}-helper"
                    skill_dir = get_skill_dir()
                    skill_file = skill_dir / f"{skill_name}.md"

                    if not skill_file.exists():
                        # Create missing skill
                        skill_content = create_skill_markdown(
                            name=f"Tool {tool} Helper",
                            description=f"Skill for using {tool} tool effectively",
                            when_to_use=f"When {tool} is needed",
                            when_not_to_use="When other tools are more appropriate",
                            procedure=f"Use {tool} with proper parameters",
                            pitfalls="Check parameters before use"
                        )
                        skill_file.write_text(skill_content)
                        evaluation["improvements_made"].append(f"Created skill for {tool}")

        return evaluation

    def reset_tool_call_count(self) -> None:
        """Reset tool call counter (e.g., after skill creation or evaluation)"""
        self._tool_call_count = 0

    def _on_tool_call(self, tool_name: str, tool_args: dict[str, Any]) -> None:
        """Callback for tracking tool calls"""
        self._last_tool_name = tool_name
        _ = tool_args  # Acknowledge for potential future use
        self.track_tool_call()

    def set_system_prompt(self, system_prompt: str) -> None:
        """Set a new system prompt for the agent."""
        self.system_prompt = system_prompt
        self.rebuild_system_prompt()

    @classmethod
    def get_system_prompt_for_profile(cls, system_prompt_id: str | None) -> str:
        """Get the appropriate system prompt for a profile's system_prompt_id."""
        from collections.abc import Callable
        from typing import cast
        if system_prompt_id and system_prompt_id in SYSTEM_PROMPT_MAP:
            value = SYSTEM_PROMPT_MAP[system_prompt_id]
            # Handle both string and lazy-loaded lambda values
            if callable(value):
                # Cast to tell type checker this callable returns str
                return cast(Callable[[], str], value)()
            return value
        return cls.SYSTEM_PROMPT  # Default to JARVIS_V2_SYSTEM_PROMPT

    async def process(self, input: str, context: dict | None = None) -> str:
        """
        Process a coding request

        Args:
            input: User input describing the coding task
            context: Optional context (e.g., current file, project path)

        Returns:
            Agent response with results or next steps
        """
        from jarvis.core.events import HookContext, HookStage

        # Run BEFORE_AGENT_START hooks
        start_ctx = HookContext(
            agent_name=getattr(self, "name", ""),
            agent_input=input,
            session_id=getattr(self, "session_id", ""),
            model=self.model,
            cwd=str(Path.cwd()),
        )
        start_result = await self._run_hooks(HookStage.BEFORE_AGENT_START, start_ctx)
        if start_result.block:
            return f"Agent start blocked by hook: {start_result.reason}"

        # Reset per-task trace buffer (self-evolving skills)
        self.current_task_input = input
        self.execution_trace = []

        # Run AFTER_AGENT_START hooks
        await self._run_hooks(HookStage.AFTER_AGENT_START, HookContext(
            agent_name=getattr(self, "name", ""),
            agent_input=input,
            session_id=getattr(self, "session_id", ""),
            model=self.model,
            cwd=str(Path.cwd()),
        ))

        try:
            # Build messages with proper roles using base class method
            messages = self._build_messages(input, include_memory=True)

            # Append context as a separate user message if provided
            if context:
                ctx_parts = []
                if "current_file" in context:
                    ctx_parts.append(f"Current file: {context['current_file']}")
                if "project_path" in context:
                    ctx_parts.append(f"Project path: {context['project_path']}")
                if "file_content" in context:
                    ctx_parts.append(f"File content:\n{context['file_content']}")
                if ctx_parts:
                    messages.append({"role": "user", "content": "\n".join(ctx_parts)})

            # Always use streaming when stream_callback is set (TUI mode)
            # This ensures real-time updates in the TUI
            stream = self.stream_callback is not None
            response = await self._process_with_tools(messages, stream=stream)

            # Run BEFORE_AGENT_END hooks
            end_ctx = HookContext(
                agent_name=getattr(self, "name", ""),
                agent_input=input,
                agent_output=response,
                session_id=getattr(self, "session_id", ""),
                model=self.model,
                cwd=str(Path.cwd()),
            )
            await self._run_hooks(HookStage.BEFORE_AGENT_END, end_ctx)

            # Store response for learning
            self._last_response_text = response
            self._interactions_since_learning += 1

            # Learn from this interaction (M1 Trace Collection)
            if self.learning_manager and self._interactions_since_learning >= 5:
                await self._learn_from_interaction(input, response)

            # Add to memory as proper role-based messages
            self.add_role_message(role="user", content=input)
            self.add_role_message(role="assistant", content=response)

            # Also persist to conversation history if available
            if self.history is not None:
                from jarvis.core.history import create_assistant_message
                self.history.append_message(create_assistant_message(response))

            # Run AFTER_AGENT_END hooks
            await self._run_hooks(HookStage.AFTER_AGENT_END, HookContext(
                agent_name=getattr(self, "name", ""),
                agent_input=input,
                agent_output=response,
                session_id=getattr(self, "session_id", ""),
                model=self.model,
                cwd=str(Path.cwd()),
            ))

            return response
        except Exception as e:
            # Run hooks even on error
            await self._run_hooks(HookStage.AFTER_AGENT_END, HookContext(
                agent_name=getattr(self, "name", ""),
                agent_input=input,
                agent_error=str(e),
                session_id=getattr(self, "session_id", ""),
                model=self.model,
                cwd=str(Path.cwd()),
            ))
            raise

    async def _learn_from_interaction(self, user_input: str, agent_response: str) -> None:
        """Learn from a user-agent interaction (M1 Trace logging)"""
        if not self.learning_manager:
            return

        try:
            # M1 Stage: Log high-quality trace
            await self.learning_manager.log_trace_m1({
                "user_input": user_input,
                "agent_response": agent_response,
                "timestamp": time.time(),
                "success": True  # Assume success for teacher model traces
            })
            self._interactions_since_learning = 0
        except Exception as e:
            # Log but don't fail
            import logging
            logging.getLogger(__name__).debug(f"M1 Trace logging failed: {e}")

    async def plan(self, task: str) -> list[dict]:
        """
        Plan the execution of a coding task

        Args:
            task: Task description

        Returns:
            List of action steps
        """
        # Build messages with proper roles
        user_content = f"Plan the following coding task step by step:\n{task}\n\nReturn your plan as a numbered list of steps."
        messages = self._build_messages(user_content, include_memory=False)

        # Process without tools
        response = await self._process_without_tools(messages, stream=False)

        # Parse the plan into steps
        steps = self._parse_plan(response)
        return steps

    async def plan_with_scheduler(
        self, task: str, max_concurrent: int = 5
    ) -> list[dict[str, Any]]:
        """
        Decompose a task using the TaskScheduler and return a structured plan
        with dependency tracking and priority ordering.

        Unlike plan() which uses LLM-based decomposition, this uses
        keyword-based analysis with topological sorting for parallel execution.

        Args:
            task: Task description to decompose
            max_concurrent: Maximum number of parallel tasks per batch

        Returns:
            List of planned steps with descriptions, priorities, and dependencies
        """
        scheduler = TaskScheduler(max_concurrent=max_concurrent)
        return await scheduler.decompose_and_plan(task)

    async def run_scheduled(
        self, task: str, executor_fn=None, max_concurrent: int = 5
    ) -> dict[str, Any]:
        """
        Decompose, schedule, and execute a task using the TaskScheduler.

        Args:
            task: High-level task description
            executor_fn: Async callable taking a Task and returning a result.
                         Defaults to using the agent's process() method.
            max_concurrent: Maximum number of parallel tasks per batch

        Returns:
            Dictionary mapping task IDs to their results
        """
        scheduler = TaskScheduler(max_concurrent=max_concurrent)

        if executor_fn is None:
            async def executor_fn(scheduled_task):
                return await self.process(scheduled_task.description)

        return await scheduler.run(task, executor_fn)

    def _parse_plan(self, plan_text: str) -> list[dict]:
        """Parse plan text into structured steps"""
        steps = []
        lines = plan_text.split('\n')

        for line in lines:
            line = line.strip()
            if line and (line[0].isdigit() or line.startswith('-')):
                steps.append({
                    "description": line,
                    "completed": False
                })

        return steps
