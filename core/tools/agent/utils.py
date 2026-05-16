"""Utility functions for agent tools."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from core.config.settings import Settings

from .filtered_registry import _FilteredToolRegistry

logger = logging.getLogger(__name__)


def get_agent_param(input_data: Any, *names: str) -> Any:
    """Get parameter using multiple possible names.

    Args:
        input_data: The input data object to get parameter from
        *names: Parameter names to try in order

    Returns:
        The first non-None value found for any name
    """
    for name in names:
        value = getattr(input_data, name, None)
        if value is not None:
            return value
    return None


def make_config_getter(
    base_config_getter: Any,
    profile: Any = None,
) -> Callable[[], Settings]:
    """Create a config getter function with optional profile application.

    Args:
        base_config_getter: Base config getter (callable or Settings instance)
        profile: Optional agent profile with apply_to_config method

    Returns:
        Config getter that applies profile if provided
    """
    def config_getter() -> Settings:
        if callable(base_config_getter):
            base_settings = base_config_getter()
        else:
            base_settings = Settings()

        if profile is not None:
            merged_config = profile.apply_to_config(base_settings.model_dump())
            return Settings(initial_config=merged_config)

        return base_settings

    return config_getter


def extract_token_usage(result: Any) -> int:
    """Extract token usage count from an agent result.

    Args:
        result: Agent result which may contain usage info

    Returns:
        Token usage count, or 0 if not available
    """
    token_usage = 0
    if isinstance(result, dict) and "usage" in result:
        usage = result["usage"]
        if isinstance(usage, dict):
            token_usage = usage.get("total_tokens", 0)
        elif hasattr(usage, "total_tokens"):
            token_usage = usage.total_tokens
    return token_usage


def update_background_status(
    task_id: str,
    status: str,
    result: Any = None,
    error: str | None = None,
    token_usage: int = 0,
) -> None:
    """Update the status of a background agent task (synchronous helper).

    Note: Call this inside an existing `async with _background_lock:` block.

    Args:
        task_id: The task ID to update
        status: New status string
        result: Optional result value
        error: Optional error message
        token_usage: Token usage count
    """
    import datetime

    from .background_task import _background_agents

    if task_id not in _background_agents:
        return

    task = _background_agents[task_id]
    task.status = status
    task.completed_at = datetime.datetime.now()

    if result is not None:
        task.result = result
        task.token_usage = token_usage

    if error is not None:
        task.error = error


def create_agent(
    agent_name: str,
    llm_provider,
    tool_registry,
    model,
    config_getter,
    allowed_tools: tuple[str, ...],
    callbacks: dict[str, Any] | None = None,
) -> Any:
    """Create and configure a subagent instance with a filtered tool registry.

    Args:
        agent_name: Agent type name (explore, plan, jarvis-help, verification)
        llm_provider: LLM provider instance
        tool_registry: Source tool registry
        model: Model name
        config_getter: Configuration getter function
        allowed_tools: Tuple of allowed tool names
        callbacks: Optional dict with 'tool_call' and 'tool_result' callbacks

    Returns:
        Configured agent instance
    """
    from core.agents import ExploreAgent, PlanAgent
    from core.agents.builtin.jarvis_help_agent import JarvisHelpAgent
    from core.agents.builtin.rubber_duck_agent import RubberDuckAgent
    from core.agents.builtin.verification_agent import VerificationAgent

    _agent_classes = {
        "explore": ExploreAgent,
        "plan": PlanAgent,
        "jarvis-help": JarvisHelpAgent,
        "verification": VerificationAgent,
        "rubber-duck": RubberDuckAgent,
    }

    agent_class = _agent_classes.get(agent_name)
    if agent_class is None:
        raise ValueError(f"Unknown agent type: {agent_name}")

    registry = _FilteredToolRegistry(
        tool_registry,
        allowed_tools=allowed_tools,
        llm_provider=llm_provider,
        model=model,
        config_getter=config_getter,
    )

    agent = agent_class(
        llm_provider=llm_provider,
        tool_registry=registry,
        model=model,
        config_getter=config_getter,
    )

    if callbacks:
        agent.tool_call_callback = callbacks.get("tool_call")
        agent.tool_result_callback = callbacks.get("tool_result")

    agent.rebuild_system_prompt()
    return agent
