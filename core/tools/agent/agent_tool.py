"""Main agent tool class for subagent management.

Subagent results are delivered via push notifications (the notification queue),
not polling. The main agent's loop automatically drains notifications each turn
and injects them as context - no explicit status/results polling needed.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any

from core.tools.base import BaseTool, ToolInput, ToolOutput, resolve_tool_ref

from .agent_lifecycle import _run_agent_in_background
from .background_task import (
    BackgroundAgentTask,
    _background_agents,
    _background_lock,
)
from .constants import (
    DEFAULT_MAX_TOKENS,
    EXPLORE_ALLOWED_TOOLS,
    JARVIS_HELP_ALLOWED_TOOLS,
    PLAN_ALLOWED_TOOLS,
    RUBBER_DUCK_ALLOWED_TOOLS,
    VERIFICATION_ALLOWED_TOOLS,
)
from .filtered_registry import _FilteredToolRegistry
from .utils import create_agent, make_config_getter

logger = logging.getLogger(__name__)


class AgentTool(BaseTool):
    """Primary agent management tool - unified interface for all subagent operations.

    Use this tool whenever you need to:
    1. Delegate tasks to specialized subagents (explore/plan/jarvis-help/verification/rubber-duck/statusline-setup)
    2. Get immediate results from subagents (foreground mode - recommended)

    Subagent completion is handled automatically via push notifications:
    - Foreground mode: blocks until done, result is returned + enqueued as notification
    - Background mode: returns immediately, notification is pushed to the main agent on completion

    Available subagents:
    - explore: Codebase exploration, file analysis, pattern finding (read-only)
    - plan: Task decomposition, implementation planning, architecture design (read-only)
    - jarvis-help: Guidance on JARVIS features, tools, and configuration (read-only)
    - verification: Post-implementation testing and adversarial verification (read/write)
    - rubber-duck: Constructive critique and review of proposals, designs, implementations (read-only)
    - statusline-setup: Shell prompt customization guidance (read-only)
    """
    name = "agents"
    description = "Launch specialized subagents (explore, plan, jarvis-help, verification, rubber-duck, statusline-setup) for delegating codebase analysis, implementation planning, documentation/help lookups, post-implementation testing, constructive critique/review, and shell prompt customization. Foreground mode (default, runInBackground=false): subagent runs synchronously, results appear inline in your conversation and you get them immediately — no extra steps needed. Background mode (runInBackground=true): subagent starts and returns control to you right away; when it finishes, a <task-notification> XML message is automatically injected into your conversation by the system so you never need to manually poll or check status. If you launch multiple background agents, each one's notification will arrive independently as they complete. Use list_agents to discover available subagent types and their capabilities."

    input_schema = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "description": "Operation to perform: 'launch' to delegate a task to a subagent (default), 'list_agents' to see all available subagent types with descriptions, 'list_tasks' to see currently running background tasks",
                "enum": ["launch", "list_agents", "list_tasks"],
                "default": "launch",
            },
            "agentName": {
                "type": "string",
                "description": "Which subagent to use. Available: explore (read-only codebase analysis, file searching, pattern finding), plan (task decomposition and implementation planning), jarvis-help (JARVIS features, tools, and configuration guidance), verification (post-implementation testing and quality assurance), rubber-duck (constructive critique and review of proposals, designs, implementations, or tests), statusline-setup (shell prompt customization). Use list_agents to see full descriptions.",
                "minLength": 1
            },
            "prompt": {
                "type": "string",
                "description": "Clear, detailed task description for the subagent. Include specific files, patterns, or requirements. The subagent will work autonomously on this prompt.",
                "minLength": 1
            },
            "runInBackground": {
                "type": "boolean",
                "description": "False (default, recommended): subagent runs synchronously, results appear in your conversation immediately. True: subagent runs asynchronously in the background; you'll receive an automatic <task-notification> XML message when it completes — no manual polling needed. Only use background when you have other work to do while waiting.",
                "default": False
            },
        },
    }

    async def execute(self, input_data: ToolInput) -> ToolOutput:
        action = self._get_param(input_data, "action")
        agent_name = self._get_param(input_data, "agentName")
        prompt = self._get_param(input_data, "prompt")
        runInBackground = self._get_param(input_data, "runInBackground", "run_in_background") or False
        tool_use_id = self._get_param(input_data, "tool_use_id") or ""

        if action is None:
            if isinstance(agent_name, str) and isinstance(prompt, str):
                action = "launch"
            else:
                action = "list_agents"

        if action not in ["launch", "list_agents", "list_tasks"]:
            return ToolOutput(
                success=False,
                result=None,
                error=f"Invalid action: {action}. Must be 'launch', 'list_agents', or 'list_tasks'."
            )

        try:
            if action == "launch":
                return await self._handle_launch(agent_name, prompt, runInBackground, tool_use_id)
            elif action == "list_agents":
                return await self._handle_list_agents()
            elif action == "list_tasks":
                return await self._handle_list_tasks()
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
            "rubber-duck": "Constructive critique and review of proposals, designs, implementations, or tests. Best called after planning but before implementing.",
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
            desc = getattr(agent, "description", "Custom agent (no description provided)")
            lines.append(f"- {agent.name}: {desc}")
            agent_data.append({"name": agent.name, "description": desc, "source": "custom"})

        return ToolOutput(
            success=True,
            result="\n".join(lines),
            metadata={"agents": agent_data}
        )


    async def _handle_launch(self, agent_name: str, prompt: str, runInBackground: bool, tool_use_id: str = "") -> ToolOutput:
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
                    tool_use_id=tool_use_id,
                )
            )

            # Store the task reference
            async with _background_lock:
                if task_id in _background_agents:
                    _background_agents[task_id].task = async_task

            return ToolOutput(
                success=True,
                result=f"Background agent '{agent_name}' started. Task ID: {task_id}. You'll be notified automatically when it completes.",
                metadata={
                    "agent": agent_name,
                    "task_id": task_id,
                    "status": "running",
                    "prompt_length": len(prompt),
                    "background": True
                }
            )
        else:
            # Run synchronously (blocking) - foreground mode
            import time

            from core.agents import EXPLORE, PLAN
            from core.agents.notification_queue import enqueue_agent_notification

            _agent_allowed = {
                "explore": EXPLORE_ALLOWED_TOOLS,
                "plan": PLAN_ALLOWED_TOOLS,
                "jarvis-help": JARVIS_HELP_ALLOWED_TOOLS,
                "verification": VERIFICATION_ALLOWED_TOOLS,
                "rubber-duck": RUBBER_DUCK_ALLOWED_TOOLS,
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

                start_time = time.time()
                result = await subagent.process(prompt)
                duration_ms = (time.time() - start_time) * 1000

                # Enqueue notification for foreground agent completion
                # This ensures the main agent loop picks it up as context
                token_usage = 0
                if isinstance(result, dict) and "usage" in result:
                    token_usage = result.get("usage", {}).get("total_tokens", 0)

                enqueue_agent_notification(
                    task_id=task_id,
                    agent_name=agent_name,
                    status="completed",
                    summary=f"Subagent '{agent_name}' completed",
                    result=result,
                    tool_use_id=tool_use_id,
                    total_tokens=token_usage,
                    duration_ms=duration_ms,
                )

                return ToolOutput(
                    success=True,
                    result=result,
                    metadata={"agent": agent_name, "prompt_length": len(prompt), "background": False, "task_id": task_id}
                )

            elif agent_name == "statusline-setup":
                # statusline-setup is read-only guidance
                result = f"I can help with statusline customization for bash, zsh, PowerShell, and other shells.\n\n{prompt}"
                return ToolOutput(
                    success=True,
                    result=result,
                    metadata={"agent": agent_name, "prompt_length": len(prompt), "background": False, "task_id": task_id}
                )

            else:
                # Try loading custom agents from .jarvis/agents/
                from core.agents.custom_loader import discover_custom_agents
                custom_agents = discover_custom_agents()
                custom_agent = next((a for a in custom_agents if a.name == agent_name), None)

                if custom_agent:
                    return await self._handle_custom_agent(
                        custom_agent, prompt, llm_provider, tool_registry, model, config_getter, tool_use_id
                    )

                # Build list of available agents
                builtin_agents = ['explore', 'plan', 'jarvis-help', 'verification', 'rubber-duck', 'statusline-setup']
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
        tool_use_id: str = "",
    ) -> ToolOutput:
        """Handle a custom agent loaded from .jarvis/agents/"""
        import time

        from core.agents.notification_queue import enqueue_agent_notification
        from core.config.settings import Settings

        def custom_config_getter() -> Any:
            if callable(config_getter):
                return config_getter()
            return Settings()

        # Create filtered registry based on agent definition
        allowed_tools = getattr(definition, "tools", None)
        disallowed_tools = getattr(definition, "disallowed_tools", None)

        if allowed_tools:
            # Resolve tool refs (str/class/instance) to string names
            resolved = [resolve_tool_ref(t) for t in allowed_tools]
            if "*" not in resolved:
                # Explicit tool whitelist (not wildcard)
                custom_registry = _FilteredToolRegistry(
                    tool_registry,
                    allowed_tools=resolved,
                    llm_provider=llm_provider,
                    model=model,
                    config_getter=custom_config_getter,
                )
            else:
                custom_registry = tool_registry
        elif disallowed_tools:
            # Filter out disallowed tools from the full set
            all_tools = set(tool_registry.get_tools().keys())
            allowed = [t for t in all_tools if t not in disallowed_tools]
            custom_registry = _FilteredToolRegistry(
                tool_registry,
                allowed_tools=allowed,
                llm_provider=llm_provider,
                model=model,
                config_getter=custom_config_getter,
            )
        else:
            custom_registry = tool_registry

        # Get system prompt from definition if available
        system_prompt = ""
        get_prompt_fn = getattr(definition, "system_prompt", None)
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

        task_id = str(uuid.uuid4())
        start_time = time.time()
        result = await subagent.process(prompt)
        duration_ms = (time.time() - start_time) * 1000

        enqueue_agent_notification(
            task_id=task_id,
            agent_name=definition.name,
            status="completed",
            summary=f"Subagent '{definition.name}' completed",
            result=result,
            tool_use_id=tool_use_id,
            duration_ms=duration_ms,
        )

        return ToolOutput(
            success=True,
            result=result,
            metadata={"agent": definition.name, "prompt_length": len(prompt), "background": False, "task_id": task_id}
        )

    async def _handle_list_tasks(self) -> ToolOutput:
        """List currently running background agents (info only - not for polling)."""
        from .background_task import list_background_agents

        agents = await list_background_agents()
        if not agents:
            return ToolOutput(
                success=True,
                result="No background agents running.",
                metadata={"count": 0}
            )

        lines = [f"Background agents: {len(agents)}"]
        for agent in agents:
            status_icon = "🔄" if agent.status == "running" else "✅" if agent.status == "completed" else "❌"
            lines.append(f"  {status_icon} Task: {agent.task_id[:8]} | Agent: {agent.agent_name} | Status: {agent.status} | Activity: {agent.current_activity or 'idle'}")

        return ToolOutput(
            success=True,
            result="\n".join(lines),
            metadata={"count": len(agents)}
        )


class AgentsTool(AgentTool):
    """Alias for AgentTool for backward compatibility."""
    name = "agents"


