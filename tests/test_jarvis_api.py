"""Tests for the jarvis.api public extension API module."""

import pytest


class TestJarvisApiImports:
    """Verify all public API exports are accessible."""

    def test_extension_system_imports(self):
        from jarvis.api import (
            ExtensionAPI,
            ExtensionManifest,
            ExtensionContext,
            ExtensionRegistry,
            ExtensionRunner,
            discover_extension_paths,
            load_from_file,
            load_from_directory,
            discover_and_load_all,
        )
        assert ExtensionAPI is not None
        assert ExtensionManifest is not None
        assert ExtensionContext is not None
        assert ExtensionRegistry is not None
        assert ExtensionRunner is not None

    def test_tool_system_imports(self):
        from jarvis.api import BaseTool, ToolInput, ToolOutput, ToolRegistry
        assert BaseTool is not None
        assert ToolInput is not None
        assert ToolOutput is not None
        assert ToolRegistry is not None

    def test_agent_system_imports(self):
        from jarvis.api import (
            AgentDefinition,
            AgentType,
            AgentSafety,
            AgentProfile,
        )
        assert AgentDefinition is not None
        assert AgentType is not None
        assert AgentSafety is not None
        assert AgentProfile is not None

    def test_builtin_profiles_imports(self):
        from jarvis.api import (
            DEFAULT,
            PLAN,
            ACCEPT_EDITS,
            AUTO_APPROVE,
            EXPLORE,
            BUILTIN_AGENTS,
            AGENT_ORDER,
        )
        assert DEFAULT.name == "default"
        assert PLAN.name == "plan"
        assert ACCEPT_EDITS.name == "accept-edits"
        assert AUTO_APPROVE.name == "auto-approve"
        assert EXPLORE.name == "explore"
        assert "default" in BUILTIN_AGENTS
        assert "plan" in BUILTIN_AGENTS

    def test_event_hook_system_imports(self):
        from jarvis.api import (
            HookStage,
            HookContext,
            HookResult,
            HookRegistry,
            EventBus,
        )
        assert HookStage is not None
        assert HookContext is not None
        assert HookResult is not None
        assert HookRegistry is not None
        assert EventBus is not None

    def test_event_types_imports(self):
        from jarvis.api import (
            AgentEvent,
            AgentStarted,
            AgentEnded,
            AgentError,
            TurnEvent,
            TurnStarted,
            TurnEnded,
            MessageEvent,
            MessageDelta,
            MessageComplete,
            ThinkingDelta,
            ToolEvent,
            ToolCallStarted,
            ToolCallEnded,
            ToolCallError,
            SessionEvent,
            SessionStarted,
            SessionShutdown,
            SkillActivated,
            SkillDeactivated,
            ExtensionEvent,
            ExtensionLoaded,
            ExtensionUnloaded,
            ExtensionError,
            StatusEvent,
            StatusUpdated,
            ProgressEvent,
            ProgressUpdated,
            SystemEvent,
            SystemWarning,
        )
        assert AgentEvent is not None
        assert ToolCallStarted is not None
        assert SessionStarted is not None

    def test_all_exports_accessible(self):
        from jarvis import api
        for name in api.__all__:
            assert hasattr(api, name), f"Missing export: {name}"


class TestExtensionAPI:
    """Test ExtensionAPI class functionality."""

    def test_create_api(self):
        from jarvis.api import ExtensionAPI
        api = ExtensionAPI(extension_name="test", version="1.0.0")
        assert api.name == "test"
        assert api.version == "1.0.0"

    def test_register_tool(self):
        from jarvis.api import ExtensionAPI, BaseTool, ToolInput, ToolOutput

        class DummyTool(BaseTool):
            name = "dummy"
            description = "A dummy tool"
            input_schema = {"type": "object", "properties": {}}

            async def execute(self, input_data: ToolInput) -> ToolOutput:
                return ToolOutput(success=True, result="ok")

        api = ExtensionAPI(extension_name="test")
        api.tools(DummyTool())
        assert len(api._tool_registrations) == 1

    def test_register_hook(self):
        from jarvis.api import ExtensionAPI, HookStage, HookContext, HookResult

        async def my_hook(ctx: HookContext) -> HookResult:
            return HookResult(proceed=True)

        api = ExtensionAPI(extension_name="test")
        api.hook(HookStage.AFTER_TOOL_CALL, my_hook)
        assert len(api._hook_registrations) == 1

    def test_register_command(self):
        from jarvis.api import ExtensionAPI

        async def cmd():
            return "hello"

        api = ExtensionAPI(extension_name="test")
        api.command("/hello", cmd, "Say hello")
        assert len(api._command_registrations) == 1

    def test_register_shortcut(self):
        from jarvis.api import ExtensionAPI

        api = ExtensionAPI(extension_name="test")
        api.shortcut("ctrl+alt+h", "app.hello", "Hello")
        assert len(api._shortcut_registrations) == 1

    def test_register_agent(self):
        from jarvis.api import ExtensionAPI, AgentDefinition, AgentType

        api = ExtensionAPI(extension_name="test")
        api.agents(AgentDefinition(
            name="test-agent",
            description="A test agent",
            agent_type=AgentType.SUBAGENT,
        ))
        assert len(api._agent_registrations) == 1

    def test_register_event(self):
        from jarvis.api import ExtensionAPI, ToolCallStarted

        async def handler(event):
            pass

        api = ExtensionAPI(extension_name="test")
        api.on(ToolCallStarted, handler)
        assert len(api._event_subscriptions) == 1


class TestToolClasses:
    """Test BaseTool, ToolInput, ToolOutput."""

    def test_tool_input_creation(self):
        from jarvis.api import ToolInput
        ti = ToolInput(message="hello")
        assert ti.message == "hello"

    def test_tool_output_creation(self):
        from jarvis.api import ToolOutput
        to = ToolOutput(success=True, result="data")
        assert to.success is True
        assert to.result == "data"
        assert to.error is None

    def test_tool_output_error(self):
        from jarvis.api import ToolOutput
        to = ToolOutput(success=False, result=None, error="failed")
        assert to.success is False
        assert to.error == "failed"

    def test_custom_tool(self):
        from jarvis.api import BaseTool, ToolInput, ToolOutput

        class EchoTool(BaseTool):
            name = "echo"
            description = "Echo tool"
            input_schema = {
                "type": "object",
                "properties": {"msg": {"type": "string"}},
            }

            async def execute(self, input_data: ToolInput) -> ToolOutput:
                return ToolOutput(success=True, result=input_data.model_dump())

        tool = EchoTool()
        assert tool.name == "echo"
        assert tool.description == "Echo tool"


class TestHookClasses:
    """Test HookStage, HookContext, HookResult."""

    def test_hook_stages(self):
        from jarvis.api import HookStage
        assert HookStage.BEFORE_TOOL_CALL.value == "before_tool_call"
        assert HookStage.AFTER_TOOL_CALL.value == "after_tool_call"
        assert HookStage.BEFORE_TURN.value == "before_turn"
        assert HookStage.AFTER_TURN.value == "after_turn"

    def test_hook_context(self):
        from jarvis.api import HookContext
        ctx = HookContext(tool_name="bash", tool_args={"command": "ls"})
        assert ctx.tool_name == "bash"
        assert ctx.tool_args["command"] == "ls"

    def test_hook_result_proceed(self):
        from jarvis.api import HookResult
        r = HookResult(proceed=True)
        assert r.proceed is True
        assert r.block is False

    def test_hook_result_block(self):
        from jarvis.api import HookResult
        r = HookResult(block=True, reason="blocked")
        assert r.block is True
        assert r.reason == "blocked"

    def test_hook_result_modify(self):
        from jarvis.api import HookResult
        r = HookResult(proceed=True, modify={"command": "safe"})
        assert r.modify == {"command": "safe"}

    def test_hook_result_inject(self):
        from jarvis.api import HookResult
        r = HookResult(proceed=True, inject="<context>")
        assert r.inject == "<context>"


class TestAgentClasses:
    """Test AgentDefinition, AgentType, AgentProfile."""

    def test_agent_definition(self):
        from jarvis.api import AgentDefinition, AgentType
        agent = AgentDefinition(
            name="test",
            description="Test agent",
            agent_type=AgentType.SUBAGENT,
            max_turns=50,
        )
        assert agent.name == "test"
        assert agent.agent_type == AgentType.SUBAGENT
        assert agent.max_turns == 50

    def test_agent_type_values(self):
        from jarvis.api import AgentType
        assert AgentType.AGENT.value == "agent"
        assert AgentType.SUBAGENT.value == "subagent"

    def test_agent_safety_values(self):
        from jarvis.api import AgentSafety
        assert AgentSafety.SAFE.value == "safe"
        assert AgentSafety.NEUTRAL.value == "neutral"
        assert AgentSafety.DESTRUCTIVE.value == "destructive"
        assert AgentSafety.YOLO.value == "yolo"

    def test_agent_profile(self):
        from jarvis.api import AgentProfile, AgentSafety
        profile = AgentProfile(
            name="test-profile",
            display_name="Test",
            description="A test profile",
            safety=AgentSafety.SAFE,
        )
        assert profile.name == "test-profile"
        assert profile.safety == AgentSafety.SAFE


class TestEventTypes:
    """Test event type dataclasses."""

    def test_tool_call_started(self):
        from jarvis.api import ToolCallStarted
        import time
        event = ToolCallStarted(
            timestamp=time.time(),
            tool_name="bash",
            tool_call_id="call_123",
            args={"command": "ls"},
        )
        assert event.tool_name == "bash"
        assert event.args["command"] == "ls"

    def test_agent_started(self):
        from jarvis.api import AgentStarted
        import time
        event = AgentStarted(timestamp=time.time(), agent_name="jarvis", input="hello")
        assert event.agent_name == "jarvis"
        assert event.input == "hello"

    def test_session_started(self):
        from jarvis.api import SessionStarted
        import time
        event = SessionStarted(timestamp=time.time(), model="gpt-4o", cwd="/tmp")
        assert event.model == "gpt-4o"
        assert event.cwd == "/tmp"


class TestJarvisPackage:
    """Test the jarvis package root."""

    def test_version(self):
        import jarvis
        assert jarvis.__version__ is not None
        assert isinstance(jarvis.__version__, str)

    def test_api_module(self):
        import jarvis
        assert hasattr(jarvis, "api")
        assert jarvis.api.ExtensionAPI is not None

    def test_api_via_from_import(self):
        from jarvis.api import ExtensionAPI
        assert ExtensionAPI is not None
