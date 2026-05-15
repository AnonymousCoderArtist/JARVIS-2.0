"""Tests for the extension-based plugin system.

The old ``discover_and_register_plugins()`` method on ToolRegistry has been
removed. Custom tools are now loaded via the extension system
(``.jarvis/extensions/``) using ``ExtensionRunner``.
"""

import pytest
from core.tools.registry import ToolRegistry


@pytest.mark.asyncio
async def test_extension_operations_backend():
    """Verify that tools can use the operations registry injected by ToolRegistry."""
    registry = ToolRegistry()

    # OperationsRegistry should be available
    assert registry.operations_registry is not None

    # Tools registered via ToolRegistry get operations injected
    from core.tools.base import BaseTool, ToolInput, ToolOutput

    class TestTool(BaseTool):
        name = "test_ops_backend"
        description = "Test tool for operations backend"
        input_schema = {"type": "object", "properties": {}}

        async def execute(self, input_data: ToolInput) -> ToolOutput:
            # Verify that file_ops is accessible
            exists = await self.file_ops.file_exists("core/tools/registry.py")
            assert exists is True
            return ToolOutput(success=True, result="operations_working")

    registry.register(TestTool())
    result = await registry.execute_tool("test_ops_backend", {})

    assert result.success is True
    assert result.result == "operations_working"

    print("✓ Tool operations backend injection works")


@pytest.mark.asyncio
async def test_tool_registry_event_bus():
    """Verify that ToolRegistry emits ToolCallStarted/Ended events via the event bus."""
    from core.events import EventBus
    from core.events.types import ToolCallStarted

    registry = ToolRegistry()
    bus = EventBus()
    registry.event_bus = bus

    events = []
    bus.subscribe(ToolCallStarted, lambda e: events.append(e))

    from core.tools.base import BaseTool, ToolInput, ToolOutput

    class SimpleTool(BaseTool):
        name = "simple"
        description = "A simple tool"
        input_schema = {"type": "object", "properties": {}}
        async def execute(self, input_data: ToolInput) -> ToolOutput:
            return ToolOutput(success=True, result="ok")

    registry.register(SimpleTool())
    await registry.execute_tool("simple", {})

    assert len(events) == 1
    assert events[0].tool_name == "simple"
    print("✓ Tool event bus integration works")
