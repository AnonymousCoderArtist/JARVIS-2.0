# JARVIS Architecture

## 1. Overview

JARVIS is a terminal-native AI engineering assistant with four UI modes (CLI, TUI, WebUI, RPC) built around a core agent loop that dispatches user requests to an LLM provider, executes tool calls the model requests, and iterates until a final response is produced. The system is organized as a Python monorepo with a layered, **event-driven, plugin-extensible** design: a thin CLI launcher at `jarvis/cli.py` delegates to an interface layer, which talks to a core agent system (`core/agents/`), which in turn uses an LLM provider abstraction (`core/llm/`, `core/llm_sdk/`), a tool system (`core/tools/`), and the new **event/extensions/operations** layers. Supporting subsystems handle configuration (with themes and keybindings), MCP integration, connectors (GitHub, HTTP, RSS, etc.), file watchers, conversation checkpointing with the rewind system, sandboxed command execution, a learning pipeline that distills interaction traces into reusable skills, a **prompt template system** (markdown → slash commands), and a **tiered resource discovery** layer.

---

## 2. Directory Structure

| Directory | Purpose |
|---|---|
| `jarvis/` | CLI entry point (`cli.py`) — parses args, dispatches to TUI/CLI/WebUI/RPC |
| `core/agents/` | Agent system: `BaseAgent`, `JarvisV2`, `AgentManager`, `AsyncAgentManager`, fork subagent, heartbeat scheduler, task scheduler, system prompts, builtin agent profiles |
| `core/tools/` | Tool system: `BaseTool`, `ToolRegistry`/`AsyncToolRegistry`, `PermissionManager`/`PermissionContext`, 20+ tool implementations, MCP adapter |
| `core/tools/operations/` | **Pluggable operation backends** — `OperationsRegistry`, `FileOperations`/`BashOperations`/`EditOperations` Protocols, default local implementations via `aiofiles`/`asyncio`. Extensions can swap backends (SSH, sandbox, Docker) without modifying tools. |
| `core/events/` | **Event-driven architecture** — `EventBus` (pub/sub), `HookRegistry` (16 lifecycle stages), 24 event types (`AgentStarted`, `TurnStarted`, `ToolCallStarted`, `MessageDelta`, etc.). Foundation for the extension system. |
| `core/extensions/` | **Extension/plugin system** — `ExtensionAPI` (register tools/hooks/commands/shortcuts), `ExtensionLoader` (dynamic import from `.jarvis/extensions/` and pip entry points), `ExtensionRunner` (bind/unbind lifecycle), `ExtensionRegistry` (conflict detection, metadata). |
| `core/prompts/` | **Prompt template system** — markdown files with YAML frontmatter auto-register as slash commands (`/review`, `/testgen`, `/explain`). Supports `$1`, `$2`, `$@`, `${@:N}` argument substitution. |
| `core/resources/` | **Tiered resource discovery** — scans `~/.jarvis/`, `.jarvis/`, and walks up from cwd to find `AGENTS.md`, `CLAUDE.md`, `SYSTEM.md`, skills, and prompt templates with precedence ranking (project > user > global). |
| `core/llm/` | LLM abstraction: `BaseLLMProvider`, `SDKAdapter`, model info, model registry |
| `core/llm_sdk/` | SDK implementations: OpenAI SDK, Anthropic SDK, tool parser, context length manager |
| `core/provider/` | Provider configuration: `ProviderManager`, provider model definitions |
| `core/connectors/` | Connector framework: `BaseConnector`, `ConnectorManager`, GitHub/HTTP/RSS/Weather/Filesystem connectors, unified `Document` schema |
| `core/config/` | Configuration: layered JSON/env/Pydantic model loading via `Settings`, `JarvisSettings`. **Theme system** (51 color tokens, truecolor/256 detection, hot-reload). **Keybinding system** (namespaced action IDs, legacy migration, JSON config). |
| `core/learn/` | Learning pipeline: M1→M2→M3 distillation, pattern detection, `SkillCrystallizer` |
| `core/skills/` | Skills CRUD management, reusable skill markdown storage |
| `core/rpc/` | **RPC mode** — JSONL protocol over stdin/stdout for embedding JARVIS in IDEs, web UIs, or other processes. Commands: `prompt`, `steer`, `bash`, `get_state`, `get_messages`, `get_tools`, `set_model`, `new_session`, `compact`. |
| `core/web/` | FastAPI web server for the WebUI — REST + WebSocket endpoints |
| `core/rewind/` | Conversation checkpointing with file snapshots for undo |
| `core/watchers/` | Passive file/event watchers |
| `core/agents/background_task_manager.py` | Long-running background task delegation with result caching |
| `interface/cli/` | `prompt_toolkit`-based interactive CLI, command handler, display manager |
| `interface/textual_ui/` | Textual-based terminal UI — 30+ widgets, agent loop integration |
| `interface/webui/` | React/TypeScript + Vite + Tailwind frontend — glass-morphism panels, thread architecture |
| `interface/jarvis/` | Legacy interface files |
| `interface/opentui_ui/` | Legacy/open TUI variant |
| `docs/` | Documentation: custom agents, custom tools, MCP, sandbox, watchers, WebUI theme, architecture |
| `tests/` | Test suite |
| `scripts/` | Utility scripts |
| `examples/extensions/` | **Reference extension examples** (hello_world, audit_tool, safety_gate, event_logger, ssh_operations) |
| `examples/prompts/` | **Prompt template examples** (review, testgen, explain) |

---

## 3. Core Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                         jarvis/cli.py                               │
│              Arg parsing, env loading, UI dispatch                   │
│              --mode tui (default) / cli / webui / rpc               │
└─────────┬──────────────────────────┬──────────────────────┬─────────┘
          │       defaults to         │                      │
          ▼                          ▼                      ▼
┌──────────────────┐   ┌────────────────────┐   ┌──────────────────────┐
│  interface/cli/  │   │ interface/textual_ │   │  interface/webui/    │
│  prompt_toolkit  │   │    ui/ (Textual)   │   │  React + Vite +     │
│  (sync/async)    │   │  rich TUI widgets  │   │  FastAPI backend     │
└─────────┬────────┘   └─────────┬──────────┘   └──────────┬───────────┘
          │                      │                          │
          └──────────────────────┼──────────────────────────┘
                                 │
                    ┌────────────┴────────────┐
                    │    core/rpc/ (stdin/     │
                    │   stdout JSONL protocol) │
                    └────────────┬────────────┘
                                 │
                                 ▼
          ┌──────────────────────────────────────────────────┐
          │              core/agents/jarvis_v2.py             │
          │         JarvisV2 extends BaseAgent               │
          │  agent loop, streaming, tool dispatch, learning   │
          └──────┬──────────────────────────────────┬─────────┘
                 │                                  │
                 ▼                                  ▼
   ┌─────────────────────────┐    ┌──────────────────────────────┐
   │     core/llm/           │    │       core/tools/             │
   │  BaseLLMProvider        │    │  BaseTool, ToolRegistry       │
   │  SDKAdapter + SDKs     │    │  20+ tools, PermissionManager  │
   │  (OpenAI, Anthropic)   │    │  MCP adapter, Rewind           │
   └─────────────────────────┘    └──────────┬───────────────────┘
                                              │
                                    ┌─────────┴──────────┐
                                    ▼                    ▼
                          ┌──────────────────┐  ┌──────────────────────┐
                          │ OperationsRegistry│  │    EventBus +         │
                          │ core/tools/ops/  │  │    HookRegistry        │
                          │ File/Bash/Edit  │  │    core/events/        │
                          │ Protocols (swap  │  │    24 event types     │
                          │  at runtime)     │  │    16 lifecycle hooks │
                          └──────────────────┘  └──────────┬───────────┘
                                                           │
                                                    ┌──────┴──────┐
                                                    │  Extensions  │
                                                    │  core/ext/   │
                                                    │  .jarvis/    │
                                                    │  pip install │
                                                    └─────────────┘
```

---

## 4. Agent System

### Class Hierarchy

```
BaseAgent (ABC)          — core/agents/base.py
  └── JarvisV2           — core/agents/jarvis_v2.py   (primary agent)
  └── ExploreAgent       — core/agents/explore_agent.py
  └── PlanAgent          — core/agents/plan_agent.py
```

`BaseAgent` provides:
- **Agent loop** (`_process_with_tools`): calls LLM with full message history + tool definitions, executes any tool calls the model returns, appends results, and repeats until the model returns a plain-text response. Tool calls/results are persisted as **proper role-based messages** (assistant with `tool_calls`, tool with `tool_call_id`) — no more injecting into user messages.
- **EventBus integration**: emits `TurnStarted`/`TurnEnded`, `MessageDelta`, `ThinkingDelta`, `AgentStarted`/`AgentEnded`/`AgentError`, `ProgressUpdated`, `StatusUpdated` events throughout the agent lifecycle. Extensions subscribe via `api.on(TurnStarted, handler)`.
- **HookRegistry integration**: runs `BEFORE_TURN` / `AFTER_TURN` lifecycle hooks. Extensions can block tool calls via `api.register_hook(HookStage.BEFORE_TOOL_CALL, handler)`.
- **Full history pipeline**: `_build_messages()` loads ALL role-based messages from `self.memory` via `get_role_memory()`, not just the last 5 entries. Legacy format entries (pre-role dicts) are still supported as a summary context string.
- **ConversationHistory integration**: tool calls and results are automatically saved to `self.history` (a `ConversationHistory` instance shared with the UI layer), ensuring complete conversation transcripts in JSONL format.
- **Streaming**: when a `stream_callback` is set, the agent uses streaming LLM calls and emits text chunks in real time to the UI.
- **Approval flow** (`_should_execute_tool`): for each tool call, checks permission level (always/never/ask), session rules, and invokes the `approval_callback` if user confirmation is needed. Supports "allow always" session rules.
- **Concurrent tool execution**: via `AsyncToolRegistry.execute_tools_concurrent`, multiple independent tool calls are dispatched in parallel using `asyncio.gather`.
- **Background task delegation**: `delegate_to_background` submits long-running tasks to `BackgroundTaskManager` with result caching.
- **Execution trace**: a per-task trace buffer (`self.execution_trace`) records every tool call and its result, consumed by the skill crystallizer.
- **Progress reporting**: `process_with_progress` reports stage-based progress (Understanding → Planning → Execution → Verification) through callbacks.

`JarvisV2` (463 lines) adds:
- **Learning integration**: after every 5 interactions, logs M1 traces to `LearningManager`.
- **Skill crystallization**: after task completion, if the execution trace has enough tool steps (≥3 steps and ≥5 tool calls), the `SkillCrystallizer` is invoked to create reusable skill markdown.
- **Heartbeat system**: optional `HeartbeatScheduler` for periodic background awareness (two-phase: decision via virtual tool call, then execution).
- **Task scheduling**: `plan_with_scheduler` / `run_scheduled` — keyword-based task decomposition with dependency tracking and topological sort via `TaskScheduler`.

### Agent Loop (simplified)

```
User Message
  │
  ├── AgentLoop saves user message → ConversationHistory (JSONL)
  ▼
_build_messages()
  │
  ├── system prompt
  ├── legacy memory context (pre-role entries as summary string)
  ├── ALL role-based messages from get_role_memory()    ← replaces limit=5
  └── current user message
  │
  ▼
_generate_with_tools() ──► LLM returns text or tool_calls
  │
  ├── tool_calls? ──► _execute_tools_and_update_messages()
  │                       │
  │                       ├── _should_execute_tool() [permission check]
  │                       ├── execute_tool() via ToolRegistry
  │                       ├── tool_call_callback / tool_result_callback
  │                       ├── persist to self.memory:
  │                       │   ├── add_role_message("assistant", tool_calls)
  │                       │   └── add_role_message("tool", result)
  │                       ├── persist to self.history:
  │                       │   ├── HistoryMessage(role="assistant", tool_calls)
  │                       │   └── HistoryMessage(role="tool", result)
  │                       └── append to working messages for LLM
  │                       │
  │                       └── loop back to LLM
  │
  └── text? ──► return final response
                   │
                   ├── JarvisV2: add_role_message("user", input)
                   ├── JarvisV2: add_role_message("assistant", response)
                   └── AgentLoop saves assistant response → ConversationHistory
```

---

## 5. Tool System

### Architecture

Every tool extends `BaseTool` (`core/tools/base.py`) and implements three things:

| Property | Description |
|---|---|
| `name` | Unique tool identifier (e.g., `"read"`, `"bash"`) |
| `description` | Natural-language description for the LLM |
| `input_schema` | JSON Schema for tool arguments |
| `execute(input_data) -> ToolOutput` | Async execution method |

Tools registered in a `ToolRegistry` (or `AsyncToolRegistry`) are exposed to the LLM via `get_function_definitions()` which returns a list in OpenAI/Anthropic tool-calling format.

### Registry Pattern

```
ToolRegistry                — core/tools/registry.py (dict-based, sync execute)
  └── AsyncToolRegistry     — core/tools/async_registry.py (semaphore, concurrent, timeout, retry)
```

- `ToolRegistry.register(tool)` — injects `tool_registry`, `llm_provider`, `model`, `operations_registry` refs into each tool.
- `ToolRegistry.discover_and_register_plugins()` — auto-loads `.py` files from `~/.jarvis/tools/` and `.jarvis/tools/`.
- `AsyncToolRegistry.execute_tools_concurrent()` — runs multiple tools in parallel with a configurable semaphore.
- `ToolRegistry` now has an embedded `OperationsRegistry` — tools can access `self.file_ops`, `self.bash_ops`, `self.edit_ops` without knowing which backend is active.

### Operations Backend

The `OperationsRegistry` (`core/tools/operations/`) decouples tool implementations from the filesystem/OS:

```
Tool (ReadTool, BashTool, EditTool)
  │
  ▼
tool.file_ops / tool.bash_ops / tool.edit_ops (BaseTool properties)
  │
  ▼
OperationsRegistry
  ├── FileOperations  (Protocol)     → LocalFileOperations (aiofiles) [default]
  ├── BashOperations  (Protocol)     → LocalBashOperations  (asyncio)  [default]
  └── EditOperations  (Protocol)     → LocalEditOperations            [default]
                                         │
                                   ┌─────┴─────┐
                                   │           │
                             Local (aiofiles)   SSH (extension)
```

Extensions can swap backends at runtime:
```python
# .jarvis/extensions/ssh_backend.py
async def jarvis_extension(api):
    api.operations_registry.set_bash_ops(SSHBashOps(), origin="ssh")
```

### Tool Categories (20+ tools)

| Category | Tools |
|---|---|
| **File** | `read`, `write`, `edit`, `ls`, `find`, `glob`, `grep` |
| **Code** | `bash`, `repl`, `run_tests` |
| **Web** | `web_fetch`, `web_search` (Exa) |
| **Memory** | `read_memory`, `save_memory` |
| **Skills** | `activate_skill`, `skill_manage` |
| **Agent** | `agents` (sub-agent delegation), `ask_user_question`, `tool_search` |
| **MCP** | MCP proxy tools (auto-registered from MCP server configs) |
| **Background** | `list_background_processes`, `read_background_output` |
| **Utility** | `worktree`, `watcher`, `data_collect` |

### Permission Model

Three-layer permission check (`core/tools/permissions.py`, `core/tools/permission_manager.py`):

1. **Global bypass**: `--bypass` flag or `bypass_tool_permissions` config skips all checks.
2. **Tool-level config**: each tool can have `always`/`never`/`ask` in settings JSON.
3. **Granular path/command permissions**: `PermissionManager` checks file paths against allowlists/denylists, trusted folders, sensitive file patterns, and workdir boundaries. Dangerous bash commands (`rm -rf`, `dd if=`, etc.) trigger `RequiredPermission` with specific scope.

Trusted folders (from `~/.jarvis/trusted_folders.json`) can mark directories as always-allowed or always-blocked, short-circuiting the normal allowlist checks.

---

## 6. Event System

The event system (`core/events/`) is a foundation layer that all other subsystems use for decoupled communication. It was added in Phase 1 of the extensibility overhaul (inspired by `pi-agent-core`).

### EventBus

```python
bus = EventBus()

# Subscribe
unsub = bus.subscribe(ToolCallStarted, my_handler, priority=10)

# Emit
await bus.emit(ToolCallStarted(timestamp=t, tool_name="read", ...))

# Unsubscribe
unsub()
```

- **24 event types** across 6 categories:
  - `AgentEvent`: `AgentStarted`, `AgentEnded`, `AgentError`
  - `TurnEvent`: `TurnStarted`, `TurnEnded`
  - `MessageEvent`: `MessageDelta`, `MessageComplete`, `ThinkingDelta`
  - `ToolEvent`: `ToolCallStarted`, `ToolCallEnded`, `ToolCallError`
  - `SessionEvent`: `SessionStarted`, `SessionShutdown`, `SkillActivated`, `SkillDeactivated`
  - `ExtensionEvent`: `ExtensionLoaded`, `ExtensionUnloaded`, `ExtensionError`
  - `StatusEvent`, `ProgressEvent`, `SystemEvent`: status changes, progress updates, warnings
- **Async-aware**: handlers can be sync or async — async handlers are gathered concurrently.
- **Priority ordering**: higher-priority handlers run first.
- **Introspection**: `bus.get_stats()` — total events, per-type counts, slowest handler.
- **Polymorphic dispatch**: subscribing to a parent class catches child events.

### HookRegistry

Hooks are higher-level lifecycle interceptors that can **block**, **modify**, or **inject** content:

```python
registry = HookRegistry()

@registry.register(HookStage.BEFORE_TOOL_CALL)
async def safety_gate(ctx):
    if ctx.tool_name == "bash" and "rm -rf" in ctx.args.get("command", ""):
        return HookResult(block=True, reason="Destructive command blocked")
    return HookResult(proceed=True)
```

**16 hook stages**: `BEFORE_AGENT_START`, `AFTER_AGENT_START`, `BEFORE_TURN`, `AFTER_TURN`, `BEFORE_TOOL_CALL`, `AFTER_TOOL_CALL`, `BEFORE_PROMPT_BUILD`, `AFTER_PROMPT_BUILD`, `BEFORE_SESSION_START`, `AFTER_SESSION_START`, `BEFORE_SESSION_SHUTDOWN`, `AFTER_SESSION_SHUTDOWN`, `BEFORE_SYSTEM_PROMPT`, `AFTER_SYSTEM_PROMPT`, `BEFORE_SKILL_ACTIVATE`, `AFTER_SKILL_ACTIVATE`.

### Integration Points

| Component | Events Emitted | Hooks Used |
|---|---|---|
| `BaseAgent.process_with_progress()` | `AgentStarted`, `AgentEnded`, `AgentError`, `ProgressUpdated`, `StatusUpdated` | — |
| `BaseAgent._process_with_tools()` | `TurnStarted`, `TurnEnded`, `MessageDelta`, `ThinkingDelta` | `BEFORE_TURN`, `AFTER_TURN` |
| `ToolRegistry.execute_tool()` | `ToolCallStarted`, `ToolCallEnded`, `ToolCallError` | — |
| `ExtensionRunner` | `ExtensionLoaded`, `ExtensionUnloaded` | — |

---

## 7. Extension System

The extension system (`core/extensions/`) is the primary mechanism for customizing and extending JARVIS. It was added in Phase 2 of the extensibility overhaul.

### Architecture

```
Extension (.jarvis/extensions/*.py or pip entry point)
  │
  ├── async def jarvis_extension(api: ExtensionAPI) — factory function
  │       │
  │       ├── api.register_tool(tool_instance)      — add/override tools
  │       ├── api.on(event_type, handler)            — subscribe to EventBus
  │       ├── api.register_hook(stage, handler)       — lifecycle hooks
  │       ├── api.register_command(name, handler)     — slash commands
  │       └── api.register_shortcut(key, action_id)   — keyboard shortcuts
  │
  └── ExtensionRunner.bind()  — flushes registrations into live session
        │
        ├── tool_registry.register(tool)              — ToolRegistry
        ├── event_bus.subscribe(type, handler)         — EventBus
        ├── hook_registry.register(stage, handler)     — HookRegistry
        └── api.operations_registry.set_*(...)         — OperationsRegistry
```

### ExtensionAPI Surface

| Method | Description | Example |
|---|---|---|
| `register_tool(tool)` | Register or override a tool | `api.register_tool(HelloTool())` |
| `on(event_type, handler)` | Subscribe to EventBus events | `api.on(ToolCallStarted, log_it)` |
| `register_hook(stage, handler)` | Lifecycle hook (block/modify) | `api.register_hook(BEFORE_TOOL_CALL, safety)` |
| `register_command(name, handler)` | Slash command | `api.register_command("/hello", cmd)` |
| `register_shortcut(key, action_id)` | Keyboard shortcut | `api.register_shortcut("ctrl+h", "app.hello")` |
| `operations_registry` | Access to swap backends | `api.operations_registry.set_bash_ops(...)` |
| `event_bus` | Read-only EventBus access | `api.event_bus.subscribe(...)` |
| `tool_registry` | Read-only ToolRegistry | `api.tool_registry.get("read")` |

### Loading & Discovery

Extensions are discovered in precedence order:

1. **Project-local**: `.jarvis/extensions/*.py` (highest priority)
2. **User-global**: `~/.jarvis/extensions/*.py`
3. **pip entry points**: packages with `[project.entry-points."jarvis.extensions"]`

The `ExtensionLoader` uses `importlib` (no JIT compiler needed). The `ExtensionRunner` orchestrates the lifecycle:

```python
runner = ExtensionRunner()
results = await runner.discover_and_load(project_dir=".")
await runner.bind(tool_registry, event_bus, hook_registry, session)
# ... agent runs ...
await runner.unbind()
```

### Tool Override Detection

When an extension registers a tool with the same name as a built-in tool, the `ExtensionRunner` logs a warning and tracks the conflict. The extension's tool replaces the built-in one in `ToolRegistry`. This enables patterns like:

- Wrapping `read` with access logging
- Replacing `bash` with SSH-based execution
- Adding permission checks around `write`/`edit`

### Reference Extensions

| Example | Pattern |
|---|---|
| `hello_world.py` | Minimal tool registration |
| `audit_tool.py` | Hook-based tool call auditing |
| `safety_gate.py` | Block destructive bash commands (`rm -rf`) |
| `event_logger.py` | EventBus subscription pattern |
| `ssh_operations.py` | Operations backend swap (SSH file/bash) |

---

## 8. LLM / Provider Layer

### Abstraction

```
BaseLLMProvider                     — core/llm/base.py
  generate(messages, model, stream)
  generate_with_tools(messages, tools, model, stream)
  get_available_models()

  └── SDKAdapter                    — core/llm/sdk_adapter.py
        wraps BaseLLMSDK              — core/llm_sdk/base/sdk.py

              ├── OpenAISDK         — core/llm_sdk/openai/sdk.py
              └── AnthropicSDK      — core/llm_sdk/anthropic/sdk.py
```

`SDKAdapter` bridges typed SDK objects (`GenerationConfig`, `GenerationResponse`, `Message`) to the dict-based interface that `BaseAgent` expects. This allows swapping providers without changing agent code.

### Context Length Management

`ContextLengthManager` (in `core/llm_sdk/`) provides model-aware token limits and can automatically truncate conversation history when approaching the context window.

### Provider Configuration

`ProviderManager` (in `core/provider/`) loads provider definitions from `providers.json`, supporting multiple API endpoints, model lists, and SDK modes. Each provider specifies `sdk_mode` (openai/anthropic), `default_model`, `base_url`, `api_key`, and model capabilities.

---

## 9. Prompts, Skills & Resource Discovery

The prompting ecosystem has three interrelated components: **skills** (on-demand capability packages), **prompt templates** (markdown → slash commands), and **resource discovery** (tiered configuration scanning).

### Skills (`core/skills/`)

Skills are self-contained instruction packages following the `agentskills.io` standard:

```
~/.jarvis/skills/my-skill/SKILL.md
  ───
  name: my-skill
  description: Specialized knowledge for task X
  when_to_use: When the user asks about X
  when_not_to_use: For general programming tasks
  ───
  # My Skill
  Step-by-step instructions...
```

- `SkillManager` discovers skills from `~/.jarvis/skills/`, `~/.agents/skills/`, `.jarvis/skills/`.
- **Progressive disclosure**: Only name/description/when_to_use/when_not_to_use are shown in the system prompt. Full content loads on demand when the agent invokes the `activate_skill` tool.
- `SkillTool` (`core/tools/skill_manage_tool.py`) provides CRUD operations (create, read, patch, edit, delete, list, activate).

### Prompt Templates (`core/prompts/`)

Markdown files with YAML frontmatter auto-register as slash commands:

```
.jarvis/prompts/pr.md:
  ───
  description: "Review a pull request"
  argument-hint: "<PR-URL>"
  ───
  Review the PR at $1. Focus on logic errors, test coverage, performance.
```

- Files in `.jarvis/prompts/` or `~/.jarvis/prompts/` are discovered automatically.
- Argument substitution: `$1`, `$2`, `$@`, `$ARGUMENTS`, `${@:N}`, `${@:N:L}`.
- Quoted argument parsing (`/review "my branch"` → one argument).
- `format_template_help()` renders a `/commands`-style help listing.

### Tiered Resource Discovery (`core/resources/`)

```
Tier 0 (highest priority):  Project explicit (.jarvis/settings.json paths)
Tier 1:                     Project auto-discovered (.jarvis/ directory)
Tier 3 (lowest priority):   User auto-discovered (~/.jarvis/)
```

Resource types discovered:

| Type | Discovered From | Injected Into |
|---|---|---|
| Context files | Walking up from cwd: `AGENTS.md`, `CLAUDE.md`, `SYSTEM.md`, `APPEND_SYSTEM.md` | System prompt as `<context>` blocks |
| Prompt templates | `.jarvis/prompts/`, `~/.jarvis/prompts/` | Slash commands |
| Skills | `.jarvis/skills/`, `~/.jarvis/skills/`, `~/.agents/skills/` | System prompt (progressive) |

---

## 10. MCP Integration

MCP (Model Context Protocol) tools are registered as standard `BaseTool` instances through:

| File | Purpose |
|---|---|
| `core/tools/mcp_adapter.py` | `MCPClient` + `MCPToolAdapter` — wraps MCP server tools as `BaseTool` |
| `core/tools/mcp_lifecycle.py` | Connection lifecycle (eager vs lazy server start) |
| `core/tools/mcp_auth.py` | Authentication for MCP servers |
| `core/tools/mcp_capabilities.py` | Server capability negotiation |
| `core/tools/mcp_metadata_cache.py` | Caches MCP tool schemas to avoid re-fetching |
| `core/tools/mcp_proxy_tool.py` | Proxy tool that routes calls through MCP |

MCP servers are configured in `.jarvis/mcp.json` with transport (`stdio` or `sse`), command/args, and lifecycle policy. On startup, `MCPRegistry` loads configs, connects servers, and registers their exposed tools as `MCPToolAdapter` instances in the global `ToolRegistry`.

---

## 11. Connector Framework

The connector framework (`core/connectors/`) provides a unified interface for fetching data from external services.

### Core Schema

```python
@dataclass
class Document:
    doc_id: str
    source: str          # e.g. "github", "weather", "filesystem"
    doc_type: str        # e.g. "issue", "forecast", "file"
    content: str
    title: str
    author: str
    participants: list[str]
    timestamp: datetime
    thread_id: str | None
    url: str | None
    attachments: list[Attachment]
    metadata: dict
```

### BaseConnector

```
BaseConnector (ABC)     — core/connectors/base.py
  ├── GitHubConnector   — core/connectors/github.py
  ├── HTTPConnector     — core/connectors/http.py
  ├── RSSConnector      — core/connectors/rss.py
  ├── WeatherConnector  — core/connectors/weather.py
  └── FilesystemConnector — core/connectors/filesystem.py
```

Each connector implements `fetch(query, limit)`, `sync(since, cursor)`, `is_connected()`, and `supports_query_type()`. `ConnectorManager.fetch_all()` dispatches parallel fetches across all registered connectors using `asyncio.gather`.

---

## 12. Configuration System

Configuration uses a layered merge pattern (`core/config/settings.py`) with hot-reload:

```
Priority (low → high):
  1. Defaults (hard-coded in JarvisSettings model)
  2. ~/.jarvis/settings.json       (user global)
  3. .jarvis/settings.json         (project overrides)
  4. Environment variables          (JARVIS_MODEL, JARVIS_API_KEY, etc.)
  5. Runtime initial_config dict    (runtime overrides)
```

`Settings` loads JSON configs, deep-merges them with env vars and any `initial_config`, then wraps everything in a `JarvisSettings` Pydantic model (`core/config/models.py`). Unknown keys from JSON sources are **preserved** — extensions can store their own configuration. The `reload()` method enables hot-reload without restart. The `save()` method uses optional file-locking via `filelock` for concurrent-instance safety.

### Settings Model Structure

```
JarvisSettings
  ├── app: AppSettings              (name, version, debug)
  ├── provider: ProviderSettings    (config_file, selected_provider_id)
  ├── tools: ToolSettings           (per-tool permissions, allow/deny/sensitive lists)
  ├── async_settings: AsyncSettings (concurrency, timeouts)
  ├── heartbeat: HeartbeatSettings  (enabled, interval, active hours)
  ├── learning: LearningSettings    (enabled, thresholds, directories)
  ├── sandbox: SandboxSettings      (enabled, backend, timeout)
  ├── theme: str                    ("dark" / "light" / custom name)
  ├── keybindings: str              ("default" / custom)
  ├── extensions: dict              (per-extension configuration, e.g. {"ssh_ops": {"host": "..."}})
  ├── bypass_tool_permissions: bool
  ├── disallowed_tools: list[str]
  └── agent_paths: list[str]
```

Extension-specific config is accessed via `settings.get_extension_config("my_extension")` and can be stored in `settings.json` as:
```json
{
  "extensions": {
    "ssh_operations": { "host": "user@server", "key_path": "~/.ssh/id_rsa" }
  }
}
```

### Theme System (`core/config/theme.py`)

Themes are JSON files with **51 color tokens** covering:
- **Core UI**: accent, border, success, error, warning, muted, text, background, surface
- **Messages**: user/assistant message backgrounds, tool output, compaction summaries
- **Markdown**: headings, code blocks, links, lists, blockquotes, inline code
- **Syntax highlighting**: keywords, strings, functions, operators, comments, types
- **Thinking levels**: 6 border colors (off, minimal, low, medium, high, xhigh)
- **UI elements**: footer, header, status bar, progress bar, scrollbar, dialog, input

Includes two built-in themes (`dark`, `light`) with truecolor/256-color auto-detection. Custom themes go in `~/.jarvis/themes/*.json`. Access via `DEFAULT_THEME`, `get_theme("name")`, `discover_themes()`.

### Keybinding System (`core/config/keybindings.py`)

Namespaced action IDs with 32 default bindings across 6 namespaces:

| Namespace | Examples |
|---|---|
| `jarvis.editor.*` | `cursorUp`, `deleteWordBackward`, `yank`, `undo` |
| `jarvis.input.*` | `newLine`, `submit`, `tab` |
| `jarvis.agent.*` | `interrupt`, `model.select`, `thinking.cycle` |
| `jarvis.model.*` | `cycleForward`, `select` |
| `jarvis.session.*` | `fork`, `tree` |
| `jarvis.view.*` | `zoomIn`, `expandTools` |

Keybindings are loaded from `~/.jarvis/keybindings.json` / `.jarvis/keybindings.json`. Legacy action IDs are auto-migrated to namespaced format. Provides `load_keybindings()`, `save_keybindings()`, `resolve_action()`, `format_keybinding_help()`.

---

## 13. User Interfaces

### CLI (`interface/cli/`)

- `prompt_toolkit`-based interactive shell.
- Always runs in bypass mode (`--bypass` enabled by default).
- Supports session resume (`--resume`), file input, and command history.
- Best for: scripting, automation, quick queries, headless environments.

### TUI (`interface/textual_ui/`)

- Textual framework with 30+ widgets — chat pane, streaming output, tool call inspector, status bar, thinking indicator.
- Rich real-time streaming with reasoning display.
- Tool approval prompts with inline keyboard interaction.
- Best for: daily interactive use, visibility into agent reasoning, long sessions.

### WebUI (`interface/webui/`)

- React/TypeScript + Vite + Tailwind frontend.
- FastAPI backend (`core/web/server.py`) with WebSocket streaming.
- Glass-morphism design, thread-based conversation architecture.
- REST endpoints for model selection, settings, MCP management, session history.
- Approval requests are sent as WebSocket events and resolved asynchronously.
- Best for: remote access, visual feedback, multi-session management.

### RPC (`core/rpc/`)

- JSONL protocol over stdin/stdout — no TUI, no prompt_toolkit dependency.
- Launch with `--mode rpc`, pipe JSONL commands, read events+responses from stdout.
- Commands: `prompt`, `steer`, `follow_up`, `bash`, `compact`, `new_session`, `get_state`, `get_messages`, `get_tools`, `set_model`.
- Best for: embedding JARVIS in IDEs (VS Code extension, etc.), CI/CD pipelines, custom UIs.

---

## 14. Data Flow

```
1. User types a message in CLI/TUI/WebUI
         │
2. Interface saves user message to ConversationHistory JSONL
   (create_user_message → ~/.jarvis/history/{session_id}.jsonl
    or {project_root}/.jarvis/history/{session_id}.jsonl)
         │
3. Interface calls agent.process(user_input)
         │
4. JarvisV2._build_messages() constructs:
   [system_prompt, legacy_memory_context,
    ALL role-based messages from get_role_memory(),
    user_message]
         │
         │  Note: role-based messages include previous turns'
         │  user, assistant (with tool_calls), and tool (with results)
         │  entries — loaded from self.memory without the old limit=5 cutoff.
         │
5. BaseAgent._process_with_tools() calls LLM via
   llm.generate_with_tools(messages, tool_definitions)
         │
         ├── LLM returns {content, tool_calls}
         │       │
         │       └── For each tool_call:
         │           ├── _should_execute_tool() — permission check
         │           │   ├── bypass? → execute
         │           │   ├── never? → skip
         │           │   ├── session rule covers? → execute
         │           │   └── ask? → approval_callback() → user decides
         │           │
         │           ├── tool.safe_execute(args) → ToolOutput
         │           │   └── callbacks: tool_call_callback, tool_result_callback
         │           │
         │           ├── Persist to self.memory (role-based):
         │           │   ├── add_role_message("assistant", tool_calls=...)
         │           │   └── add_role_message("tool", tool_call_id, content)
         │           │
         │           ├── Persist to self.history (ConversationHistory JSONL):
         │           │   ├── HistoryMessage(role="assistant", tool_calls=[...])
         │           │   └── HistoryMessage(role="tool", tool_call_id, content)
         │           │
         │           └── Append to working message list
         │           │
         │           └── Loop back to LLM with updated history
         │
         └── LLM returns plain text → final response
                  │
6. Interface displays response (streamed or complete)
                  │
7. JarvisV2 post-processes:
   ├── add_role_message("user", input) — persists user input to memory
   ├── add_role_message("assistant", response) — persists response to memory
   ├── history.append_message(assistant_msg) — persists response to JSONL
   ├── Logs M1 trace to LearningManager (every 5 interactions)
   ├── Runs SkillCrystallizer on execution trace
   └── (Optional) Heartbeat scheduler checks for pending tasks
```

---

---

## 15. Conversation History Management

### Architecture

Conversation history uses a two-tier storage system:

```
┌─────────────────────────────────────────────────────────────┐
│                    ConversationHistory                       │
│                    core/history.py                           │
│                                                             │
│  persistent store: ~/.jarvis/history/{id}.jsonl             │
│              or:   {project}/.jarvis/history/{id}.jsonl     │
│                                                             │
│  Format: JSONL (one JSON dict per line)                     │
│  Roles: system, user, assistant, tool                       │
│  Tool calls: OpenAI format (tool_calls) or Anthropic (tool_use) │
└───────────────────────────┬─────────────────────────────────┘
                            │
               ┌────────────┴────────────┐
               ▼                         ▼
     self.history (Agent)      self.agent.memory
     Persistent JSONL          Working memory (dict list)
     ┌────────────────┐        ┌─────────────────────────┐
     │ HistoryMessage │        │ Role-based dicts:       │
     │   role, content│        │ {"role":"user",...}     │
     │   tool_calls,  │        │ {"role":"assistant",...}│
     │   tool_call_id │        │ {"role":"tool",...}     │
     └────────────────┘        └─────────────────────────┘
```

### Message Flow

| Step | What | Where |
|------|------|-------|
| User input received | `create_user_message(prompt)` appended | `ConversationHistory` JSONL |
| Agent processes | `_build_messages()` loads ALL role messages from `self.memory` | `BaseAgent._build_messages()` |
| Tool called | Assistant message with `tool_calls` saved to both | `self.memory` + `self.history` |
| Tool result | Tool message with `tool_call_id` saved to both | `self.memory` + `self.history` |
| Final response | Assistant message saved to both | `self.memory` + `self.history` |

### SDK Format Converters

`core/history.py` provides bidirectional converters matching both provider SDKs:

| Function | Input | Output |
|----------|-------|--------|
| `to_openai_format()` | `list[HistoryMessage]` | `list[dict]` — OpenAI Chat Completions format |
| `to_anthropic_format()` | `list[HistoryMessage]` | `(system, list[dict])` — Anthropic Messages format |
| `from_openai_format()` | `list[dict]` | `list[HistoryMessage]` |
| `from_anthropic_format()` | `(system, list[dict])` | `list[HistoryMessage]` |
| `messages_to_role_dicts()` | `list[HistoryMessage]` | `list[dict]` with coalescing applied |

### Message Coalescing

`coalesce_messages()` merges consecutive same-role messages (except `tool` and `system`) to satisfy strict `user` ↔ `assistant` alternation required by OpenAI, vLLM, and Ollama. This is applied automatically when loading full history.

### Project-Level History

If a project has a `.jarvis/history/` directory (e.g., `{project_root}/.jarvis/history/`), it is used instead of `~/.jarvis/history/`. The directory is auto-discovered by walking up from the current working directory.

### Compaction

When the context window approaches its limit (default 80% threshold), `compact()` runs an LLM-based summarization. The summary is saved to the history file as a compaction boundary marker followed by a user message containing the summary text. This mirrors OpenClaude's `autoCompact.ts` approach of preserving compacted context in the transcript.

---

## 16. Key Design Decisions

**Why a single-agent architecture (JarvisV2) rather than multi-agent orchestration?**
> Simplicity and reliability. A single agent with a rich tool set avoids the coordination overhead, context fragmentation, and failure modes of multi-agent systems. The tool system provides equivalent modularity — tools encapsulate all "agent-like" behavior (sub-agent delegation via the `agents` tool, MCP adapters, skill activation) without the complexity of agent-to-agent handoff.

**Why the SDKAdapter pattern instead of direct API calls?**
> Provider independence. `SDKAdapter` normalizes the typed SDK interface (`BaseLLMSDK`) into the dict-based `BaseLLMProvider` contract. This means adding a new provider only requires implementing `BaseLLMSDK` — no changes to the agent loop, tool system, or UI layers.

**Why are tool results now persisted as tool role messages instead of user messages?**
> Standardization. With the new role-based memory system, tool results are persisted as proper `{"role": "tool", "tool_call_id": "...", "content": "..."}` messages in both `agent.memory` and `ConversationHistory`. The working message list passed to the LLM during a turn still uses user messages for backward compatibility, but the persistent store uses the SDK-standard tool role that both OpenAI and Anthropic support. This allows full conversation transcripts to be replayed into any provider without format conversion issues.

**Why JSON config files instead of YAML/TOML/env-only?**
> Simplicity + overridability. JSON is universally parseable, supports nested structures natively, and the layered merge (global → project → env → runtime) gives users flexible setup without requiring environment variables for every option.

**Why the heartbeat scheduler is disabled by default?**
> User autonomy. Periodic background awareness is powerful but can be surprising. Users opt in via `heartbeat.enabled: true` in `.jarvis/settings.json`, with configurable active hours and intervals.

**Why bubblewrap-based sandbox for command execution?**
> Security without containers. `bubblewrap` provides lightweight filesystem namespace isolation without requiring Docker or root privileges. It is fast enough for interactive use and prevents accidental filesystem modifications from shell commands.

**Why the EventBus + HookRegistry pattern instead of direct callbacks?**
> Decoupling. The EventBus allows any number of subscribers (extensions, UI, logging) without the agent loop knowing about them. The HookRegistry gives extensions _control_ (block/modify) not just observation, which enables safety gates, audit trails, and backend swapping without modifying core code.

**Why Python extensions via importlib instead of a custom plugin DSL?**
> Zero barrier to entry. Any Python developer can write an extension without learning a new API format. Dynamic importlib loading means extensions are just `.py` files in `.jarvis/extensions/` — no build step, no manifest registration.

**Why progressive skill disclosure?**
> Context window efficiency. Skills can be large (hundreds of lines of instructions). Showing only name + description + when_to_use in the system prompt keeps the context lean while still making the agent aware of available expertise. Full content loads on demand via `read` tool when the agent decides to use a skill.

**Why the Operations Protocol pattern for tool backends?**
> Testability and extensibility. By defining `FileOperations`, `BashOperations`, and `EditOperations` as `typing.Protocol`s, we enable runtime backend swapping (local ↔ SSH ↔ sandbox) without changing a single tool implementation. Tools call `self.file_ops.read_file(...)` and get whatever backend is active.

**Why markdown-based prompt templates instead of code-based slash commands?**
> Accessibility. Non-developers can create slash commands by writing a simple markdown file with YAML frontmatter. No Python code required. The argument substitution syntax (`$1`, `$2`, `$@`) is familiar from shell scripting.

**Why per-session EventBus instead of global singleton?**
> Isolation. Each agent session gets its own EventBus instance, so extensions bound to one session don't leak events into another. This enables future multi-session or subagent scenarios without cross-talk.

**Why preserve unknown JSON keys in settings?**
> Extension compatibility. Extensions can store their configuration in `settings.json` under the `extensions` key without requiring schema changes to `JarvisSettings`. The `get_extension_config()` method provides typed access, and `_raw_extras` ensures unknown keys survive a save/load cycle.

**Why the learning system uses M1→M2→M3 distillation?**
> Tiered quality. M1 captures raw traces (high recall, low precision), M2 filters and deduplicates, and M3 crystallizes into reusable skill markdown. This pipeline prevents low-quality or noisy data from polluting the skill library while still capturing valuable patterns.

**Why are MCP tools wrapped as BaseTool instances?**
> Uniform tool interface. By wrapping each MCP server tool as a `BaseTool`, the existing tool dispatch, permission checking, and callback infrastructure works identically for MCP tools as for built-in tools — no special-casing needed in the agent loop.

---

## What to Change vs What NOT to Touch

### ✅ Safe for Users to Change

| Area | What | Where |
|------|------|-------|
| **LLM model** | Switch provider/model | `providers.json`, `settings.json`, or `/api/settings/model` |
| **Agent profile** | Change agent behavior/safety | `settings.json` → `agent.profile` |
| **Safety level** | Restrict permissiveness | `settings.json` → `agent.safety_profile` or Shift+Tab in TUI |
| **Tools** | Enable/disable tool categories | `settings.json` → `permissions` |
| **Heartbeat** | Periodic background awareness | `settings.json` → `heartbeat.enabled`, `.interval`, `.active_hours` |
| **WebUI colors** | Full theme | `interface/webui/src/globals.css` → `:root` CSS variables |
| **System prompt** | Agent instructions | `core/agents/prompts/` → `jarvis_v2.py`, `explore.py`, etc. |
| **Extensions** | Add custom tools/hooks/commands | `.jarvis/extensions/*.py` — see `examples/extensions/` |
| **Operation backends** | Swap file/bash/edit backends | Extensions calling `api.operations_registry.set_*(...)` |
| **Custom tools** | New tool implementations | `.jarvis/extensions/` or `core/tools/` |
| **Prompt templates** | Slash commands | `.jarvis/prompts/*.md` — see `examples/prompts/` |
| **Context files** | Project-level agent instructions | `AGENTS.md`, `CLAUDE.md`, `SYSTEM.md` in project tree |
| **Skills** | On-demand capability packages | `~/.jarvis/skills/` as `SKILL.md` directories |
| **MCP servers** | Connect external tools | `.mcp.json` or `/api/mcp/servers` |
| **Connectors** | External data sources | `settings.json` → `connectors` or `/api/connectors` |
| **WebUI** | Look and feel | `interface/webui/` — all React components and CSS |
| **Settings file** | All runtime config | `~/.jarvis/settings.json` or `.jarvis/settings.json` |
| **Sandbox** | Command execution security | `settings.json` → `sandbox` |
| **Themes** | TUI color scheme | `~/.jarvis/themes/*.json` — 51 color tokens |
| **Keybindings** | Keyboard shortcuts | `~/.jarvis/keybindings.json` — namespaced action IDs |
| **Extension config** | Per-extension settings | `settings.json` → `extensions.my_ext` |

### ⚠️ Proceed with Caution (Understand Before Changing)

| Area | Why | Where |
|------|-----|-------|
| **Agent loop** | Core decision loop; breaks streaming, tool execution, approval flow | `core/agents/base.py` |
| **EventBus** | All extensions/hooks rely on it; changing event types breaks subscribers | `core/events/bus.py`, `core/events/types.py` |
| **ExtensionRunner** | Extension lifecycle; changing bind/unbind breaks all extensions | `core/extensions/runner.py` |
| **Tool registry** | Tool discovery and permission checks | `core/tools/registry.py`, `core/tools/__init__.py` |
| **SDK adapter** | All LLM communication goes through this | `core/llm/sdk_adapter.py` |
| **Provider SDKs** | Provider-specific API format | `core/llm_sdk/openai/sdk.py`, `core/llm_sdk/anthropic/sdk.py` |
| **WebSocket protocol** | Real-time message format between backend and UIs | `core/web/server.py` WebSocket handler |
| **Permission system** | Tool allow/deny/ask logic | `core/tools/permissions.py`, `core/tools/permission_manager.py` |
| **Config models** | Setting schema changes break existing configs | `core/config/models.py` |
| **API endpoints** | Changes break WebUI and external integrations | `core/web/server.py` |
| **Operations Protocols** | All tool backends implement these; adding methods breaks backends | `core/tools/operations/base.py` |

### 🚫 Don't Touch Unless You Understand the Full System

| Area | Why | Where |
|------|-----|-------|
| **`ConversationHistory`** | Stateful message store — changing ordering/format breaks all consumers | `core/history.py` |
| **`ToolOutput` / `ToolInput`** | Base models — all tools inherit from these | `core/tools/base.py` |
| **`BaseLLMProvider.generate_with_tools()`** | Contract between agent loop and LLM — changing it breaks every provider | `core/llm/base.py` |
| **WebUI CSS variables naming** | All 30+ components reference these by name | `globals.css` `:root` |
| **Thread component state contracts** | ThreadShell, ThreadComposer, ThreadMessages have specific prop contracts | `interface/webui/src/components/thread/` |
| **`JarvisClient` WebSocket message format** | Frontend-backend protocol — must stay in sync | `interface/webui/src/lib/jarvis-client.ts` and `core/web/server.py` |
| **`useJarvisStream` hook return shape** | All consuming components depend on this | `interface/webui/src/hooks/useJarvisStream.ts` |
