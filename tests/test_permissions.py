from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from unittest.mock import MagicMock
from typing import cast

import pytest

from core.agents.base import BaseAgent
from core.config.settings import Settings
from core.tools.agent_tools import AgentsTool
from core.tools.base import BaseTool, ToolInput, ToolOutput
from core.tools.file_tools import FileReadTool, FindTool, LSTool
from core.tools.grep_tool import GrepSearchTool
from core.tools.permission_manager import PermissionManager
from core.tools.permissions import (
    PermissionContext,
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

    tool = LSTool()
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
                "ls": {"permission": "ask"},
                "allowlist": [],
                "denylist": [],
                "sensitive_patterns": [],
            },
            "bypass_tool_permissions": False,
        }
    )
    manager = PermissionManager(lambda: settings)

    ctx = manager.check_permission("ls", {"path": str(tmp_path.parent)})

    assert ctx.permission == ToolPermission.ASK
    assert ctx.required_permissions
    assert ctx.required_permissions[0].scope == PermissionScope.OUTSIDE_DIRECTORY


class _SessionApprovalTool(BaseTool):
    name = "session_approval_tool"
    description = "Tool used to verify session approvals"
    input_schema = {"type": "object", "properties": {}}

    def resolve_permission(self, args: dict) -> PermissionContext:
        return PermissionContext(permission=ToolPermission.ASK)

    async def execute(self, input_data: ToolInput) -> ToolOutput:
        return ToolOutput(success=True, result="ok")


class _ApprovalTestAgent(BaseAgent):
    async def process(self, input: str, context: dict | None = None) -> str:
        return input

    async def plan(self, task: str) -> list[dict]:
        return [{"step": 1, "action": task}]


@pytest.mark.asyncio
async def test_session_allow_applies_to_generic_tools(monkeypatch) -> None:
    registry = MagicMock()
    tool = _SessionApprovalTool()
    tool.tool_registry = registry
    tool.llm_provider = MagicMock()
    tool.model = "gpt-4o"

    tools = {tool.name: tool}
    registry.get = MagicMock(side_effect=tools.get)

    agent = _ApprovalTestAgent(
        llm_provider=MagicMock(),
        tool_registry=registry,
        system_prompt="test",
    )
    agent.set_config_getter(lambda: Settings())

    async def fail_if_called(*_args, **_kwargs):
        raise AssertionError("approval callback should not be called after allow-always")

    agent.set_approval_callback(fail_if_called)
    agent.approve_always("session_approval_tool", [])

    decision = await agent._should_execute_tool("session_approval_tool", {}, "call-1")

    assert decision.verdict == "execute"
    assert decision.approval_type == ToolPermission.ALWAYS


@pytest.mark.asyncio
async def test_agents_applies_explore_profile_to_subagent(monkeypatch) -> None:
    import core.agents as agents_module

    captured: dict[str, object] = {}

    class FakeExploreAgent:
        def __init__(self, llm_provider, tool_registry, model=None, config_getter=None):
            captured["config_getter"] = config_getter
            captured["tool_names"] = list(tool_registry.get_tools().keys())

        def rebuild_system_prompt(self) -> None:
            return None

        async def process(self, prompt: str) -> str:
            config_getter = cast(Callable[[], Settings], captured["config_getter"])
            captured["config"] = config_getter()
            captured["prompt"] = prompt
            return "explore result"

    monkeypatch.setattr(agents_module, "ExploreAgent", FakeExploreAgent)

    registry = MagicMock()
    registry.config_getter = lambda: Settings()
    registry.get_tools = MagicMock(
        return_value={
            "read": FileReadTool(),
            "ls": LSTool(),
            "find": FindTool(),
            "grep": GrepSearchTool(),
            "agents": MagicMock(),
            "bash": MagicMock(),
        }
    )
    registry.execute_tool = MagicMock(return_value=ToolOutput(success=True, result="ok"))

    tool = AgentsTool(tool_registry=registry, llm_provider=MagicMock(), model="gpt-4o")

    result = await tool.execute(
        ToolInput.model_validate({"agentName": "explore", "prompt": "inspect the repo", "runInBackground": False})
    )

    assert result.success is True
    assert result.result == "explore result"

    subagent_config = captured["config"]
    assert isinstance(subagent_config, Settings)
    assert subagent_config.tools["read"]["permission"] == "always"
    assert subagent_config.tools["agents"]["permission"] == "never"
    assert captured["tool_names"] == ["read", "ls", "find", "grep"]
