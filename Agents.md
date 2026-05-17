Behavioral guidelines to reduce common LLM coding mistakes. Merge with project-specific instructions as needed.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.



## Project Overview

JARVIS v2.0 is a **Personal AI Assistant (PI)** - a next-generation agentic harness inspired by Claude Code and mistral-vibe. It provides unified agentic assistance for coding, research, documentation, and knowledge work.

## Development Commands

### Installation & Setup

```bash
# Install dependencies
uv pip install -e .
```

### Running JARVIS

```bash
# Launch TUI (default)
python main.py

# Or directly (TUI is default)
jarvis --model gpt-4o

# Launch CLI explicitly
python main.py --cli
jarvis --cli --model gpt-4o

# Launch TUI explicitly
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
# Current version: 2.1.0
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
│   │   ├── jarvis_v2.py       # JARVIS agent implementation (renamed from coding_agent.py)
│   │   ├── explore_agent.py   # Explore subagent
│   │   └── system_prompts.py  # System prompt manager
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

### JarvisV2 (`core/agents/jarvis_v2.py`)

The main JARVIS agent for coding, research, and documentation tasks. (JarvisV2 class, with CodingAgent as an alias for backwards compatibility.)

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

## Available Agents

Agents that can be invoked via the `agents` tool:

- **explore**: For codebase exploration and analysis (read-only, understands structure, finds files/patterns)
- **plan**: For task decomposition and planning (read-only, creates structured plans with phases and steps)

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

# Heartbeat Configuration (optional)
JARVIS_HEARTBEAT_ENABLED=true       # Enable periodic heartbeat checks
JARVIS_HEARTBEAT_EVERY=30m          # Interval (e.g., 15m, 1h)
JARVIS_HEARTBEAT_TARGET=last        # Target channel
JARVIS_HEARTBEAT_SKIP_WHEN_BUSY=true # Skip when agent is busy
JARVIS_HEARTBEAT_SHOW_OK=false      # Show HEARTBEAT_OK messages
```

CLI flags:
- `--model, -m`: Model name (default: gpt-4o)
- `--base_url`: API endpoint
- `--apikey`: API key
- `--sdk`: SDK mode (openai/anthropic)
- `--cli`: Launch CLI
- `--tui`: Launch TUI

## Heartbeat System (Nanobot-style)

JARVIS includes a nanobot-style two-phase heartbeat system for periodic agent awareness:

### How it Works

1. **Phase 1 (Decision)**: LLM decides via virtual tool call whether to skip or run
2. **Phase 2 (Execution)**: Only triggered when Phase 1 returns "run"
3. **Response Filtering**: Non-deliverable responses are automatically suppressed

### Configuration

```bash
# .env file
JARVIS_HEARTBEAT_ENABLED=true
JARVIS_HEARTBEAT_EVERY=30m
JARVIS_HEARTBEAT_TARGET=last
JARVIS_HEARTBEAT_SKIP_WHEN_BUSY=true
JARVIS_HEARTBEAT_SHOW_OK=false
```

### HEARTBEAT.md File

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

### Agent Integration

The heartbeat scheduler integrates with the agent:
- Checks for `.jarvis/HEARTBEAT.md` at configured intervals
- Uses `initialize_heartbeat(notifier, evaluator)` for TUI notifications
- Results appear in TUI with 🫀 emoji prefix
- `is_deliverable()` filters out leaked reasoning and implementation artifacts

---

## Common Patterns

### Adding a New Tool

1. Create tool in `core/tools/` directory
2. Register in `ToolRegistry`
3. Update `.jarvis/settings.json` if needed for permissions

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
# Run with debug output (TUI)
python main.py --tui --model gpt-4o

# Run with debug output (CLI)
python main.py --cli --model gpt-4o

# Check type errors
ty check .
```

## Rules for Agents
- use rg (rip grep) instead of grep for file searching
- use ty for type checking instead of mypy
- use Ruff for linting instead of flake8
- use pytest for testing instead of unittest
- use Pydantic for configuration management instead of custom solutions
- Use modern python syntax