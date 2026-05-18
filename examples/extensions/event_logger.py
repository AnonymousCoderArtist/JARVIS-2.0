"""Extension that subscribes to EventBus events and logs them.

Demonstrates the ``api.on()`` pattern for event-driven behaviour.
"""

from jarvis.core.events.types import ToolCallEnded, ToolCallStarted

__version__ = "1.0.0"
__description__ = "Logs all tool execution events to console"


async def jarvis(api):
    """Print a message every time a tool starts or ends."""

    async def on_tool_start(event):
        print(f"[EVENT] Tool started: {event.tool_name} args={event.args}")

    async def on_tool_end(event):
        status = "OK" if event.success else "FAIL"
        print(f"[EVENT] Tool ended: {event.tool_name} [{status}] in {event.duration_ms:.0f}ms")

    api.on(ToolCallStarted, on_tool_start)
    api.on(ToolCallEnded, on_tool_end)
