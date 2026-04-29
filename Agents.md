# JARVIS Agent System Documentation

## Overview

The JARVIS agent system implements a single-agent architecture with comprehensive capabilities for both coding and knowledge work. The system is inspired by Claude Code and OpenClaude, providing a unified agentic assistant that can handle a wide range of tasks through intelligent tool usage.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      JARVIS Agent                           │
│                 (Unified Agentic Assistant)                  │
└──────────────────────────────┬──────────────────────────────┘
                               │
                       ┌───────▼────────┐
                       │   ToolRegistry │
                       │ (Shared Tools)  │
                       └────────────────┘
```

## Core Components

### BaseAgent (`core/agents/base.py`)

The abstract base class that the JARVIS agent inherits from.

**Key Features:**
- **Memory System**: Maintains conversation history with `add_to_memory()` and `get_memory_context()`
- **Context Management**: Store and retrieve task-specific context via `update_context()` and `get_context()`
- **Streaming Support**: Real-time response streaming through `stream_callback`
- **Tool Integration**: Automatic tool calling with `_handle_tool_calls()`
- **Callback System**: Hooks for tool calls (`tool_call_callback`) and results (`tool_result_callback`)
- **Dynamic Prompt Building**: Combines base system prompt with dynamic tool descriptions

**Abstract Methods:**
```python
async def process(self, input: str, context: dict | None = None) -> str
async def plan(self, task: str) -> list[dict[str, Any]]
```

**Usage:**
```python
from core.agents.base import BaseAgent

class MyAgent(BaseAgent):
    async def process(self, input: str, context: dict | None = None) -> str:
        # Implementation
        pass
    
    async def plan(self, task: str) -> list[dict[str, Any]]:
        # Implementation
        pass
```

---

### CodingAgent (`core/agents/coding_agent.py`)

The main JARVIS agent for all tasks (coding, research, documentation, etc.).

**Purpose:** Unified agent for software development, research, document preparation, and general assistance

**System Prompt:** `JARVIS_SYSTEM_PROMPT` from `system_prompts.py`

**Key Capabilities:**
- File operations (read, write, search, list)
- Code execution (Python, shell, bash, PowerShell)
- Git operations and version control
- Test running and debugging
- Code refactoring and optimization
- Web research and content fetching
- Document processing (PDF, text)
- Data extraction and analysis
- Report generation and documentation

**Best For:**
- Writing and editing code
- Debugging and testing
- Code review and refactoring
- Project structure exploration
- Shell command execution
- Research and information gathering
- Document preparation and formatting
- Data extraction from files
- Summarization and synthesis
- Web content analysis

**Example Usage:**
```python
from core.agents.coding_agent import CodingAgent

# Initialize agent
jarvis = CodingAgent(provider, tool_registry, model="gpt-4o")

# Rebuild system prompt with dynamic tool descriptions
jarvis.rebuild_system_prompt()

# Process a task
result = await jarvis.process("Fix the authentication bug")
```

---

## System Prompts (`core/agents/system_prompts.py`)

### JARVIS_SYSTEM_PROMPT
Comprehensive prompt defining the JARVIS agent's behavior:
- **Core Principles**: Understand before acting, be explicit, think step-by-step, be agentic
- **Capabilities**: Code navigation, editing, execution, testing, git operations, research, documentation
- **Approach**: 4-phase methodology (Understanding → Planning → Implementation → Verification)
- **Quality Standards**: Clear code, proper naming, docstrings, error handling
- **Tool Instructions**: Specific guidance on when to use various tools
- **Agentic Behavior**: Proactive tool usage, error recovery, iterative improvement

### Dynamic Tool Descriptions

The system uses `generate_tool_descriptions()` to dynamically inject tool definitions at runtime:

```python
def generate_tool_descriptions(tools: dict[str, Any]) -> str:
    """
    Dynamically generate tool descriptions from tool registry.
    This follows OpenClaude's pattern of injecting tool definitions at runtime.
    """
    if not tools:
        return ""
    
    tool_sections = []
    
    for tool_name, tool in tools.items():
        tool_desc = getattr(tool, 'description', '')
        if tool_desc:
            tool_sections.append(f"### {tool_name}\n{tool_desc}\n")
    
    if tool_sections:
        return "## Available Tools\n\n" + "\n".join(tool_sections)
    return ""
```

The agent's `rebuild_system_prompt()` method combines the base system prompt with dynamically generated tool descriptions:

```python
def rebuild_system_prompt(self):
    """Rebuild the system prompt with current tool descriptions"""
    tools = self.tool_registry.get_tools()
    tool_descriptions = generate_tool_descriptions(tools)
    self.system_prompt = self.base_system_prompt + "\n\n" + tool_descriptions
```

---

## Agent Tools (`core/tools/agent_tools.py`)

### InvokeAgentTool
Allows the agent to invoke specialized subagents programmatically (for future extensibility).

```python
{
    "name": "invoke_agent",
    "description": "Invoke a specialized agent for specific tasks",
    "parameters": {
        "agent_name": "Name of the subagent",
        "prompt": "Task to send to the subagent"
    }
}
```

### ActivateSkillTool
Activates specialized skills for expert guidance.

```python
{
    "name": "activate_skill",
    "description": "Activate specialized agent skills",
    "parameters": {
        "name": "skill-creator | reverse-engineering | modern-python"
    }
}
```

---

## Integration with Tool System

The JARVIS agent has access to the shared `ToolRegistry`:

### Available Tools

| Tool Category | Tools | Description |
|--------------|-------|-------------|
| **File Operations** | FileReadTool, FileWriteTool, ListDirectoryTool, GlobTool | Read, write, list, and search files |
| **Code Operations** | BashTool, RunTestsTool, REPLTool, PowerShellTool | Execute code and commands |
| **Search** | GrepSearchTool | Search for patterns in files |
| **Document Processing** | ReadPDFTool | Process PDF documents |
| **Web** | WebFetchTool | Fetch web content |
| **Memory** | SaveMemoryTool | Save information to memory |
| **Background** | ListBackgroundProcessesTool, ReadBackgroundOutputTool | Manage background processes |
| **Agent** | InvokeAgentTool, ActivateSkillTool | Agent and skill management |

### Tool Access Pattern

```python
# Tools are automatically available through the registry
response = await self.generate_response(
    messages=messages,
    use_tools=True  # Enables tool calling
)

# Tool results are automatically handled by _handle_tool_calls()
```

---

## Communication Flow

### Agent Execution

```
User Input
    ↓
JARVIS Agent.process()
    ↓
Build messages with system prompt (including dynamic tool descriptions)
    ↓
Generate response with tool calls
    ↓
Execute tools via ToolRegistry
    ↓
Return final response
```

### Streaming Execution

```python
# Set up callbacks
jarvis.stream_callback = lambda chunk: print(chunk, end="")
jarvis.tool_call_callback = lambda name, args: print(f"Tool: {name}")
jarvis.tool_result_callback = lambda name, args, result: print(f"Result: {result}")

# Execute with streaming
result = await jarvis.process("Update the README")
```

---

## Best Practices

### 1. Agent Design
- Use clear system prompts defining behavior
- Implement proper memory management
- Handle errors gracefully
- Be agentic - use tools proactively

### 2. Memory Management
- Store relevant context in agent memory
- Use `get_memory_context()` to retrieve recent history
- Clear memory between unrelated tasks
- Respect token limits

### 3. Tool Usage
- Use appropriate tools for each task
- Verify tool outputs before proceeding
- Handle tool errors gracefully
- Chain tools for complex operations

### 4. Dynamic Prompts
- Always call `rebuild_system_prompt()` after tool registry changes
- Ensure tool descriptions are comprehensive and accurate
- Follow OpenClaude-style tool description format

---

## Configuration

### Environment Variables

```env
# Agent settings
MAX_AGENT_MEMORY=50     # Maximum memory entries per agent
CONTEXT_THRESHOLD=0.75 # Summarization threshold (75%)
```

### Agent Model Selection

```python
# Initialize with specific model
jarvis = CodingAgent(provider, tool_registry, model="gpt-4o")
```

---

## Troubleshooting

### Common Issues

**Tool calls not executing:**
- Verify `use_tools=True` in `generate_response()`
- Check tool is registered in ToolRegistry
- Review tool schema matches expected input

**Memory not persisting:**
- Ensure `add_to_memory()` is called after processing
- Check memory limit hasn't been reached
- Verify context is being passed correctly

**Streaming not working:**
- Set `stream_callback` before execution
- Ensure `stream=True` in generate calls
- Check provider supports streaming

**Tool descriptions not updating:**
- Call `rebuild_system_prompt()` after tool registry changes
- Verify tools have proper `description` attributes
- Check `generate_tool_descriptions()` is working correctly

---

## Future Extensions

Planned agent system enhancements:
- **Skill System**: Enhanced skill activation and management
- **Multi-Agent Support**: Optional multi-agent mode for complex tasks
- **Voice Interface**: Voice input and speech processing
- **Enhanced Memory**: Long-term memory and knowledge base integration

---

## API Reference

See individual agent source files for full API:
- `core/agents/base.py` - BaseAgent class
- `core/agents/coding_agent.py` - JARVIS agent implementation
- `core/agents/system_prompts.py` - System prompt definitions
