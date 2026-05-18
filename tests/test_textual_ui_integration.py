import asyncio
from types import SimpleNamespace

import pytest

from jarvis.core.agents.jarvis_v2 import JarvisV2 as CodingAgent
from jarvis.core.tools.base import ToolOutput
from jarvis.core.tools.registry import ToolRegistry
from jarvis.interface.textual_ui.agent_loop import AgentLoop
from jarvis.interface.textual_ui.app import VibeApp
from jarvis.interface.textual_ui.cli_adapters import (
    CommandCompleter,
    CommandRegistry,
    SlashCommandController,
    ToolUIDataAdapter,
)
from jarvis.interface.textual_ui.tui_main import Config, create_tool_registry
from jarvis.interface.textual_ui.types import (
    AssistantEvent,
    ReasoningEvent,
    ToolCallEvent,
    ToolResultEvent,
    UserMessageEvent,
)
from jarvis.interface.textual_ui.widgets.chat_input.container import ChatInputContainer
from jarvis.interface.textual_ui.widgets.messages import AssistantMessage, ErrorMessage, UserMessage
from jarvis.cli import _parse_args


class FakeStreamingAgent:
    def __init__(self) -> None:
        self.memory = []
        self.stream_callback = None
        self.tool_call_callback = None
        self.tool_result_callback = None
        self.reasoning_callback = None
        self.model = "gpt-4o"
        self._config_getter = None

    def set_config_getter(self, config_getter) -> None:
        self._config_getter = config_getter

    def set_approval_callback(self, callback) -> None:
        self._approval_callback = callback

    def set_user_input_callback(self, callback) -> None:
        self._user_input_callback = callback

    def set_system_prompt(self, prompt: str) -> None:
        self._system_prompt = prompt

    def clear_session_rules(self) -> None:
        pass

    def approve_always(self, tool_name: str, permissions) -> None:
        pass

    def rebuild_system_prompt(self) -> None:
        pass

    def update_context(self, key: str, value: str) -> None:
        setattr(self, key, value)

    def clear_memory(self) -> None:
        self.memory.clear()

    async def process(self, prompt: str) -> str:
        self.reasoning_callback("thinking")  # type: ignore
        self.stream_callback("hel")  # type: ignore
        await asyncio.sleep(0)
        self.stream_callback("lo")  # type: ignore
        self.tool_call_callback("fake_tool", {"x": 1})  # type: ignore
        self.tool_result_callback(  # type: ignore
            "fake_tool",
            {"x": 1},
            ToolOutput(success=True, result="tool ok"),
        )
        self.memory.append({"content": prompt, "response": "hello"})
        return "hello"


class FakeNoToolsProvider:
    async def generate_with_tools(self, *args, **kwargs):
        raise RuntimeError("tools are not supported by this model")

    async def generate(self, *args, **kwargs):
        if kwargs.get("stream"):
            async def stream():
                yield {"type": "text", "content": "plain "}
                yield {"type": "text", "content": "response"}

            return stream()
        return {"content": "plain response"}

    def get_available_models(self) -> list[str]:
        return ["fake-no-tools"]


@pytest.mark.asyncio
async def test_agent_loop_streams_chunks_without_duplicate_final_response() -> None:
    agent_loop = AgentLoop(
        agent=FakeStreamingAgent(),  # type: ignore
        config=Config("gpt-4o", None, "test-key", "openai"),  # type: ignore
        tool_registry=create_tool_registry(),
    )

    events = [event async for event in agent_loop.act("say hi")]

    assert [type(event) for event in events] == [
        UserMessageEvent,
        ReasoningEvent,
        AssistantEvent,
        AssistantEvent,
        ToolCallEvent,
        ToolResultEvent,
    ]
    assert [event.content for event in events if isinstance(event, AssistantEvent)] == [
        "hel",
        "lo",
    ]
    assert [event.result for event in events if isinstance(event, ToolResultEvent)] == [
        "tool ok",
    ]


@pytest.mark.asyncio
async def test_core_agent_falls_back_when_model_rejects_tools() -> None:
    agent = CodingAgent(FakeNoToolsProvider(), ToolRegistry(), model="fake-no-tools", config_getter=None)
    chunks: list[str] = []
    agent.stream_callback = chunks.append

    response = await agent.process("hi")

    assert response == "plain response"
    assert chunks == ["plain ", "response"]


def test_uppercase_tui_flag_is_accepted() -> None:
    launch_cli, launch_tui, *_ = _parse_args(["--TUI"])

    assert launch_cli is False
    assert launch_tui is True


def test_tool_call_display_shows_actual_tool_name_and_arguments() -> None:
    event = ToolCallEvent(
        tool_name="file_read",
        tool_args={"path": "core/agents/base.py", "offset": 10, "limit": 20},
        tool_class="FileReadTool",
    )

    display = ToolUIDataAdapter(event.tool_class).get_call_display(event)

    assert display.summary == "FILE_READ path=core/agents/base.py, offset=10, limit=20"


def test_tool_is_available_via_registry() -> None:
    registry = ToolRegistry()

    class ExampleTool:
        name = "example_tool"
        description = "Example tool description."

    registry.register(ExampleTool())  # type: ignore

    tool = registry.get("example_tool")
    assert tool is not None
    assert tool.description == "Example tool description."


def test_tui_help_text_shows_command_usage_hints() -> None:
    registry = CommandRegistry()

    help_text = registry.get_help_text()

    assert "/skills [activate <name>] - List and manage skills" in help_text
    assert "/profile [<profile>] - Switch or list agent profiles" in help_text


def test_tui_completion_entries_include_command_usage_hints() -> None:
    container = ChatInputContainer(command_registry=CommandRegistry())

    entries = container._get_slash_entries()

    assert (
        "/skills",
        "List and manage skills · [activate <name>]",
    ) in entries
    assert (
        "/profile",
        "Switch or list agent profiles · [<profile>]",
    ) in entries


def test_tui_slash_command_argument_completion_suggests_matching_args() -> None:
    class FakeParent:
        def __init__(self) -> None:
            self.suggestions: list[tuple[str, str]] = []
            self.replacement: tuple[int, int, str] | None = None

        def render_completion_suggestions(
            self, suggestions: list[tuple[str, str]], selected_index: int
        ) -> None:
            self.suggestions = suggestions

        def clear_completion_suggestions(self) -> None:
            self.suggestions = []

        def replace_completion_range(
            self, start: int, end: int, replacement: str
        ) -> None:
            self.replacement = (start, end, replacement)

    parent = FakeParent()
    controller = SlashCommandController(
        CommandCompleter(
            lambda: [("/skills", "List and manage skills")],
            lambda alias, _text: (
                [("activate", "Activate a skill")]
                if alias == "/skills"
                else []
            ),
        ),
        parent,
    )

    text = "/skills act"
    controller.on_text_changed(text, len(text))

    assert parent.suggestions == [("activate", "Activate a skill", "activate")]

    result = controller.on_key(SimpleNamespace(key="tab"), text, len(text))

    assert str(result) == "handled"
    assert parent.replacement == (8, 11, "activate ")


def test_vibe_app_provides_live_profile_argument_entries() -> None:
    agent_loop = AgentLoop(
        agent=FakeStreamingAgent(),  # type: ignore
        config=Config("gpt-4o", None, "test-key", "openai"),  # type: ignore
        tool_registry=create_tool_registry(),
    )
    app = VibeApp(
        agent_loop,
        update_notifier=None,
        update_cache_repository=None,
        plan_offer_gateway=None,
    )

    entries = app._get_slash_argument_entries("/profile", "/profile ")

    assert ("default", "Current profile") in entries
    assert any(label == "plan" for label, _ in entries)


@pytest.mark.asyncio
async def test_tui_profile_command_arg_switches_profile() -> None:
    agent_loop = AgentLoop(
        agent=FakeStreamingAgent(),  # type: ignore
        config=Config("gpt-4o", None, "test-key", "openai"),  # type: ignore
        tool_registry=create_tool_registry(),
    )
    app = VibeApp(
        agent_loop,
        update_notifier=None,
        update_cache_repository=None,
        plan_offer_gateway=None,
    )

    mounted_messages: list[str] = []

    async def capture_mount(widget) -> None:
        mounted_messages.append(getattr(widget, "_content", ""))

    app._mount_and_scroll = capture_mount  # type: ignore
    app._refresh_profile_widgets = lambda: None  # type: ignore

    await app._switch_to_profile_app(cmd_args="plan")

    assert agent_loop.agent_profile.name == "plan"
    assert mounted_messages == ["Switched to profile: plan"]


@pytest.mark.asyncio
async def test_vibe_app_submit_runs_agent_turn_and_renders_response() -> None:
    agent_loop = AgentLoop(
        agent=FakeStreamingAgent(),  # type: ignore
        config=Config("gpt-4o", None, "test-key", "openai"),  # type: ignore
        tool_registry=create_tool_registry(),
    )
    app = VibeApp(
        agent_loop,
        update_notifier=None,
        update_cache_repository=None,
        plan_offer_gateway=None,
    )

    async with app.run_test(size=(100, 40)) as pilot:
        await pilot.pause(0.5)
        await pilot.press("h", "i", "enter")
        await pilot.pause(1.0)

        assert [message.get_content() for message in app.query(UserMessage)] == ["hi"]
        assert [
            message.get_content() for message in app.query(AssistantMessage)
        ] == ["hello"]
        assert list(app.query(ErrorMessage)) == []
        assert app._agent_running is False
        assert app._agent_task is None
