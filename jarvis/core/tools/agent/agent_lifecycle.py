"""Agent lifecycle management - background execution and agent creation.

This module handles the creation and execution of subagents with support for
fork-based isolation using git worktrees and memory inheritance.
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime
from typing import Any

from .background_task import (
    _background_agents,
    _background_lock,
)
from .constants import (
    EXPLORE_ALLOWED_TOOLS,
    JARVIS_HELP_ALLOWED_TOOLS,
    PLAN_ALLOWED_TOOLS,
    VERIFICATION_ALLOWED_TOOLS,
)
from .fork_subagent import (
    ForkMetadata,
    complete_fork,
    create_fork_subagent,
    track_fork,
)

logger = logging.getLogger(__name__)


def _enqueue_completion_notification(
    task_id: str,
    agent_name: str,
    status: str,
    result: str = "",
    error: str = "",
    tool_uses: int = 0,
    token_usage: int = 0,
    duration_ms: float = 0.0,
    tool_use_id: str = "",
    worktree_path: str = "",
    worktree_branch: str = "",
) -> None:
    """Enqueue a notification for the main agent about subagent completion."""
    from jarvis.core.agents.notification_queue import enqueue_agent_notification

    summary = f"Subagent '{agent_name}' {status}"
    if error:
        summary += f" - {error}"

    enqueue_agent_notification(
        task_id=task_id,
        agent_name=agent_name,
        status=status,
        summary=summary,
        result=result or error,
        tool_use_id=tool_use_id,
        total_tokens=token_usage,
        tool_uses=tool_uses,
        duration_ms=duration_ms,
        worktree_path=worktree_path,
        worktree_branch=worktree_branch,
    )


async def _run_agent_in_background(
    task_id: str,
    agent_name: str,
    prompt: str,
    llm_provider,
    tool_registry,
    model,
    config_getter,
    event_queue=None,
    tool_use_id: str = "",
):
    """Run an agent in the background and update status when done.

    Args:
        task_id: Unique task identifier
        agent_name: Name of the agent type to run
        prompt: The prompt/task for the agent
        llm_provider: LLM provider instance
        tool_registry: Tool registry for tool execution
        model: Model name to use
        config_getter: Configuration getter function
        event_queue: Optional event queue for UI updates
        tool_use_id: The tool call ID that launched this subagent
    """
    from jarvis.core.agents import EXPLORE, PLAN

    from .utils import create_agent, extract_token_usage, make_config_getter

    start_time = time.time()
    notified = False  # Prevent duplicate notifications
    last_progress_tool_count = 0  # Track for progress emission

    # Define callback to track tool usage and emit progress
    def _on_tool_call(tool_name: str, tool_args: dict) -> None:
        """Increment tool usage counter and emit progress updates."""
        import asyncio
        async def _update():
            nonlocal last_progress_tool_count
            async with _background_lock:
                if task_id in _background_agents:
                    task = _background_agents[task_id]
                    task.tool_uses += 1
                    task.current_activity = f"{tool_name}"
                    tool_count = task.tool_uses

                    # Emit progress update every 3 tool calls
                    if tool_count - last_progress_tool_count >= 3:
                        last_progress_tool_count = tool_count
                        from jarvis.core.agents.notification_queue import enqueue_progress_update
                        enqueue_progress_update(
                            task_id=task_id,
                            agent_name=agent_name,
                            progress=min(0.9, tool_count * 0.05),
                            activity=f"Currently using {tool_name}",
                        )

        asyncio.create_task(_update())

    def _on_tool_result(tool_name: str, tool_args: dict[str, Any], result: Any) -> None:
        """Clear current activity after tool completes."""
        import asyncio
        async def _update():
            async with _background_lock:
                if task_id in _background_agents:
                    _background_agents[task_id].current_activity = ""
        asyncio.create_task(_update())

    callbacks = {"tool_call": _on_tool_call, "tool_result": _on_tool_result}

    try:
        # Update status to running
        async with _background_lock:
            if task_id in _background_agents:
                _background_agents[task_id].status = "running"

        # Create the appropriate subagent
        if agent_name == "explore":
            from .utils import make_config_getter
            conf_getter = make_config_getter(config_getter, EXPLORE)
            subagent = create_agent(
                agent_name="explore",
                llm_provider=llm_provider,
                tool_registry=tool_registry,
                model=model,
                config_getter=conf_getter,
                allowed_tools=EXPLORE_ALLOWED_TOOLS,
                callbacks=callbacks,
            )

        elif agent_name == "plan":
            conf_getter = make_config_getter(config_getter, PLAN)
            subagent = create_agent(
                agent_name="plan",
                llm_provider=llm_provider,
                tool_registry=tool_registry,
                model=model,
                config_getter=conf_getter,
                allowed_tools=PLAN_ALLOWED_TOOLS,
                callbacks=callbacks,
            )

        elif agent_name == "jarvis-help":
            conf_getter = make_config_getter(config_getter)
            subagent = create_agent(
                agent_name="jarvis-help",
                llm_provider=llm_provider,
                tool_registry=tool_registry,
                model=model,
                config_getter=conf_getter,
                allowed_tools=JARVIS_HELP_ALLOWED_TOOLS,
                callbacks=callbacks,
            )

        elif agent_name == "verification":
            conf_getter = make_config_getter(config_getter)
            subagent = create_agent(
                agent_name="verification",
                llm_provider=llm_provider,
                tool_registry=tool_registry,
                model=model,
                config_getter=conf_getter,
                allowed_tools=VERIFICATION_ALLOWED_TOOLS,
                callbacks=callbacks,
            )

        elif agent_name == "statusline-setup":
            # statusline-setup is a read-only guidance agent (no edit/bash tools)
            result = "I can help with statusline customization for bash, zsh, PowerShell, and other shells. " + prompt
            async with _background_lock:
                if task_id in _background_agents:
                    _background_agents[task_id].status = "completed"
                    _background_agents[task_id].result = result
                    _background_agents[task_id].completed_at = datetime.now()
            duration_ms = (time.time() - start_time) * 1000
            _enqueue_completion_notification(
                task_id=task_id,
                agent_name=agent_name,
                status="completed",
                result=result,
                duration_ms=duration_ms,
                tool_use_id=tool_use_id,
            )
            notified = True
            return

        else:
            async with _background_lock:
                if task_id in _background_agents:
                    _background_agents[task_id].status = "failed"
                    _background_agents[task_id].error = f"Unknown agent: {agent_name}"
                    _background_agents[task_id].completed_at = datetime.now()
            duration_ms = (time.time() - start_time) * 1000
            _enqueue_completion_notification(
                task_id=task_id,
                agent_name=agent_name,
                status="failed",
                error=f"Unknown agent: {agent_name}",
                duration_ms=duration_ms,
                tool_use_id=tool_use_id,
            )
            notified = True
            return

        # Execute the task
        result = await subagent.process(prompt)
        token_usage = extract_token_usage(result)
        duration_ms = (time.time() - start_time) * 1000

        # Update with result and enqueue notification
        async with _background_lock:
            if task_id in _background_agents:
                task = _background_agents[task_id]
                task.status = "completed"
                task.result = result
                task.token_usage = token_usage
                task.completed_at = datetime.now()
                tool_uses = task.tool_uses

                _enqueue_completion_notification(
                    task_id=task_id,
                    agent_name=agent_name,
                    status="completed",
                    result=result,
                    tool_uses=tool_uses,
                    token_usage=token_usage,
                    duration_ms=duration_ms,
                    tool_use_id=tool_use_id,
                )
                notified = True

    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        async with _background_lock:
            if task_id in _background_agents:
                task = _background_agents[task_id]
                task.status = "failed"
                task.error = str(e)
                task.completed_at = datetime.now()
                tool_uses = task.tool_uses

                _enqueue_completion_notification(
                    task_id=task_id,
                    agent_name=agent_name,
                    status="failed",
                    error=str(e),
                    tool_uses=tool_uses,
                    duration_ms=duration_ms,
                    tool_use_id=tool_use_id,
                )
                notified = True


async def _run_forked_agent(
    task_id: str,
    agent_name: str,
    prompt: str,
    llm_provider,
    tool_registry,
    model,
    config_getter,
    event_queue=None,
    inherit_memory: list[dict[str, Any]] | None = None,
    fork_config: dict[str, Any] | None = None,
    tool_use_id: str = "",
):
    """Run a forked agent with worktree isolation and context inheritance.

    This function provides OpenCLaude-style fork subagent functionality with:
    - Git worktree-based isolation
    - Message forking for context inheritance
    - Isolated environment variables
    - Memory snapshot management

    Args:
        task_id: Unique task identifier
        agent_name: Name of the agent type to run
        prompt: The prompt/task for the agent (may contain fork markers)
        llm_provider: LLM provider instance
        tool_registry: Tool registry for tool execution
        model: Model name to use
        config_getter: Configuration getter function
        event_queue: Optional event queue for UI updates
        inherit_memory: Optional memory to inherit from parent agent
        fork_config: Optional configuration from fork marker in prompt
        tool_use_id: The tool call ID that launched this subagent
    """
    from jarvis.core.tools.agent.constants import (
        EXPLORE_ALLOWED_TOOLS,
        JARVIS_HELP_ALLOWED_TOOLS,
        PLAN_ALLOWED_TOOLS,
        VERIFICATION_ALLOWED_TOOLS,
    )

    from .utils import extract_token_usage

    start_time = time.time()

    start_time = time.time()
    last_progress_tool_count = 0

    # Define callback to track tool usage and emit progress
    def _on_tool_call(tool_name: str, tool_args: dict) -> None:
        """Increment tool usage counter and emit progress updates."""
        async def _update():
            nonlocal last_progress_tool_count
            async with _background_lock:
                if task_id in _background_agents:
                    task = _background_agents[task_id]
                    task.tool_uses += 1
                    task.current_activity = f"{tool_name}"
                    tool_count = task.tool_uses

                    # Emit progress update every 3 tool calls
                    if tool_count - last_progress_tool_count >= 3:
                        last_progress_tool_count = tool_count
                        from jarvis.core.agents.notification_queue import enqueue_progress_update
                        enqueue_progress_update(
                            task_id=task_id,
                            agent_name=agent_name,
                            progress=min(0.9, tool_count * 0.05),
                            activity=f"Currently using {tool_name}",
                        )

        asyncio.create_task(_update())

    def _on_tool_result(tool_name: str, tool_args: dict[str, Any], result: Any) -> None:
        """Clear current activity after tool completes"""
        async def _update():
            async with _background_lock:
                if task_id in _background_agents:
                    _background_agents[task_id].current_activity = ""
        asyncio.create_task(_update())

    fork_metadata: ForkMetadata | None = None

    try:
        # Update status to running
        async with _background_lock:
            if task_id in _background_agents:
                _background_agents[task_id].status = "running"

        # Create forked subagent with enhanced capabilities
        subagent, fork_metadata = create_fork_subagent(
            agent_name=agent_name,
            prompt=prompt,
            llm_provider=llm_provider,
            tool_registry=tool_registry,
            model=model,
            config_getter=config_getter,
            allowed_tools={
                "explore": EXPLORE_ALLOWED_TOOLS,
                "plan": PLAN_ALLOWED_TOOLS,
                "jarvis-help": JARVIS_HELP_ALLOWED_TOOLS,
                "verification": VERIFICATION_ALLOWED_TOOLS,
            }.get(agent_name, ()),
            parent_task_id=task_id,
            inherit_memory=inherit_memory,
            fork_config=fork_config,
        )

        # Track the fork for lifecycle management
        await track_fork(fork_metadata)

        # Set callbacks for metrics tracking
        subagent.tool_call_callback = _on_tool_call
        subagent.tool_result_callback = _on_tool_result
        subagent.rebuild_system_prompt()

        # Execute the task
        result = await subagent.process(prompt)

        # Try to capture token usage from result if available
        token_usage = extract_token_usage(result)
        duration_ms = (time.time() - start_time) * 1000

        # Update with result and enqueue notification
        async with _background_lock:
            if task_id in _background_agents:
                task = _background_agents[task_id]
                task.status = "completed"
                task.result = result
                task.token_usage = token_usage
                task.completed_at = datetime.now()
                tool_uses = task.tool_uses

                _enqueue_completion_notification(
                    task_id=task_id,
                    agent_name=agent_name,
                    status="completed",
                    result=result,
                    tool_uses=tool_uses,
                    token_usage=token_usage,
                    duration_ms=duration_ms,
                    tool_use_id=tool_use_id,
                    worktree_path=str(fork_metadata.worktree_path) if fork_metadata and fork_metadata.worktree_path else "",
                    worktree_branch="",
                )

        # Complete fork tracking and cleanup
        if fork_metadata:
            await complete_fork(fork_metadata.fork_id, status="completed")

    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        # Update error status and enqueue notification
        async with _background_lock:
            if task_id in _background_agents:
                task = _background_agents[task_id]
                task.status = "failed"
                task.error = str(e)
                task.completed_at = datetime.now()
                tool_uses = task.tool_uses

                _enqueue_completion_notification(
                    task_id=task_id,
                    agent_name=agent_name,
                    status="failed",
                    error=str(e),
                    tool_uses=tool_uses,
                    duration_ms=duration_ms,
                    tool_use_id=tool_use_id,
                )

        # Complete fork tracking with failure status
        if fork_metadata:
            await complete_fork(fork_metadata.fork_id, status="failed")
