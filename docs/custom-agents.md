# Custom Agents

JARVIS supports loading custom agents as extensions. This allows you to create specialized agents with custom system prompts, tool whitelists, and lifecycle controls — then invoke them via the `agents` tool or switch between them in the TUI.

## How It Works

Custom agents are Python files in `~/.jarvis/extensions/` (global) or `.jarvis/extensions/` (project-level). Each file exports a `jarvis(api)` factory function that registers agents via `api.agents()`.

There are two kinds of agents, controlled by the `agent_type` field:

| Kind | Profiles (Shift+Tab) | `agents` tool | Use Case |
|------|----------------------|---------------|----------|
| `AGENT` (default) | Yes | Yes | Full agents the user switches between |
| `SUBAGENT` | No | Yes | Specialized workers only the LLM invokes |

## Quick Start

Create `.jarvis/extensions/my-reviewer.py`:

```python
from core.agents.agent_definition import AgentDefinition
from core.agents.profiles import AgentType
from core.tools.file_tools import FileReadTool, FindTool, LSTool
from core.tools.grep_tool import GrepSearchTool

def system_prompt() -> str:
    return """You are a code reviewer. Focus on:
- Security vulnerabilities (OWASP Top 10)
- Logic bugs and edge cases
- Performance issues
- Code style and conventions
"""

async def jarvis(api):
    api.agents(AgentDefinition(
        name="code-review",
        agent_type=AgentType.AGENT,     # appears in profiles + agents tool
        description="Review code for bugs, security issues, and style problems",
        tools=[FileReadTool, GrepSearchTool, FindTool, LSTool],  # import tool classes
        model="inherit",
        max_turns=50,
        system_prompt=system_prompt,
    ))
```

Restart JARVIS. The agent appears in:
- **Shift+Tab cycling** (because `agent_type=AgentType.AGENT`)
- **`agents` tool** — the LLM can delegate to it by name `"code-review"`

## All Fields

| Field | Required | Default | Description |
|-------|----------|---------|-------------|
| `name` | Yes | — | Unique identifier (used to invoke via `agents` tool) |
| `description` | Yes | — | Description for the LLM to decide when to delegate |
| `tools` | No | `None` | Tool whitelist: `None` = all, `["*"]` = all, `[FileReadTool, GrepSearchTool]` = restricted (accepts tool classes, instances, or string names) |
| `disallowed_tools` | No | `None` | Tools to block (applied after `tools`) |
| `model` | No | `"inherit"` | Model to use: `"inherit"` or specific model name |
| `max_turns` | No | `100` | Max agentic loop iterations |
| `agent_type` | No | `AGENT` | `AGENT` or `SUBAGENT` |
| `system_prompt` | No | `None` | Callable returning the system prompt |

## Specifying Tools

The `tools` field accepts tool classes, tool instances, or string names (for backward compatibility):

```python
from core.tools.file_tools import FileReadTool, FindTool, LSTool
from core.tools.grep_tool import GrepSearchTool
from core.tools.code_tools import BashTool

# Using tool classes (recommended)
tools=[FileReadTool, GrepSearchTool, FindTool, LSTool]

# Using tool instances
tools=[FileReadTool(), GrepSearchTool(), FindTool(), LSTool()]

# Mixing with custom tools registered via api.tools()
tools=[FileReadTool, MyCustomTool]

# All tools (no filtering)
tools=["*"]
```

Under the hood, `resolve_tool_ref()` extracts the `name` attribute from classes/instances, so `FileReadTool` resolves to `"read"`, `GrepSearchTool` resolves to `"grep"`, etc.

## Creating Custom Tools

You can create your own tools and use them in agents. Here's a complete example:

```python
# .jarvis/extensions/weather_agent.py
from core.agents.agent_definition import AgentDefinition
from core.agents.profiles import AgentType
from core.tools.base import BaseTool, ToolInput, ToolOutput
from core.tools.file_tools import FileReadTool


class WeatherTool(BaseTool):
    """Get current weather for a city."""
    name = "get_weather"
    description = "Get current weather information for a specified city"
    input_schema = {
        "type": "object",
        "properties": {
            "city": {
                "type": "string",
                "description": "City name (e.g., 'London', 'New York')",
            },
        },
        "required": ["city"],
    }

    async def execute(self, input_data: ToolInput) -> ToolOutput:
        city = input_data.get("city", "Unknown")
        # In a real tool, you'd call a weather API here
        return ToolOutput(
            success=True,
            result=f"Weather in {city}: 22°C, Sunny",
        )


async def jarvis(api):
    # Register the custom tool so it's available in the system
    api.tools(WeatherTool())

    # Create an agent that uses the custom tool alongside built-in tools
    api.agents(AgentDefinition(
        name="weather-assistant",
        agent_type=AgentType.SUBAGENT,
        description="Answer questions about weather and read weather-related files",
        tools=[WeatherTool, FileReadTool],  # custom + built-in
        model="inherit",
        max_turns=10,
        system_prompt=lambda: "You are a weather assistant. Use the get_weather tool to check conditions.",
    ))
```

## Extension API

The `api` object passed to `jarvis(api)` provides these methods:

### `api.agents(definition)`

Register a custom agent definition. The definition should be an `AgentDefinition` instance.

```python
from core.tools.file_tools import FileReadTool
from core.tools.grep_tool import GrepSearchTool

async def jarvis(api):
    api.agents(AgentDefinition(
        name="my-agent",
        description="...",
        tools=[FileReadTool, GrepSearchTool],  # import tool classes
        system_prompt=lambda: "You are...",
    ))
```

### Mixing Agents with Other Extensions

An extension can register agents alongside tools, hooks, and events:

```python
from core.tools.file_tools import FileReadTool

async def jarvis(api):
    # Register a custom tool
    api.tools(MyCustomTool())

    # Register an agent that uses the custom tool (by class or instance)
    api.agents(AgentDefinition(
        name="my-agent",
        description="...",
        tools=[FileReadTool, MyCustomTool],  # mix built-in and custom
        system_prompt=lambda: "...",
    ))

    # Register a hook
    api.hook(HookStage.BEFORE_TOOL_CALL, my_safety_hook)
```

## Examples

### Read-Only Reviewer (SUBAGENT)

```python
from core.agents.agent_definition import AgentDefinition
from core.agents.profiles import AgentType
from core.tools.file_tools import FileReadTool, FindTool, LSTool
from core.tools.grep_tool import GrepSearchTool

async def jarvis(api):
    api.agents(AgentDefinition(
        name="reviewer",
        agent_type=AgentType.SUBAGENT,
        description="Review code for bugs and security issues",
        tools=[FileReadTool, GrepSearchTool, FindTool, LSTool],
        model="inherit",
        max_turns=50,
        system_prompt=lambda: "You are a code reviewer. Be thorough and specific.",
    ))
```

### Full-Access Implementer (AGENT)

```python
from core.agents.agent_definition import AgentDefinition
from core.agents.profiles import AgentType

async def jarvis(api):
    api.agents(AgentDefinition(
        name="implementer",
        agent_type=AgentType.AGENT,
        description="Implement features and fix bugs",
        tools=["*"],
        model="inherit",
        max_turns=100,
        system_prompt=lambda: "You are a senior engineer. Write clean, tested code.",
    ))
```

### Custom Model

```python
from core.agents.agent_definition import AgentDefinition
from core.agents.profiles import AgentType
from core.tools.file_tools import FileReadTool
from core.tools.grep_tool import GrepSearchTool
from core.tools.web_tools import ExaWebSearchTool

async def jarvis(api):
    api.agents(AgentDefinition(
        name="fast-helper",
        agent_type=AgentType.SUBAGENT,
        description="Quick questions and simple tasks",
        tools=[FileReadTool, GrepSearchTool, ExaWebSearchTool],
        model="gpt-4o-mini",  # Use a cheaper model for simple tasks
        max_turns=20,
        system_prompt=lambda: "You are a helpful assistant. Be concise.",
    ))
```

## Advanced

### Custom Working Directory

Agents run in the current working directory by default. To change this, override the agent's execution context by setting `base_dir` in the definition:

```python
AgentDefinition(
    name="docs-agent",
    base_dir="docs/",  # Agent sees docs/ as its working directory
    ...
)
```

### Discovery Order

1. Built-in agents (explore, plan, general-purpose, fork, verification, rubber-duck)
2. Project extensions (`.jarvis/extensions/*.py`)
3. User extensions (`~/.jarvis/extensions/*.py`)

If two agents have the same name, the first one discovered wins.

### Disabling Agents

Use `enabled_agents` or `disabled_agents` in your JARVIS settings:

```json
{
    "enabled_agents": ["default", "plan", "explore", "my-agent"]
}
```

Or disable specific agents:

```json
{
    "disabled_agents": ["superagent"]
}
```

## Legacy `.jarvis/agents/` Support

The old `.jarvis/agents/` directory with `AGENT_DEFINITION` attribute is still supported but deprecated. Please migrate to `.jarvis/extensions/` using the `api.agents()` pattern.

**Old pattern:**
```python
# .jarvis/agents/my_agent.py
MY_AGENT = AgentDefinition(name="my-agent", ...)
```

**New pattern:**
```python
# .jarvis/extensions/my_agent.py
async def jarvis(api):
    api.agents(AgentDefinition(name="my-agent", ...))
```

## Troubleshooting

### Agent not appearing

1. Check the file is in `.jarvis/extensions/` (not `.jarvis/agents/`)
2. Ensure the factory function is named `jarvis` (or `__jarvis__` or `default`)
3. Check for syntax errors — JARVIS logs load failures to the console
4. Verify the `name` doesn't conflict with an existing agent

### Agent not invoked by LLM

1. Improve `description` — be specific about what triggers delegation
2. Check `enabled_agents`/`disabled_agents` settings
3. Ensure the agent's `tools` list includes tools needed for the task
