# Custom Agents

JARVIS supports loading custom agents from `.jarvis/agents/`. This allows you to create specialized agents with custom system prompts and tool configurations.

## Creating a Custom Agent

1. Create `.jarvis/agents/my-agent.py`:

```python
from core.agents.agent_definition import AgentDefinition

def get_system_prompt() -> str:
    return "You are a specialized assistant for..."

MY_AGENT_DEFINITION = AgentDefinition(
    agent_type="my-agent",  # Unique identifier
    when_to_use="Use for specific tasks",
    tools=["read", "ls", "find", "grep"],  # Allowed tools
    disallowed_tools=["write", "edit", "bash"],  # Disallowed tools
    model="inherit",  # Uses CLI/TUI model
    max_turns=50,
    get_system_prompt=get_system_prompt,
)
```

2. Restart JARVIS or reload to discover the agent

3. Use via `agents my-agent`

## Agent Definition Fields

| Field | Required | Description |
|-------|----------|-------------|
| `agent_type` | Yes | Unique identifier for this agent |
| `when_to_use` | Yes | Description of when to use this agent |
| `tools` | No | List of allowed tool names |
| `disallowed_tools` | No | List of blocked tool names |
| `model` | No | Model to use (`"inherit"` uses CLI/TUI model) |
| `max_turns` | No | Maximum conversation turns (default: 50) |
| `get_system_prompt` | No | Function returning system prompt string |

## Example: Research Assistant

```python
# .jarvis/agents/research.py
from core.agents.agent_definition import AgentDefinition

def get_system_prompt() -> str:
    return """You are a Research Assistant specializing in academic papers and technical documentation.

## Your Purpose
- Analyze research papers and summarize key findings
- Explain complex technical concepts in simple terms
- Find and cite relevant sources

## Guidelines
- Be thorough but concise
- Cite sources when possible
- Use available tools to gather information
"""

RESEARCH_AGENT_DEFINITION = AgentDefinition(
    agent_type="research",
    when_to_use="Use this agent for literature reviews, paper analysis, and technical explanations",
    tools=["read", "ls", "find", "grep", "web_search", "fetch_webpage"],
    disallowed_tools=["bash", "edit", "write_file"],
    model="inherit",
    max_turns=100,
    get_system_prompt=get_system_prompt,
)
```

## Example: Code Reviewer

```python
# .jarvis/agents/code_review.py
from core.agents.agent_definition import AgentDefinition

CODE_REVIEW_DEFINITION = AgentDefinition(
    agent_type="code-review",
    when_to_use="Use this agent for code quality analysis and suggestions",
    tools=["read", "ls", "find", "grep", "glob"],
    disallowed_tools=["write", "edit", "bash", "create_agent"],
    model="inherit",
    max_turns=50,
)
```

## TUI Integration

Custom agents appear in the **Shift+Tab** profile cycle. You need **BOTH** files:

1. `.jarvis/agents/my-agent.py` - Python agent definition (required for agent logic)
2. `.jarvis/agents/my-agent.toml` - Profile for TUI cycling (required for profile integration)

Example TOML profile:

```toml
# .jarvis/agents/my-agent.toml
display_name = "My Agent"
description = "Custom agent for specific tasks"
safety = "neutral"
agent_type = "subagent"
```

## Tips

- Use `model="inherit"` to respect the user's model selection
- Keep `max_turns` reasonable to avoid long conversations
- Use `disallowed_tools` to keep agents safe (e.g., block file writes)
- The `get_system_prompt` function allows dynamic prompts based on context