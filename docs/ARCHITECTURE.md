# JARVIS Architecture

## 1. Overview

JARVIS is a terminal-native AI engineering assistant with three UI modes (CLI, TUI, WebUI) built around a core agent loop that dispatches user requests to an LLM provider, executes tool calls the model requests, and iterates until a final response is produced. The system is organized as a Python monorepo with a layered design: a thin CLI launcher at `jarvis/cli.py` delegates to an interface layer, which talks to a core agent system (`core/agents/`), which in turn uses an LLM provider abstraction (`core/llm/`, `core/llm_sdk/`) and a tool system (`core/tools/`). Supporting subsystems handle configuration, MCP integration, connectors (GitHub, HTTP, RSS, etc.), file watchers, conversation checkpointing with the rewind system, sandboxed command execution, and a learning pipeline that distills interaction traces into reusable skills.

---

## 2. Directory Structure

| Directory | Purpose |
|---|---|
| `jarvis/` | CLI entry point (`cli.py`) — parses args, dispatches to TUI/CLI/WebUI |
| `core/agents/` | Agent system: `BaseAgent`, `JarvisV2`, `AgentManager`, `AsyncAgentManager`, fork subagent, heartbeat scheduler, task scheduler, system prompts, builtin agent profiles |
| `core/tools/` | Tool system: `BaseTool`, `ToolRegistry`/`AsyncToolRegistry`, `PermissionManager`/`PermissionContext`, 20+ tool implementations, MCP adapter, sandbox |
| `core/llm/` | LLM abstraction: `BaseLLMProvider`, `SDKAdapter`, model info, model registry |
| `core/llm_sdk/` | SDK implementations: OpenAI SDK, Anthropic SDK, tool parser, context length manager |
| `core/provider/` | Provider configuration: `ProviderManager`, provider model definitions |
| `core/connectors/` | Connector framework: `BaseConnector`, `ConnectorManager`, GitHub/HTTP/RSS/Weather/Filesystem connectors, unified `Document` schema |
| `core/config/` | Configuration: layered JSON/env/Pydantic model loading via `Settings`, `JarvisSettings` |
| `core/learn/` | Learning pipeline: M1→M2→M3 distillation, pattern detection, `SkillCrystallizer` |
| `core/skills/` | Skills CRUD management, reusable skill markdown storage |
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

---

## 3. Core Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                         jarvis/cli.py                               │
│              Arg parsing, env loading, UI dispatch                   │
└─────────┬──────────────────────────┬──────────────────────┬─────────┘
          │       defaults to         │                      │
          ▼                          ▼                      ▼
┌──────────────────┐   ┌────────────────────┐   ┌──────────────────────┐
│  interface/cli/  │   │ interface/textual_ │   │  interface/webui/    │
│  prompt_toolkit  │   │    ui/ (Textual)   │   │  React + Vite +     │
│  (sync/async)    │   │  rich TUI widgets  │   │  FastAPI backend    │
└─────────┬────────┘   └─────────┬──────────┘   └──────────┬───────────┘
          │                      │                          │
          └──────────────────────┼──────────────────────────┘
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
   │  (OpenAI, Anthropic)   │    │  MCP adapter, Sandbox, Rewind  │
   └─────────────────────────┘    └──────────────────────────────┘
                                              │
                                    ┌─────────┴──────────┐
                                    ▼                    ▼
                          ┌──────────────┐    ┌──────────────────┐
                          │ MCP Servers  │    │ External APIs     │
                          │ (stdio/sse)  │    │ (web, git, etc.)  │
                          └──────────────┘    └──────────────────┘
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

`BaseAgent` (1257 lines) provides:
- **Agent loop** (`_process_with_tools`): calls LLM with message history + tool definitions, executes any tool calls the model returns, appends results as user messages, and repeats until the model returns a plain-text response.
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
  ▼
_build_messages() ────► system prompt + memory + user content
  │
  ▼
_generate_with_tools() ──► LLM returns text or tool_calls
  │
  ├── tool_calls? ──► _execute_tools_and_update_messages()
  │                       │
  │                       ├── _should_execute_tool() [permission check]
  │                       ├── execute_tool() via ToolRegistry
  │                       ├── tool_call_callback / tool_result_callback
  │                       └── append results as user message
  │                       │
  │                       └── loop back to LLM
  │
  └── text? ──► return final response
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

- `ToolRegistry.register(tool)` — injects `tool_registry`, `llm_provider`, `model` refs into each tool.
- `ToolRegistry.discover_and_register_plugins()` — auto-loads `.py` files from `~/.jarvis/tools/` and `.jarvis/tools/`.
- `AsyncToolRegistry.execute_tools_concurrent()` — runs multiple tools in parallel with a configurable semaphore.

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

## 6. LLM / Provider Layer

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

## 7. MCP Integration

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

## 8. Connector Framework

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

## 9. Configuration System

Configuration uses a layered merge pattern (`core/config/settings.py`):

```
Priority (low → high):
  1. ~/.jarvis/settings.json       (global defaults)
  2. .jarvis/settings.json         (project overrides)
  3. Environment variables          (JARVIS_MODEL, JARVIS_API_KEY, etc.)
  4. initial_config dict            (runtime overrides)
```

`Settings` loads JSON configs, deep-merges them with env vars and any `initial_config`, then wraps everything in a `JarvisSettings` Pydantic model (`core/config/models.py`). Convenience properties expose typed access (`settings.heartbeat_enabled`, `settings.sandbox_enabled`, etc.). The `save()` method writes back to the highest-priority JSON file.

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
  ├── bypass_tool_permissions: bool
  ├── disallowed_tools: list[str]
  └── agent_paths: list[str]
```

---

## 10. User Interfaces

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

---

## 11. Data Flow

```
1. User types a message in CLI/TUI/WebUI
         │
2. Interface calls agent.process(user_input)
         │
3. JarvisV2._build_messages() constructs:
   [system_prompt, memory, context, user_message]
         │
4. BaseAgent._process_with_tools() calls LLM via
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
         │           └── Append tool result as user message
         │           │
         │           └── Loop back to LLM with updated history
         │
         └── LLM returns plain text → final response
                  │
5. Interface displays response (streamed or complete)
                  │
6. JarvisV2 post-processes:
   ├── Logs M1 trace to LearningManager (every 5 interactions)
   ├── Runs SkillCrystallizer on execution trace
   ├── Stores in agent memory
   └── (Optional) Heartbeat scheduler checks for pending tasks
```

---

## 12. Key Design Decisions

**Why a single-agent architecture (JarvisV2) rather than multi-agent orchestration?**
> Simplicity and reliability. A single agent with a rich tool set avoids the coordination overhead, context fragmentation, and failure modes of multi-agent systems. The tool system provides equivalent modularity — tools encapsulate all "agent-like" behavior (sub-agent delegation via the `agents` tool, MCP adapters, skill activation) without the complexity of agent-to-agent handoff.

**Why the SDKAdapter pattern instead of direct API calls?**
> Provider independence. `SDKAdapter` normalizes the typed SDK interface (`BaseLLMSDK`) into the dict-based `BaseLLMProvider` contract. This means adding a new provider only requires implementing `BaseLLMSDK` — no changes to the agent loop, tool system, or UI layers.

**Why are tool results injected as user messages rather than a tool role?**
> LLM compatibility. Some models (especially older OpenAI versions) do not reliably support a dedicated `tool` role. Injecting tool results as user messages with consistent formatting achieves identical behavior across all providers without branch logic in the agent loop.

**Why JSON config files instead of YAML/TOML/env-only?**
> Simplicity + overridability. JSON is universally parseable, supports nested structures natively, and the layered merge (global → project → env → runtime) gives users flexible setup without requiring environment variables for every option.

**Why the heartbeat scheduler is disabled by default?**
> User autonomy. Periodic background awareness is powerful but can be surprising. Users opt in via `heartbeat.enabled: true` in `.jarvis/settings.json`, with configurable active hours and intervals.

**Why bubblewrap-based sandbox for command execution?**
> Security without containers. `bubblewrap` provides lightweight filesystem namespace isolation without requiring Docker or root privileges. It is fast enough for interactive use and prevents accidental filesystem modifications from shell commands.

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
| **Custom agents** | New agent definitions | `~/.jarvis/agents/` as `.py` files |
| **Custom tools** | New tool implementations | `core/tools/` or MCP server |
| **MCP servers** | Connect external tools | `.mcp.json` or `/api/mcp/servers` |
| **Connectors** | External data sources | `settings.json` → `connectors` or `/api/connectors` |
| **WebUI** | Look and feel | `interface/webui/` — all React components and CSS |
| **Settings file** | All runtime config | `~/.jarvis/settings.json` or `.jarvis/settings.json` |
| **Sandbox** | Command execution security | `settings.json` → `sandbox` |

### ⚠️ Proceed with Caution (Understand Before Changing)

| Area | Why | Where |
|------|-----|-------|
| **Agent loop** | Core decision loop; breaks streaming, tool execution, approval flow | `core/agents/base.py` |
| **Tool registry** | Tool discovery and permission checks | `core/tools/registry.py`, `core/tools/__init__.py` |
| **SDK adapter** | All LLM communication goes through this | `core/llm/sdk_adapter.py` |
| **Provider SDKs** | Provider-specific API format | `core/llm_sdk/openai/sdk.py`, `core/llm_sdk/anthropic/sdk.py` |
| **WebSocket protocol** | Real-time message format between backend and UIs | `core/web/server.py` WebSocket handler |
| **Permission system** | Tool allow/deny/ask logic | `core/tools/permissions.py`, `core/tools/permission_manager.py` |
| **Config models** | Setting schema changes break existing configs | `core/config/models.py` |
| **API endpoints** | Changes break WebUI and external integrations | `core/web/server.py` |

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
