"""Tests for agent-local tool registration (extension-private tools).

Tests cover:
- ToolRegistry.register_agent_local_tool() isolation
- ExtensionAPI.agent_tools() queuing
- _FilteredToolRegistry resolution of agent-local tools
- End-to-end bind flow
- ExtensionAPI.load_config()
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import pytest

from collections.abc import Callable

from jarvis.api import BaseTool, ToolInput, ToolOutput
from jarvis.core.extensions.api import ExtensionAPI
from jarvis.core.extensions.runner import ExtensionRunner
from jarvis.core.tools.registry import ToolRegistry


# ── Helpers ──


class _PingTool(BaseTool):
    name = "ping"
    description = "A simple test tool"
    input_schema = {"type": "object", "properties": {}}

    async def execute(self, input_data: ToolInput) -> ToolOutput:
        return ToolOutput(success=True, result="pong")


class _EchoTool(BaseTool):
    name = "echo"
    description = "A test tool that echoes"
    input_schema = {
        "type": "object",
        "properties": {"msg": {"type": "string"}},
        "required": ["msg"],
    }

    async def execute(self, input_data: ToolInput) -> ToolOutput:
        msg = getattr(input_data, "msg", "")
        return ToolOutput(success=True, result=msg)


class _SecretTool(BaseTool):
    name = "secret"
    description = "Should only be visible to extension agents"
    input_schema = {"type": "object", "properties": {}}

    async def execute(self, input_data: ToolInput) -> ToolOutput:
        return ToolOutput(success=True, result="you found the secret tool")


# ── ToolRegistry isolation tests ──


class TestToolRegistryAgentLocalTools:
    """Verify register_agent_local_tool() isolates tools from global listings."""

    def setup_method(self):
        self.registry = ToolRegistry()
        self.ping = _PingTool()
        self.secret = _SecretTool()

    def test_register_agent_local_tool_not_in_function_definitions(self):
        self.registry.register_agent_local_tool(self.secret)
        names = [d["function"]["name"] for d in self.registry.get_function_definitions()]
        assert "secret" not in names

    def test_register_agent_local_tool_not_in_list_tools(self):
        self.registry.register_agent_local_tool(self.secret)
        names = [t["name"] for t in self.registry.list_tools()]
        assert "secret" not in names

    def test_register_agent_local_tool_not_in_get_tools(self):
        self.registry.register_agent_local_tool(self.secret)
        assert "secret" not in self.registry.get_tools()

    def test_register_agent_local_tool_findable_via_get(self):
        self.registry.register_agent_local_tool(self.secret)
        assert self.registry.get("secret") is self.secret

    def test_global_tools_still_appear_alongside_agent_local(self):
        self.registry.register(self.ping)
        self.registry.register_agent_local_tool(self.secret)
        # Global listings only show ping
        names = [d["function"]["name"] for d in self.registry.get_function_definitions()]
        assert "ping" in names
        assert "secret" not in names
        # get() finds both
        assert self.registry.get("ping") is self.ping
        assert self.registry.get("secret") is self.secret

    def test_mixed_register_and_agent_local_no_collision(self):
        public = _PingTool()
        private = _PingTool()
        private.name = "ping_private"
        self.registry.register(public)
        self.registry.register_agent_local_tool(private)
        assert self.registry.get("ping") is public
        assert self.registry.get("ping_private") is private
        names = [d["function"]["name"] for d in self.registry.get_function_definitions()]
        assert "ping" in names
        assert "ping_private" not in names

    async def test_execute_tool_works_for_agent_local(self):
        self.registry.register_agent_local_tool(self.secret)
        result = await self.registry.execute_tool("secret", {})
        assert result.success is True
        assert result.result == "you found the secret tool"

    async def test_execute_tool_works_for_mixed_registry(self):
        self.registry.register(self.ping)
        self.registry.register_agent_local_tool(self.secret)
        r1 = await self.registry.execute_tool("ping", {})
        r2 = await self.registry.execute_tool("secret", {})
        assert r1.result == "pong"
        assert r2.result == "you found the secret tool"

    def test_register_agent_local_tool_injects_references(self):
        self.registry.register_agent_local_tool(self.secret)
        assert self.secret.tool_registry is self.registry

    def test_update_tool_providers_propagates_to_agent_local(self):
        self.registry.register(self.ping)
        self.registry.register_agent_local_tool(self.secret)
        self.registry.update_tool_providers(model="test-model")
        assert self.ping.model == "test-model"
        assert self.secret.model == "test-model"


class TestFilteredRegistryWithAgentLocal:
    """Verify _FilteredToolRegistry correctly resolves agent-local tools."""

    def setup_method(self):
        self.registry = ToolRegistry()
        self.ping = _PingTool()
        self.secret = _SecretTool()
        self.echo = _EchoTool()
        self.registry.register(self.ping)
        self.registry.register_agent_local_tool(self.secret)
        self.registry.register_agent_local_tool(self.echo)

    def test_filtered_registry_resolves_agent_local_by_name(self):
        from jarvis.core.tools.agent.filtered_registry import _FilteredToolRegistry
        fr = _FilteredToolRegistry(self.registry, allowed_tools=["ping", "secret", "echo"])
        assert fr.get("ping") is self.ping
        assert fr.get("secret") is self.secret
        assert fr.get("echo") is self.echo
        assert fr.get("nonexistent") is None

    def test_filtered_registry_excludes_unlisted(self):
        from jarvis.core.tools.agent.filtered_registry import _FilteredToolRegistry
        fr = _FilteredToolRegistry(self.registry, allowed_tools=["ping"])
        assert fr.get("ping") is self.ping
        assert fr.get("secret") is None

    def test_filtered_function_definitions_include_agent_local(self):
        from jarvis.core.tools.agent.filtered_registry import _FilteredToolRegistry
        fr = _FilteredToolRegistry(self.registry, allowed_tools=["secret"])
        names = [d["function"]["name"] for d in fr.get_function_definitions()]
        assert "secret" in names
        assert "ping" not in names

    def test_filtered_list_tools_includes_agent_local(self):
        from jarvis.core.tools.agent.filtered_registry import _FilteredToolRegistry
        fr = _FilteredToolRegistry(self.registry, allowed_tools=["secret", "echo"])
        names = [t["name"] for t in fr.list_tools()]
        assert "secret" in names
        assert "echo" in names
        assert "ping" not in names

    async def test_filtered_execute_tool_works_for_agent_local(self):
        from jarvis.core.tools.agent.filtered_registry import _FilteredToolRegistry
        fr = _FilteredToolRegistry(self.registry, allowed_tools=["secret"])
        result = await fr.execute_tool("secret", {})
        assert result.success is True
        assert result.result == "you found the secret tool"

    async def test_filtered_execute_tool_rejects_unlisted(self):
        from jarvis.core.tools.agent.filtered_registry import _FilteredToolRegistry
        fr = _FilteredToolRegistry(self.registry, allowed_tools=["ping"])
        result = await fr.execute_tool("secret", {})
        assert result.success is False
        assert "not available" in (result.error or "")


# ── ExtensionAPI agent_tools() tests ──


class TestExtensionAPIAgentTools:
    """Verify agent_tools() queues tools separately from tools()."""

    def setup_method(self):
        self.api = ExtensionAPI("test_ext")
        self.ping = _PingTool()
        self.secret = _SecretTool()

    def test_agent_tools_queues_in_agent_tool_registrations(self):
        self.api.agent_tools(self.ping)
        assert self.ping in self.api._agent_tool_registrations
        assert self.api._tool_registrations == []

    def test_tools_queues_in_tool_registrations(self):
        self.api.tools(self.ping)
        assert self.api._tool_registrations[0]["tool"] is self.ping
        assert self.api._agent_tool_registrations == []

    def test_mixed_queues_are_separate(self):
        self.api.tools(self.ping)
        self.api.agent_tools(self.secret)
        assert len(self.api._tool_registrations) == 1
        assert len(self.api._agent_tool_registrations) == 1
        assert self.api._tool_registrations[0]["tool"] is self.ping
        assert self.api._agent_tool_registrations[0] is self.secret

    async def test_bind_registers_tools_via_correct_method(self):
        registry = ToolRegistry()
        self.api.tools(self.ping)
        self.api.agent_tools(self.secret)
        await self.api._bind(registry, event_bus=None, hook_registry=None, session=None)

        assert registry.get("ping") is self.ping
        assert registry.get("secret") is self.secret
        # secret is agent-local
        names = [d["function"]["name"] for d in registry.get_function_definitions()]
        assert "ping" in names
        assert "secret" not in names


# ── ExtensionAPI.load_config() tests ──


class TestExtensionAPILoadConfig:
    """Verify load_config() reads from settings.json extension section."""

    def test_load_config_returns_empty_dict_when_no_settings(self):
        api = ExtensionAPI("test_ext")
        assert api.load_config() == {}

    def test_load_config_returns_extension_section(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            orig_cwd = Path.cwd()
            try:
                os.chdir(tmpdir)
                jarvis_dir = Path(tmpdir) / ".jarvis"
                jarvis_dir.mkdir()
                settings = jarvis_dir / "settings.json"
                settings.write_text(json.dumps({
                    "extension": {
                        "ml_intern": {
                            "enabled": True,
                            "agent_local_tools": ["hf_papers", "hf_jobs"],
                        }
                    }
                }))

                api = ExtensionAPI("ml_intern")
                config = api.load_config()
                assert config["enabled"] is True
                assert "hf_papers" in config["agent_local_tools"]
                assert "hf_jobs" in config["agent_local_tools"]
            finally:
                os.chdir(orig_cwd)

    def test_load_config_returns_empty_for_unknown_extension(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            orig_cwd = Path.cwd()
            try:
                os.chdir(tmpdir)
                jarvis_dir = Path(tmpdir) / ".jarvis"
                jarvis_dir.mkdir()
                settings = jarvis_dir / "settings.json"
                settings.write_text(json.dumps({
                    "extension": {
                        "ml_intern": {"enabled": True},
                    }
                }))

                api = ExtensionAPI("unknown_ext")
                assert api.load_config() == {}
            finally:
                os.chdir(orig_cwd)

    def test_load_config_returns_empty_when_no_extension_section(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            orig_cwd = Path.cwd()
            try:
                os.chdir(tmpdir)
                jarvis_dir = Path(tmpdir) / ".jarvis"
                jarvis_dir.mkdir()
                settings = jarvis_dir / "settings.json"
                settings.write_text(json.dumps({"app": {"name": "JARVIS"}}))

                api = ExtensionAPI("ml_intern")
                assert api.load_config() == {}
            finally:
                os.chdir(orig_cwd)

    def test_load_config_handles_malformed_json_gracefully(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            orig_cwd = Path.cwd()
            try:
                os.chdir(tmpdir)
                jarvis_dir = Path(tmpdir) / ".jarvis"
                jarvis_dir.mkdir()
                settings = jarvis_dir / "settings.json"
                settings.write_text("{invalid json}")

                api = ExtensionAPI("ml_intern")
                assert api.load_config() == {}
            finally:
                os.chdir(orig_cwd)


# ── End-to-end extension flow ──


class TestEndToEndExtensionAgentLocalTools:
    """Simulate the full extension registration + subagent tool access flow."""

    async def test_extension_registers_agent_local_tools_then_subagent_uses_them(self):
        registry = ToolRegistry()
        # Simulate what Runner.discover_and_load → bind does
        api = ExtensionAPI("ml_intern")
        ping = _PingTool()
        secret = _SecretTool()

        # Extension registers tools
        api.tools(ping)
        api.agent_tools(secret)

        # Bind flushes registrations
        await api._bind(registry, event_bus=None, hook_registry=None, session=None)

        # Main agent sees only global tools
        main_tools = [d["function"]["name"] for d in registry.get_function_definitions()]
        assert "ping" in main_tools
        assert "secret" not in main_tools

        # Subagent gets filtered registry with agent-local tools
        from jarvis.core.tools.agent.filtered_registry import _FilteredToolRegistry
        fr = _FilteredToolRegistry(registry, allowed_tools=["ping", "secret"])
        subagent_tools = [d["function"]["name"] for d in fr.get_function_definitions()]
        assert "ping" in subagent_tools
        assert "secret" in subagent_tools

        # Subagent can execute agent-local tool
        result = await fr.execute_tool("secret", {})
        assert result.success is True
        assert result.result == "you found the secret tool"

        # Main agent CANNOT execute agent-local tool (not in LLM's tool list)
        # But if it somehow knew the name, execute_tool still works via get()
        result = await registry.execute_tool("secret", {})
        assert result.success is True
        assert result.result == "you found the secret tool"
        # The protection is at the LLM prompt level (function definitions),
        # not at the execution level — the LLM can only call tools it knows about

    async def test_ml_intern_extension_loads_agent_local_via_runner(self):
        """Verify ml_intern registers tools as agent-local through the Runner."""
        from jarvis.core.extensions.loader import load_from_package_dir

        ext_path = Path(".jarvis") / "extensions" / "ml_intern"
        result = load_from_package_dir(str(ext_path))
        assert result.success, f"Failed to load ml_intern extension: {result.error}"
        assert result.manifest is not None
        assert result.factory_fn is not None

        registry = ToolRegistry()
        api = ExtensionAPI(result.manifest.name, result.manifest.version)
        await result.factory_fn(api)

        assert len(api._agent_tool_registrations) > 0
        assert len(api._tool_registrations) == 0

        await api._bind(registry, event_bus=None, hook_registry=None, session=None)

        global_names = [d["function"]["name"] for d in registry.get_function_definitions()]
        for tool in api._agent_tool_registrations:
            assert tool.name not in global_names, f"{tool.name} leaked into global tools"

        for tool in api._agent_tool_registrations:
            found = registry.get(tool.name)
            assert found is not None, f"{tool.name} not found via get()"
            assert found is tool

        from jarvis.core.tools.agent.filtered_registry import _FilteredToolRegistry
        allowed = [t.name for t in api._agent_tool_registrations]
        fr = _FilteredToolRegistry(registry, allowed_tools=allowed)
        filtered_names = [d["function"]["name"] for d in fr.get_function_definitions()]
        for name in allowed:
            assert name in filtered_names, f"{name} missing from filtered registry"

    async def test_ml_intern_agent_definition_includes_agent_local_tools(self):
        """Verify the ml_intern AgentDefinition lists all its agent-local tools."""
        from jarvis.core.agents.profiles import AgentType
        from jarvis.core.extensions.loader import load_from_package_dir

        ext_path = Path(".jarvis") / "extensions" / "ml_intern"
        result = load_from_package_dir(str(ext_path))
        assert result.success
        assert result.manifest is not None
        assert result.factory_fn is not None

        registry = ToolRegistry()
        api = ExtensionAPI(result.manifest.name, result.manifest.version)
        await result.factory_fn(api)
        await api._bind(registry, event_bus=None, hook_registry=None, session=None)

        agent_defs = api._agent_registrations
        assert len(agent_defs) == 1
        ad = agent_defs[0]
        assert ad.name == "ml-intern"
        assert ad.agent_type == AgentType.AGENT

        for tool in api._agent_tool_registrations:
            assert tool.name in ad.tools, f"{tool.name} missing from agent definition"

    async def test_extension_api_has_name_and_version(self):
        api = ExtensionAPI("my_ext", "2.0.0")
        assert api.name == "my_ext"
        assert api.version == "2.0.0"
