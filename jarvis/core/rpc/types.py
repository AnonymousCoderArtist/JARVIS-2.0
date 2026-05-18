"""RPC type definitions — JSONL command/response/event schemas.

Protocol
--------
Framing: strict JSONL (``\\n`` delimited)

**stdin** (commands from host):
.. code-block:: json

    {"id": "1", "type": "prompt", "message": "Hello", "images": []}

**stdout** (events + responses from agent):
.. code-block:: json

    {"id": "1", "type": "response", "success": true, "data": "..."}
    {"type": "event", "event": "text_delta", "delta": "Hello"}
    {"type": "event", "event": "tool_call_start", "tool_name": "read", "args": {...}}
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# ---------------------------------------------------------------------------
# Commands (received on stdin)
# ---------------------------------------------------------------------------

@dataclass
class RpcCommand:
    """A command received from the RPC client."""
    id: str
    type: str  # "prompt", "steer", "follow_up", "bash", "compact", "new_session", "get_state", "get_messages", "get_tools", "set_model"
    message: str = ""
    images: list[str] | None = None  # base64-encoded image data
    command: str = ""  # for "bash" commands
    timeout: int = 60
    model: str = ""  # for "set_model" commands


# ---------------------------------------------------------------------------
# Responses (sent to stdout — paired with command id)
# ---------------------------------------------------------------------------

@dataclass
class RpcResponse:
    """A response to a specific command."""
    id: str
    type: str = "response"
    success: bool = True
    data: Any = None
    error: str | None = None


# ---------------------------------------------------------------------------
# Events (sent to stdout — streaming, no id)
# ---------------------------------------------------------------------------

@dataclass
class RpcEvent:
    """An asynchronous event from the agent loop."""
    type: str = "event"
    event: str = ""  # event type name
    # Payload fields (varies by event type)
    delta: str = ""
    content: str = ""
    tool_name: str = ""
    tool_args: dict[str, Any] = field(default_factory=dict)
    tool_result: Any = None
    tool_call_id: str = ""
    success: bool = True
    duration_ms: float = 0.0
    error: str = ""
    status: str = ""
    progress: float = 0.0
    task: str = ""
    turn_number: int = 0


# ---------------------------------------------------------------------------
# Serialization helpers
# ---------------------------------------------------------------------------

def serialize(obj: Any) -> str:
    """Serialize a dataclass to a JSONL line."""
    import json
    if hasattr(obj, "__dataclass_fields__"):
        d = {f.name: getattr(obj, f.name) for f in obj.__dataclass_fields__.values()}
        # Clean None values
        d = {k: v for k, v in d.items() if v is not None}
        return json.dumps(d, default=str)
    return json.dumps(obj, default=str)


def make_event(event_type: str, **kwargs: Any) -> RpcEvent:
    """Create an RpcEvent with the given type and kwargs."""
    return RpcEvent(event=event_type, **kwargs)
