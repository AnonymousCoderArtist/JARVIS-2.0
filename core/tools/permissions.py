"""Permission system for tool execution safety"""

from __future__ import annotations

from enum import StrEnum, auto

from pydantic import BaseModel, Field


class ToolPermission(StrEnum):
    """Permission levels for tool execution"""
    ALWAYS = auto()
    NEVER = auto()
    ASK = auto()


class PermissionScope(StrEnum):
    """Scopes for permission rules"""
    COMMAND_PATTERN = auto()
    OUTSIDE_DIRECTORY = auto()
    FILE_PATTERN = auto()
    URL_PATTERN = auto()


class RequiredPermission(BaseModel):
    """A required permission for tool execution"""
    scope: PermissionScope
    invocation_pattern: str
    session_pattern: str
    label: str


class PermissionContext(BaseModel):
    """Context for permission checking"""
    permission: ToolPermission
    required_permissions: list[RequiredPermission] = Field(default_factory=list)
    reason: str | None = None


class ApprovedRule(BaseModel):
    """An approved rule for session-level permissions"""
    tool_name: str
    scope: PermissionScope
    session_pattern: str
