"""Tools package.

IMPORTANT:
Keep this module **side-effect free**.

Historically, importing `core.tools` eagerly imported most tools, which caused
test collection failures and circular-import issues.

We now expose a lazy import surface via `__getattr__` so that callers can keep
using `from core.tools import X` without pulling in the entire tool graph.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .base import BaseTool, ToolInput, ToolOutput

if TYPE_CHECKING:
    # These are for type-checkers only; runtime imports are lazy.
    from .agent_tool import AgentsTool, AgentTool
    from .ask_user_question_tool import AskUserQuestionTool
    from .background_tools import ListBackgroundProcessesTool, ReadBackgroundOutputTool
    from .code_tools import BashTool, RunTestsTool
    from .file_edit_tool import EditTool
    from .file_tools import FileReadTool, FileWriteTool, FindTool, LSTool
    from .grep_tool import GrepSearchTool
    from .memory_tool import ReadMemoryTool, SaveMemoryTool, get_memory_context
    from .permission_manager import PermissionManager
    from .permissions import (
        ApprovedRule,
        PermissionContext,
        PermissionScope,
        RequiredPermission,
        ToolPermission,
    )
    from .registry import ToolRegistry
    from .repl_tool import REPLTool
    from .sandbox import wrap_command
    from .skill_manage_tool import SkillTool
    from .web_tools import ExaWebSearchTool, WebFetchTool
    from .worktree_tool import EnterWorktreeTool, ExitWorktreeTool

__all__ = [
    "BaseTool",
    "ToolInput",
    "ToolOutput",
    "ToolRegistry",
    # File tools
    "FileReadTool",  # read
    "FileWriteTool",  # write
    "EditTool",  # edit (renamed from ReplaceTool)
    "LSTool",  # ls
    "FindTool",  # find
    # Code tools
    "BashTool",
    "REPLTool",
    "RunTestsTool",
    # Search tools
    "GrepSearchTool",  # grep
    # Background tools
    "ListBackgroundProcessesTool",
    "ReadBackgroundOutputTool",
    # Web tools
    "WebFetchTool",  # fetch_webpage
    "ExaWebSearchTool",  # web_search
    # Memory tools
    "SaveMemoryTool",
    "ReadMemoryTool",
    # Agent tools
    "AgentTool",
    "AgentsTool",
    "AgentStatusTool",
    # Skill tool
    "SkillTool",
    # Ask User Question tool
    "AskUserQuestionTool",
    # Worktree tools
    "EnterWorktreeTool",
    "ExitWorktreeTool",
]


_LAZY_IMPORTS: dict[str, str] = {
    # registry/base
    "ToolRegistry": "core.tools.registry:ToolRegistry",
    # File tools
    "FileReadTool": "core.tools.file_tools:FileReadTool",
    "FileWriteTool": "core.tools.file_tools:FileWriteTool",
    "EditTool": "core.tools.file_edit_tool:EditTool",
    "LSTool": "core.tools.file_tools:LSTool",
    "FindTool": "core.tools.file_tools:FindTool",
    # Code tools
    "BashTool": "core.tools.code_tools:BashTool",
    "REPLTool": "core.tools.repl_tool:REPLTool",
    "RunTestsTool": "core.tools.code_tools:RunTestsTool",
    # Search tools
    "GrepSearchTool": "core.tools.grep_tool:GrepSearchTool",
    # Background tools
    "ListBackgroundProcessesTool": "core.tools.background_tools:ListBackgroundProcessesTool",
    "ReadBackgroundOutputTool": "core.tools.background_tools:ReadBackgroundOutputTool",
    # Web tools
    "WebFetchTool": "core.tools.web_tools:WebFetchTool",
    "ExaWebSearchTool": "core.tools.web_tools:ExaWebSearchTool",
    # Memory tools
    "SaveMemoryTool": "core.tools.memory_tool:SaveMemoryTool",
    "ReadMemoryTool": "core.tools.memory_tool:ReadMemoryTool",
    "get_memory_context": "core.tools.memory_tool:get_memory_context",
    "MemoryManagementTool": "core.tools.memory_tool:MemoryManagementTool",
    # Agent tools
    "AgentTool": "core.tools.agent_tool:AgentTool",
    "AgentsTool": "core.tools.agent_tool:AgentsTool",

    # Skill tool
    "SkillTool": "core.tools.skill_manage_tool:SkillTool",
    # Ask user
    "AskUserQuestionTool": "core.tools.ask_user_question_tool:AskUserQuestionTool",
    # Permissions
    "PermissionManager": "core.tools.permission_manager:PermissionManager",
    "ApprovedRule": "core.tools.permissions:ApprovedRule",
    "PermissionContext": "core.tools.permissions:PermissionContext",
    "PermissionScope": "core.tools.permissions:PermissionScope",
    "RequiredPermission": "core.tools.permissions:RequiredPermission",
    "ToolPermission": "core.tools.permissions:ToolPermission",
    # Sandbox
    "wrap_command": "core.tools.sandbox:wrap_command",
    # Worktrees
    "EnterWorktreeTool": "core.tools.worktree_tool:EnterWorktreeTool",
    "ExitWorktreeTool": "core.tools.worktree_tool:ExitWorktreeTool",
    # MCP
    "MCPRegistry": "core.tools.mcp_adapter:MCPRegistry",
    "MCPServerConfig": "core.tools.mcp_adapter:MCPServerConfig",
    "MCPClient": "core.tools.mcp_adapter:MCPClient",
    "MCPProxyTool": "core.tools.mcp_proxy_tool:MCPProxyTool",
    "MCPMetadataCache": "core.tools.mcp_metadata_cache:MCPMetadataCache",
    "MCPLifecycleManager": "core.tools.mcp_lifecycle:MCPLifecycleManager",
}


def __getattr__(name: str) -> Any:
    target = _LAZY_IMPORTS.get(name)
    if not target:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    mod_name, attr = target.split(":", 1)
    import importlib

    mod = importlib.import_module(mod_name)
    value = getattr(mod, attr)
    globals()[name] = value
    return value
