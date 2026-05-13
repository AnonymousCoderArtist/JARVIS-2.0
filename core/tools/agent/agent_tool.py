"""Main agent tool class for subagent management."""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any

from core.tools.base import BaseTool, ToolInput, ToolOutput

from .agent_lifecycle import _run_agent_in_background
from .background_task import (
    BackgroundAgentTask,
    _background_agents,
    _background_lock,
    clear_completed_background_agents,
    get_background_agent,
    get_completed_background_agents,
    list_background_agents,
)
from .constants import (
    DEFAULT_MAX_TOKENS,
    EXPLORE_ALLOWED_TOOLS,
    JARVIS_HELP_ALLOWED_TOOLS,
    PLAN_ALLOWED_TOOLS,
    VERIFICATION_ALLOWED_TOOLS,
)
from .filtered_registry import _FilteredToolRegistry
from .utils import create_agent, get_agent_param, make_config_getter

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
                "description": "Action to perform: 'launch', 'list_agents', 'list_tasks', 'status', 'results'",
                "enum": ["launch", "list_agents", "list_tasks", "status", "results"],
                "default": "launch",
            },
            "agentName": {
                "type": "string",
                "description": "Name of specialized subagent to launch",
                "minLength": 1
            },
            "prompt": {
                "type": "string",
                "description": "Task description to send to the subagent",
                "minLength": 1
            },
            "runInBackground": {
                "type": "boolean",
                "description": "Run agent in background (async) or foreground (sync).",
                "default": False
            },
            "taskId": {
                "type": "string",
                "description": "Task ID for status/results queries",
                "minLength": 1
            },
            "resultsAction": {
                "type": "string",
                "description": "For 'results' action: 'check', 'retrieve', or 'clear'",
                "enum": ["check", "retrieve", "clear"]
            }
        },
    }

    async def execute(self, input_data: ToolInput) -> ToolOutput:
        # Get parameters
        action = self._get_param(input_data, "action")
        agent_name = self._get_param(input_data, "agentName")
        prompt = self._get_param(input_data, "prompt")
        runInBackground = self._get_param(input_data, "runInBackground", "run_in_background") or False
        taskId = self._get_param(input_data, "taskId")
        resultsAction = self._get_param(input_data, "resultsAction")

        # Backwards-compatible inference
        if action is None:
            if isinstance(agent_name, str) and isinstance(prompt, str):
                action = "launch"
            elif isinstance(resultsAction, str):
                action = "results"
            elif isinstance(taskId, str):
                action = "status"
            else:
                action = "list_agents"

        # Validate action
        if action not in ["launch", "list_agents", "list_tasks", "status", "results"]:
            return ToolOutput(
                success=False,
                result=None,
                error=f"Invalid action: {action}. Must be 'launch', 'list_agents', 'list_tasks', 'status', or 'results'."
            )

        try:
            if action == "launch":
                return await self._handle_launch(agent_name, prompt, runInBackground)
            elif action == "list_agents":
                return await self._handle_list_agents()
            elif action == "list_tasks":
                return await self._handle_status("list")
            elif action == "status":
                return await self._handle_status(taskId)
            elif action == "results":
                return await self._handle_results(resultsAction, taskId)
            else:
                return ToolOutput(success=False, result=None, error="Internal error: unhandled action")

        except Exception as e:
            return ToolOutput(success=False, result=None, error=f"Operation failed: {str(e)}")

    async def _handle_list_agents(self) -> ToolOutput:
        """List all available agent types with their descriptions."""
        from core.agents.custom_loader import discover_custom_agents
        
        # Define built-in agent metadata
        builtin_definitions = {
            "explore": "Codebase exploration, file analysis, and pattern finding. Best for read-only investigative tasks.",
            "plan": "Task decomposition, architecture design, and implementation planning. Best for breaking down complex requirements.",
            "jarvis-help": "General assistance and guidance on JARVIS features, custom tools, and configuration.",
            "verification": "Post-implementation testing, adversarial verification, and quality assurance.",
            "statusline-setup": "Guidance and scripts for customizing your shell prompt (bash, zsh, powershell)."
        }
        
        custom_agents = discover_custom_agents()
        
        lines = ["Available subagents:"]
        agent_data = []

        # Add built-ins
        for name, desc in builtin_definitions.items():
            lines.append(f"- {name}: {desc}")
            agent_data.append({"name": name, "description": desc, "source": "built-in"})
            
        # Add customs
        for agent in custom_agents:
            desc = getattr(agent, "when_to_use", "Custom agent (no description provided)")
            lines.append(f"- {agent.name}: {desc}")
            agent_data.append({"name": agent.name, "description": desc, "source": "custom"})
        
        return ToolOutput(
            success=True,
            result="\n".join(lines),
            metadata={"agents": agent_data}
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
            from core.agents import EXPLORE, PLAN
            from core.config.settings import Settings

            _agent_allowed = {
                "explore": EXPLORE_ALLOWED_TOOLS,
                "plan": PLAN_ALLOWED_TOOLS,
                "jarvis-help": JARVIS_HELP_ALLOWED_TOOLS,
                "verification": VERIFICATION_ALLOWED_TOOLS,
            }

            if agent_name in _agent_allowed:
                profile = {
                    "explore": EXPLORE,
                    "plan": PLAN,
                }.get(agent_name)
                conf_getter = make_config_getter(config_getter, profile)
                subagent = create_agent(
                    agent_name=agent_name,
                    llm_provider=llm_provider,
                    tool_registry=tool_registry,
                    model=model,
                    config_getter=conf_getter,
                    allowed_tools=_agent_allowed[agent_name],
                )
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
                # Try loading custom agents from .jarvis/agents/
                from core.agents.custom_loader import discover_custom_agents
                custom_agents = discover_custom_agents()
                custom_agent = next((a for a in custom_agents if a.name == agent_name), None)

                if custom_agent:
                    return await self._handle_custom_agent(
                        custom_agent, prompt, llm_provider, tool_registry, model, config_getter
                    )

                # Build list of available agents
                builtin_agents = ['explore', 'plan', 'jarvis-help', 'verification', 'statusline-setup']
                custom_names = [a.name for a in custom_agents]
                all_agents = builtin_agents + custom_names

                return ToolOutput(
                    success=False,
                    result=None,
                    error=f"Unknown agent: {agent_name}. Available agents: {', '.join(all_agents)}"
                )

    async def _handle_custom_agent(
        self,
        definition,
        prompt: str,
        llm_provider,
        tool_registry,
        model,
        config_getter,
    ) -> ToolOutput:
        """Handle a custom agent loaded from .jarvis/agents/"""
        from core.config.settings import Settings
        from typing import Any

        def custom_config_getter() -> Any:
            if callable(config_getter):
                return config_getter()
            return Settings()

        # Create filtered registry based on agent definition
        allowed_tools = getattr(definition, "tools", None)

        if allowed_tools:
            custom_registry = _FilteredToolRegistry(
                tool_registry,
                allowed_tools=allowed_tools,
                llm_provider=llm_provider,
                model=model,
                config_getter=custom_config_getter,
            )
        else:
            custom_registry = tool_registry

        # Get system prompt from definition if available
        system_prompt = ""
        get_prompt_fn = getattr(definition, "get_system_prompt", None)
        if callable(get_prompt_fn):
            result = get_prompt_fn()
            system_prompt = result if isinstance(result, str) else ""

        # Create agent instance dynamically
        from core.agents.base import BaseAgent

        class CustomAgent(BaseAgent):
            def __init__(self, llm_provider, tool_registry, system_prompt: str = "", model=None, config_getter=None):
                super().__init__(
                    llm_provider=llm_provider,
                    tool_registry=tool_registry,
                    system_prompt=system_prompt,
                    model=model,
                    config_getter=config_getter,
                )
                self.rebuild_system_prompt()

            async def process(self, input: str, context: dict | None = None) -> str:
                messages = self._build_messages(input, include_memory=False)
                return await self._process_with_tools(messages, stream=False)

            async def plan(self, task: str) -> list[dict[str, Any]]:
                """Required abstract method implementation."""
                return [{"action": "custom_agent_process", "input": task}]

        subagent = CustomAgent(
            llm_provider=llm_provider,
            tool_registry=custom_registry,
            system_prompt=system_prompt,
            model=model,
            config_getter=custom_config_getter,
        )

        result = await subagent.process(prompt)

        return ToolOutput(
            success=True,
            result=result,
            metadata={"agent": definition.name, "prompt_length": len(prompt), "background": False}
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