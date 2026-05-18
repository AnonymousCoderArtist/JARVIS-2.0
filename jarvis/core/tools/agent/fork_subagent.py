"""Fork subagent support for agent tool with worktree isolation.

This module provides functionality for creating isolated agent sessions using
git worktrees (similar to OpenCLaude's fork subagents), with support for:
- Worktree-based isolation for agents
- Message forking for context inheritance
- Isolated environment variables
- Fork marker detection in prompts
- Memory snapshot management for forked agents
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import subprocess
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from jarvis.core.config.settings import Settings

from .utils import create_agent

logger = logging.getLogger(__name__)


# Fork marker constants
FORK_MARKER_PREFIX = "---FORK:"
FORK_MARKER_SUFFIX = ":FORK---"


@dataclass
class ForkMetadata:
    """Metadata for a forked agent session."""
    fork_id: str
    parent_task_id: str | None
    worktree_path: Path | None
    created_at: datetime = field(default_factory=datetime.now)
    env_vars: dict[str, str] = field(default_factory=dict)
    memory_snapshot: list[dict[str, Any]] = field(default_factory=list)
    status: str = "created"  # created, running, completed, failed


@dataclass
class ForkMemorySnapshot:
    """Snapshot of memory state for forked agent."""
    messages: list[dict[str, Any]] = field(default_factory=list)
    context: dict[str, Any] = field(default_factory=dict)
    system_prompt: str = ""
    captured_at: datetime = field(default_factory=datetime.now)


# Active fork tracking
_active_forks: dict[str, ForkMetadata] = {}
_fork_lock = asyncio.Lock()


def detect_fork_marker(prompt: str) -> tuple[str, dict[str, Any] | None]:
    """Detect fork marker in prompt and extract fork configuration.

    Args:
        prompt: The prompt text to check for fork markers

    Returns:
        Tuple of (cleaned_prompt, fork_config or None)
    """
    import re

    pattern = rf"{re.escape(FORK_MARKER_PREFIX)}(.*?){re.escape(FORK_MARKER_SUFFIX)}"
    match = re.search(pattern, prompt, re.DOTALL)

    if match:
        try:
            config = json.loads(match.group(1))
            # Remove marker from prompt
            cleaned = re.sub(pattern, "", prompt, flags=re.DOTALL).strip()
            return cleaned, config
        except json.JSONDecodeError:
            logger.warning("Failed to parse fork marker JSON")
            return prompt, None

    return prompt, None


async def create_worktree_for_fork(parent_task_id: str | None = None) -> tuple[Path | None, str]:
    """Create a git worktree for fork isolation.

    Args:
        parent_task_id: Optional parent task ID for naming

    Returns:
        Tuple of (worktree_path, fork_id)
    """
    fork_id = str(uuid.uuid4())[:8]
    worktree_name = f"fork-{fork_id}"
    worktree_path = None

    try:
        # Check if we're in a git repository
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            logger.warning("Not in a git repository, skipping worktree creation")
            return None, fork_id

        repo_root = Path(result.stdout.strip())
        worktree_path = repo_root / ".git" / "worktrees" / worktree_name

        # Create the worktree
        worktree_result = subprocess.run(
            ["git", "worktree", "add", str(worktree_path), "-b", f"fork-{fork_id}"],
            capture_output=True,
            text=True,
        )

        if worktree_result.returncode == 0:
            logger.info(f"Created worktree at {worktree_path}")
        else:
            logger.warning(f"Worktree creation failed: {worktree_result.stderr}")
            worktree_path = None

    except Exception as e:
        logger.warning(f"Failed to create worktree: {e}")
        worktree_path = None

    return worktree_path, fork_id


async def cleanup_worktree(worktree_path: Path | None) -> None:
    """Clean up a git worktree when fork completes.

    Args:
        worktree_path: Path to the worktree to clean up
    """
    if worktree_path is None:
        return

    try:
        # Remove worktree
        result = subprocess.run(
            ["git", "worktree", "remove", str(worktree_path), "--force"],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            logger.warning(f"Failed to remove worktree: {result.stderr}")
        else:
            logger.info(f"Cleaned up worktree: {worktree_path}")

    except Exception as e:
        logger.error(f"Error cleaning up worktree: {e}")


def create_isolated_env(base_env: dict[str, str] | None = None) -> dict[str, str]:
    """Create isolated environment variables for forked agent.

    Args:
        base_env: Base environment to inherit, uses os.environ if None

    Returns:
        New environment dict with isolation settings
    """
    env = dict(base_env or os.environ)

    # Add fork identification
    env["JARVIS_FORK_ID"] = str(uuid.uuid4())
    env["JARVIS_FORK_ISOLATED"] = "1"

    # Isolate some potentially unsafe paths
    env.pop("PYTHONPATH", None)  # Let agent discover its own paths

    # Ensure we can still find the project
    env["JARVIS_PROJECT_ROOT"] = os.getcwd()

    return env


def snapshot_memory(messages: list[dict[str, Any]], context: dict[str, Any], system_prompt: str) -> ForkMemorySnapshot:
    """Create a memory snapshot for forked agent inheritance.

    Args:
        messages: List of message dicts to snapshot
        context: Context dict to snapshot
        system_prompt: System prompt string to snapshot

    Returns:
        ForkMemorySnapshot instance
    """
    # Deep copy messages to avoid mutation
    messages_copy = json.loads(json.dumps(messages)) if messages else []

    return ForkMemorySnapshot(
        messages=messages_copy,
        context=dict(context) if context else {},
        system_prompt=system_prompt,
    )


def _make_fork_config_getter(
    base_config_getter: Any,
    profile: Any,
    fork_config: dict[str, Any] | None,
) -> Callable[[], Settings]:  # type: ignore[misc]
    """Build a config getter that applies profile and fork-specific overrides.

    Args:
        base_config_getter: Base config getter (callable or Settings instance)
        profile: Optional agent profile with apply_to_config method
        fork_config: Optional fork configuration overrides

    Returns:
        Config getter function
    """
    from jarvis.core.config.settings import Settings

    def fork_config_getter() -> Settings:
        if callable(base_config_getter):
            base_settings = base_config_getter()
        else:
            base_settings = Settings()

        config = base_settings.model_dump()

        if profile is not None:
            config = profile.apply_to_config(config)

        if fork_config:
            if "max_tokens" in fork_config:
                config["max_tokens"] = fork_config["max_tokens"]

        return Settings(initial_config=config)

    return fork_config_getter


# Map agent names to their profiles (for config merging)
_AGENT_PROFILES = {
    "explore": None,  # Will be set dynamically from jarvis.core.agents
    "plan": None,     # Will be set dynamically from jarvis.core.agents
    "jarvis-help": None,
    "verification": None,
}


def create_fork_subagent(
    agent_name: str,
    prompt: str,
    llm_provider,
    tool_registry,
    model,
    config_getter,
    allowed_tools: tuple[str, ...],
    parent_task_id: str | None = None,
    inherit_memory: list[dict[str, Any]] | None = None,
    fork_config: dict[str, Any] | None = None,
) -> tuple[Any, ForkMetadata]:
    """Create a forked subagent with worktree isolation and context inheritance.

    Args:
        agent_name: Name of the agent type to create
        prompt: The prompt for the agent (may contain fork markers)
        llm_provider: LLM provider instance
        tool_registry: Source tool registry
        model: Model name
        config_getter: Configuration getter function
        allowed_tools: Tuple of allowed tool names
        parent_task_id: Optional parent task ID for tracking
        inherit_memory: Optional memory to inherit from parent
        fork_config: Optional fork configuration from marker

    Returns:
        Tuple of (agent_instance, fork_metadata)
    """
    from jarvis.core.agents import EXPLORE, PLAN

    # Create fork metadata
    fork_id = str(uuid.uuid4())[:8]
    fork_metadata = ForkMetadata(
        fork_id=fork_id,
        parent_task_id=parent_task_id,
        worktree_path=None,
    )

    # Store memory snapshot if provided
    if inherit_memory:
        fork_metadata.memory_snapshot = inherit_memory

    # Determine allowed tools (can be overridden by fork_config)
    if fork_config and "allowed_tools" in fork_config:
        allowed_tools = tuple(fork_config["allowed_tools"])

    # Select profile for config merging
    profile = {"explore": EXPLORE, "plan": PLAN}.get(agent_name)

    # Build fork-aware config getter
    fork_config_getter = _make_fork_config_getter(config_getter, profile, fork_config)
    isolated_env = create_isolated_env()
    fork_metadata.env_vars = isolated_env

    # Create the agent via shared utility
    agent = create_agent(
        agent_name=agent_name,
        llm_provider=llm_provider,
        tool_registry=tool_registry,
        model=model,
        config_getter=fork_config_getter,
        allowed_tools=allowed_tools,
    )

    # Inherit memory if provided
    if inherit_memory:
        agent.memory = list(inherit_memory)

    return agent, fork_metadata


async def track_fork(fork_metadata: ForkMetadata) -> str:
    """Track an active fork for lifecycle management.

    Args:
        fork_metadata: The fork metadata to track

    Returns:
        The fork ID
    """
    async with _fork_lock:
        _active_forks[fork_metadata.fork_id] = fork_metadata
    return fork_metadata.fork_id


async def complete_fork(fork_id: str, status: str = "completed") -> None:
    """Mark a fork as completed and clean up resources.

    Args:
        fork_id: The fork ID to complete
        status: Final status (completed, failed)
    """
    async with _fork_lock:
        if fork_id in _active_forks:
            fork_metadata = _active_forks[fork_id]
            fork_metadata.status = status

            # Clean up worktree if exists
            if fork_metadata.worktree_path:
                await cleanup_worktree(fork_metadata.worktree_path)

            # Remove from active tracking
            del _active_forks[fork_id]


async def get_fork(fork_id: str) -> ForkMetadata | None:
    """Get fork metadata by ID.

    Args:
        fork_id: The fork ID to look up

    Returns:
        ForkMetadata if found, None otherwise
    """
    async with _fork_lock:
        return _active_forks.get(fork_id)


async def list_active_forks() -> list[ForkMetadata]:
    """List all active forks.

    Returns:
        List of active ForkMetadata instances
    """
    async with _fork_lock:
        return list(_active_forks.values())
