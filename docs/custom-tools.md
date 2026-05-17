# Custom Tools

JARVIS supports registering custom tools that extend its capabilities. Custom tools are sent to the LLM via the native `tools` API parameter alongside built-in tools.

The recommended way to add custom tools is via the **extension system** — Python files in `.jarvis/extensions/`. This replaces the old `register_plugin()` / `.jarvis/tools/` mechanism, which has been removed.

---

## Table of Contents

1. [Quick Start](#quick-start-extension-based-custom-tools)
2. [Tool Architecture](#tool-architecture)
3. [BaseTool Contract](#basetool-contract)
4. [Tool Registry](#tool-registry)
5. [Operations Backend](#operations-backend)
6. [Permission System](#permission-system)
7. [Event Integration](#event-integration)
8. [Hook Integration](#hook-integration)
9. [Tool Template](#tool-template)
10. [Required Fields](#required-fields)
11. [Return Format](#return-format)
12. [Overriding Built-in Tools](#overriding-built-in-tools)
13. [Using Operation Backends](#using-operation-backends-in-custom-tools)
14. [Advanced Patterns](#advanced-patterns)
15. [Tips](#tips)
16. [See Also](#see-also)

---

## Quick Start: Extension-Based Custom Tools

Save a `.py` file in `.jarvis/extensions/` (project-local) or `~/.jarvis/extensions/` (global):

### Example: Calculator Tool

Save as `.jarvis/extensions/calc_tool.py`:

```python
"""Calculator tool extension."""
from core.tools.base import BaseTool, ToolInput, ToolOutput


async def jarvis(api):
    """Register a calculator tool via the extension API."""

    class CalcTool(BaseTool):
        name = "calc"
        description = "Evaluate mathematical expressions."
        input_schema = {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "Expression to evaluate (e.g., '2 + 2')"
                }
            },
            "required": ["expression"]
        }

        async def execute(self, input_data: ToolInput) -> ToolOutput:
            try:
                expr = input_data.model_dump().get("expression", "")
                result = eval(expr, {"__builtins__": {}}, {})
                return ToolOutput(success=True, result=str(result))
            except Exception as e:
                return ToolOutput(success=False, result=None, error=str(e))

    api.tools(CalcTool())
```

---

## Tool Architecture

The tool system is organized into four layers:

```
┌─────────────────────────────────────────────────────────────────┐
│                    Extension Layer                               │
│  .jarvis/extensions/*.py  →  api.tools(MyTool())        │
│  ~.jarvis/extensions/*.py  →  auto-discovered on startup        │
└──────────────┬──────────────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Tool Registry                                 │
│  ToolRegistry (sync)  /  AsyncToolRegistry (concurrent)         │
│  - register(tool)                                                │
│  - execute_tool(name, args) → ToolOutput                        │
│  - get_function_definitions() → LLM tool format                 │
│  - embedded OperationsRegistry                                   │
└──────────────┬──────────────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────────────┐
│                    BaseTool + Implementations                    │
│  BaseTool (ABC) → 20+ built-in tools + custom tools             │
│  - name, description, input_schema, execute()                   │
│  - safe_execute() with error handling                           │
│  - injected: tool_registry, llm_provider, model, ops_registry   │
└──────────────┬──────────────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Operations Backend                            │
│  OperationsRegistry → FileOps / BashOps / EditOps (Protocols)   │
│  - LocalFileOperations (aiofiles) [default]                     │
│  - LocalBashOperations (asyncio) [default]                      │
│  - LocalEditOperations [default]                                │
│  - Swappable at runtime by extensions (SSH, sandbox, Docker)    │
└─────────────────────────────────────────────────────────────────┘
```

### Key Files

| File | Purpose |
|---|---|
| `core/tools/base.py` | `BaseTool` ABC, `ToolInput`, `ToolOutput` |
| `core/tools/registry.py` | `ToolRegistry` — dict-based registration, sync execution, event emission |
| `core/tools/async_registry.py` | `AsyncToolRegistry` — semaphore-controlled concurrent execution with timeout/retry |
| `core/tools/permissions.py` | Permission enums, `PermissionContext`, path resolution, wildcard matching |
| `core/tools/permission_manager.py` | `PermissionManager` — session rules, config-based checks, path-aware resolution |
| `core/tools/operations/registry.py` | `OperationsRegistry` — holds active File/Bash/Edit backend implementations |
| `core/tools/operations/base.py` | `FileOperations`, `BashOperations`, `EditOperations` Protocols |
| `core/tools/operations/local.py` | Default local implementations using `aiofiles`/`asyncio` |
| `core/tools/__init__.py` | Lazy import surface — avoids circular imports and eager loading |

### Tool Categories (20+ built-in tools)

| Category | Tools | Files |
|---|---|---|
| **File** | `read`, `write`, `edit`, `ls`, `find` | `file_tools.py`, `file_edit_tool.py` |
| **Code** | `bash`, `repl`, `run_tests` | `code_tools.py`, `repl_tool.py` |
| **Search** | `grep` | `grep_tool.py` |
| **Web** | `web_fetch`, `web_search` (Exa) | `web_tools.py` |
| **Memory** | `read_memory`, `save_memory` | `memory_tool.py` |
| **Agent** | `agents`, `ask_user_question` | `agent_tool.py`, `ask_user_question_tool.py` |
| **Skills** | `skill_manage` | `skill_manage_tool.py` |
| **Background** | `list_background_processes`, `read_background_output` | `background_tools.py` |
| **Utility** | `worktree_enter`, `worktree_exit`, `watcher` | `worktree_tool.py`, `watcher_tool.py` |
| **MCP** | MCP proxy tools (auto-registered) | `mcp_adapter.py`, `mcp_proxy_tool.py` |

---

## BaseTool Contract

Every tool extends `BaseTool` (`core/tools/base.py`) and must implement:

### Class Attributes

| Attribute | Type | Description |
|---|---|---|
| `name` | `str` | Unique tool identifier (snake_case). Used by the LLM to call it. |
| `description` | `str` | Natural-language description shown to the LLM. Include **WHEN TO USE** and parameter details. |
| `input_schema` | `dict` | JSON Schema defining the parameters the tool accepts. |
| `is_deferred` | `bool` | Mark tool as deferred/lazy-loadable (default: `False`). |
| `search_hint` | `str \| None` | Curated hint for search matching (default: `None`). |

### Injected References

When `ToolRegistry.register(tool)` is called, these references are injected:

| Reference | Type | Description |
|---|---|---|
| `tool.tool_registry` | `ToolRegistry` | Reference to the parent registry |
| `tool.llm_provider` | `BaseLLMProvider` | Active LLM provider (for tools that need LLM calls) |
| `tool.model` | `str` | Current model name |
| `tool.event_queue` | `Any` | Event queue for notifications |
| `tool.operations_registry` | `OperationsRegistry` | Access to file/bash/edit backends |

### Abstract Method

```python
@abstractmethod
async def execute(self, input_data: ToolInput) -> ToolOutput:
    """Execute the tool with the given input."""
```

### Convenience Properties

`BaseTool` provides property accessors for the operations backends:

```python
@property
def file_ops(self) -> FileOperations:
    """Access the active file operations backend."""

@property
def bash_ops(self) -> BashOperations:
    """Access the active bash operations backend."""

@property
def edit_ops(self) -> EditOperations:
    """Access the active edit operations backend."""
```

### Safe Execution

`BaseTool.safe_execute(input_data)` wraps `execute()` with error handling:

```python
async def safe_execute(self, input_data: dict) -> ToolOutput:
    try:
        parsed = ToolInput(**input_data)
        return await self.execute(parsed)
    except Exception as e:
        return ToolOutput(success=False, result=None, error=str(e))
```

---

## Tool Registry

### ToolRegistry (Sync)

`ToolRegistry` (`core/tools/registry.py`) is the primary tool management class:

```python
registry = ToolRegistry(llm_provider=provider, model="gpt-4o")
registry.register(MyTool())
registry.get_tools()              # dict[str, BaseTool]
registry.get("read")              # BaseTool | None
registry.list_tools()             # list[dict] — name, description, input_schema
registry.get_function_definitions()  # list[dict] — OpenAI/Anthropic tool format
await registry.execute_tool("read", {"filePath": "main.py"})  # ToolOutput
```

**Key behaviors:**
- `register(tool)` — injects registry/provider references into the tool, stores by `tool.name`.
- `execute_tool(name, input_data)` — emits `ToolCallStarted`/`ToolCallEnded`/`ToolCallError` events via the EventBus.
- `update_tool_providers(...)` — updates provider references on all registered tools.
- Embedded `OperationsRegistry` — created during `__init__`, accessible via `registry.operations_registry`.

### AsyncToolRegistry (Concurrent)

`AsyncToolRegistry` (`core/tools/async_registry.py`) extends `ToolRegistry` with:

```python
async_registry = AsyncToolRegistry(max_concurrent_tools=10)

# Single tool with timeout
await async_registry.execute_tool_async("bash", {"command": "sleep 5"}, timeout=30.0)

# Multiple tools concurrently
results = await async_registry.execute_tools_concurrent([
    ("read", {"filePath": "a.py"}),
    ("read", {"filePath": "b.py"}),
])
```

- **Semaphore control**: limits concurrent tool execution to `max_concurrent_tools`.
- **Timeout support**: per-tool timeout via `execute_tool_async()`.
- **Exception handling**: converts exceptions to error `ToolOutput` in `execute_tools_concurrent()`.

---

## Operations Backend

The `OperationsRegistry` (`core/tools/operations/`) decouples tool implementations from the filesystem/OS:

### Protocol Interfaces

```python
@runtime_checkable
class FileOperations(Protocol):
    async def read_file(self, path, offset=1, limit=None) -> str: ...
    async def write_file(self, path, content) -> None: ...
    async def file_exists(self, path) -> bool: ...
    async def list_dir(self, path) -> list[dict]: ...
    async def delete_file(self, path) -> None: ...

@runtime_checkable
class BashOperations(Protocol):
    async def run(self, command, timeout=None, cwd=None, env=None) -> dict: ...
    async def spawn(self, command, cwd=None, env=None) -> dict: ...
    async def terminate(self, pid) -> None: ...

@runtime_checkable
class EditOperations(Protocol):
    async def apply_edit(self, path, old_string, new_string) -> dict: ...
```

### Default Implementations

| Backend | Protocol | Default Implementation | Technology |
|---|---|---|---|
| File | `FileOperations` | `LocalFileOperations` | `aiofiles` + `pathlib` |
| Bash | `BashOperations` | `LocalBashOperations` | `asyncio.create_subprocess_shell` |
| Edit | `EditOperations` | `LocalEditOperations` | String search-and-replace |

### Swapping Backends

Extensions can swap backends at runtime:

```python
# .jarvis/extensions/ssh_backend.py
async def jarvis(api):
    api.operations_registry.set_bash_ops(SSHBashOps(), origin="ssh")
    api.operations_registry.set_file_ops(SSHFileOps(), origin="ssh")
```

The registry tracks which extension last changed each backend (for auditing):

```python
info = registry.get_backend_info()
# {"file_ops": {"class": "LocalFileOperations", "origin": "builtin"},
#  "bash_ops": {"class": "SSHBashOps", "origin": "ssh"},
#  "edit_ops": {"class": "LocalEditOperations", "origin": "builtin"}}
```

---

## Permission System

The permission system has three layers:

### 1. Global Bypass

`--bypass` flag or `bypass_tool_permissions` config skips all checks.

### 2. Tool-Level Config

Each tool can have `always`/`never`/`ask` in settings JSON:

```json
{
  "tools": {
    "bash": {"permission": "ask"},
    "read": {"permission": "always"}
  }
}
```

### 3. Granular Path/Command Permissions

`PermissionManager` (`core/tools/permission_manager.py`) checks:

| Check | Description |
|---|---|
| **Disallowed tools** | Profile-level `disallowed_tools` list (wildcard patterns) |
| **Trusted folders** | `~/.jarvis/trusted_folders.json` — always-allowed or always-blocked directories |
| **Denylist** | Patterns like `~/.ssh/*`, `*.key` — never allowed |
| **Allowlist** | Patterns like `*.py`, `*.md` — always allowed |
| **Sensitive files** | Patterns like `*secret*`, `*.env` — require approval |
| **Workdir boundary** | Files outside working directory require approval |
| **Scratchpad** | `.jarvis/scratchpad` and `/tmp/scratchpad` always allowed |
| **Session rules** | `ApprovedRule` list — session-level pattern-based approvals |

### Permission Enums

```python
class ToolPermission(str, Enum):
    ALWAYS = "always"   # No approval needed
    NEVER = "never"     # Blocked
    ASK = "ask"         # Requires user approval

class PermissionScope(str, Enum):
    COMMAND_PATTERN = "command_pattern"
    OUTSIDE_DIRECTORY = "outside_directory"
    FILE_PATTERN = "file_pattern"
    URL_PATTERN = "url_pattern"
    SENSITIVE_FILE = "sensitive_file"
```

### Permission Resolution Flow

```
check_permission(tool_name, args)
  │
  ├── bypass enabled? → ALWAYS
  ├── disallowed_tools match? → NEVER
  ├── tool-level config → always/never/ask
  ├── path-aware resolution (trusted folders, allowlist, denylist)
  │     ├── trusted + not denied → ALWAYS
  │     ├── denylist match → NEVER
  │     └── allowlist match → ALWAYS
  ├── session rules → check if patterns covered
  └── return PermissionContext(permission, required_permissions)
```

---

## Event Integration

The `ToolRegistry` emits events through the `EventBus` during tool execution:

```
execute_tool(name, args)
  │
  ├── emit ToolCallStarted(timestamp, tool_name, tool_call_id, args)
  │
  ├── tool.safe_execute(input_data)
  │
  ├── emit ToolCallEnded(timestamp, tool_name, tool_call_id, result, duration_ms, success)
  │
  └── (on error) emit ToolCallError(timestamp, tool_name, tool_call_id, error, duration_ms)
```

Extensions can subscribe to these events:

```python
async def jarvis(api):
    async def log_tool_call(event):
        print(f"[TOOL] {event.tool_name} called with {event.args}")

    api.on(ToolCallStarted, log_tool_call)
```

See [Event System](ARCHITECTURE.md#6-event-system) for the full event type catalog.

---

## Hook Integration

Hooks are higher-level lifecycle interceptors that can **block**, **modify**, or **inject** content at specific stages. Custom tools can register hooks via the extension API:

```python
from core.events.hooks import HookContext, HookResult, HookStage

async def jarvis(api):
    @api.hook(HookStage.BEFORE_TOOL_CALL)
    async def safety_gate(ctx: HookContext) -> HookResult:
        if ctx.tool_name == "bash" and "rm -rf" in ctx.tool_args.get("command", ""):
            return HookResult(block=True, reason="Destructive command blocked")
        return HookResult(proceed=True)
```

**Available hook stages relevant to tools:**

| Stage | When | Can Block? | Can Modify? |
|---|---|---|---|
| `BEFORE_TOOL_CALL` | Before tool execution | Yes | Yes (modify args) |
| `AFTER_TOOL_CALL` | After tool execution | No | Yes (modify result) |
| `BEFORE_TURN` | Before each LLM turn | Yes | — |
| `AFTER_TURN` | After each LLM turn | No | — |

See [HookRegistry](ARCHITECTURE.md#hookregistry) for all 16 lifecycle stages.

---

## Tool Template

```python
"""Description of what this tool does."""

from core.events.hooks import HookResult, HookStage
from core.tools.base import BaseTool, ToolInput, ToolOutput


async def jarvis(api):
    """Register a custom tool using the extension API."""

    class MyTool(BaseTool):
        """Tool description shown to the LLM."""

        name = "my_tool"
        description = """Full description with WHEN TO USE and Parameters sections."""

        input_schema = {
            "type": "object",
            "properties": {
                "param1": {
                    "type": "string",
                    "description": "Description of param1",
                },
            },
            "required": ["param1"],
        }

        async def execute(self, input_data: ToolInput) -> ToolOutput:
            try:
                # Tool logic here
                return ToolOutput(success=True, result="Done")
            except Exception as e:
                return ToolOutput(success=False, result=None, error=str(e))

    api.tools(MyTool())
```

---

## Required Fields

Every tool must define these three class attributes:

| Field | Description |
|-------|-------------|
| `name` | Unique tool name (snake_case). Used by the LLM to call it. |
| `description` | Full description. Include WHEN TO USE and parameter details. The LLM uses this to decide if the tool is relevant. |
| `input_schema` | JSON Schema dict defining the parameters the tool accepts. |

---

## Return Format

Every tool must return a `ToolOutput` instance:

```python
ToolOutput(
    success=True,          # True if successful
    result="Done",         # Result data returned to the LLM
    error=None,            # Error message if failed
    metadata={"key": "value"},  # Optional additional data
)
```

On failure, set `success=False` and provide a descriptive `error` message. The LLM sees this and retries with corrected parameters.

---

## Overriding Built-in Tools

Extensions can override built-in tools by registering a tool with the same name. This enables patterns like:

- Wrapping `read` with access logging
- Replacing `bash` with SSH-based execution
- Adding extra permission checks around `write`/`edit`

```python
async def jarvis(api):
    """Override the 'read' tool with an audited version."""
    from core.tools.base import BaseTool, ToolInput, ToolOutput

    class AuditedReadTool(BaseTool):
        name = "read"
        description = "Read file contents (audited)."
        # ... same input_schema as built-in ...

        async def execute(self, input_data: ToolInput) -> ToolOutput:
            # Log the access
            file_path = input_data.model_dump().get("files", [{}])[0].get("filePath", "?")
            print(f"[AUDIT] Reading: {file_path}")
            # Use the default backend to do the actual read
            content = await self.file_ops.read_file(file_path)
            return ToolOutput(success=True, result=content)

    api.tools(AuditedReadTool())
```

When an extension registers a tool with the same name as a built-in tool, the `ExtensionRunner` logs a warning and tracks the conflict. The extension's tool replaces the built-in one in `ToolRegistry`.

---

## Using Operation Backends in Custom Tools

Custom tools can use the operations backends (file, bash, edit) just like built-in tools:

```python
class MyTool(BaseTool):
    name = "my_tool"
    # ...

    async def execute(self, input_data: ToolInput) -> ToolOutput:
        # Use the active operations backend (local, SSH, sandbox, etc.)
        content = await self.file_ops.read_file("/path/to/file")
        result = await self.bash_ops.run("echo hello")
        return ToolOutput(success=True, result=content)
```

---

## Advanced Patterns

### Tools That Call the LLM

Some tools (like `AgentsTool`) need access to the LLM provider. The registry injects `llm_provider` and `model` references:

```python
class MyLLMTool(BaseTool):
    name = "my_llm_tool"
    description = "A tool that calls the LLM for analysis."
    input_schema = {...}

    async def execute(self, input_data: ToolInput) -> ToolOutput:
        messages = [{"role": "user", "content": input_data.query}]
        response = await self.llm_provider.generate(messages, model=self.model)
        return ToolOutput(success=True, result=response.content)
```

### Tools That Spawn Sub-Agents

Tools can access the `tool_registry` to invoke other agents:

```python
class MyAgentTool(BaseTool):
    name = "my_agent_tool"
    # ...

    async def execute(self, input_data: ToolInput) -> ToolOutput:
        explore_agent = self.tool_registry.get("explore")
        # ... delegate to sub-agent ...
```

### Deferred/Lazy Tools

Set `is_deferred = True` to mark a tool as lazy-loadable:

```python
class HeavyTool(BaseTool):
    name = "heavy_tool"
    is_deferred = True  # Won't be loaded until first use
    # ...
```

### Event-Emitting Tools

Tools can emit events directly via the injected `event_queue`:

```python
class MyNotifyingTool(BaseTool):
    # ...

    async def execute(self, input_data: ToolInput) -> ToolOutput:
        if self.event_queue:
            self.event_queue.put({"type": "progress", "message": "Starting..."})
        # ... do work ...
        return ToolOutput(success=True, result="Done")
```

---

## Tips

- Tool descriptions should mention **when to use** the tool so the LLM can decide correctly
- Use snake_case for tool names
- Make `input_schema` `required` lists minimal — only truly mandatory parameters
- The `name` must be unique across all tools (built-in, custom, and MCP)
- Extensions are auto-discovered on startup — no registration needed
- Use `/reload` in TUI to reload extensions without restarting
- Project-level extensions (`.jarvis/extensions/`) override global ones (`~/.jarvis/extensions/`) with the same name
- Use `self.file_ops`, `self.bash_ops`, `self.edit_ops` for backend-agnostic operations
- Handle errors gracefully — the LLM will retry with corrected parameters if `success=False`
- For long-running operations, consider using the background task system (`bash_ops.spawn()`)

---

## See Also

- [Custom Agents](custom-agents.md) — Creating specialized agent profiles with tool restrictions
- [Architecture: Tool System](ARCHITECTURE.md#5-tool-system) — Full tool architecture documentation
- [Architecture: Extension System](ARCHITECTURE.md#7-extension-system) — Extension API and lifecycle
- [Architecture: Event System](ARCHITECTURE.md#6-event-system) — EventBus and HookRegistry
- [Architecture: Operations Backend](ARCHITECTURE.md#operations-backend) — Pluggable file/bash/edit backends
- [Extension Examples](../examples/extensions/) — Hello world, safety gate, SSH tools, event logger
- [BaseTool](../core/tools/base.py) — The base class for all tools
- [ToolOutput](../core/tools/base.py) — The return type for tools
- [ToolRegistry](../core/tools/registry.py) — Tool registration and execution
- [Permissions](../core/tools/permissions.py) — Permission enums and resolution logic
- [PermissionManager](../core/tools/permission_manager.py) — Session rules and config-based checks
