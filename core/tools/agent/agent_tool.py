"""Main agent tool class for subagent management."""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any

from core.tools.base import BaseTool, ToolInput, ToolOutput
from .background_task import (
    BackgroundAgentTask,
    _background_agents,
    _background_lock,
    get_background_agent,
    list_background_agents,
    get_completed_background_agents,
    clear_completed_background_agents,
)
from .agent_lifecycle import _run_agent_in_background
from .agent_memory import SubagentActivity, add_subagent_activity
from .constants import (
    AGENT_TOOL_NAME,
    DEFAULT_MAX_TOKENS,
    EXPLORE_ALLOWED_TOOLS,
    PLAN_ALLOWED_TOOLS,
    JARVIS_HELP_ALLOWED_TOOLS,
    VERIFICATION_ALLOWED_TOOLS,
    STATUSLINE_SETUP_ALLOWED_TOOLS,
)
from .filtered_registry import _FilteredToolRegistry
from .utils import get_agent_param
from datetime import datetime

logger = logging.getLogger(__name__)


class AgentTool(BaseTool):
    """Primary agent management tool - unified interface for all subagent operations.

    Use this tool whenever you need to:
    1. Delegate tasks to specialized subagents (explore/plan/jarvis-help/verification/statusline-setup)
    2. Get immediate results from subagents (foreground mode)
    3. Monitor progress of background agent tasks
    4. Retrieve results from completed background work

    Usage rules (Foreground is recommended):
    - Prefer runInBackground=false (default): Agent runs synchronously, tool calls appear in your conversation, you get results immediately
    - Only use runInBackground=true when you need to do other work while waiting for a long-running task
    - When using background mode, use 'status' or 'results' action to check progress and get results
    - Use 'list' operation to see all active agents before launching new ones

    Available subagents:
    - explore: Codebase exploration, file analysis, pattern finding (read-only)
    - plan: Task decomposition, implementation planning, architecture design (read-only)
    - jarvis-help: Guidance on JARVIS features, tools, and configuration (read-only)
    - verification: Post-implementation testing and adversarial verification (read/write)
    - statusline-setup: Shell prompt customization guidance (read-only)
    """
    name = "agents"
    description = "Launch subagents (explore/plan/jarvis-help/verification/statusline-setup) for codebase analysis, planning, help, and testing. Defaults to foreground mode for immediate results."

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
                "description": "Run agent in background (async) or foreground (sync, default). Use false for immediate results in your conversation.",
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
        return get_agent_param(input_data, *names)

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
            else:
                # This should never happen due to validation above, but type checker needs it
                return ToolOutput(
                    success=False,
                    result=None,
                    error="Internal error: unhandled action type"
                )

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
                max_tokens=DEFAULT_MAX_TOKENS,
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
            from core.agents.builtin.jarvis_help_agent import JarvisHelpAgent
            from core.agents.builtin.verification_agent import VerificationAgent
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
                    allowed_tools=EXPLORE_ALLOWED_TOOLS,
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
                    allowed_tools=PLAN_ALLOWED_TOOLS,
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

            elif agent_name == "jarvis-help":
                def help_config_getter() -> Settings:
                    if callable(config_getter):
                        return config_getter()
                    return Settings()

                help_registry = _FilteredToolRegistry(
                    tool_registry,
                    allowed_tools=JARVIS_HELP_ALLOWED_TOOLS,
                    llm_provider=llm_provider,
                    model=model,
                    config_getter=help_config_getter,
                )

                subagent = JarvisHelpAgent(
                    llm_provider=llm_provider,
                    tool_registry=help_registry,
                    model=model,
                    config_getter=help_config_getter,
                )
                subagent.rebuild_system_prompt()

                result = await subagent.process(prompt)

                return ToolOutput(
                    success=True,
                    result=result,
                    metadata={"agent": agent_name, "prompt_length": len(prompt), "background": False}
                )

            elif agent_name == "verification":
                def verify_config_getter() -> Settings:
                    if callable(config_getter):
                        return config_getter()
                    return Settings()

                verify_registry = _FilteredToolRegistry(
                    tool_registry,
                    allowed_tools=VERIFICATION_ALLOWED_TOOLS,
                    llm_provider=llm_provider,
                    model=model,
                    config_getter=verify_config_getter,
                )

                subagent = VerificationAgent(
                    llm_provider=llm_provider,
                    tool_registry=verify_registry,
                    model=model,
                    config_getter=verify_config_getter,
                )
                subagent.rebuild_system_prompt()

                result = await subagent.process(prompt)

                return ToolOutput(
                    success=True,
                    result=result,
                    metadata={"agent": agent_name, "prompt_length": len(prompt), "background": False}
                )

            elif agent_name == "statusline-setup":
                # statusline-setup is read-only guidance
                return ToolOutput(
                    success=True,
                    result=f"I can help with statusline customization for bash, zsh, PowerShell, and other shells.\n\n{prompt}",
                    metadata={"agent": agent_name, "prompt_length": len(prompt), "background": False}
                )

            else:
                return ToolOutput(
                    success=False,
                    result=None,
                    error=f"Unknown agent: {agent_name}. Available agents: 'explore', 'plan', 'jarvis-help', 'verification', 'statusline-setup'"
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
            else:
                # This should never happen due to validation above, but type checker needs it
                return ToolOutput(
                    success=False,
                    result=None,
                    error="Internal error: unhandled results action type"
                )

        except Exception as e:
            return ToolOutput(
                success=False,
                result=None,
                error=f"Failed to process background agent results: {str(e)}"
            )


class AgentsTool(AgentTool):
    """Alias for AgentTool for backward compatibility."""
    name = "agents"


class AgentStatusTool(AgentTool):
    """Specialized tool for checking agent status.
    
    This tool provides a simpler interface focused on status and results
    operations for background agents.
    """
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


import asyncio  # Required for create_task