"""Tools Package"""

# Agent and Skill tools
from .agent_tools import ActivateSkillTool, InvokeAgentTool

# Permission system
from .permissions import (
    ApprovedRule,
    PermissionContext,
    PermissionScope,
    RequiredPermission,
    ToolPermission,
)
from .permission_manager import PermissionManager

# Background tools
from .background_tools import ListBackgroundProcessesTool, ReadBackgroundOutputTool
from .base import BaseTool, ToolInput, ToolOutput

# Code tools
from .code_tools import BashTool, RunTestsTool

# Document tools
# Removed: ReadPDFTool

# File tools
from .file_edit_tool import EditTool
from .file_tools import FileReadTool, FileWriteTool, GlobTool, ListDirectoryTool

# Search tools
from .grep_tool import GrepSearchTool

# Memory tools
from .memory_tool import SaveMemoryTool, ReadMemoryTool, get_memory_context
from .registry import ToolRegistry
from .repl_tool import REPLTool

# Web tools
from .web_tools import WebFetchTool

__all__ = [
    "BaseTool",
    "ToolInput",
    "ToolOutput",
    "ToolRegistry",
    # File tools
    "FileReadTool",  # read
    "FileWriteTool",  # write
    "EditTool",  # edit (renamed from ReplaceTool)
    "ListDirectoryTool",  # list_dir
    "GlobTool",  # glob
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
    # Memory tools
    "SaveMemoryTool",
    "ReadMemoryTool",
    # Agent tools
    "InvokeAgentTool",
    "ActivateSkillTool",
]
