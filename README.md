<div align="center">

# JARVIS v2.1
<img align="center" height="150" src="https://i.pinimg.com/originals/20/e0/83/20e0839cefb31bc03e058be16bacc26e.gif"  />

<a href="https://github.com/OEvortex/JARVIS"><img src="https://img.shields.io/badge/version-2.1.0-blue?style=for-the-badge"></a>
<a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-green?style=for-the-badge"></a>
<a href="https://github.com/OEvortex/JARVIS/stargazers"><img src="https://img.shields.io/github/stars/OEvortex/JARVIS?style=for-the-badge&color=yellow"></a>
<a href="https://github.com/OEvortex/JARVIS/issues"><img src="https://img.shields.io/github/issues/OEvortex/JARVIS?style=for-the-badge&color=red"></a>

**Your Personal AI Assistant - Fully Agentic AI Harness with Claude Code-style Capabilities**

</div>

<div align="center">

[📖 Docs](docs/SUMMARY.md) • [🚀 Setup](docs/SETUP.md) • [🏗️ Architecture](docs/ARCHITECTURE.md) • [🔌 Extensions](docs/EXTENSIONS.md) • [📡 API](docs/API.md) • [💻 Contributing](docs/CONTRIBUTING.md)

</div>

---

## 🚀 Overview

JARVIS v2.1 is a **Personal AI Assistant (PI)** - a next-generation agentic harness inspired by Claude Code and mistral-vibe. It provides unified agentic assistance for coding, research, documentation, and knowledge work through intelligent tool usage. Built with a **plugin-extensible, event-driven architecture** featuring an extension system, lifecycle hooks, pub/sub event bus, pluggable operation backends, persistent memory, RPC mode, and comprehensive tooling.

### Key Features

| Feature | Description |
|---------|-------------|
| **🤖 Fully Agentic** | JARVIS agent handles coding, research, documentation, and complex tasks autonomously |
| **🔍 Explore Subagent** | Specialized agent for codebase exploration and architecture analysis |
| **📝 Plan Subagent** | Specialized agent for planning and task decomposition |
| **🍴 Fork Subagent** | Fork conversation context for parallel exploration |
| **🧠 Persistent Memory** | Structured memory with types (user/feedback/project/reference/global), scopes (private/team/global), tagging, and priority |
| **🔌 Extension System** | Plugin architecture — custom tools, hooks, commands, shortcuts loaded from `.jarvis/extensions/*.py` |
| **🔧 Pluggable Operations** | Swap file/bash/edit backends at runtime (SSH, Docker, sandbox) via OperationsRegistry |
| **🔔 Event & Hook System** | Pub/sub EventBus (24 event types) + lifecycle HookRegistry (16 stages) for observability and interception |
| **📜 Prompt Templates** | Markdown files with YAML frontmatter auto-register as slash commands (`/review`, `/testgen`, `/explain`) |
| **🔄 Rewind System** | Conversation checkpointing with file snapshots for undo |
| **📡 RPC Mode** | JSONL protocol over stdin/stdout for IDE/process embedding |
| **🔌 MCP Integration** | Lazy MCP proxy tool with on-demand connections, metadata cache, auth support |
| **🌐 WebUI** | Full-featured browser-based interface with FastAPI backend |
| **🎨 Techy WebUI** | Modern dark UI with infinite canvas, dot grid, slash commands, active tool call widget |
| **💡 Learning System** | Pattern detection, skill creation, and self-evaluation |
| **💻 Dual Interfaces** | Rich CLI, modern TUI (Textual), and WebUI |
| **🔒 Safety First** | Granular permission system with 5 agent profiles |
| **🔧 25+ Tools** | Comprehensive tools for file ops, code execution, web, memory, worktree, MCP, and more |
| **🔌 Multi-LLM** | OpenAI, Anthropic, and custom SDK adapters |
| **☁️ Remote Sessions** | Connect to remote JARVIS instances via JARVIS_REMOTE_URL |

---

## 📦 Installation

### Prerequisites

- **Python 3.10+** (recommended 3.11+)
- **Node.js 18+** (only needed for WebUI mode)
- **API Key** from OpenAI or Anthropic

### Quick Setup (CLI/TUI)

```bash
# Clone the repository
git clone https://github.com/OEvortex/JARVIS.git
cd JARVIS

# Create and activate virtual environment with uv
uv venv
source .venv/bin/activate     # Linux/macOS
# .venv\Scripts\activate       # Windows

# Install Python dependencies
uv sync

# Configure your API key
cp .env.example .env
# Then edit .env with your API key
```

### Quick Setup (WebUI)

If you want the browser-based WebUI, do the extra step after installing Python deps:

```bash
# Install WebUI frontend dependencies
cd jarvis/interface/webui
npm install
cd ../../..
```

### Quick Start

```bash
# TUI mode (default)
jarvis

# WebUI mode
jarvis --webui
```

### Configuration

Create a `.env` file with your API keys:

```bash
cp .env.example .env
```

```env
JARVIS_MODEL=gpt-4o
JARVIS_BASE_URL=https://api.openai.com/v1
JARVIS_API_KEY=your_api_key_here
JARVIS_SDK=openai
```

For more advanced configuration, create a `.jarvis/settings.json` file (see Configuration Reference below).

---

## 🚀 Usage

### TUI Mode (Default)

```bash
jarvis
jarvis --model gpt-4o --apikey YOUR_KEY
jarvis --model llama-3-70b --base_url http://localhost:8000/v1 --apikey dummy --sdk openai
```

### CLI Mode

```bash
jarvis --cli --model gpt-4o --apikey YOUR_KEY --sdk openai
jarvis --cli
```

### WebUI Mode

> **Prerequisite**: Run `cd jarvis/interface/webui && npm install && cd ../../..` first to install frontend dependencies.

```bash
jarvis --webui
jarvis --webui --port 8080 --backend-port 8765
jarvis --webui --host 0.0.0.0 --port 5173
```

### RPC Mode

```bash
echo '{"id":"1","type":"prompt","message":"Hello"}' | jarvis --mode rpc
```

### Available CLI Flags

| Flag | Short | Description |
|------|-------|-------------|
| `--model` | `-m` | Model name (e.g., `gpt-4o`, `claude-3-5-sonnet-20241022`) |
| `--base_url` | | Base URL for LLM API |
| `--apikey` | `--api-key` | API key for the provider |
| `--sdk` | | SDK mode: `openai` or `anthropic` |
| `--mode` | | Interface mode: `tui` (default), `cli`, `webui`, `rpc` |
| `--cli` | | Launch CLI interface |
| `--tui` | `--TUI` | Launch TUI interface (default) |
| `--webui` | | Launch WebUI interface |
| `--rpc` | | Launch RPC mode |
| `--bypass` | `--yolo` | Bypass all tool permissions |
| `--host` | `-H` | WebUI host (default: 127.0.0.1) |
| `--port` | `-p` | WebUI frontend port (default: 5173) |
| `--backend-port` | `-b` | WebUI backend port (default: 8765) |

---

## 🎯 Current Status

| Component | Status |
|-----------|--------|
| ✅ LLM Provider Abstraction | Complete |
| ✅ Tool System | Complete (25+ tools) |
| ✅ JARVIS Agent (PI) | Complete |
| ✅ Explore Subagent | Ready |
| ✅ Plan Subagent | Ready |
| ✅ Fork Subagent | Ready |
| ✅ Rubber Duck Agent | Ready |
| ✅ CLI Interface | Stable |
| ✅ TUI Interface | Complete (Default) |
| ✅ WebUI | Complete (with slash commands, active tool call widget, remote sessions) |
| ✅ Permission System | Complete |
| ✅ MCP Integration | Complete (lazy proxy, lifecyle mgmt, auth, cache) |
| ✅ Extension System | Complete (API, loader, runner, registry) |
| ✅ Event/Hook System | Complete (EventBus + 16 HookStages) |
| ✅ Operations Registry | Complete (pluggable file/bash/edit backends) |
| ✅ Persistent Memory | Complete (typed, scoped, tagged, priority) |
| ✅ Prompt Templates | Complete (markdown frontmatter → slash commands) |
| ✅ Resource Discovery | Complete (tiered: project > user > global) |
| ✅ Learning System | Complete |
| ✅ Heartbeat System | Complete |
| ✅ Connectors System | Complete |
| ✅ Rewind System | Complete (checkpoints + file snapshots) |
| ✅ RPC Mode | Complete (JSONL stdin/stdout protocol) |
| ✅ Worktree Tools | Complete (enter/exit git worktrees) |
| ✅ Theme & Keybindings | Complete (51 tokens, hot-reload, namespaced actions) |
| ✅ Session Management | Complete (local + remote) |

---

## 🏗️ Architecture

### System Overview

```mermaid
graph TB
    %% Nodes definition
    subgraph "JARVIS Agent Layer"
        Jarvis["JarvisV2 (Main Agent)<br/>jarvis/core/agents/jarvis_v2.py"]
    end

    subgraph "Core Managers & Controllers"
        AgentMgr["AgentManager<br/>jarvis/core/agents/manager.py"]
        ToolReg["ToolRegistry<br/>jarvis/core/tools/registry.py"]
        Config["Settings & Models<br/>jarvis/core/config/settings.py"]
        History["ConversationHistory<br/>jarvis/core/history.py"]
    end

    subgraph "Specialized Agents"
        ExploreAg["ExploreAgent<br/>explore_agent.py"]
        PlanAg["PlanAgent<br/>plan_agent.py"]
        ForkAg["ForkSubagent<br/>fork_subagent.py"]
        DuckAg["RubberDuckAgent<br/>rubber_duck_agent.py"]
        BuiltinAg["BuiltinAgents<br/>builtin_agents.py"]
    end

    subgraph "Toolbox (25+ Tools)"
        FileTools["File Tools<br/>file_tools.py / file_edit_tool.py"]
        GrepTool["Grep Tool<br/>grep_tool.py"]
        ReplTool["REPL Tool<br/>repl_tool.py"]
        MCPTool["MCP Adapter<br/>mcp_adapter.py"]
        WebTools["Web Tools<br/>web_tools.py"]
        MemTool["Memory Tools<br/>memory_tool.py"]
        WtTool["Worktree Tools<br/>worktree_tool.py"]
        SkillTool["Skill Tools<br/>skill_tool.py"]
    end

    subgraph "Plugin & Event Layer"
        ExtAPI["Extension System<br/>core/extensions/"]
        EventBus["EventBus + Hooks<br/>core/events/"]
        OpsReg["OperationsRegistry<br/>core/tools/operations/"]
    end

    subgraph "Supporting Systems"
        Skills["SkillManager<br/>core/skills/manager.py"]
        Safety["PermissionManager<br/>core/tools/permissions.py"]
        Learn["LearningManager<br/>core/learn/learning_manager.py"]
        Connectors["ConnectorManager<br/>core/connectors/manager.py"]
        Prompts["Prompt Templates<br/>core/prompts/"]
        Resources["Resource Discovery<br/>core/resources/"]
        Rewind["Rewind Manager<br/>core/rewind/manager.py"]
    end

    subgraph "LLM Provider Layer"
        SDK["LLM SDK Adapter<br/>core/llm/sdk_adapter.py"]
        OpenAI["OpenAI SDK<br/>core/llm_sdk/openai"]
        Anthropic["Anthropic SDK<br/>core/llm_sdk/anthropic"]
    end

    %% Relationships & Flow
    Jarvis --> AgentMgr
    Jarvis --> ToolReg
    Jarvis --> Config
    Jarvis --> History
    Jarvis --> ExtAPI
    Jarvis --> EventBus

    AgentMgr --> ExploreAg
    AgentMgr --> PlanAg
    AgentMgr --> ForkAg
    AgentMgr --> DuckAg
    AgentMgr --> BuiltinAg

    ToolReg --> FileTools
    ToolReg --> GrepTool
    ToolReg --> ReplTool
    ToolReg --> MCPTool
    ToolReg --> WebTools
    ToolReg --> MemTool
    ToolReg --> WtTool
    ToolReg --> SkillTool
    ToolReg --> OpsReg

    Jarvis --> Learn
    Jarvis --> Connectors
    Jarvis --> Rewind
    Jarvis --> Prompts
    Jarvis --> Resources

    FileTools --> Safety
    GrepTool --> Safety
    ReplTool --> Safety

    SkillTool --> Skills
    Learn --> Skills

    Jarvis --> SDK
    ExploreAg --> SDK
    PlanAg --> SDK
    ForkAg --> SDK

    SDK --> OpenAI
    SDK --> Anthropic

    %% Styling
    classDef main fill:#ffcccc,stroke:#333,stroke-width:2px;
    classDef core fill:#ccffcc,stroke:#333,stroke-width:1px;
    classDef agent fill:#ccccff,stroke:#333,stroke-width:1px;
    classDef tool fill:#ffffcc,stroke:#333,stroke-width:1px;
    classDef plugin fill:#ccddff,stroke:#333,stroke-width:1px;
    classDef support fill:#ffccff,stroke:#333,stroke-width:1px;
    classDef sdk fill:#ccffff,stroke:#333,stroke-width:1px;

    class Jarvis main;
    class AgentMgr,ToolReg,Config,History core;
    class ExploreAg,PlanAg,ForkAg,DuckAg,BuiltinAg agent;
    class FileTools,GrepTool,ReplTool,MCPTool,WebTools,MemTool,WtTool,SkillTool tool;
    class ExtAPI,EventBus,OpsReg plugin;
    class Skills,Safety,Learn,Connectors,Prompts,Resources,Rewind support;
    class SDK,OpenAI,Anthropic sdk;
```


### Directory Structure

```
JARVIS/
├── jarvis/                # Main Python package
│   ├── core/                  # Core systems
│   │   ├── agents/            # Agent system (base.py, jarvis_v2.py, manager.py, profiles, prompts/)
│   │   ├── tools/             # Tool system (registry, base, permissions, 20+ tools, MCP, sandbox)
│   │   ├── extensions/        # Extension system (api, loader, runner, registry, types)
│   │   ├── events/            # Event bus and hook registry
│   │   ├── llm/               # LLM provider abstraction (SDKAdapter, model info)
│   │   ├── llm_sdk/           # Provider SDKs (openai/, anthropic/)
│   │   ├── provider/          # Provider manager & models
│   │   ├── config/            # Settings (JSON + env overrides)
│   │   ├── connectors/        # External data connectors (github, http, rss, weather, filesystem)
│   │   ├── learn/             # Learning system (pattern detection, skill crystallization)
│   │   ├── skills/            # Skill management (CRUD, sources, trace collection)
│   │   ├── rewind/            # Conversation checkpointing with file snapshots
│   │   ├── watchers/          # Passive file/event watchers
│   │   └── web/               # FastAPI web server (REST + WebSocket endpoints)
│   ├── interface/             # User interfaces
│   │   ├── cli/               # prompt_toolkit-based CLI
│   │   ├── textual_ui/        # Textual-based TUI (30+ widgets)
│   │   └── webui/             # React/TypeScript WebUI (Vite + Tailwind + shadcn)
│   ├── api.py                 # Public extension API (stable surface)
│   └── _version.py            # Version management
├── .jarvis/               # Project-local config & extensions
│   ├── extensions/            # Project extension files (*.py)
│   └── settings.json          # Project settings
├── tests/                 # Python test suite (pytest)
├── docs/                  # 📖 Documentation
│   ├── SUMMARY.md            # Entry point with quick-links
│   ├── SETUP.md              # Installation & configuration
│   ├── ARCHITECTURE.md       # Full system architecture
│   ├── API.md                # REST + WebSocket API reference
│   ├── CONTRIBUTING.md       # Development guide
│   ├── EXTENSIONS.md         # Extension system documentation
│   ├── HOOKS.md              # Lifecycle hooks reference
│   ├── custom-agents.md      # Custom agent profiles
│   ├── custom-tools.md       # Writing new tools
│   ├── MCP.md                # MCP server integration
│   ├── SANDBOX.md            # Sandboxed execution
│   ├── EXTENSIONS.md         # Extension plugin system
│   ├── HOOKS.md              # Event & hook system
│   ├── watchers.md           # File/event watchers
│   └── webui-theme.md        # CSS variable theming
├── examples/              # Reference examples
│   ├── extensions/           # Extension examples (hello_world, audit, safety, ssh, etc.)
│   └── prompts/              # Prompt template examples (review, testgen, explain)
├── main.py               # Application entry point
├── providers.json         # LLM provider definitions
├── pyproject.toml          # Python project config
└── .env.example           # Environment variables template
```

---

## 🧠 Persistent Memory System

JARVIS features a structured persistent memory system (inspired by OpenClaude and Hermes):

### Memory Types

| Type | Description |
|------|-------------|
| `user` | Details about user's role, goals, preferences |
| `feedback` | Guidance on how to approach work, corrections |
| `project` | Ongoing work, goals, initiatives, bugs |
| `project_context` | Architecture, technical decisions, implementation details |
| `reference` | Pointers to external systems and resources |
| `global` | Cross-project patterns and best practices |

### Scopes & Organization

| Scope | Location | Visibility |
|-------|----------|------------|
| `private` | `.jarvis/memory/private/` | Current project only |
| `team` | `.jarvis/memory/team/` | Shared within project |
| `global` | `~/.jarvis/global_memory/` | All projects |

Memories are stored as Markdown files with YAML frontmatter (name, description, type, priority, tags, project), automatically indexed via `MEMORY.md`, and searchable by type, scope, tags, priority, and content.

### Memory Tools

| Tool | Description |
|------|-------------|
| `save_memory` | Save structured memories with type, scope, priority, tags |
| `read_memory` | Search/retrieve memories with filtering |
| `memory` | Hermes-style MEMORY.md/USER.md management (add/replace/read/remove) |

---

## 🔌 Extension System

JARVIS has a full plugin architecture. Extensions are plain Python files loaded from `.jarvis/extensions/`:

```
.jarvis/extensions/
├── my_tool.py          # Register custom tools
├── safety_gate.py      # Block dangerous operations via hooks
└── ssh_backend.py      # Swap operations backend to SSH
```

```python
# .jarvis/extensions/example.py
async def jarvis_extension(api: ExtensionAPI):
    api.register_tool(MyTool())
    api.on(ToolCallStarted, my_handler)
    api.register_hook(HookStage.BEFORE_TOOL_CALL, safety_gate)
    api.register_command("/hello", hello_cmd, "Say hello")
    api.register_shortcut("ctrl+h", "app.hello", "Hello")
```

See [docs/EXTENSIONS.md](docs/EXTENSIONS.md) for the full reference.

Access via `ExtensionAPI`:
- `register_tool(tool)` — Override or add tools
- `register_command(name, handler, desc)` — Slash commands
- `on(event_type, handler)` — Subscribe to events
- `register_hook(stage, handler)` — Lifecycle hooks
- `register_shortcut(key, action_id, desc)` — Keyboard shortcuts
- `api.operations_registry.set_bash_ops(...)` — Swap backends

---

## 🔔 Event & Hook System

Dual-layer architecture for observability and interception:

### EventBus (Pub/Sub)
- 24 event types across 8 categories (Agent, Turn, Message, Tool, Session, Extension, Status, System)
- Priority-ordered handlers, polymorphic dispatch (MRO walking)
- Per-session instances, introspection stats

### HookRegistry (Lifecycle Interception)
- 16 hook stages covering agent/turn/tool/session/skill lifecycles
- Handlers can **block**, **modify arguments**, or **inject content**
- Short-circuit on block, error-tolerant execution

See [docs/HOOKS.md](docs/HOOKS.md) for the full reference.

---

## 📡 RPC Mode

Embed JARVIS in IDEs, web UIs, or other processes via JSONL over stdin/stdout:

```bash
echo '{"id":"1","type":"prompt","message":"Hello"}' | jarvis --mode rpc
```

**Commands:** `prompt`, `steer`, `follow_up`, `bash`, `compact`, `new_session`, `get_state`, `get_messages`, `get_tools`, `set_model`

**Events:** `text_delta`, `thinking_delta`, `tool_call_start`, `tool_call_end`, `turn_start`, `turn_end`, `status`, `session_started`

---

## 🔧 Pluggable Operations Backend

The `OperationsRegistry` decouples tool implementations from OS calls. Extensions can swap backends at runtime:

| Backend | Protocol | Use Case |
|---------|----------|----------|
| `LocalFileOperations` | `aiofiles` | Default local operations |
| `LocalBashOperations` | `asyncio` | Default subprocess execution |
| `LocalEditOperations` | `aiofiles` | Default file editing |
| *Custom* | Any | SSH, Docker, sandbox, remote |

```python
api.operations_registry.set_bash_ops(MySSHBackend())
api.operations_registry.set_file_ops(MyDockerBackend())
```

---

## 📜 Prompt Templates

Markdown files with YAML frontmatter auto-register as slash commands:

```markdown
---
name: review
description: Review code for issues
arguments: path
---
# Code Review

Review the code at `$1` for:
- Security vulnerabilities
- Performance issues
- Best practices
```

Arguments use shell-style substitution (`$1`, `$2`, `$@`, `${@:2}`). Templates are discovered from `.jarvis/prompts/` and `~/.jarvis/prompts/`.

---

## 🛠️ Available Tools

JARVIS comes with 25+ built-in tools for comprehensive task handling:

### File Operations

| Tool | Description |
|------|-------------|
| `read` | Read file(s) with parallel support and offset/limit |
| `write` | Create new files (fails if exists) |
| `edit` | Edit existing files with string replacements |
| `list_dir` | List directory contents |
| `glob` | Search files by glob pattern |

### Code Execution

| Tool | Description |
|------|-------------|
| `bash` | Execute shell commands |
| `repl` | Interactive Python REPL |
| `run_tests` | Run test files with pytest |

### Search & Discovery

| Tool | Description |
|------|-------------|
| `grep` | Search for patterns in files |
| `tool_search` | Search and discover available tools |

### Web & Network

| Tool | Description |
|------|-------------|
| `web_fetch` | Fetch web content |
| `web_search` | Search the web via Brave/Exa API |

### Background & Async

| Tool | Description |
|------|-------------|
| `run_in_background` | Run commands in background |
| `list_background_processes` | List running background processes |
| `read_background_output` | Read background process output |

### Memory & Knowledge

| Tool | Description |
|------|-------------|
| `save_memory` | Save structured memories (typed, scoped, tagged) |
| `read_memory` | Search/retrieve memories with filtering |
| `memory` | Hermes-style MEMORY.md/USER.md management |

### Agents & Skills

| Tool | Description |
|------|-------------|
| `agents` | Invoke subagents (explore, plan, fork, duck) |
| `activate_skill` | Activate specialized skills |
| `manage_skills` | Create and manage custom skills |
| `ask_user_question` | Ask user structured questions |

### MCP Tools

| Tool | Description |
|------|-------------|
| `mcp` | Unified proxy tool for all MCP servers (status, list, search, describe, call, connect) |
| `mcp_list_servers` | List connected MCP servers |

### Worktree Tools

| Tool | Description |
|------|-------------|
| `enter_worktree` | Create and enter an isolated git worktree |
| `exit_worktree` | Exit current worktree and return to main |

### System Tools

| Tool | Description |
|------|-------------|
| `clipboard_read` | Read system clipboard |
| `clipboard_write` | Write to system clipboard |
| `resource_monitor` | Check system resources |

---

## 👤 Agent Profiles

**JARVIS** is your main **Personal AI Assistant (PI)** agent with multiple specialized subagents:

| Agent | Purpose |
|-------|---------|
| **JARVIS** | Main agent for all tasks (coding, research, documentation) |
| **Explore** | Codebase exploration and architecture analysis |
| **Plan** | Task decomposition and planning |
| **Fork** | Fork conversation for parallel exploration |
| **Rubber Duck** | Constructive critique and code review |

### Safety Profiles (WebUI)

5 safety levels with Shift+Tab cycling:

| Level | Name | Code | Files | Dangerous |
|-------|------|------|-------|-----------|
| L1 | Lockdown | never | ask | ask |
| L2 | Restricted | ask | ask | ask |
| L3 | Balanced | ask | always | ask |
| L4 | Permissive | always | always | ask |
| L5 | Unrestricted | always | always | always |

**Cycle profiles with `Shift+Tab` in WebUI or TUI.**

### Permission System

**Permission Levels:**
- **ALWAYS**: Tool executes without asking
- **NEVER**: Tool is permanently disabled
- **ASK**: Tool requires user approval (default)

**Granular Permissions (Vibe-style):**
- **Path-based allowlist/denylist**: Files matching patterns are always/never allowed
- **Sensitive file patterns**: Files matching sensitive patterns require special approval
- **Workdir boundary**: Files outside working directory require approval
- **Scratchpad paths**: Files in scratchpad directories are always allowed
- **Dangerous command patterns**: Bash commands with dangerous patterns require special approval

---

## 🔌 MCP Integration

JARVIS uses a **lazy MCP** architecture with a single `mcp` proxy tool and on-demand connections:

```json
// .mcp.json (or ~/.jarvis/mcp.json)
{
  "mcp_servers": [
    {
      "name": "filesystem",
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/path/to/allowed"],
      "transport": "stdio"
    },
    {
      "name": "github",
      "command": "python",
      "args": ["-m", "mcp.server.github"],
      "transport": "stdio",
      "env": { "GITHUB_TOKEN": "..." }
    },
    {
      "name": "http-server",
      "url": "http://localhost:3000/mcp",
      "transport": "http"
    }
  ]
}
```

### MCP Transport Types
- **stdio**: Local subprocess-based MCP servers
- **http/sse**: Remote MCP servers via HTTP

Features: token-efficient proxy tool, lazy connections, metadata cache (`~/.jarvis/mcp-cache.json`), OAuth/Bearer/API key auth, resources/prompts/sampling support.

---

## 🔌 Extension System

JARVIS has a full plugin architecture. Extensions are plain Python files loaded from `.jarvis/extensions/` or `~/.jarvis/extensions/`:

```
.jarvis/extensions/
├── my_tool.py          # Register custom tools
├── safety_gate.py      # Block dangerous operations via hooks
└── my_backend.py       # Swap tool implementations
```

```python
# .jarvis/extensions/example.py
from jarvis.api import ExtensionAPI, BaseTool, ToolInput, ToolOutput
from jarvis.api import HookStage, HookContext, HookResult
from jarvis.api import ToolCallStarted

async def jarvis(api: ExtensionAPI):
    api.tools(MyTool())
    api.on(ToolCallStarted, my_handler)
    api.hook(HookStage.BEFORE_TOOL_CALL, safety_gate)
    api.command("/hello", hello_cmd, "Say hello")
    api.shortcut("ctrl+h", "app.hello", "Hello")
```

See [docs/EXTENSIONS.md](docs/EXTENSIONS.md) for the full reference.

### ExtensionAPI Methods

| Method | Description |
|--------|-------------|
| `tools(tool)` | Register a `BaseTool` instance (overrides built-ins if name matches) |
| `agents(definition)` | Register a custom `AgentDefinition` |
| `command(name, handler, desc)` | Register a slash command |
| `on(event_type, handler)` | Subscribe to an `EventBus` event |
| `hook(stage, handler)` | Register a lifecycle hook at a `HookStage` |
| `shortcut(key, action_id, desc)` | Register a keyboard shortcut |

### Discovery & Precedence

Extensions are loaded from three sources (highest → lowest priority):
1. **Project-local**: `.jarvis/extensions/*.py`
2. **User global**: `~/.jarvis/extensions/*.py`
3. **pip entry points**: packages registered under `jarvis.extensions`

If the same filename exists in multiple locations, the higher-precedence version wins.

---

## 🔔 Event & Hook System

Dual-layer architecture for observability and interception:

### EventBus (Pub/Sub)
- **24 event types** across 8 categories (Agent, Turn, Message, Tool, Session, Extension, Status, System)
- Priority-ordered handlers, polymorphic dispatch (MRO walking)
- Per-session instances, introspection stats

### HookRegistry (Lifecycle Interception)
- **16 hook stages** covering agent/turn/tool/session/skill lifecycles
- Handlers can block, modify arguments, or inject content
- Short-circuit on block, error-tolerant execution

```python
from jarvis.api import HookStage, HookContext, HookResult

async def safety_gate(ctx: HookContext) -> HookResult:
    if ctx.tool_name == "bash" and "rm -rf" in str(ctx.args):
        return HookResult(proceed=False, message="Blocked: dangerous command")
    return HookResult(proceed=True)
```

See [docs/HOOKS.md](docs/HOOKS.md) for the full reference.

---

## 📡 RPC Mode

Embed JARVIS in IDEs, web UIs, or other processes via JSONL over stdin/stdout:

```bash
echo '{"id":"1","type":"prompt","message":"Hello"}' | jarvis --mode rpc
```

**Commands**: `prompt`, `steer`, `follow_up`, `bash`, `compact`, `new_session`, `get_state`, `get_messages`, `get_tools`, `set_model`

**Events**: `text_delta`, `thinking_delta`, `tool_call_start`, `tool_call_end`, `turn_start`, `turn_end`, `status`, `session_started`

---

## 💡 Learning System

JARVIS includes an intelligent learning system that:

1. **Pattern Detection**: Identifies recurring patterns in user interactions
2. **Skill Creation**: Automatically creates skills after threshold interactions
3. **Self-Evaluation**: Periodically evaluates its own performance
4. **Memory Management**: Semantic memory with importance scoring
5. **Classification**: ML-based interaction categorization

### Configuration

```toml
[learning]
enabled = true
skill_creation_threshold = 5
self_evaluation_interval = 15
memory_dir = "~/.jarvis/memory"
skills_dir = "~/.jarvis/skills"
max_memory_chars = 100000
max_user_chars = 50000
```

---

## 💓 Heartbeat System

JARVIS includes a nanobot-style two-phase heartbeat for periodic awareness:

### How it Works

1. **Phase 1 (Decision)**: LLM decides via virtual tool call whether to skip or run
2. **Phase 2 (Execution)**: Only triggered when Phase 1 returns "run"
3. **Response Filtering**: Non-deliverable responses are automatically suppressed

### Configuration

```toml
[heartbeat]
enabled = true
every = "30m"
target = "last"
light_context = false
isolated_session = false
skip_when_busy = true
prompt = "Review tasks and decide if action is needed."
active_hours = { start = "09:00", end = "18:00", timezone = "America/New_York" }
show_ok = false
show_alerts = true
use_indicator = true
```

### HEARTBEAT.md

Create `.jarvis/HEARTBEAT.md` in your project to define periodic tasks:

```markdown
# Heartbeat Tasks

## Active Tasks

- [ ] Review open PRs
- [ ] Check build status
- [ ] Update dependencies

## Completed

- [x] Last task description
```

---

## 🔧 Configuration Reference

### Environment Variables

```env
# LLM Configuration
JARVIS_MODEL=gpt-4o
JARVIS_BASE_URL=https://api.openai.com/v1
JARVIS_API_KEY=your_api_key
JARVIS_SDK=openai

# Heartbeat Configuration (optional)
JARVIS_HEARTBEAT_ENABLED=true
JARVIS_HEARTBEAT_EVERY=30m
JARVIS_HEARTBEAT_TARGET=last
JARVIS_HEARTBEAT_SKIP_WHEN_BUSY=true
JARVIS_HEARTBEAT_SHOW_OK=false

# Remote sessions (optional)
JARVIS_REMOTE_URL=https://your-remote-jarvis.com

# Agent Loop Configuration (optional)
# Maximum number of turns before stopping (default: 100)
JARVIS_MAX_TURNS=100
# Maximum consecutive skipped tool calls before stopping (default: 5)
JARVIS_MAX_CONSECUTIVE_SKIPS=5
```

### Full Configuration (settings.json)

```json
{
  "app": {
    "name": "JARVIS",
    "version": "2.1.0",
    "debug": false
  },
  "provider": {
    "selected_provider_id": "openai",
    "config_file": "providers.json"
  },
  "learning": {
    "enabled": true,
    "skill_creation_threshold": 5,
    "self_evaluation_interval": 15,
    "memory_dir": "~/.jarvis/memory",
    "skills_dir": "~/.jarvis/skills"
  },
  "tools": {
    "enable_code_execution": true,
    "enable_file_operations": true,
    "enable_git_operations": true
  },
  "async": {
    "max_concurrent_agents": 5,
    "max_concurrent_tools": 10,
    "default_timeout": 300,
    "enable_background_tasks": true,
    "resource_monitoring": true,
    "progress_updates": true
  },
  "heartbeat": {
    "enabled": false,
    "every": "30m",
    "target": "last",
    "light_context": false,
    "skip_when_busy": true,
    "show_ok": false
  }
}
```


---

## 📚 Documentation

| Doc | For |
|-----|-----|
| [📖 SUMMARY.md](docs/SUMMARY.md) | Entry point — quick-links + AI agent instructions |
| [🚀 SETUP.md](docs/SETUP.md) | Installing, configuring, and running JARVIS |
| [🏗️ ARCHITECTURE.md](docs/ARCHITECTURE.md) | Understanding the full system — agents, tools, LLM, frontends |
| [📡 API.md](docs/API.md) | REST + WebSocket API reference for building on top |
| [💻 CONTRIBUTING.md](docs/CONTRIBUTING.md) | Developing JARVIS — code style, tests, PRs |
| [🔌 EXTENSIONS.md](docs/EXTENSIONS.md) | Extension system — writing plugins, API reference |
| [🪝 HOOKS.md](docs/HOOKS.md) | Lifecycle hooks — stages, context, results |
| [🤖 custom-agents.md](docs/custom-agents.md) | Creating custom agent profiles |
| [🔧 custom-tools.md](docs/custom-tools.md) | Writing new tools |
| [🔌 MCP.md](docs/MCP.md) | Connecting MCP servers |
| [📦 SANDBOX.md](docs/SANDBOX.md) | Sandboxed command execution |
| [🔌 EXTENSIONS.md](docs/EXTENSIONS.md) | Extension plugin system |
| [🔔 HOOKS.md](docs/HOOKS.md) | Event & hook system |
| [👁️ watchers.md](docs/watchers.md) | File/event watchers |
| [🎨 webui-theme.md](docs/webui-theme.md) | Customizing WebUI colors |

---

## ✅ What You Can Change vs What NOT to Touch

### Safe to Customize

| What | How |
|------|-----|
| **LLM model/provider** | Edit `providers.json` or `settings.json` |
| **Agent behavior** | Switch profile or write a custom agent (`~/.jarvis/agents/`) |
| **Safety level** | `settings.json` → `agent.safety_profile` or Shift+Tab |
| **WebUI colors** | Edit CSS variables in `jarvis/interface/webui/src/globals.css` |
| **System prompt** | Edit files in `jarvis/core/agents/prompts/` |
| **Tool permissions** | `settings.json` → `permissions` |
| **MCP servers** | Configure in `.mcp.json` |
| **Custom tools** | Write a `BaseTool` subclass — see [custom-tools.md](docs/custom-tools.md) |
| **Extensions** | Drop `.py` files in `.jarvis/extensions/` — see [EXTENSIONS.md](docs/EXTENSIONS.md) |
| **All settings** | `~/.jarvis/settings.json` or `.jarvis/settings.json` |

### Don't Touch (Internal Invariants)

| File(s) | Why |
|---------|-----|
| `jarvis/core/agents/base.py` | Agent loop — streaming, tool dispatch, approval |
| `jarvis/core/tools/base.py` | `ToolInput`/`ToolOutput` — all tools inherit these |
| `jarvis/core/tools/registry.py` | Tool discovery — changing breaks every tool |
| `jarvis/core/llm/base.py` + `sdk_adapter.py` | All LLM communication goes through these |
| `jarvis/core/history.py` | Message store — all consumers depend on its format |
| `jarvis/core/web/server.py` | API routes — changing endpoints breaks all frontends |
| `jarvis/core/config/models.py` | Settings schema — existing configs will fail to load |
| `jarvis/api.py` | Public extension surface — changing breaks all extensions |

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the full breakdown.

---

## 💻 Development

See [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md) for the full development guide.

```bash
# Run all tests
pytest tests/ -v

# Lint & format
ruff check jarvis/
ruff format jarvis/
```

---

## 🤝 Contributing

Contributions are welcome! See [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md) for the full guide.

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## 📄 License

MIT License - see [LICENSE](LICENSE) for details.

---

## 🔗 Links

- **Repository**: https://github.com/OEvortex/JARVIS
- **Issues**: https://github.com/OEvortex/JARVIS/issues
- **Authors**: [OEvortex](https://github.com/OEvortex) and [AnonymousCoderLokesh](https://github.com/AnonymousCoderArtist)

---

<div align="center">
<sub>Built with ❤️ for developers who want a truly agentic AI assistant</sub>
</div>
