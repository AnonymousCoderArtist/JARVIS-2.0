# JARVIS Extension System

## 1. Overview

The JARVIS extension system is a **plugin architecture** that allows users and third-party developers to extend JARVIS with custom tools, lifecycle hooks, slash commands, keyboard shortcuts, and event handlers. Extensions are plain Python files or subfolder packages — no build step, no package manager required — loaded dynamically at session startup.

All extension development imports from `jarvis.api` — a stable public API that works whether JARVIS is installed from source or via PyPI.

The system is built around four core components:

| Component | Module | Purpose |
|-----------|--------|---------|
| **ExtensionAPI** | `jarvis.api` | Public surface exposed to every extension — register tools, hooks, commands, shortcuts, events, and agents |
| **ExtensionLoader** | `jarvis/core/extensions/loader.py` | Dynamic discovery and loading of extension modules from filesystem paths and pip entry points |
| **ExtensionRunner** | `jarvis/core/extensions/runner.py` | Orchestrates the full lifecycle — discover → load → bind → run → unbind |
| **ExtensionRegistry** | `jarvis/core/extensions/registry.py` | Tracks all loaded extensions, provides introspection and conflict detection |

---

## 2. Directory Structure

| Path | Purpose |
|------|---------|
| `jarvis/core/extensions/` | Extension system core — API, loader, runner, registry, types |
| `jarvis/api.py` | **Public API** — all extension imports come from here |
| `.jarvis/extensions/*.py` | Project-local single-file extensions (highest precedence) |
| `.jarvis/extensions/<name>/` | Project-local package extensions (subfolder with `__init__.py`) |
| `~/.jarvis/extensions/*.py` | Global user single-file extensions |
| `~/.jarvis/extensions/<name>/` | Global user package extensions |
| `.jarvis/extensions/example_extension.py` | Reference extension example |

---

## 3. Extension Lifecycle

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Session Startup                               │
│                                                                      │
│  1. discover_and_load()                                              │
│     ┌──────────────────────────────────────────────────────────┐    │
│     │  Scan .jarvis/extensions/  (project, highest prio)       │    │
│     │    *.py files + subdirs with __init__.py                 │    │
│     │  Scan ~/.jarvis/extensions/  (user global)               │    │
│     │    *.py files + subdirs with __init__.py                 │    │
│     │  Scan pip entry points (jarvis.extensions group)         │    │
│     │  De-duplicate by filename stem (higher prio wins)        │    │
│     └──────────────────────────────────────────────────────────┘    │
│                              │                                       │
│                              ▼                                       │
│  2. load_from_file() / load_from_package_dir()                       │
│     ┌──────────────────────────────────────────────────────────┐    │
│     │  importlib.util.spec_from_file_location()                │    │
│     │    (for packages: submodule_search_locations set)        │    │
│     │  spec.loader.exec_module()                               │    │
│     │  Find factory: jarvis / jarvis_extension / default       │    │
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

An extension can be a single Python file or a subfolder package.

### Single-File Extension

A single Python file that exports an async factory function:

```python
# .jarvis/extensions/my_extension.py

__version__ = "1.0.0"
__description__ = "My custom extension"
__author__ = "Your Name"

from jarvis.api import ExtensionAPI, BaseTool, ToolInput, ToolOutput
from jarvis.api import HookStage, HookContext, HookResult
from jarvis.api import ToolCallStarted


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
        query = input_data.model_dump().get("query", "")
        return ToolOutput(success=True, result=f"Processed: {query}")


async def jarvis(api: ExtensionAPI):
    """Default factory function — receives the ExtensionAPI instance."""

    # Register a custom tool
    api.tools(MyTool())

    # Subscribe to an event
    api.on(ToolCallStarted, my_event_handler)

    # Register a lifecycle hook
    api.hook(HookStage.BEFORE_TOOL_CALL, safety_gate_hook)

    # Register a slash command
    api.command("/hello", hello_command, "Say hello")

    # Register a keyboard shortcut
    api.shortcut("ctrl+alt+h", "app.hello", "Hello shortcut")


async def my_event_handler(event):
    """Called when ToolCallStarted is emitted."""
    print(f"Tool called: {event.tool_name}")


async def safety_gate_hook(ctx: HookContext) -> HookResult:
    """Called before every tool call — can modify or block."""
    return HookResult(proceed=True)


async def hello_command() -> str:
    return "Hello from my extension!"
```

### Factory Function Names

The loader looks for the factory function in this order:
1. `jarvis(api)` — preferred
2. `jarvis_extension(api)` — alternative
3. `__jarvis_extension__(api)` — fallback
4. `default(api)` — last resort

### Module-Level Metadata (Optional)

| Attribute | Type | Description |
|-----------|------|-------------|
| `__version__` | `str` | Semantic version (default: `"1.0.0"`) |
| `__description__` | `str` | Human-readable description |
| `__author__` | `str` | Author name or handle |

### Package Extension (Multi-File)

A subfolder with `__init__.py` is recognized as a package extension. The `__init__.py` is the entry point and must export the `async def jarvis(api)` factory function. Submodules can be imported with relative imports.

**Directory structure:**

```
.jarvis/extensions/my_extension/
    __init__.py      # entry point: async def jarvis(api): ...
    models.py        # helper modules
    utils.py
```

**Example `__init__.py`:**

```python
__version__ = "2.0.0"
__description__ = "A multi-file extension"

from jarvis.api import ExtensionAPI
from .models import MyTool


async def jarvis(api: ExtensionAPI):
    api.tools(MyTool())
```

**Precedence:** If both `my_extension.py` and `my_extension/` exist in the same directory, the `.py` file wins.

---

## 5. ExtensionAPI Reference

Every extension receives an `ExtensionAPI` instance with these methods:

### Registration Methods

| Method | Description |
|--------|-------------|
| `tools(tool)` | Register a `BaseTool` instance. If a tool with the same name exists, it is **overridden** (built-in tools can be replaced). |
| `agents(definition)` | Register a custom agent definition (`AgentDefinition` instance). |
| `command(name, handler, description)` | Register a slash command (e.g., `"/my-command"`). Handler returns `str` or `None`. |
| `on(event_type, handler)` | Subscribe to an `EventBus` event. Handler receives the event instance. |
| `hook(stage, handler)` | Register a lifecycle hook at a `HookStage`. Handler receives `HookContext`, returns `HookResult`. |
| `shortcut(key, action_id, description)` | Register a keyboard shortcut mapping. |

### Runtime Accessors (valid after `bind()`)

| Property | Description |
|----------|-------------|
| `api.event_bus` | The session's `EventBus` (read-only) |
| `api.tool_registry` | The session's `ToolRegistry` (read-only) |
| `api.hook_registry` | The session's `HookRegistry` (read-only) |
| `api.session` | The current `AgentSession` (read-only) |
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

1. **Project-local**: `.jarvis/extensions/` — highest priority, project-specific
2. **User global**: `~/.jarvis/extensions/` — shared across all projects
3. **pip entry points**: packages registered under the `jarvis.extensions` entry point group

Each directory is scanned for both single `.py` files and subfolder packages (directories containing `__init__.py`).

### De-duplication

If the same name exists in multiple locations, the **higher-precedence** version wins. For example, `.jarvis/extensions/ssh.py` overrides `~/.jarvis/extensions/ssh.py`. If both `foo.py` and `foo/` exist in the same directory, the `.py` file takes precedence.

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

Extensions subscribe to events via `api.on(EventType, handler)`. All event types are available from `jarvis.api`:

```python
from jarvis.api import (
    ToolCallStarted, ToolCallEnded, ToolCallError,
    AgentStarted, AgentEnded, AgentError,
    TurnStarted, TurnEnded,
    SessionStarted, SessionShutdown,
)
```

### With HookRegistry

Extensions register hooks at lifecycle stages via `api.hook(stage, handler)`. Available stages:

```python
from jarvis.api import HookStage

# Agent lifecycle
HookStage.BEFORE_AGENT_START, HookStage.AFTER_AGENT_START
HookStage.BEFORE_AGENT_END, HookStage.AFTER_AGENT_END

# Turn lifecycle
HookStage.BEFORE_TURN, HookStage.AFTER_TURN

# Tool execution
HookStage.BEFORE_TOOL_CALL, HookStage.AFTER_TOOL_CALL

# Session lifecycle
HookStage.BEFORE_SESSION_START, HookStage.AFTER_SESSION_START
HookStage.BEFORE_SESSION_SHUTDOWN, HookStage.AFTER_SESSION_SHUTDOWN

# System prompt
HookStage.BEFORE_SYSTEM_PROMPT, HookStage.AFTER_SYSTEM_PROMPT

# Skills
HookStage.BEFORE_SKILL_ACTIVATE, HookStage.AFTER_SKILL_ACTIVATE
```

---

## 11. Example Extensions

Located in `.jarvis/extensions/`:

| File | Description |
|------|-------------|
| `example_extension.py` | Template showing all extension capabilities |
| `calc_tool.py` | Calculator tool for evaluating math expressions |
| `auto_type_check.py` | Hook that tracks tool call counts |
| `superagent.py` | Autonomous planning agent registered as extension |

---

## 12. Programmatic API

The extension system can also be used programmatically:

```python
from jarvis.api import ExtensionAPI, ExtensionRunner, ExtensionManifest

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

---

## 13. PyPI Usage

When JARVIS is installed via `pip install jarvis`, all extension APIs are available:

```bash
pip install jarvis
```

```python
# In your extension file:
from jarvis.api import ExtensionAPI, BaseTool, ToolInput, ToolOutput
from jarvis.api import AgentDefinition, AgentType
from jarvis.api import HookStage, HookContext, HookResult
from jarvis.api import ToolCallStarted, ToolCallEnded
from jarvis.api import EventBus, ToolRegistry

async def jarvis(api: ExtensionAPI):
    api.tools(MyTool())
    api.hook(HookStage.AFTER_TOOL_CALL, my_hook)
```

No need to import from `core.*` — everything is available through `jarvis.api`.
