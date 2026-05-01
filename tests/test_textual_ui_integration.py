import asyncio

import pytest

from core.agents.coding_agent import CodingAgent
from core.tools.base import ToolOutput
from core.tools.registry import ToolRegistry
from interface.textual_ui.agent_loop import AgentLoop
from interface.textual_ui.app import VibeApp
from interface.textual_ui.cli_adapters import ToolUIDataAdapter
from interface.textual_ui.tui_main import Config, create_tool_registry
from interface.textual_ui.types import (
    AssistantEvent,
    ReasoningEvent,
    ToolCallEvent,
    ToolResultEvent,
    UserMessageEvent,
)
from interface.textual_ui.widgets.messages import AssistantMessage, ErrorMessage, UserMessage
from jarvis.cli import _parse_args


class FakeStreamingAgent:
    def __init__(self) -> None:
        self.memory = []
        self.stream_callback = None
        self.tool_call_callback = None
        self.tool_result_callback = None
        self.reasoning_callback = None

    def get_memory_context(self) -> str:
        return ""

    def rebuild_system_prompt(self) -> None:
        pass

    def update_context(self, key: str, value: str) -> None:
        setattr(self, key, value)

    async def process(self, prompt: str) -> str:
        self.reasoning_callback("thinking")
        self.stream_callback("hel")
        await asyncio.sleep(0)
        self.stream_callback("lo")
        self.tool_call_callback("fake_tool", {"x": 1})
        self.tool_result_callback(
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
        agent=FakeStreamingAgent(),
        config=Config("gpt-4o", None, "test-key", "openai"),
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

    assert display.summary == (
        "Calling file_read(path=core/agents/base.py, offset=10, limit=20)"
    )


def test_system_prompt_includes_registered_tool_descriptions() -> None:
    registry = ToolRegistry()

    class ExampleTool:
        name = "example_tool"
        description = "Example tool description."
        input_schema = {"type": "object", "properties": {}}

    registry.register(ExampleTool())
    agent = CodingAgent(FakeNoToolsProvider(), registry, model="fake-no-tools", config_getter=None)

    assert "### example_tool" in agent.system_prompt
    assert "Example tool description." in agent.system_prompt


@pytest.mark.asyncio
async def test_vibe_app_submit_runs_agent_turn_and_renders_response() -> None:
    agent_loop = AgentLoop(
        agent=FakeStreamingAgent(),
        config=Config("gpt-4o", None, "test-key", "openai"),
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
