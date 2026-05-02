## Project Overview

JARVIS v2.0 is a **Personal AI Assistant (PI)** - a next-generation agentic harness inspired by Claude Code and mistral-vibe. It provides unified agentic assistance for coding, research, documentation, and knowledge work.

## Development Commands

### Installation & Setup

```bash
# Install dependencies
pip install -e .

# Or with uv
uv pip install -e .
```

### Running JARVIS

```bash
# Launch CLI
python main.py --cli

# Or directly
jarvis --cli --model gpt-4o

# Launch TUI (Textual-based)
python main.py --tui
```

### Testing

```bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_async_agents.py -v

# Run single test
pytest tests/test_async_agents.py::test_function_name -v
```

### Type Checking

```bash
# Run ty type checker
ty check .
```

### Build & Version

```bash
# Version is managed via jarvis/_version.py
# Current version: 2.0.1
```

## Architecture Overview

```
JARVIS/
├── main.py                    # Entry point
├── jarvis/
│   ├── cli.py                 # CLI launcher with arg parsing
│   └── _version.py            # Version management
├── core/
│   ├── agents/
│   │   ├── base.py            # BaseAgent abstract class
│   │   ├── coding_agent.py    # JARVIS agent implementation
│   │   ├── explore_agent.py   # Explore subagent
│   │   └── system_prompts.py  # System prompt definitions
│   ├── config/
│   │   ├── settings.py        # Configuration management
│   │   └── models.py          # Pydantic settings models
│   ├── tools/
│   │   ├── registry.py        # ToolRegistry for tool management
│   │   ├── permissions.py     # Permission system
│   │   └── agent_tools.py     # Agent invocation tools
│   ├── llm/                   # LLM provider abstraction
│   ├── llm_sdk/               # SDK adapters
│   └── mcp/                   # MCP integration
├── interface/
│   ├── cli/                   # CLI interface
│   └── textual_ui/            # TUI interface
├── tests/                     # Test files
└── pyproject.toml             # Project configuration
```

## Key Components

### BaseAgent (`core/agents/base.py`)

Abstract base class for all agents. Key methods:
- `process(input, context)` - Main agent processing
- `_process_with_tools(messages)` - Tool calling loop
- `_build_messages(user_content)` - Build message list with roles
- `rebuild_system_prompt()` - Update system prompt with tool descriptions

### CodingAgent (`core/agents/coding_agent.py`)

The main JARVIS agent for coding, research, and documentation tasks.

### ExploreAgent (`core/agents/explore_agent.py`)

Specialized subagent for codebase exploration and analysis.

### ToolRegistry (`core/tools/registry.py`)

Central tool management. Access via `tool_registry.get_tools()` or `tool_registry.execute_tool(name, args)`.

### Settings (`core/config/settings.py`)

Configuration management with properties for:
- `bypass_tool_permissions` - Skip permission checks
- `tools` - Tool configuration including allowlist/denylist
- `max_memory_entries` - Memory limits

## Agent Profiles

Five safety levels controlled via TUI (Shift+Tab to cycle):

| Profile | Safety Level | Description |
|---------|-------------|-------------|
| Default | NEUTRAL | Requires approval for tool executions |
| Plan | SAFE | Read-only (explore mode) |
| Accept Edits | DESTRUCTIVE | Auto-approves file edits |
| Auto Approve | YOLO | Auto-approves all tools |
| Explore | SAFE | Read-only subagent mode |

## Permission System

Granular permissions based on file paths:
- **Scratchpad**: `.jarvis/scratchpad` and `/tmp/scratchpad` always allowed
- **Denylist**: Patterns like `~/.ssh/*`, `*.key` never allowed
- **Allowlist**: Patterns like `*.py`, `*.md` always allowed
- **Sensitive patterns**: Files matching `*secret*`, `*.env` require approval
- **Workdir boundary**: Files outside working directory require approval

## Environment Configuration

CLI flags take precedence over `.env` file:

```bash
# .env file
JARVIS_MODEL=gpt-4o
JARVIS_BASE_URL=https://api.openai.com/v1
JARVIS_API_KEY=your_key
JARVIS_SDK=openai
```

CLI flags:
- `--model, -m`: Model name (default: gpt-4o)
- `--base_url`: API endpoint
- `--apikey`: API key
- `--sdk`: SDK mode (openai/anthropic)
- `--cli`: Launch CLI
- `--tui`: Launch TUI

## Common Patterns

### Adding a New Tool

1. Create tool in `core/tools/` directory
2. Register in `ToolRegistry`
3. Update `config.toml` if needed for permissions

### Running Tests

```bash
# Test async agent functionality
pytest tests/test_async_agents.py -v

# Test permissions
pytest tests/test_permissions.py -v

# Test file reading
pytest tests/test_read_many_files.py -v
```

### Debugging

```bash
# Run with debug output
python main.py --cli --model gpt-4o

# Check type errors
ty check .
```
## Rules for Agents
- use rg instead of grep for file searching
- use ty for type checking instead of mypy