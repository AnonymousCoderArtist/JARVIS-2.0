"""Agent lifecycle management - background execution and agent creation.

This module handles the creation and execution of subagents with support for
fork-based isolation using git worktrees and memory inheritance.
"""

from __future__ import annotations

import asyncio
import logging
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
    STATUSLINE_SETUP_ALLOWED_TOOLS,
    VERIFICATION_ALLOWED_TOOLS,
)
from .filtered_registry import _FilteredToolRegistry
from .fork_subagent import (
    ForkMetadata,
    complete_fork,
    create_fork_subagent,
    track_fork,
)

logger = logging.getLogger(__name__)


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
    """
    from core.agents import EXPLORE, PLAN, ExploreAgent, PlanAgent
    from core.agents.builtin.jarvis_help_agent import JarvisHelpAgent
    from core.agents.builtin.verification_agent import VerificationAgent
    from core.config.settings import Settings

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

    def _on_tool_result(tool_name: str, tool_args: dict[str, Any], result: Any) -> None:
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
            subagent.tool_call_callback = _on_tool_call
            subagent.tool_result_callback = _on_tool_result
            subagent.rebuild_system_prompt()

            result = await subagent.process(prompt)

            async with _background_lock:
                if task_id in _background_agents:
                    _background_agents[task_id].status = "completed"
                    _background_agents[task_id].result = result
                    _background_agents[task_id].completed_at = datetime.now()

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
            subagent.tool_call_callback = _on_tool_call
            subagent.tool_result_callback = _on_tool_result
            subagent.rebuild_system_prompt()

            result = await subagent.process(prompt)

            async with _background_lock:
                if task_id in _background_agents:
                    _background_agents[task_id].status = "completed"
                    _background_agents[task_id].result = result
                    _background_agents[task_id].completed_at = datetime.now()

        elif agent_name == "statusline-setup":
            def statusline_config_getter() -> Settings:
                if callable(config_getter):
                    return config_getter()
                return Settings()

            statusline_registry = _FilteredToolRegistry(
                tool_registry,
                allowed_tools=STATUSLINE_SETUP_ALLOWED_TOOLS,
                llm_provider=llm_provider,
                model=model,
                config_getter=statusline_config_getter,
            )

            # statusline-setup is a read-only guidance agent (no edit/bash tools)
            result = "I can help with statusline customization for bash, zsh, PowerShell, and other shells. " + prompt

            async with _background_lock:
                if task_id in _background_agents:
                    _background_agents[task_id].status = "completed"
                    _background_agents[task_id].result = result
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
    """
    from core.tools.agent.constants import (
        EXPLORE_ALLOWED_TOOLS,
        JARVIS_HELP_ALLOWED_TOOLS,
        PLAN_ALLOWED_TOOLS,
        VERIFICATION_ALLOWED_TOOLS,
    )

    # Define callback to track tool usage
    def _on_tool_call(tool_name: str, tool_args: dict) -> None:
        """Increment tool usage counter"""
        async def _update():
            async with _background_lock:
                if task_id in _background_agents:
                    _background_agents[task_id].tool_uses += 1
                    _background_agents[task_id].current_activity = f"{tool_name}"
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

        # Complete fork tracking and cleanup
        if fork_metadata:
            await complete_fork(fork_metadata.fork_id, status="completed")

    except Exception as e:
        # Update error status
        async with _background_lock:
            if task_id in _background_agents:
                _background_agents[task_id].status = "failed"
                _background_agents[task_id].error = str(e)
                _background_agents[task_id].completed_at = datetime.now()

        # Complete fork tracking with failure status
        if fork_metadata:
            await complete_fork(fork_metadata.fork_id, status="failed")
