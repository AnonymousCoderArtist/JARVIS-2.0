"""Consolidated agent tool that combines AgentsTool, AgentStatusTool, and BackgroundAgentResultsTool functionality."""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from .base import BaseTool, ToolInput, ToolOutput

logger = logging.getLogger(__name__)


# Global background agent tracker with activity support
_background_agents: dict[str, 'BackgroundAgentTask'] = {}
_background_lock = asyncio.Lock()


@dataclass
class BackgroundAgentTask:
    """Represents a background agent task"""
    task_id: str
    agent_name: str
    prompt: str
    status: str = "pending"  # pending, running, completed, failed
    result: str = ""
    error: str | None = None
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: datetime | None = None
    task: asyncio.Task | None = None
    # Metrics
    tool_uses: int = 0
    token_usage: int = 0
    max_tokens: int = 0
    retries: int = 0
    max_retries: int = 30
    current_activity: str = ""  # e.g., "editing", "searching"


async def get_background_agent(task_id: str) -> BackgroundAgentTask | None:
    """Get a background agent task by ID"""
    async with _background_lock:
        return _background_agents.get(task_id)


async def list_background_agents() -> list[BackgroundAgentTask]:
    """List all background agent tasks"""
    async with _background_lock:
        return list(_background_agents.values())


async def get_completed_background_agents() -> list[BackgroundAgentTask]:
    """Get list of completed background agent tasks"""
    async with _background_lock:
        return [agent for agent in _background_agents.values() if agent.status == "completed"]


async def clear_completed_background_agents() -> None:
    """Clear completed background agent tasks from the registry"""
    async with _background_lock:
        completed_task_ids = [task_id for task_id, agent in _background_agents.items() if agent.status == "completed"]
        for task_id in completed_task_ids:
            del _background_agents[task_id]


async def _run_agent_in_background(
    task_id: str,
    agent_name: str,
    prompt: str,
    llm_provider,
    tool_registry,
    model,
    config_getter,
    event_queue=None,
):
    """Run an agent in the background and update status when done"""
    from core.agents import EXPLORE, ExploreAgent, PLAN, PlanAgent
    from core.config.settings import Settings
    from core.agents.base import BaseAgent

    # Define callback to track tool usage
    def _on_tool_call(tool_name: str, tool_args: dict) -> None:
        """Increment tool usage counter"""
        import asyncio
        async def _update():
            async with _background_lock:
                if task_id in _background_agents:
                    _background_agents[task_id].tool_uses += 1
                    _background_agents[task_id].current_activity = f"{tool_name}"
        asyncio.create_task(_update())
    
    def _on_tool_result(tool_name: str, result: Any) -> None:
        """Clear current activity after tool completes"""
        import asyncio
        async def _update():
            async with _background_lock:
                if task_id in _background_agents:
                    _background_agents[task_id].current_activity = ""
        asyncio.create_task(_update())

    try:
        # Update status to running
        async with _background_lock:
            if task_id in _background_agents:
                _background_agents[task_id].status = "running"

        # Create the appropriate subagent
        if agent_name == "explore":
            def explore_config_getter() -> Settings:
                if callable(config_getter):
                    base_settings = config_getter()
                else:
                    base_settings = Settings()
                merged_config = EXPLORE.apply_to_config(base_settings.model_dump())
                return Settings(initial_config=merged_config)

            explore_registry = _FilteredToolRegistry(
                tool_registry,
                allowed_tools=("read", "ls", "find", "grep"),
                llm_provider=llm_provider,
                model=model,
                config_getter=explore_config_getter,
            )

            subagent = ExploreAgent(
                llm_provider=llm_provider,
                tool_registry=explore_registry,
                model=model,
                config_getter=explore_config_getter,
            )
            # Set callbacks for metrics tracking
            subagent.tool_call_callback = _on_tool_call
            subagent.tool_result_callback = _on_tool_result
            subagent.rebuild_system_prompt()

            # Execute the task
            result = await subagent.process(prompt)
            
            # Try to capture token usage from result if available
            token_usage = 0
            if isinstance(result, dict) and "usage" in result:
                usage = result["usage"]
                if isinstance(usage, dict):
                    token_usage = usage.get("total_tokens", 0)
                elif hasattr(usage, "total_tokens"):
                    token_usage = usage.total_tokens

            # Update with result
            async with _background_lock:
                if task_id in _background_agents:
                    _background_agents[task_id].status = "completed"
                    _background_agents[task_id].result = result
                    _background_agents[task_id].token_usage = token_usage
                    _background_agents[task_id].completed_at = datetime.now()

        elif agent_name == "plan":
            def plan_config_getter() -> Settings:
                if callable(config_getter):
                    base_settings = config_getter()
                else:
                    base_settings = Settings()
                merged_config = PLAN.apply_to_config(base_settings.model_dump())
                return Settings(initial_config=merged_config)

            plan_registry = _FilteredToolRegistry(
                tool_registry,
                allowed_tools=("read", "ls", "find", "grep", "web_search", "fetch_webpage", "save_memory", "read_memory"),
                llm_provider=llm_provider,
                model=model,
                config_getter=plan_config_getter,
            )

            subagent = PlanAgent(
                llm_provider=llm_provider,
                tool_registry=plan_registry,
                model=model,
                config_getter=plan_config_getter,
            )
            # Set callbacks for metrics tracking
            subagent.tool_call_callback = _on_tool_call
            subagent.tool_result_callback = _on_tool_result
            subagent.rebuild_system_prompt()

            # Execute the task
            result = await subagent.process(prompt)
            
            # Try to capture token usage from result if available
            token_usage = 0
            if isinstance(result, dict) and "usage" in result:
                usage = result["usage"]
                if isinstance(usage, dict):
                    token_usage = usage.get("total_tokens", 0)
                elif hasattr(usage, "total_tokens"):
                    token_usage = usage.total_tokens

            # Update with result
            async with _background_lock:
                if task_id in _background_agents:
                    _background_agents[task_id].status = "completed"
                    _background_agents[task_id].result = result
                    _background_agents[task_id].token_usage = token_usage
                    _background_agents[task_id].completed_at = datetime.now()

        else:
            async with _background_lock:
                if task_id in _background_agents:
                    _background_agents[task_id].status = "failed"
                    _background_agents[task_id].error = f"Unknown agent: {agent_name}"
                    _background_agents[task_id].completed_at = datetime.now()

    except Exception as e:
        async with _background_lock:
            if task_id in _background_agents:
                _background_agents[task_id].status = "failed"
                _background_agents[task_id].error = str(e)
                _background_agents[task_id].completed_at = datetime.now()


class _FilteredToolRegistry:
    """Read-only filtered view over a tool registry."""

    def __init__(
        self,
        source_registry,
        allowed_tools: Iterable[str],
        llm_provider=None,
        model=None,
        config_getter=None,
    ):
        self._source_registry = source_registry
        self._allowed_tools = set(allowed_tools)
        self.llm_provider = llm_provider
        self.model = model
        self.config_getter = config_getter
        self.active_skills = getattr(source_registry, "active_skills", {})

    def get(self, name: str):
        if name not in self._allowed_tools:
            return None
        return self._source_registry.get(name)

    def get_tools(self) -> dict[str, BaseTool]:
        return {
            name: tool
            for name, tool in self._source_registry.get_tools().items()
            if name in self._allowed_tools
        }

    def list_tools(self) -> list[dict[str, object]]:
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.input_schema,
            }
            for tool in self.get_tools().values()
        ]

    def get_function_definitions(self) -> list[dict[str, object]]:
        return [tool.get_function_definition() for tool in self.get_tools().values()]

    async def execute_tool(self, name: str, input_data: dict) -> ToolOutput:
        if name not in self._allowed_tools:
            return ToolOutput(
                success=False,
                result=None,
                error=f"Tool '{name}' is not available to the explore subagent.",
            )
        return await self._source_registry.execute_tool(name, input_data)


class AgentTool(BaseTool):
    """Primary agent management tool - unified interface for all subagent operations.

    Use this tool whenever you need to:
    1. Delegate tasks to specialized subagents (explore/plan)
    2. Monitor progress of background agent tasks
    3. Retrieve results from completed background work
    4. Manage your active and completed agent tasks

    Usage rules:
    - Always use runInBackground=true when you can do other work while waiting
    - Only use runInBackground=false when you need immediate results for current task
    - Do not repeatedly check status - do meaningful work between checks
    - Always retrieve results when tasks complete to avoid memory buildup
    - Use 'list' operation to see all active agents before launching new ones

    Available subagents:
    - explore: Codebase exploration, file analysis, pattern finding
    - plan: Task decomposition, implementation planning, architecture design

    """
    name = "agents"
    description = "Launch, monitor, and retrieve results from specialized subagents (explore, plan)"

    input_schema = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "description": "Action to perform: 'launch', 'status', 'results', or 'list'",
                "enum": ["launch", "status", "results", "list"],
                "default": "launch",
            },
            "agentName": {
                "type": "string",
                "description": "Name of specialized subagent: 'explore' (codebase analysis), 'plan' (task decomposition)",
                "minLength": 1
            },
            "prompt": {
                "type": "string",
                "description": "Task description to send to the subagent",
                "minLength": 1
            },
            "runInBackground": {
                "type": "boolean",
                "description": "Run agent in background (true) or wait for immediate results (false)",
                "default": False
            },
            "taskId": {
                "type": "string",
                "description": "Task ID for status/results queries, or 'list' for all tasks",
                "minLength": 1
            },
            "resultsAction": {
                "type": "string",
                "description": "For 'results' action: 'check', 'retrieve', or 'clear'",
                "enum": ["check", "retrieve", "clear"]
            }
        },
        # Backwards compatible: older callers omitted "action" and used agentName/prompt.
        "required": []
    }

    def _get_param(self, input_data: ToolInput, *names) -> Any:
        """Get parameter using multiple possible names"""
        for name in names:
            value = getattr(input_data, name, None)
            if value is not None:
                return value
        return None

    async def execute(self, input_data: ToolInput) -> ToolOutput:
        # Get parameters - 'action' is the primary parameter name
        action = self._get_param(input_data, "action")
        agent_name = self._get_param(input_data, "agentName")
        prompt = self._get_param(input_data, "prompt")
        runInBackground = self._get_param(input_data, "runInBackground", "run_in_background")
        taskId = self._get_param(input_data, "taskId")
        resultsAction = self._get_param(input_data, "resultsAction")

        # Backwards-compatible inference for legacy callers:
        # - If agentName + prompt are provided, treat as launch.
        # - Otherwise infer status/results/list from the other parameters.
        if action is None:
            if isinstance(agent_name, str) and isinstance(prompt, str):
                action = "launch"
            elif isinstance(resultsAction, str):
                action = "results"
            elif isinstance(taskId, str):
                action = "status"
            else:
                action = "list"

        # Normalize runInBackground default (legacy callers frequently omit it).
        if runInBackground is None:
            runInBackground = False  # Default to foreground (run immediately)

        # Validate action
        if not isinstance(action, str) or action not in ["launch", "status", "results", "list"]:
            return ToolOutput(
                success=False,
                result=None,
                error="Invalid action: must be 'launch', 'status', 'results', or 'list'. Please provide a valid action."
            )

        try:
            if action == "launch":
                return await self._handle_launch(agent_name, prompt, runInBackground)
            elif action == "status":
                return await self._handle_status(taskId)
            elif action == "results":
                return await self._handle_results(resultsAction, taskId)
            elif action == "list":
                # List is an alias for status with taskId='list'
                return await self._handle_status("list")

        except ImportError as e:
            return ToolOutput(
                success=False,
                result=None,
                error=f"Failed to import agent classes: {str(e)}. Please ensure the agent modules are properly installed and accessible."
            )
        except Exception as e:
            return ToolOutput(
                success=False,
                result=None,
                error=f"Failed to execute agent operation: {str(e)}. Please check your parameters and try again."
            )

    async def _handle_launch(self, agent_name: str, prompt: str, runInBackground: bool) -> ToolOutput:
        """Handle agent launch operation"""
        # Validate parameters
        if not isinstance(agent_name, str) or not isinstance(prompt, str):
            return ToolOutput(
                success=False,
                result=None,
                error="Invalid agent invocation input: agentName and prompt must be non-empty strings. Please provide a valid agent name and a descriptive task prompt."
            )

        # Resolve tool registry, provider, model, config getter, and event queue.
        # Prefer attributes set directly on the tool, but fall back to the registry
        # so the tool keeps working when the provider is injected via
        # ToolRegistry.update_tool_providers() after registration.
        tool_registry = self.tool_registry
        llm_provider = self.llm_provider or (tool_registry.llm_provider if tool_registry is not None else None)
        model = self.model or (tool_registry.model if tool_registry is not None else None)
        config_getter = tool_registry.config_getter if tool_registry is not None else None
        event_queue = tool_registry.event_queue if tool_registry is not None else None

        if tool_registry is None or llm_provider is None:
            # Build a detailed diagnostic message so the TUI shows exactly what is missing.
            missing = []
            if tool_registry is None:
                missing.append("tool_registry=None (tool was never registered into a ToolRegistry)")
            if llm_provider is None:
                reg_provider = getattr(tool_registry, "llm_provider", "<no attr>") if tool_registry is not None else "<no registry>"
                missing.append(
                    f"llm_provider=None (self.llm_provider=None, registry.llm_provider={reg_provider!r}). "
                    "This usually means update_tool_providers() was called without a provider after "
                    "the provider was set, wiping it out."
                )
            diag = " | ".join(missing)
            logger.error("agents tool initialization failure: %s", diag)
            return ToolOutput(
                success=False,
                result=None,
                error=(
                    f"Agent tool not properly initialized. Diagnostic: {diag}. "
                    "Ensure ToolRegistry.update_tool_providers(llm_provider=...) is called with a "
                    "non-None provider before any call to update_tool_providers() that omits it."
                )
            )

        # Create task ID for execution
        task_id = str(uuid.uuid4())

        if runInBackground:
            # Run in background - non-blocking
            # Create background task
            bg_task = BackgroundAgentTask(
                task_id=task_id,
                agent_name=agent_name,
                prompt=prompt,
                status="pending",
                max_tokens=128000,  # Default context window, should be fetched from model config
            )

            async with _background_lock:
                _background_agents[task_id] = bg_task

            # Emit agent tool call event
            if event_queue:
                from interface.textual_ui.types import AgentToolCallEvent
                event_queue.put_nowait(AgentToolCallEvent(
                    agent_name=agent_name,
                    prompt=prompt,
                    task_id=task_id
                ))

            # Create async task to run the agent
            async_task = asyncio.create_task(
                _run_agent_in_background(
                    task_id=task_id,
                    agent_name=agent_name,
                    prompt=prompt,
                    llm_provider=llm_provider,
                    tool_registry=tool_registry,
                    model=model,
                    config_getter=config_getter,
                    event_queue=event_queue,
                )
            )

            # Store the task reference
            async with _background_lock:
                if task_id in _background_agents:
                    _background_agents[task_id].task = async_task

            return ToolOutput(
                success=True,
                result=f"Background agent '{agent_name}' started. Task ID: {task_id}. Use operation 'status' with this task ID to check progress and get results.",
                metadata={
                    "agent": agent_name,
                    "task_id": task_id,
                    "status": "running",
                    "prompt_length": len(prompt),
                    "background": True
                }
            )
        else:
            # Run synchronously (blocking) - for backwards compatibility
            from core.agents import EXPLORE, ExploreAgent, PLAN, PlanAgent
            from core.config.settings import Settings

            if agent_name == "explore":
                def explore_config_getter() -> Settings:
                    if callable(config_getter):
                        base_settings = config_getter()
                    else:
                        base_settings = Settings()
                    merged_config = EXPLORE.apply_to_config(base_settings.model_dump())
                    return Settings(initial_config=merged_config)

                explore_registry = _FilteredToolRegistry(
                    tool_registry,
                    allowed_tools=("read", "ls", "find", "grep"),
                    llm_provider=llm_provider,
                    model=model,
                    config_getter=explore_config_getter,
                )

                subagent = ExploreAgent(
                    llm_provider=llm_provider,
                    tool_registry=explore_registry,
                    model=model,
                    config_getter=explore_config_getter,
                )
                subagent.rebuild_system_prompt()

                result = await subagent.process(prompt)

                return ToolOutput(
                    success=True,
                    result=result,
                    metadata={"agent": agent_name, "prompt_length": len(prompt), "background": False}
                )

            elif agent_name == "plan":
                def plan_config_getter() -> Settings:
                    if callable(config_getter):
                        base_settings = config_getter()
                    else:
                        base_settings = Settings()
                    merged_config = PLAN.apply_to_config(base_settings.model_dump())
                    return Settings(initial_config=merged_config)

                plan_registry = _FilteredToolRegistry(
                    tool_registry,
                    allowed_tools=("read", "ls", "find", "grep", "web_search", "fetch_webpage", "save_memory", "read_memory"),
                    llm_provider=llm_provider,
                    model=model,
                    config_getter=plan_config_getter,
                )

                subagent = PlanAgent(
                    llm_provider=llm_provider,
                    tool_registry=plan_registry,
                    model=model,
                    config_getter=plan_config_getter,
                )
                subagent.rebuild_system_prompt()

                result = await subagent.process(prompt)

                return ToolOutput(
                    success=True,
                    result=result,
                    metadata={"agent": agent_name, "prompt_length": len(prompt), "background": False}
                )

            else:
                return ToolOutput(
                    success=False,
                    result=None,
                    error=f"Unknown agent: {agent_name}. Available agents: 'explore', 'plan'"
                )

    async def _handle_status(self, taskId: str) -> ToolOutput:
        """Handle agent status operation"""
        if not isinstance(taskId, str) or not taskId:
            return ToolOutput(
                success=False,
                result=None,
                error="Invalid taskId: must be a non-empty string. Use 'list' to see all background agents."
            )

        try:
            if taskId.lower() == "list":
                # List all background agents
                agents = await list_background_agents()
                if not agents:
                    return ToolOutput(
                        success=True,
                        result="No background agents running.",
                        metadata={"count": 0}
                    )

                # Format list
                lines = [f"Total background agents: {len(agents)}\n"]
                for agent in agents:
                    lines.append(
                        f"- Task ID: {agent.task_id}\n"
                        f"  Agent: {agent.agent_name}\n"
                        f"  Status: {agent.status}\n"
                        f"  Created: {agent.created_at.strftime('%Y-%m-%d %H:%M:%S')}\n"
                    )
                    if agent.completed_at:
                        lines.append(f"  Completed: {agent.completed_at.strftime('%Y-%m-%d %H:%M:%S')}\n")

                return ToolOutput(
                    success=True,
                    result="\n".join(lines),
                    metadata={"count": len(agents), "agents": [
                        {"taskId": a.task_id, "agent": a.agent_name, "status": a.status}
                        for a in agents
                    ]}
                )

            # Get specific agent status
            agent = await get_background_agent(taskId)
            if not agent:
                return ToolOutput(
                    success=False,
                    result=None,
                    error=f"Task ID '{taskId}' not found. Use 'list' to see available background agents."
                )

            # Format the response based on status
            if agent.status == "completed":
                result_text = f"Background agent completed!\n\nOutput:\n{agent.result}"
            elif agent.status == "failed":
                result_text = f"Background agent failed!\n\nError: {agent.error}"
            elif agent.status == "running":
                result_text = f"Background agent is still running...\n\nTask: {agent.prompt[:100]}...\n\nIMPORTANT: Do NOT check status again immediately. Do OTHER meaningful work first (read files, search patterns, etc.) before checking again. Check status only when you actually need the result or have completed other tasks."
            else:
                result_text = f"Background agent status: {agent.status}\n\nDo other work before checking again."

            return ToolOutput(
                success=True,
                result=result_text,
                metadata={
                    "task_id": agent.task_id,
                    "agent": agent.agent_name,
                    "status": agent.status,
                    "prompt": agent.prompt,
                    "result": agent.result if agent.status == "completed" else None,
                    "error": agent.error if agent.status == "failed" else None,
                    "created_at": agent.created_at.isoformat(),
                    "completed_at": agent.completed_at.isoformat() if agent.completed_at else None,
                }
            )

        except Exception as e:
            return ToolOutput(
                success=False,
                result=None,
                error=f"Failed to get agent status: {str(e)}"
            )

    async def _handle_results(self, action: str, taskId: str | None = None) -> ToolOutput:
        """Handle agent results operation"""
        if not isinstance(action, str) or action not in ["check", "retrieve", "clear"]:
            return ToolOutput(
                success=False,
                result=None,
                error="Invalid action: must be 'check', 'retrieve', or 'clear'. Please provide a valid action."
            )

        try:
            if action == "check":
                # Check for completed background agents
                completed_agents = await get_completed_background_agents()
                if not completed_agents:
                    return ToolOutput(
                        success=True,
                        result="No completed background agents found.",
                        metadata={"completed_count": 0}
                    )

                # Format list of completed agents
                lines = [f"Found {len(completed_agents)} completed background agent(s):"]
                for agent in completed_agents:
                    lines.append(
                        f"- Task ID: {agent.task_id} | Agent: {agent.agent_name} | Status: {agent.status}"
                    )

                return ToolOutput(
                    success=True,
                    result="\n".join(lines),
                    metadata={
                        "completed_count": len(completed_agents),
                        "agents": [
                            {"taskId": a.task_id, "agent": a.agent_name, "status": a.status}
                            for a in completed_agents
                        ]
                    }
                )

            elif action == "retrieve":
                if taskId:
                    # Retrieve specific task
                    agent = await get_background_agent(taskId)
                    if not agent:
                        return ToolOutput(
                            success=False,
                            result=None,
                            error=f"Task ID '{taskId}' not found."
                        )
                    if agent.status != "completed":
                        return ToolOutput(
                            success=False,
                            result=None,
                            error=f"Task ID '{taskId}' is not completed (status: {agent.status})."
                        )

                    # Return the result and clear this specific task
                    await clear_completed_background_agents()

                    return ToolOutput(
                        success=True,
                        result=f"Background agent result:\n\n{agent.result}",
                        metadata={
                            "task_id": agent.task_id,
                            "agent": agent.agent_name,
                            "status": agent.status,
                            "result": agent.result,
                            "prompt": agent.prompt
                        }
                    )
                else:
                    # Retrieve all completed agents
                    completed_agents = await get_completed_background_agents()
                    if not completed_agents:
                        return ToolOutput(
                            success=True,
                            result="No completed background agents to retrieve.",
                            metadata={"retrieved_count": 0}
                        )

                    # Combine results and clear all completed tasks
                    results = []
                    metadata_list = []
                    for agent in completed_agents:
                        results.append(f"=== Agent {agent.agent_name} (Task ID: {agent.task_id}) ===")
                        results.append(f"Prompt: {agent.prompt}")
                        results.append(f"Result:\n{agent.result}")
                        results.append("")

                        metadata_list.append({
                            "taskId": agent.task_id,
                            "agent": agent.agent_name,
                            "prompt": agent.prompt,
                            "result": agent.result,
                            "status": agent.status
                        })

                    await clear_completed_background_agents()

                    return ToolOutput(
                        success=True,
                        result="\n".join(results).strip(),
                        metadata={
                            "retrieved_count": len(completed_agents),
                            "agents": metadata_list
                        }
                    )

            elif action == "clear":
                # Clear all completed background agents
                completed_agents = await get_completed_background_agents()
                cleared_count = len(completed_agents)
                await clear_completed_background_agents()

                return ToolOutput(
                    success=True,
                    result=f"Cleared {cleared_count} completed background agent(s).",
                    metadata={"cleared_count": cleared_count}
                )

        except Exception as e:
            return ToolOutput(
                success=False,
                result=None,
                error=f"Failed to process background agent results: {str(e)}"
            )




# Activity tracking for subagent view-only mode
@dataclass
class SubagentActivity:
    """Activity event from a subagent for view-only display."""
    timestamp: datetime = field(default_factory=datetime.now)
    event_type: str = "info"  # info, tool_use, tool_result, output
    message: str = ""
    tool_name: str | None = None
    tool_input: dict | None = None
    tool_output: str | None = None


# Activity registry for view-only display
_subagent_activities: dict[str, list[SubagentActivity]] = {}  # task_id -> activities


def add_subagent_activity(task_id: str, activity: SubagentActivity) -> None:
    """Add an activity event for a subagent task."""
    if task_id not in _subagent_activities:
        _subagent_activities[task_id] = []
    _subagent_activities[task_id].append(activity)


def get_subagent_activities(task_id: str) -> list[SubagentActivity]:
    """Get all activities for a subagent task."""
    return _subagent_activities.get(task_id, [])


def clear_subagent_activities(task_id: str | None = None) -> None:
    """Clear activities for a specific task or all tasks."""
    if task_id:
        _subagent_activities.pop(task_id, None)
    else:
        _subagent_activities.clear()


class AgentsTool(AgentTool):
    """Alias for AgentTool for backward compatibility"""
    name = "agents"


class AgentStatusTool(AgentTool):
    """Specialized tool for checking agent status"""
    name = "agent_status"
    description = "Check the status and results of background agents"

    input_schema = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "description": "Action to perform: 'status', 'results', or 'list'",
                "enum": ["status", "results", "list"],
                "default": "status"
            },
            "taskId": {
                "type": "string",
                "description": "Task ID for status/results queries, or 'list' for all tasks",
                "minLength": 1
            },
            "resultsAction": {
                "type": "string",
                "description": "For 'results' action: 'check', 'retrieve', or 'clear'",
                "enum": ["check", "retrieve", "clear"]
            }
        }
    }

    async def execute(self, input_data: ToolInput) -> ToolOutput:
        # Default action to 'status' if not provided
        action = self._get_param(input_data, "action") or "status"
        # If taskId not provided but action is status, default to 'list'
        taskId = self._get_param(input_data, "taskId")
        if action == "status" and not taskId:
            taskId = "list"

        # Call base execute with adjusted input
        if action == "status":
            return await self._handle_status(taskId)
        elif action == "results":
            resultsAction = self._get_param(input_data, "resultsAction") or "check"
            return await self._handle_results(resultsAction, taskId)
        elif action == "list":
            return await self._handle_status("list")

        return await super().execute(input_data)