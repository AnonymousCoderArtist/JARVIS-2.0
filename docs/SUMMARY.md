# JARVIS Documentation

> **AI agents**: Read SUMMARY.md first to find the right doc for your task. Each doc has an explicit "AI Agent" section.

## Quick Links

| Doc | For |
|-----|-----|
| [ARCHITECTURE.md](ARCHITECTURE.md) | Understanding the full system — agents, tools, LLM layer, frontends |
| [SETUP.md](SETUP.md) | Installing, configuring, and running JARVIS |
| [API.md](API.md) | Building on top of JARVIS — REST + WebSocket API reference |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Developing JARVIS itself — code style, tests, PRs |
| [custom-agents.md](custom-agents.md) | Creating custom agent profiles |
| [custom-tools.md](custom-tools.md) | Writing new tools for JARVIS |
| [MCP.md](MCP.md) | Connecting MCP (Model Context Protocol) servers |
| [HOOKS.md](HOOKS.md) | Event system (24 event types) and lifecycle hooks (16 stages) |
| [EXTENSIONS.md](EXTENSIONS.md) | Extension/plugin system — custom tools, hooks, commands, shortcuts |
| [SANDBOX.md](SANDBOX.md) | Sandboxed command execution with bubblewrap |
| [watchers.md](watchers.md) | Passive file/event watchers |
| [webui-theme.md](webui-theme.md) | Customizing the WebUI look and feel |

## For AI Agents

When an AI agent is asked to work on JARVIS:

1. **Read SUMMARY.md** (this file) to understand what's available
2. **Read ARCHITECTURE.md** to understand which subsystem your task involves
3. **Read the specific doc** for your task (e.g., custom-tools.md for adding a tool)
4. **Read the relevant source files** guided by the doc's "Key Files" section

### Conventions

- **Python**: Python 3.10+, uses `ruff` for linting, `pytest` for tests
- **TypeScript**: React 18, Vite, Tailwind CSS, shadcn/ui components
- **Config**: JSON files in `~/.jarvis/` and `.jarvis/` (project-local)
- **Colors**: All WebUI colors are CSS variables in `globals.css` — never hardcode
