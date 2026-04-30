"""Permission manager for tool execution control"""

from __future__ import annotations

from typing import TYPE_CHECKING

from core.tools.permissions import (
    ApprovedRule,
    PermissionContext,
    RequiredPermission,
    ToolPermission,
)
from core.tools.utils import wildcard_match

if TYPE_CHECKING:
    from core.config.settings import Settings


class PermissionManager:
    """Manages tool permissions and session rules"""

    def __init__(self, config_getter: callable[[], Settings]):
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
        # Check tool-level permission
        tool_config = self._config.tools.get(tool_name, {})
        permission = ToolPermission(tool_config.get("permission", "ask"))

        # Check if bypass is enabled
        if self._config.bypass_tool_permissions:
            return PermissionContext(permission=ToolPermission.ALWAYS)

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
        permissions = []

        # Check for file operations outside working directory
        if "path" in args:
            from pathlib import Path

            path = Path(args["path"])
            if not path.resolve().is_relative_to(Path.cwd()):
                permissions.append(
                    RequiredPermission(
                        scope=PermissionScope.OUTSIDE_DIRECTORY,
                        invocation_pattern=str(path),
                        session_pattern=str(path.parent),
                        label=f"access {path}",
                    )
                )

        # Check for dangerous command patterns
        if tool_name == "bash" and "command" in args:
            command = args["command"]
            dangerous_patterns = ["rm -rf", "delete", "format", "truncate"]
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
