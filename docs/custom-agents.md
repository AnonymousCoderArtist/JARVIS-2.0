# Custom Agents

JARVIS supports loading custom agents from `.jarvis/agents/`. This allows you to create specialized agents with custom system prompts, tool whitelists, and lifecycle controls — then invoke them via the `agents` tool or switch between them in the TUI.

## How It Works

Custom agents are Python files in `~/.jarvis/agents/` (global) or `.jarvis/agents/` (project-level). Each file defines an `AgentDefinition` that the system discovers at startup.

There are two kinds of agents, controlled by the `agent_type` field:

| Kind | Profiles (Shift+Tab) | `agents` tool | Use Case |
|------|----------------------|---------------|----------|
| `AGENT` (default) | Yes | Yes | Full agents the user switches between |
| `SUBAGENT` | No | Yes | Specialized workers only the LLM invokes |

## Quick Start

Create `.jarvis/agents/my-reviewer.py`:

```python
from core.agents.agent_definition import AgentDefinition
from core.agents.profiles import AgentType

def get_system_prompt() -> str:
    return """You are a code reviewer. Focus on:
- Security vulnerabilities (OWASP Top 10)
- Logic bugs and edge cases
- Performance issues
- Code style and conventions
"""

MY_REVIEWER = AgentDefinition(
    name="code-review",
    agent_type=AgentType.AGENT,     # appears in profiles + agents tool
    when_to_use="Review code for bugs, security issues, and style problems",
    tools=["read", "grep", "find", "ls"],
    model="inherit",
    max_turns=50,
    get_system_prompt=get_system_prompt,
)
```

Restart JARVIS. The agent appears in:
- **Shift+Tab cycling** (because `agent_type=AgentType.AGENT`)
- **`agents` tool** — the LLM can delegate to it by name `"code-review"`

## All Fields

| Field | Required | Default | Description |
|-------|----------|---------|-------------|
| `name` | Yes | — | Unique identifier (used to invoke via `agents` tool) |
| `when_to_use` | Yes | — | Description shown to the LLM when deciding whether to delegate |
| `agent_type` | No | `AgentType.AGENT` | `AGENT` (profile + tool) or `SUBAGENT` (tool only) |
| `tools` | No | `None` | Tool access control — see below |
| `model` | No | `"inherit"` | Model name or `"inherit"` to use parent's model |
| `max_turns` | No | `100` | Maximum tool-calling turns before forced stop |
| `get_system_prompt` | No | `None` | Callable returning a system prompt string |
| `source` | No | `"built-in"` | Set automatically by the loader |
| `base_dir` | No | `"built-in"` | Set automatically by the loader |

## Tool Access Control (`tools` field)

The `tools` field controls which tools the agent can see and call:

| Value | Behavior |
|-------|----------|
| `None` (default) | **Inherit all tools** from the parent agent that spawned it. No filtering. |
| `["*"]` | **Explicitly allow all tools**. Same effect as `None` but makes the intent clear. |
| `["read", "grep", "find"]` | **Restrict to only these tools**. Everything else is blocked. The LLM won't even see other tools exist. |

When `tools` is set to a specific list, a `_FilteredToolRegistry` wraps the real tool registry and returns `None` / error for any tool not in the list. This is enforced at two levels:

1. **Tool listing** — `get_tools()` and `get_function_definitions()` only return allowed tools, so the LLM never sees blocked ones
2. **Tool execution** — `execute_tool()` returns an error for disallowed tools

```python
# Read-only researcher — can't touch files or run commands
AgentDefinition(
    name="read-only-researcher",
    tools=["read", "grep", "find", "ls", "web_search", "fetch_webpage"],
    ...
)
```

```python
# Full implementation agent — everything allowed
AgentDefinition(
    name="implementer",
    tools=["*"],
    ...
)
```

## Agent vs Subagent

### AGENT (default)
Appears in the TUI profile selector (Shift+Tab to cycle). The user can switch to it manually. Also available via the `agents` tool for LLM-driven delegation.

```python
from core.agents.profiles import AgentType

AgentDefinition(
    name="my-agent",
    agent_type=AgentType.AGENT, # appears in profiles + agents tool
    ...
)
```

### SUBAGENT
Hidden from the profile selector. Only invocable via the `agents` tool. Best for specialized workers the LLM calls internally — the user doesn't need to know they exist.

```python
AgentDefinition(
    name="data-analyzer",
    agent_type=AgentType.SUBAGENT,  # profiles hidden, agents tool only
    ...
)
```

## The `get_system_prompt` Function

For dynamic prompts that depend on runtime context:

```python
import os
from datetime import datetime

def get_system_prompt() -> str:
    return f"""You are a project auditor.

Current project: {os.path.basename(os.getcwd())}
Date: {datetime.now().strftime("%Y-%m-%d")}

Audit the codebase for:
1. Outdated dependencies
2. Deprecated API usage
3. Missing type annotations
4. Test coverage gaps
"""
```

## Example: Research Agent (Subagent)

```python
# .jarvis/agents/researcher.py
from core.agents.agent_definition import AgentDefinition
from core.agents.profiles import AgentType

RESEARCH_AGENT = AgentDefinition(
    name="researcher",
    agent_type=AgentType.SUBAGENT,
    when_to_use="Deep research on technical topics, papers, and documentation",
    tools=["web_search", "fetch_webpage", "read", "grep"],
    model="inherit",
    max_turns=30,
)
```

## Example: Full-Stack Implementation Agent

```python
# .jarvis/agents/implementer.py
from core.agents.agent_definition import AgentDefinition
from core.agents.profiles import AgentType

IMPLEMENTER = AgentDefinition(
    name="implementer",
    agent_type=AgentType.AGENT,
    when_to_use="Implement features end-to-end: write code, run tests, fix issues",
    tools=["read", "write", "edit", "grep", "find", "ls", "bash", "run_tests"],
    model="inherit",
    max_turns=100,
)
```

## Loading Order & Discovery

1. **Global**: `~/.jarvis/agents/*.py` (lower priority)
2. **Project**: `.jarvis/agents/*.py` (higher priority, overrides globals with same `name`)

The `name` field must be unique. If two agents have the same `name`, the project-level one wins.

## Integration with the `agents` Tool

When the LLM uses the `agents` tool, it sees:

```
Available agents:
- explorer: Explore codebase structure and find files
- plan: Break down tasks into implementation steps
- researcher: Deep research on technical topics
```

The description comes from `when_to_use`. Make it LLM-friendly — describe what the agent does and when to delegate to it.

## Tips

- Use `agent_type=AgentType.SUBAGENT` for utility agents the user doesn't need to see in profiles
- Keep `max_turns` proportional to task complexity (30 for focused tasks, 100 for complex builds)
- Use a restrictive `tools` list to keep agents safe — read-only agents should only have `["read", "grep", "find", "ls"]`
- `tools=None` (default) inherits all parent tools. If you want to explicitly allow everything, set `tools=["*"]`
- Write `when_to_use` descriptions that help the LLM decide when to delegate
- The `get_system_prompt` callable is re-invoked each time the agent starts — great for injecting dynamic context like dates or project names
- For agents that only need a static prompt, omit `get_system_prompt` and rely on the base prompt

## See Also

- [Custom Tools](custom-tools.md) — register new tools that agents can use
- [Agent Profiles](../core/agents/profiles.py) — the AgentType enum and safety system
- [Agent Definition](../core/agents/agent_definition.py) — the dataclass backing custom agents
