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

from .agent_tool import AgentTool, AgentsTool, AgentStatusTool
from .background_task import (
    BackgroundAgentTask,
    get_background_agent,
    list_background_agents,
    get_completed_background_agents,
    clear_completed_background_agents,
)
from .agent_memory import (
    SubagentActivity,
    AgentMemorySnapshot,
    add_subagent_activity,
    add_subagent_activity_async,
    get_subagent_activities,
    get_subagent_activities_async,
    clear_subagent_activities,
    clear_subagent_activities_async,
    save_memory_snapshot,
    load_memory_snapshot,
    clear_memory_snapshot,
    save_memory_snapshot_to_file,
    load_memory_snapshot_from_file,
    create_tool_activity,
    create_tool_result_activity,
    create_info_activity,
    create_output_activity,
)
from .progress_tracker import (
    ProgressTracker,
    run_with_tracking,
    TokenUsage,
    ProgressUpdate,
)
from .fork_subagent import (
    ForkMetadata,
    ForkMemorySnapshot,
    create_fork_subagent,
    detect_fork_marker,
    snapshot_memory,
    create_worktree_for_fork,
    cleanup_worktree,
    create_isolated_env,
    track_fork,
    complete_fork,
    get_fork,
    list_active_forks,
    FORK_MARKER_PREFIX,
    FORK_MARKER_SUFFIX,
)
from .constants import (
    AGENT_TOOL_NAME,
    AGENT_STATUS_TOOL_NAME,
    EXPLORE_AGENT_TYPE,
    PLAN_AGENT_TYPE,
    JARVIS_HELP_AGENT_TYPE,
    VERIFICATION_AGENT_TYPE,
    STATUSLINE_SETUP_AGENT_TYPE,
    GENERAL_PURPOSE_AGENT_TYPE,
    FORK_AGENT_TYPE,
    ONE_SHOT_BUILTIN_AGENT_TYPES,
    EXPLORE_ALLOWED_TOOLS,
    PLAN_ALLOWED_TOOLS,
    JARVIS_HELP_ALLOWED_TOOLS,
    VERIFICATION_ALLOWED_TOOLS,
    STATUSLINE_SETUP_ALLOWED_TOOLS,
    DEFAULT_MAX_TOKENS,
)
from .filtered_registry import _FilteredToolRegistry
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