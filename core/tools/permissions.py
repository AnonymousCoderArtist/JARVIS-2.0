"""Permission system for tool execution safety - Vibe-style granular permissions"""

from __future__ import annotations

from enum import Enum
from pathlib import Path

from pydantic import BaseModel, Field

from core.trusted_folders import trusted_folders_manager


class ToolPermission(str, Enum):
    """Permission levels for tool execution"""
    ALWAYS = "always"
    NEVER = "never"
    ASK = "ask"

    def __str__(self) -> str:
        return self.value


class PermissionScope(str, Enum):
    """Scopes for permission rules"""
    COMMAND_PATTERN = "command_pattern"
    OUTSIDE_DIRECTORY = "outside_directory"
    FILE_PATTERN = "file_pattern"
    URL_PATTERN = "url_pattern"
    SENSITIVE_FILE = "sensitive_file"

    def __str__(self) -> str:
        return self.value


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


def wildcard_match(text: str, pattern: str) -> bool:
    """Match text against a wildcard pattern using fnmatch.
    If pattern ends with "*", trailing part is optional (matches with or without args).
    """
    import fnmatch

    if fnmatch.fnmatch(text, pattern):
        return True
    if pattern.endswith("*") and fnmatch.fnmatch(text, pattern[:-1]):
        return True
    return False


def resolve_path_permission(
    path_str: str,
    *,
    allowlist: list[str],
    denylist: list[str],
) -> PermissionContext | None:
    """Resolve permission for a file path against glob patterns.
    Returns NEVER on denylist match, ALWAYS on allowlist match, None otherwise.
    Trusted folders are treated as ALWAYS and explicit untrusted folders as NEVER.
    """
    from pathlib import Path

    path = Path(path_str).expanduser()
    if not path.is_absolute():
        path = Path.cwd() / path

    file_str = str(path.resolve())

    trust_status = trusted_folders_manager.is_trusted(path)
    if trust_status is False:
        return PermissionContext(permission=ToolPermission.NEVER)

    # Check denylist first (deny takes precedence)
    for pattern in denylist:
        if wildcard_match(file_str, pattern):
            return PermissionContext(permission=ToolPermission.NEVER)

    if trust_status is True:
        return PermissionContext(permission=ToolPermission.ALWAYS)

    # Check allowlist
    for pattern in allowlist:
        if wildcard_match(file_str, pattern):
            return PermissionContext(permission=ToolPermission.ALWAYS)

    return None


def is_path_within_workdir(path_str: str) -> bool:
    """Return True if the resolved path is inside cwd."""
    from pathlib import Path

    try:
        path = Path(path_str).expanduser()
        if not path.is_absolute():
            path = Path.cwd() / path
        path.resolve().relative_to(Path.cwd().resolve())
        return True
    except ValueError:
        return False


def is_scratchpad_path(path_str: str) -> bool:
    """Check if path is in scratchpad directory."""
    from pathlib import Path

    path = Path(path_str).expanduser()
    if not path.is_absolute():
        path = Path.cwd() / path

    # Check for .jarvis/scratchpad or similar patterns
    resolved = path.resolve()
    cwd = Path.cwd().resolve()

    # Check if path is in .jarvis/scratchpad
    jarvis_scratchpad = cwd / ".jarvis" / "scratchpad"
    if resolved.is_relative_to(jarvis_scratchpad):
        return True

    # Check for /tmp scratchpad patterns
    if "/tmp/scratchpad" in str(resolved) or "scratchpad" in resolved.parts:
        return True

    return False


def resolve_file_tool_permission(
    path_str: str,
    *,
    tool_name: str,
    allowlist: list[str],
    denylist: list[str],
    config_permission: ToolPermission,
    sensitive_patterns: list[str],
) -> PermissionContext | None:
    """Resolve permission for a file-based tool invocation.
    Checks scratchpad, then allowlist/denylist, then sensitive patterns, then workdir boundary.
    Returns PermissionContext with granular required_permissions when applicable.
    """
    from pathlib import PurePath

    # Scratchpad paths are always allowed
    if is_scratchpad_path(path_str):
        return PermissionContext(permission=ToolPermission.ALWAYS)

    path = Path(path_str).expanduser()
    if not path.is_absolute():
        path = Path.cwd() / path

    resolved_path = path.resolve()
    trust_status = trusted_folders_manager.is_trusted(resolved_path)

    if trust_status is False:
        return PermissionContext(permission=ToolPermission.NEVER)

    if trust_status is True:
        file_str = str(resolved_path)

        # Explicit deny rules still win over trust.
        for pattern in denylist:
            if wildcard_match(file_str, pattern):
                return PermissionContext(permission=ToolPermission.NEVER)

        required: list[RequiredPermission] = []

        # Trusted paths can still trigger sensitivity checks.
        for pattern in sensitive_patterns:
            if PurePath(file_str).match(pattern):
                required.append(
                    RequiredPermission(
                        scope=PermissionScope.SENSITIVE_FILE,
                        invocation_pattern=path.name,
                        session_pattern="*",
                        label=f"accessing sensitive files ({tool_name})",
                    )
                )
                break

        if required:
            return PermissionContext(
                permission=ToolPermission.ASK, required_permissions=required
            )

        return PermissionContext(permission=ToolPermission.ALWAYS)

    # Check allowlist/denylist
    if (
        result := resolve_path_permission(
            path_str, allowlist=allowlist, denylist=denylist
        )
    ) is not None:
        return result

    required: list[RequiredPermission] = []

    # Check sensitive file patterns
    file_path = Path(path_str).expanduser()
    if not file_path.is_absolute():
        file_path = Path.cwd() / file_path

    file_str = str(file_path.resolve())

    for pattern in sensitive_patterns:
        if PurePath(file_str).match(pattern):
            required.append(
                RequiredPermission(
                    scope=PermissionScope.SENSITIVE_FILE,
                    invocation_pattern=file_path.name,
                    session_pattern="*",
                    label=f"accessing sensitive files ({tool_name})",
                )
            )
            break

    # Check workdir boundary
    if not is_path_within_workdir(path_str):
        if config_permission == ToolPermission.NEVER:
            return PermissionContext(permission=ToolPermission.NEVER)

        resolved = file_path.resolve()
        parent_dir = str(resolved.parent)
        glob = str(Path(parent_dir) / "*")
        required.append(
            RequiredPermission(
                scope=PermissionScope.OUTSIDE_DIRECTORY,
                invocation_pattern=glob,
                session_pattern=glob,
                label=f"outside workdir ({glob})",
            )
        )

    if required:
        return PermissionContext(
            permission=ToolPermission.ASK, required_permissions=required
        )

    return None
