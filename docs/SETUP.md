# JARVIS v2.0 Setup Guide

A comprehensive guide to installing, configuring, and running JARVIS — your personal AI assistant.

---

## Table of Contents

- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Installation Methods](#installation-methods)
  - [From Source](#from-source)
  - [pip Install](#pip-install)
- [Configuration](#configuration)
  - [Settings File Locations](#settings-file-locations)
  - [Environment Variables](#environment-variables)
  - [Provider Configuration](#provider-configuration)
- [Running JARVIS](#running-jarvis)
  - [CLI Mode](#cli-mode)
  - [TUI Mode (Default)](#tui-mode-default)
  - [Web UI Mode](#web-ui-mode)
  - [Web UI Dev Mode](#web-ui-dev-mode)
- [Configuration Reference](#configuration-reference)
  - [Full settings.json Reference](#full-settingsjson-reference)
  - [Model Settings](#model-settings)
  - [Agent Settings](#agent-settings)
  - [Tool Settings](#tool-settings)
  - [Heartbeat Settings](#heartbeat-settings)
  - [Learning System](#learning-system)
  - [Sandbox Settings](#sandbox-settings)
- [Troubleshooting](#troubleshooting)

---

## Prerequisites

| Dependency            | Minimum Version | Recommended |
|-----------------------|-----------------|-------------|
| Python                | 3.10            | 3.11+       |
| Node.js               | 18              | 20+         |
| npm or bun            | 8+              | 10+         |
| Git                   | 2.30            | latest      |
| API Key (OpenAI/Anthropic) | —          | —           |

**Required API Key**: You need an API key from at least one LLM provider:
- [OpenAI API Keys](https://platform.openai.com/api-keys)
- [Anthropic Console](https://console.anthropic.com/)

---

## Quick Start

```bash
# 1. Clone the repository
git clone https://github.com/OEvortex/JARVIS.git
cd JARVIS

# 2. Create and activate a virtual environment
python3.11 -m venv .venv
source .venv/bin/activate   # Linux/macOS
# .venv\Scripts\activate    # Windows

# 3. Install Python dependencies
pip install -e .

# 4. Set up your API key
echo 'JARVIS_API_KEY=sk-...' >> .env
echo 'JARVIS_MODEL=gpt-4o' >> .env

# 5. Launch JARVIS (TUI mode is the default)
jarvis
```

That's it. JARVIS will start in TUI mode and prompt you for input.

---

## Installation Methods

### From Source

#### 1. Clone the Repository

```bash
git clone https://github.com/OEvortex/JARVIS.git
cd JARVIS
```

#### 2. Set Up Python Virtual Environment

Using `uv` (fast, recommended):

```bash
uv venv
source .venv/bin/activate
uv pip install -e .
```

Using `pip`:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

> **Note**: On Windows, activate with `.venv\Scripts\activate`.

#### 3. Install Web UI Dependencies (optional — only needed for `--webui`)

```bash
cd interface/webui
npm install
# or with bun:
bun install
cd ../..
```

#### 4. Configure Your API Key

```bash
cp .env.example .env
```

Then edit `.env` and set your API key:

```env
JARVIS_API_KEY=sk-your-key-here
JARVIS_MODEL=gpt-4o
JARVIS_SDK=openai
```

#### 5. Verify Installation

```bash
jarvis --help
```

You should see the help output with all available CLI flags.

### pip Install

If JARVIS is published to PyPI:

```bash
pip install jarvis-ai
```

> **Note**: At this time, installing from source is recommended for the latest features. PyPI availability may vary.

---

## Configuration

### Settings File Locations

JARVIS loads configuration from multiple sources with the following precedence (lowest to highest):

| Priority | Location                  | Description                       |
|----------|---------------------------|-----------------------------------|
| 1        | `~/.jarvis/settings.json` | Global defaults (user-wide)       |
| 2        | `.jarvis/settings.json`   | Per-project overrides             |
| 3        | `.env` file               | Environment variable overrides    |
| 4        | CLI flags                 | Command-line arguments (highest)  |

**Global settings** (`~/.jarvis/settings.json`):

```json
{
  "app": {
    "name": "JARVIS",
    "version": "2.0.0",
    "debug": false,
    "installed_agents": []
  },
  "provider": {
    "selected_provider_id": "openai",
    "config_file": "providers.json"
  },
  "tools": {
    "enable_code_execution": true,
    "enable_file_operations": true,
    "enable_git_operations": true
  },
  "async": {
    "max_concurrent_agents": 5,
    "max_concurrent_tools": 10,
    "default_timeout": 1800,
    "enable_background_tasks": true,
    "resource_monitoring": true,
    "progress_updates": true
  },
  "heartbeat": {
    "enabled": false,
    "every": "30m",
    "target": "last",
    "skip_when_busy": false,
    "show_ok": true
  },
  "learning": {
    "enabled": false,
    "skill_creation_threshold": 5,
    "self_evaluation_interval": 15,
    "memory_dir": "~/.jarvis/memory",
    "skills_dir": "~/.jarvis/skills"
  },
  "sandbox": {
    "enabled": false,
    "backend": "bwrap",
    "timeout": 30
  }
}
```

Create the directory and file:

```bash
mkdir -p ~/.jarvis
touch ~/.jarvis/settings.json
# Then edit with your preferred JSON content
```

**Project-specific settings** — place a `.jarvis/settings.json` in your project root to override global defaults for that project:

```bash
mkdir -p .jarvis
```

### Environment Variables

JARVIS reads the following environment variables. Create a `.env` file in the project root:

```bash
cp .env.example .env
```

#### Required

| Variable           | Description                          | Example                           |
|--------------------|--------------------------------------|-----------------------------------|
| `JARVIS_API_KEY`   | API key for your LLM provider        | `sk-proj-...` or `sk-ant-...`     |
| `JARVIS_MODEL`     | Model name to use                    | `gpt-4o` or `claude-3-5-sonnet-20241022` |

#### Optional

| Variable                       | Default              | Description                              |
|--------------------------------|----------------------|------------------------------------------|
| `JARVIS_BASE_URL`              | `https://api.openai.com/v1` | Custom API base URL (for local LLMs) |
| `JARVIS_SDK`                   | `openai`             | SDK mode: `openai` or `anthropic`        |
| `OPENAI_API_KEY`               | —                    | Alternative OpenAI key variable           |
| `ANTHROPIC_API_KEY`            | —                    | Alternative Anthropic key variable        |
| `JARVIS_HEARTBEAT_ENABLED`     | `false`              | Enable periodic heartbeat checks         |
| `JARVIS_HEARTBEAT_EVERY`       | `30m`                | Heartbeat interval (`1m`, `15m`, `30m`, `1h`) |
| `JARVIS_HEARTBEAT_TARGET`      | `last`               | Target channel for heartbeat output       |
| `JARVIS_HEARTBEAT_SKIP_WHEN_BUSY` | `true`           | Skip heartbeat when agent is busy        |
| `JARVIS_HEARTBEAT_SHOW_OK`     | `true`               | Show HEARTBEAT_OK messages               |
| `JARVIS_MAX_CONTEXT_TOKENS`    | `131072` (128K)      | Maximum total context tokens              |
| `JARVIS_MAX_INPUT_TOKENS`      | `111616` (109K)      | Maximum input tokens                      |
| `JARVIS_MAX_OUTPUT_TOKENS`     | `16384` (16K)        | Maximum output tokens                     |
| `JARVIS_REMOTE_URL`            | —                    | Connect to a remote JARVIS instance       |

#### Example .env

```env
# LLM Provider
JARVIS_MODEL=gpt-4o
JARVIS_BASE_URL=https://api.openai.com/v1
JARVIS_API_KEY=sk-your-key-here
JARVIS_SDK=openai

# Heartbeat (optional)
JARVIS_HEARTBEAT_ENABLED=false
JARVIS_HEARTBEAT_EVERY=30m

# Token Limits (optional)
JARVIS_MAX_CONTEXT_TOKENS=131072
```

### Provider Configuration

JARVS uses a `providers.json` file at the project root for additional LLM provider definitions:

```json
{
  "openai": {
    "api_key_env": "OPENAI_API_KEY",
    "base_url": "https://api.openai.com/v1",
    "models": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo"]
  },
  "anthropic": {
    "api_key_env": "ANTHROPIC_API_KEY",
    "base_url": "https://api.anthropic.com",
    "models": ["claude-3-5-sonnet-20241022", "claude-3-opus-20240229"]
  },
  "custom": {
    "api_key": "",
    "base_url": "http://localhost:8000/v1",
    "models": ["local-model"]
  }
}
```

You can switch providers at runtime using the SDK flag:

```bash
jarvis --sdk anthropic --model claude-3-5-sonnet-20241022 --apikey sk-ant-...
```

---

## Running JARVIS

### CLI Mode

CLI mode provides a text-based interactive prompt in your terminal:

```bash
# Using .env configuration
jarvis --cli

# With explicit arguments
jarvis --cli --model gpt-4o --apikey sk-... --sdk openai

# With short flags
jarvis --cli -m claude-3-5-sonnet-20241022 --apikey sk-ant-...

# Via main.py
python main.py --cli
```

CLI mode automatically enables bypass mode for smooth tool execution.

### TUI Mode (Default)

The TUI (Textual User Interface) is the default mode. It provides a rich terminal UI with syntax highlighting, tool output rendering, and session management:

```bash
# Launch default (TUI)
jarvis

# Explicitly launch TUI
jarvis --tui

# With custom model
jarvis --tui --model claude-3-5-sonnet-20241022 --apikey sk-ant-...

# With bypass mode (yolo)
jarvis --tui --bypass

# Resume last session
jarvis --tui --resume

# Resume a specific session
jarvis --tui --resume session-name-here

# List available sessions
jarvis --resume list
```

### Web UI Mode

The Web UI provides a full browser-based interface with a FastAPI backend and React/Vite frontend:

```bash
# Launch Web UI (defaults: http://127.0.0.1:5173)
jarvis --webui

# With custom ports
jarvis --webui --port 8080 --backend-port 8765

# Expose to network (other devices can connect)
jarvis --webui --host 0.0.0.0 --port 5173

# Direct module launch
python -m interface.webui.webui_main
```

> **Note for Web UI**: The first time you run `jarvis --webui`, make sure you've run `npm install` in `interface/webui/` (see [Web UI Dev Mode](#web-ui-dev-mode)).

**Web UI will automatically:**
1. Start the FastAPI backend server (default port: 8765)
2. Start the Vite dev server (default port: 5173)
3. Open your browser to the frontend
4. Handle graceful shutdown on Ctrl+C

### Web UI Dev Mode

For development on the Web UI frontend:

```bash
# Terminal 1: Start the backend server
cd interface/webui
python -m uvicorn core.web.server:app --host 127.0.0.1 --port 8765 --reload

# Terminal 2: Start the Vite dev server
cd interface/webui
npm run dev
# or
bun dev

# Run tests
cd interface/webui
npm run test
npm run test:watch   # watch mode

# Build for production
npm run build

# Lint
npm run lint
```

The Vite dev server proxies `/api`, `/jarvis`, and `/jarvis/ws` requests to the backend automatically (configured in `vite.config.ts`).

---

## Configuration Reference

### Full settings.json Reference

Below is the complete structure of `~/.jarvis/settings.json` with all available fields:

```jsonc
{
  // ── Application ──────────────────────────────────────────────
  "app": {
    "name": "JARVIS",
    "version": "2.0.0",
    "debug": false,
    "installed_agents": []   // List of installed custom agent paths
  },

  // ── Provider ─────────────────────────────────────────────────
  "provider": {
    "selected_provider_id": "openai",  // Active provider ID
    "config_file": "providers.json"    // Provider definitions file
  },

  // ── Tools ────────────────────────────────────────────────────
  "tools": {
    "enable_code_execution": true,
    "enable_file_operations": true,
    "enable_git_operations": true,

    // Per-tool permission overrides
    "read":    { "permission": "always" },
    "ls":      { "permission": "always" },
    "find":    { "permission": "always" },
    "list_dir": { "permission": "always" },
    "glob":    { "permission": "always" },
    "grep":    { "permission": "always" },
    "read_memory": { "permission": "always" },
    "write":   { "permission": "ask" },
    "edit":    { "permission": "ask" },
    "bash":    { "permission": "ask" },
    "run_tests": { "permission": "ask" },
    "repl":    { "permission": "ask" },
    "save_memory": { "permission": "ask" },
    "fetch_webpage": { "permission": "ask" },
    "agents":  { "permission": "ask" },
    "activate_skill": { "permission": "ask" },

    // Path-based security rules
    "allowlist": [
      "*.md", "*.txt", "*.py", "*.js", "*.ts",
      "*.json", "*.yaml", "*.yml", "*.toml", "*.cfg", "*.ini"
    ],
    "denylist": [
      "/etc/passwd", "/etc/shadow", "/etc/hosts",
      "~/.ssh/*", "~/.aws/*", "~/.kube/*",
      "*.key", "*.pem", "*.p12", "*.pfx"
    ],
    "sensitive_patterns": [
      "*secret*", "*password*", "*credential*", "*token*",
      "*api_key*", "*private_key*", "*.env", "*.env.*",
      "config/production*", "config/prod*"
    ]
  },

  // ── Async / Concurrent Settings ──────────────────────────────
  "async": {
    "max_concurrent_agents": 5,
    "max_concurrent_tools": 10,
    "default_timeout": 1800,
    "enable_background_tasks": true,
    "resource_monitoring": true,
    "progress_updates": true
  },

  // ── Heartbeat ────────────────────────────────────────────────
  "heartbeat": {
    "enabled": false,
    "every": "30m",
    "target": "last",
    "light_context": false,
    "isolated_session": false,
    "skip_when_busy": false,
    "prompt": "Read HEARTBEAT.md if exists. Follow strictly. If nothing needs attention, reply HEARTBEAT_OK.",
    "ack_max_chars": 300,
    "show_ok": true,
    "show_alerts": true,
    "use_indicator": true,
    "active_hours": {
      "start": "08:00",
      "end": "22:00",
      "timezone": "America/New_York"
    }
  },

  // ── Learning System ──────────────────────────────────────────
  "learning": {
    "enabled": false,
    "skill_creation_threshold": 5,
    "self_evaluation_interval": 15,
    "memory_dir": "~/.jarvis/memory",
    "skills_dir": "~/.jarvis/skills"
  },

  // ── Sandbox ──────────────────────────────────────────────────
  "sandbox": {
    "enabled": false,
    "backend": "bwrap",
    "base_url": "http://localhost:8080",
    "timeout": 30,
    "runtime": "opensandbox/code-interpreter:v1.0.2"
  },

  // ── Global Flags ─────────────────────────────────────────────
  "bypass_tool_permissions": false,
  "disallowed_tools": [],
  "agent_paths": [],
  "enabled_agents": [],
  "disabled_agents": [],
  "vibe_code_enabled": false
}
```

### Model Settings

Configure the LLM model via CLI flags:

| Flag          | Description                                      | Example                                   |
|---------------|--------------------------------------------------|-------------------------------------------|
| `--model`     | Model name to use                                | `gpt-4o`, `claude-3-5-sonnet-20241022`   |
| `--sdk`       | SDK provider (`openai` or `anthropic`)           | `openai` or `anthropic`                   |
| `--base_url`  | Custom API base URL (for local/proxy LLMs)       | `http://localhost:8000/v1`                |
| `--apikey`    | API key for the provider                         | `sk-...` or `sk-ant-...`                  |

Example — using a local LLM:

```bash
jarvis --model llama-3-70b --base_url http://localhost:8000/v1 --apikey dummy --sdk openai
```

### Agent Settings

Agent profiles determine JARVIS's behavior and autonomy level.

**Safety Profiles (5 levels)**:

| Level | Name         | Code Execution | File Ops | Dangerous Ops |
|-------|--------------|----------------|----------|---------------|
| L1    | Lockdown     | never          | ask      | ask           |
| L2    | Restricted   | ask            | ask      | ask           |
| L3    | Balanced     | ask            | always   | ask           |
| L4    | Permissive   | always         | always   | ask           |
| L5    | Unrestricted | always         | always   | always        |

Cycle through profiles in the WebUI with **Shift+Tab**.

**Bypass all permissions**:

```bash
jarvis --bypass
# or
jarvis --yolo
```

### Tool Settings

Configure individual tool permissions in `settings.json`:

```json
{
  "tools": {
    "read": { "permission": "always" },
    "write": { "permission": "ask" },
    "edit": { "permission": "ask" },
    "bash": { "permission": "ask" },
    "run_tests": { "permission": "ask" },
    "repl": { "permission": "ask" }
  }
}
```

**Permission levels**:
- `always` — Tool executes without asking
- `never` — Tool is permanently disabled
- `ask` — Tool requires user approval (default for sensitive tools)

**Path-based rules** in `settings.json`:
- `allowlist` — File patterns that are always allowed
- `denylist` — File patterns that are always blocked
- `sensitive_patterns` — Patterns requiring special approval

### Heartbeat Settings

JARVIS includes a nanobot-style two-phase heartbeat for periodic agent awareness. Create a `.jarvis/HEARTBEAT.md` in your project to define tasks:

```markdown
# Heartbeat Tasks

## Active
- [ ] Review open PRs
- [ ] Check build status

## Completed
- [x] Update dependencies
```

**Phase 1 (Decision)**: LLM decides via virtual tool call whether to skip or run.
**Phase 2 (Execution)**: Only triggered when Phase 1 returns "run".

Configure via environment variables:

```env
JARVIS_HEARTBEAT_ENABLED=true
JARVIS_HEARTBEAT_EVERY=30m
JARVIS_HEARTBEAT_SKIP_WHEN_BUSY=true
JARVIS_HEARTBEAT_SHOW_OK=false
```

Or in `settings.json`:

```json
{
  "heartbeat": {
    "enabled": true,
    "every": "30m",
    "target": "last",
    "skip_when_busy": true,
    "show_ok": false,
    "active_hours": {
      "start": "09:00",
      "end": "18:00",
      "timezone": "America/New_York"
    }
  }
}
```

### MCP Servers

JARVIS supports connecting to external MCP servers for extended capabilities. Create a `.mcp.json` file in your project root (or `~/.jarvis/mcp_servers.json`):

```json
{
  "mcpServers": {
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/path/to/allowed"],
      "transport": "stdio"
    },
    "github": {
      "command": "python",
      "args": ["-m", "mcp.server.github"],
      "transport": "stdio",
      "env": { "GITHUB_TOKEN": "your_token_here" }
    },
    "http-server": {
      "url": "http://localhost:3000/mcp",
      "transport": "http"
    }
  }
}
```

**Transport types**:
- `stdio` — Local subprocess-based MCP servers
- `http` — Remote MCP servers via HTTP/S

---

## Troubleshooting

### "Command not found: jarvis"

```bash
# Make sure your virtual environment is activated
source .venv/bin/activate

# Verify installation
pip list | grep jarvis

# Run directly via Python
python main.py
```

### "No API key provided"

```bash
# Set the key in .env
echo 'JARVIS_API_KEY=sk-your-key' >> .env

# Or pass it as a flag
jarvis --apikey sk-your-key

# Or set the environment variable
export JARVIS_API_KEY=sk-your-key
```

### Web UI: "node_modules not found"

```bash
cd interface/webui
npm install
cd ../..
```

### Web UI: "npm is not available"

Install Node.js and npm:

```bash
# Ubuntu/Debian
sudo apt install nodejs npm

# macOS (Homebrew)
brew install node

# Or download from https://nodejs.org/
```

### Web UI: Backend fails to start

```bash
# Check if port 8765 is available
lsof -i :8765

# Kill any process using it
kill $(lsof -t -i:8765)

# Start backend manually
python -m uvicorn core.web.server:app --host 127.0.0.1 --port 8765
```

### Port already in use

```bash
# WebUI frontend default: 5173
# WebUI backend default: 8765

# Use different ports
jarvis --webui --port 8080 --backend-port 8766
```

### "ModuleNotFoundError" on startup

```bash
# Ensure all dependencies are installed
pip install -e .

# If using development extras
pip install -e ".[dev]"
```

### TUI rendering issues

```bash
# Make sure your terminal supports 24-bit color
# Try a different terminal emulator (kitty, alacritty, ghostty, foot, etc.)

# Set TERM environment variable
export TERM=xterm-256color
```

### SSL / Certificate errors

```bash
# For custom/local API endpoints
jarvis --base_url http://localhost:8000/v1 --apikey dummy

# Or set the environment variable
export JARVIS_BASE_URL=http://localhost:8000/v1
```

### uv: command not found

```bash
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Or use pip instead
pip install -e .
```

### Getting help

```bash
# Show all available CLI flags
jarvis --help

# Check version
jarvis --version

# Or open an issue at:
# https://github.com/OEvortex/JARVIS/issues
```

---

## What You Can (Safely) Change

These are the parts of JARVIS designed for user customization:

| What | How | File / Command |
|------|-----|----------------|
| **LLM model & provider** | Edit or create a provider config | `providers.json` |
| **Agent personality** | Switch profile or write a custom agent | `settings.json` → `agent.profile` or `~/.jarvis/agents/` |
| **Safety level** | Restrict what the agent can do | `settings.json` → `agent.safety_profile` |
| **WebUI colors** | Change CSS variable values | `interface/webui/src/globals.css` `:root` |
| **System prompt** | Edit the agent's instructions | `core/agents/prompts/` |
| **Tools enabled** | Allow/deny/ask per tool | `settings.json` → `permissions` |
| **MCP servers** | Connect external tools | `.mcp.json` or `jarvis --mcp-add` |
| **Custom tools** | Write your own tool | See [custom-tools.md](custom-tools.md) |
| **Custom agents** | Define new agent types | See [custom-agents.md](custom-agents.md) |
| **Config values** | All runtime settings | `~/.jarvis/settings.json` or `.jarvis/settings.json` |
| **Sandbox settings** | Toggle sandbox on/off | `settings.json` → `sandbox.enabled` |

## What You Should NOT Touch

These are **internal invariants**. Changing them will break things subtly or catastrophically:

| File(s) | Why Leave It Alone |
|---------|-------------------|
| `core/agents/base.py` | Core agent loop — streaming, tool dispatch, approval flow |
| `core/tools/base.py` | `ToolInput` / `ToolOutput` base models — all tools inherit these |
| `core/tools/registry.py` | Tool discovery and registration — changing breaks every tool |
| `core/llm/base.py` | LLM provider contract — changing breaks all integrations |
| `core/llm/sdk_adapter.py` | All provider SDKs go through this adapter |
| `core/history.py` | Message store — all consumers depend on its format |
| `core/web/server.py` | API routing — changing endpoints breaks all frontends |
| `core/config/models.py` | Settings schema — existing config files will fail to load |
| `interface/webui/src/globals.css` `:root` variable *names* | OK to change *values* but renaming breaks all 30+ components |
| `interface/webui/src/lib/jarvis-client.ts` WebSocket message format | Must stay in sync with `core/web/server.py` |
| `interface/webui/src/hooks/useJarvisStream.ts` return shape | All consuming components depend on this |

**Rule of thumb:** If a file is imported by 5+ other files across different directories, assume changing its public interface will have cascading effects. If you must change it, update all callers in the same commit.
