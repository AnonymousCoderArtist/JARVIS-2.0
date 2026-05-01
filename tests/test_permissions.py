from __future__ import annotations

from pathlib import Path

from core.config.settings import Settings
from core.tools.file_tools import ListDirectoryTool
from core.tools.permission_manager import PermissionManager
from core.tools.permissions import (
    PermissionScope,
    ToolPermission,
    resolve_file_tool_permission,
)
import core.tools.permissions as permissions_module


def test_file_permission_allows_trusted_folders(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(permissions_module.trusted_folders_manager, "is_trusted", lambda _path: True)

    ctx = resolve_file_tool_permission(
        str(tmp_path / "nested" / "file.txt"),
        tool_name="read",
        allowlist=[],
        denylist=[],
        config_permission=ToolPermission.ASK,
        sensitive_patterns=[],
    )

    assert ctx is not None
    assert ctx.permission == ToolPermission.ALWAYS
    assert ctx.required_permissions == []


def test_file_permission_denies_untrusted_folders(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(permissions_module.trusted_folders_manager, "is_trusted", lambda _path: False)

    ctx = resolve_file_tool_permission(
        str(tmp_path / "nested" / "file.txt"),
        tool_name="read",
        allowlist=[],
        denylist=[],
        config_permission=ToolPermission.ASK,
        sensitive_patterns=[],
    )

    assert ctx is not None
    assert ctx.permission == ToolPermission.NEVER
    assert ctx.required_permissions == []


def test_list_directory_tool_trusted_path_is_auto_allowed(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(permissions_module.trusted_folders_manager, "is_trusted", lambda _path: True)

    tool = ListDirectoryTool()
    ctx = tool.resolve_permission({"path": str(tmp_path / "project")})

    assert ctx is not None
    assert ctx.permission == ToolPermission.ALWAYS
    assert ctx.required_permissions == []


def test_permission_manager_list_dir_outside_workdir_requires_approval(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(permissions_module.trusted_folders_manager, "is_trusted", lambda _path: None)
    monkeypatch.chdir(tmp_path)

    settings = Settings(
        initial_config={
            "tools": {
                "list_dir": {"permission": "ask"},
                "allowlist": [],
                "denylist": [],
                "sensitive_patterns": [],
            },
            "bypass_tool_permissions": False,
        }
    )
    manager = PermissionManager(lambda: settings)

    ctx = manager.check_permission("list_dir", {"path": str(tmp_path.parent)})

    assert ctx.permission == ToolPermission.ASK
    assert ctx.required_permissions
    assert ctx.required_permissions[0].scope == PermissionScope.OUTSIDE_DIRECTORY
