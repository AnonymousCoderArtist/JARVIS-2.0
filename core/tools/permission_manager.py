"""Permission manager for tool execution control"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from core.tools.permissions import (
    ApprovedRule,
    PermissionContext,
    PermissionScope,
    RequiredPermission,
    ToolPermission,
    is_tool_disallowed,
    resolve_path_permission,
    resolve_file_tool_permission,
)
from core.tools.utils import wildcard_match

if TYPE_CHECKING:
    from core.config.settings import Settings


class PermissionManager:
    """Manages tool permissions and session rules"""

    def __init__(self, config_getter: Callable[[], Settings]):
        self._config_getter = config_getter
        self.session_rules: list[ApprovedRule] = []
        self.tool_permissions: dict[str, ToolPermission] = {}

    @property
    def _config(self) -> Settings:
        return self._config_getter()

    def check_permission(
        self, tool_name: str, args: dict
    ) -> PermissionContext:
        """
        Check if tool execution requires approval

        Args:
            tool_name: Name of the tool being executed
            args: Arguments passed to the tool

        Returns:
            PermissionContext with permission level and required permissions
        """
        # Check if bypass is enabled
        if self._config.bypass_tool_permissions:
            return PermissionContext(permission=ToolPermission.ALWAYS)

        # Check disallowed_tools from profile config - takes precedence
        disallowed = getattr(self._config, 'disallowed_tools', [])
        if disallowed and is_tool_disallowed(tool_name, disallowed):
            return PermissionContext(
                permission=ToolPermission.NEVER,
                reason=f"Tool '{tool_name}' is explicitly disallowed for this agent"
            )

        # Check tool-level permission
        tool_config = self._config.tools.get(tool_name, {})
        permission = ToolPermission(tool_config.get("permission", "ask"))

        # Check path-aware tool permissions first so trusted folders can short-circuit.
        path_ctx = self._resolve_path_permission(tool_name, args)
        if path_ctx is not None and path_ctx.permission in (ToolPermission.ALWAYS, ToolPermission.NEVER):
            return path_ctx

        # Check session rules
        required_permissions = self._get_required_permissions(tool_name, args)

        # Check if all required permissions are covered by session rules
        uncovered = [
            rp
            for rp in required_permissions
            if not self._is_permission_covered(tool_name, rp)
        ]

        if required_permissions and not uncovered:
            return PermissionContext(
                permission=ToolPermission.ALWAYS,
                required_permissions=required_permissions,
            )

        return PermissionContext(
            permission=permission,
            required_permissions=uncovered,
        )

    def _resolve_path_permission(
        self, tool_name: str, args: dict
    ) -> PermissionContext | None:
        """Resolve immediate allow/deny decisions for path-aware tools."""
        from core.tools.permissions import is_path_within_workdir

        if tool_name in ("read", "write", "edit") and "filePath" in args:
            file_path = args["filePath"]
            allowlist = self._config.tools.get("allowlist", [])
            denylist = self._config.tools.get("denylist", [])
            sensitive_patterns = self._config.tools.get("sensitive_patterns", [])
            config_permission = ToolPermission(
                self._config.tools.get(tool_name, {}).get("permission", "ask")
            )
            return resolve_file_tool_permission(
                file_path,
                tool_name=tool_name,
                allowlist=allowlist,
                denylist=denylist,
                config_permission=config_permission,
                sensitive_patterns=sensitive_patterns,
            )

        if tool_name == "ls" and "path" in args:
            allowlist = self._config.tools.get("allowlist", [])
            denylist = self._config.tools.get("denylist", [])
            path = args["path"]

            result = resolve_path_permission(
                path,
                allowlist=allowlist,
                denylist=denylist,
            )
            if result is not None:
                return result

            if not is_path_within_workdir(path):
                from pathlib import Path

                resolved = Path(path).expanduser().resolve()
                parent_dir = str(resolved.parent)
                glob = str(Path(parent_dir) / "*")
                return PermissionContext(
                    permission=ToolPermission.ASK,
                    required_permissions=[
                        RequiredPermission(
                            scope=PermissionScope.OUTSIDE_DIRECTORY,
                            invocation_pattern=str(resolved),
                            session_pattern=glob,
                            label=f"list {resolved}",
                        )
                    ],
                )

        return None

    def _get_required_permissions(
        self, tool_name: str, args: dict
    ) -> list[RequiredPermission]:
        """
        Get required permissions for a tool execution

        Args:
            tool_name: Name of the tool
            args: Tool arguments

        Returns:
            List of required permissions
        """
        from core.tools.permissions import is_path_within_workdir

        permissions = []

        # Check for file operations with granular permissions
        if tool_name in ("read", "write", "edit") and "filePath" in args:
            file_path = args["filePath"]
            allowlist = self._config.tools.get("allowlist", [])
            denylist = self._config.tools.get("denylist", [])
            sensitive_patterns = self._config.tools.get("sensitive_patterns", [])
            config_permission = ToolPermission(
                self._config.tools.get(tool_name, {}).get("permission", "ask")
            )

            ctx = resolve_file_tool_permission(
                file_path,
                tool_name=tool_name,
                allowlist=allowlist,
                denylist=denylist,
                config_permission=config_permission,
                sensitive_patterns=sensitive_patterns,
            )

            if ctx and ctx.required_permissions:
                permissions.extend(ctx.required_permissions)

        # Check for ls operations
        elif tool_name == "ls" and "path" in args:
            from pathlib import Path

            path = Path(args["path"])
            if not is_path_within_workdir(args["path"]):
                permissions.append(
                    RequiredPermission(
                        scope=PermissionScope.OUTSIDE_DIRECTORY,
                        invocation_pattern=str(path),
                        session_pattern=str(path.parent),
                        label=f"list {path}",
                    )
                )

        # Check for dangerous command patterns
        if tool_name == "bash" and "command" in args:
            command = args["command"]
            dangerous_patterns = ["rm -rf", "delete", "format", "truncate", "dd if=", "mkfs"]
            for pattern in dangerous_patterns:
                if pattern in command.lower():
                    permissions.append(
                        RequiredPermission(
                            scope=PermissionScope.COMMAND_PATTERN,
                            invocation_pattern=pattern,
                            session_pattern=command,
                            label=f"execute '{command}'",
                        )
                    )

        return permissions

    def _is_permission_covered(
        self, tool_name: str, required_permission: RequiredPermission
    ) -> bool:
        """
        Check if a required permission is covered by session rules

        Args:
            tool_name: Name of the tool
            required_permission: The permission to check

        Returns:
            True if covered, False otherwise
        """
        return any(
            rule.tool_name == tool_name
            and rule.scope == required_permission.scope
            and wildcard_match(
                required_permission.invocation_pattern, rule.session_pattern
            )
            for rule in self.session_rules
        )

    def add_session_rule(self, rule: ApprovedRule) -> None:
        """
        Add a session-level permission rule

        Args:
            rule: The rule to add
        """
        self.session_rules.append(rule)

    def set_tool_permission(
        self, tool_name: str, permission: ToolPermission, save_permanently: bool = False
    ) -> None:
        """
        Set a tool's permission level

        Args:
            tool_name: Name of the tool
            permission: Permission level to set
            save_permanently: Whether to save to config file
        """
        self.tool_permissions[tool_name] = permission

        if save_permanently:
            # This would integrate with config system to persist
            pass

    def clear_session_rules(self) -> None:
        """Clear all session-level rules"""
        self.session_rules.clear()

    def get_stats(self) -> dict:
        """Get permission manager statistics"""
        return {
            "session_rules": len(self.session_rules),
            "tool_permissions": len(self.tool_permissions),
        }
