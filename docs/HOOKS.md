# JARVIS Event & Hook System

## 1. Overview

JARVIS uses a **dual-layer event architecture** to enable extensions, observability, and lifecycle interception:

| Layer | Component | Purpose |
|-------|-----------|---------|
| **EventBus** | `bus.py` | Pub/sub event bus — fire-and-forget notifications. Subscribers receive event instances asynchronously. |
| **HookRegistry** | `hooks.py` | Lifecycle hooks — handlers can **block**, **modify**, or **inject** content at specific execution stages. |

The key difference: **events are notifications** (one-way, no return value), while **hooks are interception points** (can block, modify args, inject content).

---

## 2. Directory Structure

| File | Purpose |
|------|---------|
| `jarvis/core/events/__init__.py` | Re-exports all public types and classes |
| `jarvis/core/events/bus.py` | `EventBus` — per-session pub/sub with priority ordering, stats, and polymorphic dispatch |
| `jarvis/core/events/hooks.py` | `HookRegistry`, `HookStage` (16 stages), `HookContext`, `HookResult` |
| `jarvis/core/events/types.py` | 24 event type definitions across 8 categories |

---

## 3. EventBus

A per-session pub/sub event bus. Each agent session owns its own `EventBus` instance.

### Usage

```python
from jarvis.api import EventBus
from jarvis.api import ToolCallStarted, ToolCallEnded

bus = EventBus()

# Subscribe with optional priority (higher runs first)
unsubscribe = bus.subscribe(ToolCallStarted, my_handler, priority=10)

# Emit an event (from within the agent loop)
await bus.emit(ToolCallStarted(
    timestamp=time.time(),
    tool_name="bash",
    tool_call_id="call_abc123",
    args={"command": "ls -la"},
))

# Cleanup
unsubscribe()
# or: bus.clear()  # removes ALL subscribers
```

### API

| Method | Description |
|--------|-------------|
| `subscribe(event_type, handler, *, priority=0)` | Register handler. Returns an `unsubscribe()` callable. |
| `unsubscribe(event_type, handler)` | Remove a specific handler. |
| `clear()` | Remove all subscribers (session teardown). |
| `emit(event)` | Fire event to all subscribers. Async handlers run concurrently; sync handlers run sequentially. |
| `emit_async(event)` | Fire-and-forget variant — logs errors but doesn't propagate. |

### Introspection

| Property/Method | Description |
|-----------------|-------------|
| `subscriber_count` | Total registered handler slots |
| `event_type_count` | Number of distinct event types with subscribers |
| `get_stats()` | Snapshot: total emitted, per-type counts, slowest handler |
| `get_subscribers(event_type=None)` | Subscriber names, optionally filtered by type |

### Polymorphic Dispatch

If no handler is registered for the exact event type, the bus walks the MRO (method resolution order) and dispatches to handlers subscribed to parent classes. For example, a handler subscribed to `ToolEvent` will receive `ToolCallStarted`, `ToolCallEnded`, and `ToolCallError`.

---

## 4. HookRegistry

Hooks are higher-level than raw EventBus subscriptions. They allow extensions to **block**, **modify**, or **inject** content at specific stages of the agent's execution.

### Usage

```python
from jarvis.api import HookRegistry, HookStage, HookContext, HookResult

registry = HookRegistry()

# Register as a decorator
@registry.register(HookStage.BEFORE_TOOL_CALL)
async def safety_gate(ctx: HookContext) -> HookResult:
    if ctx.tool_name == "bash" and "rm -rf" in ctx.tool_args.get("command", ""):
        return HookResult(block=True, reason="Destructive command blocked")
    return HookResult(proceed=True)

# Or register directly
registry.register(HookStage.BEFORE_TOOL_CALL, safety_gate)

# Run all hooks for a stage (called by the agent loop)
result = await registry.run(HookStage.BEFORE_TOOL_CALL, ctx)
if result.block:
    print(f"Blocked: {result.reason}")
```

### API

| Method | Description |
|--------|-------------|
| `register(stage, handler=None)` | Register a handler. Works as decorator or direct call. |
| `unregister(stage, handler)` | Remove a specific handler from a stage. |
| `clear()` | Remove all registered hooks. |
| `run(stage, ctx=None)` | Execute all handlers for a stage. Returns the last non-default `HookResult`. |

### Introspection

| Property/Method | Description |
|-----------------|-------------|
| `get_handlers(stage=None)` | Handler names, optionally filtered by stage |
| `total_handlers` | Total number of registered handlers across all stages |

---

## 5. Hook Stages

16 well-known lifecycle stages where hooks can be registered:

### Agent Lifecycle

| Stage | When | Context Fields |
|-------|------|----------------|
| `BEFORE_AGENT_START` | Before the agent begins processing | `agent_name`, `agent_input` |
| `AFTER_AGENT_START` | After the agent has started | `agent_name`, `session_id` |
| `BEFORE_AGENT_END` | Before the agent finishes | `agent_name`, `agent_output` |
| `AFTER_AGENT_END` | After the agent has finished | `agent_name`, `agent_output` |

### Turn Lifecycle

| Stage | When | Context Fields |
|-------|------|----------------|
| `BEFORE_TURN` | Before each LLM request cycle | `turn_number`, `messages` |
| `AFTER_TURN` | After a turn completes | `turn_number`, `messages` |

### Message / Prompt Building

| Stage | When | Context Fields |
|-------|------|----------------|
| `BEFORE_PROMPT_BUILD` | Before building the message list | `messages`, `agent_input` |
| `AFTER_PROMPT_BUILD` | After the message list is built | `messages` |

### Tool Execution

| Stage | When | Context Fields |
|-------|------|----------------|
| `BEFORE_TOOL_CALL` | Before a tool is executed | `tool_name`, `tool_args` |
| `AFTER_TOOL_CALL` | After a tool completes | `tool_name`, `tool_result`, `tool_error` |

### Session Lifecycle

| Stage | When | Context Fields |
|-------|------|----------------|
| `BEFORE_SESSION_START` | Before a session begins | `session_id`, `model`, `cwd` |
| `AFTER_SESSION_START` | After the session is initialized | `session_id`, `model`, `cwd` |
| `BEFORE_SESSION_SHUTDOWN` | Before the session is torn down | `session_id` |
| `AFTER_SESSION_SHUTDOWN` | After the session is closed | `session_id` |

### System Prompt

| Stage | When | Context Fields |
|-------|------|----------------|
| `BEFORE_SYSTEM_PROMPT` | Before the system prompt is assembled | `system_prompt` |
| `AFTER_SYSTEM_PROMPT` | After the system prompt is finalized | `system_prompt` |

### Skills

| Stage | When | Context Fields |
|-------|------|----------------|
| `BEFORE_SKILL_ACTIVATE` | Before a skill is activated | `skill_name` |
| `AFTER_SKILL_ACTIVATE` | After a skill is activated | `skill_name` |

---

## 6. HookContext

Passed to every hook handler. Extensions read from this to make decisions; in some stages they can write back to modify behavior.

| Field | Type | Description |
|-------|------|-------------|
| `agent_name` | `str` | Current agent name |
| `agent_input` | `str` | User input for this turn |
| `agent_output` | `str` | Agent's final output |
| `agent_error` | `str \| None` | Error message if any |
| `turn_number` | `int` | Current turn iteration |
| `messages` | `list[dict] \| None` | Full message list (some hooks can modify) |
| `tool_name` | `str` | Name of the tool being called |
| `tool_args` | `dict[str, Any]` | Arguments passed to the tool |
| `tool_result` | `Any` | Result from tool execution |
| `tool_error` | `str \| None` | Error from tool execution |
| `system_prompt` | `str` | Current system prompt text |
| `session_id` | `str` | Unique session identifier |
| `model` | `str` | Current model name |
| `cwd` | `str` | Current working directory |
| `skill_name` | `str` | Name of the skill being activated |
| `extra` | `dict[str, Any]` | Custom extension data (arbitrary key-value store) |

---

## 7. HookResult

Return value from a hook handler. Controls whether execution proceeds, is blocked, or is modified.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `proceed` | `bool` | `True` | If `True`, normal execution continues. If `False` (and `block` is also `False`), the stage is skipped without error. |
| `block` | `bool` | `False` | If `True`, the action is blocked with a reason message. Remaining handlers are skipped. |
| `reason` | `str` | `""` | Human-readable explanation for blocking or skipping. |
| `modify` | `dict \| None` | `None` | For stages that support modification (e.g., `BEFORE_TOOL_CALL`), return updated args here. |
| `inject` | `str \| None` | `None` | Content to inject into the pipeline (e.g., an extra system prompt message). |

### Convenience Constructors

```python
# Allow execution to continue
HookResult(proceed=True)

# Block with a reason
HookResult(block=True, reason="Permission denied")

# Skip the stage silently
HookResult(proceed=False, reason="Not applicable")

# Modify tool arguments
HookResult(proceed=True, modify={"command": "safe_command"})

# Inject content into the pipeline
HookResult(proceed=True, inject="<additional context>")
```

---

## 8. Event Types

24 event types across 8 categories. All are frozen dataclasses (immutable).

### Agent Lifecycle (4)

| Event | Base | Fields | When |
|-------|------|--------|------|
| `AgentEvent` | — | `timestamp`, `agent_name` | Base class |
| `AgentStarted` | `AgentEvent` | `input` | Agent begins processing |
| `AgentEnded` | `AgentEvent` | `output` | Agent finishes processing |
| `AgentError` | `AgentEvent` | `error`, `recoverable` | Agent encounters an error |

### Turn Events (3)

| Event | Base | Fields | When |
|-------|------|--------|------|
| `TurnEvent` | — | `timestamp`, `turn_number` | Base class |
| `TurnStarted` | `TurnEvent` | — | Start of each LLM request cycle |
| `TurnEnded` | `TurnEvent` | `tool_count` | Turn completes with assistant message and tool results |

### Message / Streaming (4)

| Event | Base | Fields | When |
|-------|------|--------|------|
| `MessageEvent` | — | `timestamp` | Base class |
| `MessageDelta` | `MessageEvent` | `delta`, `content_index` | Every chunk of text from the LLM |
| `MessageComplete` | `MessageEvent` | `content`, `content_index` | Full message block completed |
| `ThinkingDelta` | `MessageEvent` | `delta` | Reasoning/thinking chunks from the LLM |

### Tool Execution (4)

| Event | Base | Fields | When |
|-------|------|--------|------|
| `ToolEvent` | — | `timestamp`, `tool_name`, `tool_call_id` | Base class |
| `ToolCallStarted` | `ToolEvent` | `args` | Before tool execution |
| `ToolCallEnded` | `ToolEvent` | `result`, `duration_ms`, `success` | After tool completes |
| `ToolCallError` | `ToolEvent` | `error`, `duration_ms` | Tool execution failed |

### Session Events (5)

| Event | Base | Fields | When |
|-------|------|--------|------|
| `SessionEvent` | — | `timestamp`, `session_id` | Base class |
| `SessionStarted` | `SessionEvent` | `model`, `cwd` | New session begins |
| `SessionShutdown` | `SessionEvent` | `reason` | Before session is closed |
| `SkillActivated` | `SessionEvent` | `skill_name` | Skill activated |
| `SkillDeactivated` | `SessionEvent` | `skill_name` | Skill deactivated |

### Extension Events (4)

| Event | Base | Fields | When |
|-------|------|--------|------|
| `ExtensionEvent` | — | `timestamp`, `extension_name` | Base class |
| `ExtensionLoaded` | `ExtensionEvent` | `version`, `tools_count` | Extension successfully loaded |
| `ExtensionUnloaded` | `ExtensionEvent` | `reason` | Extension unloaded |
| `ExtensionError` | `ExtensionEvent` | `error` | Extension encountered an error |

### Status / Progress (3)

| Event | Base | Fields | When |
|-------|------|--------|------|
| `StatusEvent` | — | `timestamp`, `message` | Base class |
| `StatusUpdated` | `StatusEvent` | `status` | Agent status changed |
| `ProgressEvent` | — | `timestamp`, `task` | Base class |
| `ProgressUpdated` | `ProgressEvent` | `progress` (0.0–1.0) | Progress on long-running task |

### System Events (2)

| Event | Base | Fields | When |
|-------|------|--------|------|
| `SystemEvent` | — | `timestamp` | Base class |
| `SystemWarning` | `SystemEvent` | `message`, `source` | Non-fatal warning (e.g., config issues) |

---

## 9. EventBus vs HookRegistry — When to Use Which

| Use Case | Use | Why |
|----------|-----|-----|
| Log every tool call | **EventBus** | One-way notification, no need to block or modify |
| Block dangerous commands | **HookRegistry** | Need to return `HookResult(block=True)` |
| Track agent status for UI | **EventBus** | Fire-and-forget status updates |
| Modify tool arguments | **HookRegistry** | Return `HookResult(modify={...})` |
| Inject extra context into prompts | **HookRegistry** | Return `HookResult(inject="...")` |
| Record metrics/analytics | **EventBus** | Passive observation |
| Safety gate before tool execution | **HookRegistry** | Can block with a reason |
| Notify extensions of session start | **Both** | EventBus for notification, HookRegistry if extension needs to initialize something before the session proceeds |

---

## 10. Integration with Extensions

Extensions use the `ExtensionAPI` to register with both systems:

```python
# In an extension file:
from jarvis.api import ExtensionAPI, HookStage, HookContext, HookResult
from jarvis.api import ToolCallStarted

async def jarvis(api: ExtensionAPI):
    # EventBus subscription
    api.on(ToolCallStarted, log_tool_call)

    # Hook registration
    api.hook(HookStage.BEFORE_TOOL_CALL, safety_gate)
```

The `ExtensionRunner.bind()` method flushes these registrations into the live session's `EventBus` and `HookRegistry`.

---

## 11. Execution Flow

```
Agent Loop
    │
    ├── HookRegistry.run(BEFORE_TURN, ctx)
    │       └── handlers called in registration order
    │       └── if any returns block=True → skip turn
    │
    ├── EventBus.emit(TurnStarted(...))
    │       └── all subscribers notified (fire-and-forget)
    │
    ├── LLM call → tool calls requested
    │
    ├── HookRegistry.run(BEFORE_TOOL_CALL, ctx)
    │       └── if block=True → skip tool, return reason
    │       └── if modify={...} → use modified args
    │
    ├── EventBus.emit(ToolCallStarted(...))
    │
    ├── tool.execute(input_data)
    │
    ├── EventBus.emit(ToolCallEnded(...))
    │
    ├── HookRegistry.run(AFTER_TOOL_CALL, ctx)
    │       └── if inject="..." → inject into pipeline
    │
    └── HookRegistry.run(AFTER_TURN, ctx)
```

---

## 12. Error Handling

- **Hook handlers**: If a hook handler raises an exception, it is logged and the next handler continues. The hook does **not** block on error.
- **EventBus handlers**: Async handlers that fail are caught by `asyncio.gather(return_exceptions=True)` and logged. Sync handler failures are caught individually.
- **Short-circuit**: Only `HookResult(block=True)` stops the handler chain. Errors do not.
