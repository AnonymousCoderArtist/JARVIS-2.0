"""Agent tool module for JARVIS subagent management.

This module provides tools for launching and managing specialized subagents
for codebase analysis, planning, help, and testing. It also provides fork
subagent functionality with worktree isolation similar to OpenCLaude.

Main exports:
    - AgentTool: Primary agent management tool
    - AgentsTool: Alias for AgentTool
    - AgentStatusTool: Specialized tool for checking agent status
    - BackgroundAgentTask: Dataclass representing background agent tasks
    - SubagentActivity: Dataclass for tracking subagent activity
    - ProgressTracker: Class for tracking agent progress with callbacks
    - run_with_tracking: Helper function for running coroutines with tracking
    - Fork-related functionality for worktree-isolated agents
"""

from .agent_memory import (
    AgentMemorySnapshot,
    SubagentActivity,
    add_subagent_activity,
    add_subagent_activity_async,
    clear_memory_snapshot,
    clear_subagent_activities,
    clear_subagent_activities_async,
    create_info_activity,
    create_output_activity,
    create_tool_activity,
    create_tool_result_activity,
    get_subagent_activities,
    get_subagent_activities_async,
    load_memory_snapshot,
    load_memory_snapshot_from_file,
    save_memory_snapshot,
    save_memory_snapshot_to_file,
)
from .agent_tool import AgentStatusTool, AgentsTool, AgentTool
from .background_task import (
    BackgroundAgentTask,
    clear_completed_background_agents,
    get_background_agent,
    get_completed_background_agents,
    list_background_agents,
)
from .constants import (
    AGENT_STATUS_TOOL_NAME,
    AGENT_TOOL_NAME,
    DEFAULT_MAX_TOKENS,
    EXPLORE_AGENT_TYPE,
    EXPLORE_ALLOWED_TOOLS,
    FORK_AGENT_TYPE,
    GENERAL_PURPOSE_AGENT_TYPE,
    JARVIS_HELP_AGENT_TYPE,
    JARVIS_HELP_ALLOWED_TOOLS,
    ONE_SHOT_BUILTIN_AGENT_TYPES,
    PLAN_AGENT_TYPE,
    PLAN_ALLOWED_TOOLS,
    STATUSLINE_SETUP_AGENT_TYPE,
    STATUSLINE_SETUP_ALLOWED_TOOLS,
    VERIFICATION_AGENT_TYPE,
    VERIFICATION_ALLOWED_TOOLS,
)
from .filtered_registry import _FilteredToolRegistry
from .fork_subagent import (
    FORK_MARKER_PREFIX,
    FORK_MARKER_SUFFIX,
    ForkMemorySnapshot,
    ForkMetadata,
    cleanup_worktree,
    complete_fork,
    create_fork_subagent,
    create_isolated_env,
    create_worktree_for_fork,
    detect_fork_marker,
    get_fork,
    list_active_forks,
    snapshot_memory,
    track_fork,
)
from .progress_tracker import (
    ProgressTracker,
    ProgressUpdate,
    TokenUsage,
    run_with_tracking,
)
from .utils import get_agent_param

__all__ = [
    # Main tool classes
    "AgentTool",
    "AgentsTool",
    "AgentStatusTool",
    # Task management
    "BackgroundAgentTask",
    "get_background_agent",
    "list_background_agents",
    "get_completed_background_agents",
    "clear_completed_background_agents",
    # Activity tracking
    "SubagentActivity",
    "AgentMemorySnapshot",
    "add_subagent_activity",
    "add_subagent_activity_async",
    "get_subagent_activities",
    "get_subagent_activities_async",
    "clear_subagent_activities",
    "clear_subagent_activities_async",
    "save_memory_snapshot",
    "load_memory_snapshot",
    "clear_memory_snapshot",
    "save_memory_snapshot_to_file",
    "load_memory_snapshot_from_file",
    "create_tool_activity",
    "create_tool_result_activity",
    "create_info_activity",
    "create_output_activity",
    # Progress tracking
    "ProgressTracker",
    "run_with_tracking",
    "TokenUsage",
    "ProgressUpdate",
    # Fork subagent functionality
    "ForkMetadata",
    "ForkMemorySnapshot",
    "create_fork_subagent",
    "detect_fork_marker",
    "snapshot_memory",
    "create_worktree_for_fork",
    "cleanup_worktree",
    "create_isolated_env",
    "track_fork",
    "complete_fork",
    "get_fork",
    "list_active_forks",
    "FORK_MARKER_PREFIX",
    "FORK_MARKER_SUFFIX",
    # Constants
    "AGENT_TOOL_NAME",
    "AGENT_STATUS_TOOL_NAME",
    "EXPLORE_AGENT_TYPE",
    "PLAN_AGENT_TYPE",
    "JARVIS_HELP_AGENT_TYPE",
    "VERIFICATION_AGENT_TYPE",
    "STATUSLINE_SETUP_AGENT_TYPE",
    "GENERAL_PURPOSE_AGENT_TYPE",
    "FORK_AGENT_TYPE",
    "ONE_SHOT_BUILTIN_AGENT_TYPES",
    "EXPLORE_ALLOWED_TOOLS",
    "PLAN_ALLOWED_TOOLS",
    "JARVIS_HELP_ALLOWED_TOOLS",
    "VERIFICATION_ALLOWED_TOOLS",
    "STATUSLINE_SETUP_ALLOWED_TOOLS",
    "DEFAULT_MAX_TOKENS",
    # Internal
    "_FilteredToolRegistry",
    "get_agent_param",
]
