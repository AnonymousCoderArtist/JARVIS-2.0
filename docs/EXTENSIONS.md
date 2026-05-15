# JARVIS Extension System

## 1. Overview

The JARVIS extension system is a **plugin architecture** that allows users and third-party developers to extend JARVIS with custom tools, lifecycle hooks, slash commands, keyboard shortcuts, and event handlers. Extensions are plain Python files — no build step, no package manager required — loaded dynamically at session startup.

The system is built around four core components:

| Component | File | Purpose |
|-----------|------|---------|
| **ExtensionAPI** | `api.py` | Public surface exposed to every extension — register tools, hooks, commands, shortcuts, and event subscriptions |
| **ExtensionLoader** | `loader.py` | Dynamic discovery and loading of extension modules from filesystem paths and pip entry points |
| **ExtensionRunner** | `runner.py` | Orchestrates the full lifecycle — discover → load → bind → run → unbind |
| **ExtensionRegistry** | `registry.py` | Tracks all loaded extensions, provides introspection and conflict detection |

---

## 2. Directory Structure

| Path | Purpose |
|------|---------|
| `core/extensions/` | Extension system core — API, loader, runner, registry, types |
| `core/extensions/api.py` | `ExtensionAPI` class — the object every extension receives |
| `core/extensions/loader.py` | Discovery and loading logic — filesystem + pip entry points |
| `core/extensions/runner.py` | `ExtensionRunner` — lifecycle orchestration per session |
| `core/extensions/registry.py` | `ExtensionRegistry` — metadata tracking and conflict detection |
| `core/extensions/types.py` | Type definitions — `ExtensionManifest`, `ExtensionContext`, `ToolRegistration`, `ExtensionLoadResult`, handler type aliases |
| `.jarvis/extensions/*.py` | Project-local extensions (highest precedence) |
| `~/.jarvis/extensions/*.py` | Global user extensions |
| `examples/extensions/` | Reference extension examples (hello_world, audit_tool, safety_gate, event_logger, ssh_operations) |

---

## 3. Extension Lifecycle

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Session Startup                               │
│                                                                      │
│  1. discover_and_load()                                              │
│     ┌──────────────────────────────────────────────────────────┐    │
│     │  Scan .jarvis/extensions/*.py  (project, highest prio)   │    │
│     │  Scan ~/.jarvis/extensions/*.py  (user global)           │    │
│     │  Scan pip entry points (jarvis.extensions group)         │    │
│     │  De-duplicate by filename stem (higher prio wins)        │    │
│     └──────────────────────────────────────────────────────────┘    │
│                              │                                       │
│                              ▼                                       │
│  2. load_from_file()                                                 │
│     ┌──────────────────────────────────────────────────────────┐    │
│     │  importlib.util.spec_from_file_location()                │    │
│     │  spec.loader.exec_module()                               │    │
│     │  Find factory: jarvis_extension / __jarvis_extension__   │    │
│     │                  / default                               │    │
│     │  Build ExtensionManifest from module attrs               │    │
│     └──────────────────────────────────────────────────────────┘    │
│                              │                                       │
│                              ▼                                       │
│  3. bind()                                                           │
│     ┌──────────────────────────────────────────────────────────┐    │
│     │  For each pending extension:                             │    │
│     │    1. Create ExtensionAPI(name, version)                 │    │
│     │    2. Call factory_fn(api) — extension registers stuff   │    │
│     │    3. api._bind() — flush registrations to live session  │    │
│     │       • Register tools (with override detection)         │    │
│     │       • Subscribe to EventBus events                     │    │
│     │       • Register lifecycle hooks                         │    │
│     │       • Register slash commands                          │    │
│     │       • Register keyboard shortcuts                      │    │
│     └──────────────────────────────────────────────────────────┘    │
│                              │                                       │
│                              ▼                                       │
│  4. Agent runs — extensions are active                               │
│                                                                      │
│  5. unbind()                                                         │
│     ┌──────────────────────────────────────────────────────────┐    │
│     │  For each bound API: api._unbind()                       │    │
│     │  Clear references, session teardown                      │    │
│     └──────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 4. Writing an Extension

An extension is a single Python file that exports an async factory function:

```python
# .jarvis/extensions/my_extension.py

__version__ = "1.0.0"
__description__ = "My custom extension"
__author__ = "Your Name"

from core.extensions.api import ExtensionAPI
from core.tools.base import BaseTool, ToolInput, ToolOutput


class MyTool(BaseTool):
    name = "my_tool"
    description = "Does something useful"
    input_schema = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "The query to process"}
        },
        "required": ["query"],
    }

    async def execute(self, input_data: ToolInput) -> ToolOutput:
        query = input_data.get("query", "")
        return ToolOutput(success=True, output=f"Processed: {query}")


async def jarvis_extension(api: ExtensionAPI):
    """Default factory function — receives the ExtensionAPI instance."""

    # Register a custom tool
    api.register_tool(MyTool())

    # Subscribe to an event
    from core.events.types import ToolCallStarted
    api.on(ToolCallStarted, my_event_handler)

    # Register a lifecycle hook
    from core.events.hooks import HookStage, HookContext, HookResult
    api.register_hook(HookStage.BEFORE_TOOL_CALL, safety_gate_hook)

    # Register a slash command
    api.register_command("/hello", hello_command, "Say hello")

    # Register a keyboard shortcut
    api.register_shortcut("ctrl+alt+h", "app.hello", "Hello shortcut")


async def my_event_handler(event):
    """Called when ToolCallStarted is emitted."""
    print(f"Tool called: {event.tool_name}")


async def safety_gate_hook(ctx: HookContext) -> HookResult:
    """Called before every tool call — can modify or block."""
    return HookResult.continue_()


async def hello_command() -> str:
    return "Hello from my extension!"
```

### Factory Function Names

The loader looks for the factory function in this order:
1. `jarvis_extension(api)` — preferred
2. `__jarvis_extension__(api)` — alternative
3. `default(api)` — fallback

### Module-Level Metadata (Optional)

| Attribute | Type | Description |
|-----------|------|-------------|
| `__version__` | `str` | Semantic version (default: `"1.0.0"`) |
| `__description__` | `str` | Human-readable description |
| `__author__` | `str` | Author name or handle |

---

## 5. ExtensionAPI Reference

Every extension receives an `ExtensionAPI` instance with these methods:

### Registration Methods

| Method | Description |
|--------|-------------|
| `register_tool(tool)` | Register a `BaseTool` instance. If a tool with the same name exists, it is **overridden** (built-in tools can be replaced). |
| `register_command(name, handler, description)` | Register a slash command (e.g., `"/my-command"`). Handler returns `str` or `None`. |
| `on(event_type, handler)` | Subscribe to an `EventBus` event. Handler receives the event instance. |
| `register_hook(stage, handler)` | Register a lifecycle hook at a `HookStage`. Handler receives `HookContext`, returns `HookResult`. |
| `register_shortcut(key, action_id, description)` | Register a keyboard shortcut mapping. |

### Runtime Accessors (valid after `bind()`)

| Property | Description |
|----------|-------------|
| `api.event_bus` | The session's `EventBus` (read-only) |
| `api.tool_registry` | The session's `ToolRegistry` (read-only) |
| `api.hook_registry` | The session's `HookRegistry` (read-only) |
| `api.session` | The current `AgentSession` (read-only) |
| `api.operations_registry` | The session's `OperationsRegistry` — extensions can swap backends (SSH, sandbox, Docker) |
| `api.name` | Extension name |
| `api.version` | Extension version |

---

## 6. Type Definitions

### ExtensionManifest

Metadata about an installed extension:

| Field | Type | Description |
|-------|------|-------------|
| `name` | `str` | Unique extension name (1–64 chars) |
| `version` | `str` | Semantic version (default: `"1.0.0"`) |
| `description` | `str` | Human-readable description (max 512 chars) |
| `author` | `str` | Author name (max 128 chars) |
| `requires` | `list[str]` | Names of extensions that must load first |
| `tools` | `list[str]` | Tool names this extension provides (populated at registration) |
| `hooks` | `list[str]` | Hook stages this extension uses |
| `settings_schema` | `dict \| None` | JSON Schema for extension-specific settings |
| `source_path` | `str` | Filesystem path the extension was loaded from |

### ExtensionContext

Passed to extension factories and handlers:

| Field | Type | Description |
|-------|------|-------------|
| `api` | `ExtensionAPI` | The API instance bound to this extension's session |
| `agent_name` | `str` | Current agent name |
| `model` | `str` | Current model name |
| `session_id` | `str` | Current session ID |
| `cwd` | `str` | Current working directory |
| `messages` | `list[dict] \| None` | Working message list (some hooks can modify) |
| `storage` | `dict[str, Any]` | Extension-local storage (survives for session lifetime) |

### Handler Type Aliases

| Type | Signature |
|------|-----------|
| `EventHandler` | `Callable[[Any], Coroutine \| None]` |
| `HookHandler` | `Callable[[HookContext], Coroutine[HookResult] \| HookResult]` |
| `CommandHandler` | `Callable[..., Coroutine[str \| None] \| str \| None]` |
| `ShortcutHandler` | `Callable[[], Coroutine \| None]` |

---

## 7. Discovery & Precedence

Extensions are discovered from three sources, in precedence order (highest → lowest):

1. **Project-local**: `.jarvis/extensions/*.py` — highest priority, project-specific
2. **User global**: `~/.jarvis/extensions/*.py` — shared across all projects
3. **pip entry points**: packages registered under the `jarvis.extensions` entry point group

### De-duplication

If the same filename (stem) exists in multiple locations, the **higher-precedence** version wins. For example, `.jarvis/extensions/ssh.py` overrides `~/.jarvis/extensions/ssh.py`.

---

## 8. Tool Override & Conflict Detection

When an extension registers a tool with the same name as an existing built-in tool:

1. The built-in tool is **replaced** in the `ToolRegistry`
2. A conflict info dict is recorded: `{"extension": "...", "tool": "...", "type": "override"}`
3. The conflict is logged and returned from `bind()` for diagnostics

The `ExtensionRegistry` provides:
- `get_tool_origin(tool_name)` — which extension provides a given tool
- `check_conflicts(tool_name)` — all extensions that register a given tool

---

## 9. Extension Configuration

Extensions can store their own settings in `.jarvis/settings.json` under the `extensions` key:

```json
{
  "extensions": {
    "my_extension": {
      "host": "example.com",
      "api_key": "sk-..."
    }
  }
}
```

Access from within an extension:

```python
config = api.session.settings.get_extension_config("my_extension")
host = config.get("host")
```

Extensions can also define a `settings_schema` in their manifest for validation.

---

## 10. Integration Points

### With EventBus

Extensions subscribe to events via `api.on(EventType, handler)`. Available event types include:

- `AgentStarted`, `AgentEnded`, `AgentError`
- `TurnStarted`, `TurnEnded`
- `ToolCallStarted`, `ToolCallEnded`
- `MessageDelta`, `MessageComplete`
- `ExtensionLoaded`, `ExtensionUnloaded`
- And 18 more (see `core/events/types.py`)

### With HookRegistry

Extensions register hooks at lifecycle stages via `api.register_hook(stage, handler)`. Available stages include:

- `BEFORE_AGENT_RUN`, `AFTER_AGENT_RUN`
- `BEFORE_LLM_CALL`, `AFTER_LLM_CALL`
- `BEFORE_TOOL_CALL`, `AFTER_TOOL_CALL`
- `BEFORE_MESSAGE_SEND`, `AFTER_MESSAGE_SEND`
- And 12 more (see `core/events/hooks.py`)

### With OperationsRegistry

Extensions can swap operation backends at runtime:

```python
api.operations_registry.set_bash_ops(ssh_backend)
api.operations_registry.set_file_ops(remote_backend)
```

---

## 11. Example Extensions

Located in `examples/extensions/`:

| File | Description |
|------|-------------|
| `hello_world.py` | Minimal extension — registers a simple tool and command |
| `audit_tool.py` | Security audit tool that scans for common vulnerabilities |
| `safety_gate.py` | Lifecycle hook that blocks dangerous tool calls |
| `event_logger.py` | Subscribes to all events and logs them |
| `ssh_operations.py` | Swaps file/bash operations to use SSH remote execution |
| `ssh_tools.py` | SSH connection and command execution tools |

---

## 12. Programmatic API

The extension system can also be used programmatically:

```python
from core.extensions import ExtensionAPI, ExtensionRunner, ExtensionManifest

# Create a runner
runner = ExtensionRunner()

# Discover and load extensions
results = await runner.discover_and_load(project_dir=".")

# Bind to live session components
conflicts = await runner.bind(
    tool_registry=tool_registry,
    event_bus=event_bus,
    hook_registry=hook_registry,
    session=agent_session,
)

# ... agent runs ...

# Clean up
await runner.unbind()
```

### ExtensionRunner Properties

| Property | Description |
|----------|-------------|
| `runner.registry` | The `ExtensionRegistry` instance |
| `runner.bound_apis` | List of bound `ExtensionAPI` instances |
| `runner.extension_count` | Total loaded + pending extensions |

### ExtensionRegistry Methods

| Method | Description |
|--------|-------------|
| `register(manifest)` | Add or update an extension |
| `unregister(name)` | Remove an extension |
| `clear()` | Remove all extensions |
| `get(name)` | Get manifest by name |
| `list_extensions()` | List all manifests |
| `has_extension(name)` | Check if extension is loaded |
| `get_tool_origin(tool_name)` | Which extension provides a tool |
| `check_conflicts(tool_name)` | All extensions registering a tool |
