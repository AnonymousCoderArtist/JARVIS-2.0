"""Headless smoke tests for redesigned JARVIS TUI."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from interface.tui.app import JARVISApp
from interface.tui.widgets.chat_panel import ChatPanel
from interface.tui.widgets.status_bar import StatusBar


def _stub_initialize_systems(self):
    self._initialize_tools()
    self.agent_coordinator = None


class DummyCoordinator:
    def __init__(self):
        self.calls = []

    async def execute_task(self, task: str) -> str:
        self.calls.append(task)
        return f"echo:{task}"


@pytest.mark.asyncio
async def test_redesigned_layout_mounts(monkeypatch):
    monkeypatch.setattr(JARVISApp, "_initialize_systems", _stub_initialize_systems)
    app = JARVISApp()
    async with app.run_test():
        assert app.query_one("#transcript-panel", ChatPanel)
        assert app.query_one("#input-panel")
        assert app.query_one("#status-bar", StatusBar)


@pytest.mark.asyncio
async def test_commands_and_text_submission(monkeypatch):
    monkeypatch.setattr(JARVISApp, "_initialize_systems", _stub_initialize_systems)
    app = JARVISApp()
    app.agent_coordinator = DummyCoordinator()
    async with app.run_test():
        await app._handle_submit("/status")
        transcript = app.query_one("#transcript-panel", ChatPanel)
        assert any(entry["kind"] == "status" for entry in transcript.entries)

        await app._handle_submit("hello from test")
        assert app.agent_coordinator.calls == ["hello from test"]
        assert any(
            entry.get("role") == "assistant" and "echo:hello from test" in entry.get("content", "")
            for entry in transcript.entries
            if entry.get("role") == "assistant"
        )
