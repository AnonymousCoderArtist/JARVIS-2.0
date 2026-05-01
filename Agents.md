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

## Safety Features

JARVIS includes comprehensive safety features inspired by mistral-vibe to provide secure and controlled tool execution.

### Agent Profile System

JARVIS supports multiple agent profiles with different safety levels:

- **Default (NEUTRAL)**: Requires approval for tool executions
- **Plan (SAFE)**: Read-only agent for exploration and planning
- **Accept Edits (DESTRUCTIVE)**: Auto-approves file edits only
- **Auto Approve (YOLO)**: Auto-approves all tool executions
- **Explore (SAFE)**: Read-only subagent for codebase exploration

**Key Features:**
- Shift+Tab to cycle through agent profiles in TUI
- Visual safety level indicators (green/blue/orange/red)
- Profile-specific tool permissions
- Custom profile support via TOML files

See [docs/AGENT_PROFILES.md](docs/AGENT_PROFILES.md) for detailed configuration.

### Tool Permission System

**Permission Levels:**
- **ALWAYS**: Tool executes without asking
- **NEVER**: Tool is permanently disabled
- **ASK**: Tool requires user approval (default)

**Permission Scopes:**
- Tool-level permissions (configurable per tool)
- Session rules (temporary permissions for specific patterns)
- Required permissions (fine-grained checks based on arguments)
- **Vibe-style granular permissions**:
  - **Path-based allowlist/denylist**: Files matching allowlist patterns are always allowed, denylist patterns are never allowed
  - **Sensitive file patterns**: Files matching sensitive patterns (e.g., *secret*, *.env) require special approval
  - **Workdir boundary**: Files outside working directory require approval
  - **Scratchpad paths**: Files in scratchpad directories are always allowed
  - **Dangerous command patterns**: Bash commands with dangerous patterns (e.g., rm -rf, dd if=) require special approval

**Implementation:**
- `core/tools/permissions.py` - Permission models, enums, and Vibe-style granular permission functions
- `core/tools/permission_manager.py` - Permission management logic
- `core/tools/base.py` - Tool permission resolution interface

**Granular Permission Functions:**
- `resolve_file_tool_permission()` - Checks scratchpad, allowlist/denylist, sensitive patterns, and workdir boundary
- `resolve_path_permission()` - Checks path against allowlist/denylist patterns
- `is_path_within_workdir()` - Checks if path is inside working directory
- `is_scratchpad_path()` - Checks if path is in scratchpad directory
- `wildcard_match()` - Matches text against wildcard patterns with optional trailing parts

**Profile Integration:**
The permission system is integrated with agent profiles through the `config_getter` mechanism. When an agent is initialized with a `config_getter` function that returns profile-applied configuration, the permission system automatically respects the active profile's tool permissions. This ensures that:

- **Default profile**: Read operations (`read`, `list_dir`, `glob`, `grep`, `read_memory`) are `ALWAYS`, write operations require approval (`ASK`), and `edit` is auto-approved (`ALWAYS`) - similar to Vibe's approach
- **Plan profile**: Explore-level tools (`read`, `list_dir`, `glob`, `grep`) are `ALWAYS`, all other tools are `NEVER`
- **Accept Edits profile**: File write and edit tools are set to `ALWAYS` permission, other tools use default `ASK`
- **Auto Approve profile**: All tools bypass permission checks via `bypass_tool_permissions`
- **Explore profile** (subagent only): Explore-level tools (`read`, `list_dir`, `glob`, `grep`) are `ALWAYS`, all other tools are `NEVER`

The `AgentManager` handles applying profile overrides to the base configuration through the `apply_to_config()` method, and the agent uses this merged configuration for permission checks.

### Vibe-Style Granular Permission System

JARVIS implements a comprehensive permission system inspired by mistral-vibe, providing granular control over tool execution based on file paths, patterns, and command safety.

#### Permission Resolution Flow

For file-based tools (`read`, `write`, `edit`), the permission system checks in this order:

1. **Scratchpad Check**: Files in `.jarvis/scratchpad` or `/tmp/scratchpad` are always allowed
2. **Denylist Check**: Files matching denylist patterns (e.g., `~/.ssh/*`, `*.key`) are never allowed
3. **Allowlist Check**: Files matching allowlist patterns (e.g., `*.py`, `*.md`) are always allowed
4. **Sensitive Pattern Check**: Files matching sensitive patterns (e.g., `*secret*`, `*.env`) require special approval
5. **Workdir Boundary Check**: Files outside working directory require approval

#### Configuration

The granular permission system is configured in `core/config/settings.py`:

```python
"tools": {
    # Tool-level permissions
    "read": {"permission": "always"},
    "write": {"permission": "ask"},
    "edit": {"permission": "ask"},

    # Granular path-based permissions
    "allowlist": [
        "*.md", "*.txt", "*.py", "*.js", "*.ts",
        "*.json", "*.yaml", "*.yml", "*.toml",
    ],
    "denylist": [
        "/etc/passwd", "/etc/shadow", "~/.ssh/*",
        "~/.aws/*", "*.key", "*.pem",
    ],
    "sensitive_patterns": [
        "*secret*", "*password*", "*credential*",
        "*token*", "*.env", "config/production*",
    ],
}
```

#### Tool-Level Permission Resolution

Tools can implement custom permission logic by overriding the `resolve_permission()` method:

```python
def resolve_permission(self, args: dict) -> PermissionContext | None:
    """Resolve permission for this tool execution"""
    file_path = args.get("filePath")
    if not file_path:
        return None

    return resolve_file_tool_permission(
        file_path,
        tool_name=self.name,
        allowlist=config.allowlist,
        denylist=config.denylist,
        config_permission=config_permission,
        sensitive_patterns=config.sensitive_patterns,
    )
```

#### Dangerous Command Detection

The bash tool automatically detects dangerous command patterns:

- File deletion: `rm -rf`, `rm -r`, `delete`, `shred`, `wipe`
- Disk operations: `dd if=`, `mkfs`, `fdisk`, `format`, `truncate`
- Permission changes: `chmod 777`, `chown`
- System operations: `sudo rm`, `sudo dd`, `sudo mkfs`

These commands trigger special approval with clear warning labels.

#### Approval Dialog

When granular permissions are required, the approval dialog shows specific reasons:

1. **Yes** - Approve this single execution
2. **Yes and always allow for this session** - Add session rule for this pattern (e.g., "outside workdir", "accessing sensitive files")
3. **No and tell the agent what to do instead** - Reject with feedback

This allows users to make informed decisions based on the specific permission requirements.

### Trust Folder System

JARVIS includes a trust folder system to prevent accidental execution in sensitive directories:

- Checks for `.jarvis` subfolder and configuration files
- Prompts user to trust/untrust directories
- Persists trust decisions in `~/.jarvis/trusted_folders.toml`
- Session-level trust with `--trust` flag

**Implementation:**
- `core/trusted_folders.py` - Trust folder management

### Approval UI

The TUI includes a three-option approval dialog:

1. **Yes** - Approve this execution
2. **Yes and always allow for this session** - Add session rule
3. **No and tell the agent what to do instead** - Reject with feedback

**Keyboard Shortcuts:**
- 1/Y - Yes
- 2 - Always allow
- 3/N - No
- Enter - Select
- ESC - Reject

## Core Components

### BaseAgent (`core/agents/base.py`)

The abstract base class that the JARVIS agent inherits from.

**Key Features:**
- **Memory System**: Maintains conversation history with `add_to_memory()` and `get_memory_context()`
- **Context Management**: Store and retrieve task-specific context via `update_context()` and `get_context()`
- **Streaming Support**: Real-time response streaming through `stream_callback`
- **Tool Integration**: Automatic tool calling with `_process_with_tools()` and `_execute_tools_and_update_messages()`
- **Callback System**: Hooks for tool calls (`tool_call_callback`) and results (`tool_result_callback`)
- **Dynamic Prompt Building**: Combines base system prompt with dynamic tool descriptions
- **Standard Message Roles**: Uses system, user, and assistant roles for all LLM interactions
- **Permission System**: Tool approval callbacks and session rule management

**Abstract Methods:**
```python
async def process(self, input: str, context: dict | None = None) -> str
async def plan(self, task: str) -> list[dict[str, Any]]
```

**Safety Methods:**
```python
def set_approval_callback(self, callback: Callable) -> None
def add_session_rule(self, rule: ApprovedRule) -> None
def clear_session_rules(self) -> None
def set_config_getter(self, config_getter: Callable[[], Settings]) -> None
async def _should_execute_tool(self, tool_name: str, tool_args: dict, tool_call_id: str) -> ToolDecision
def approve_always(self, tool_name: str, required_permissions: list, save_permanently: bool = False) -> None
```

**Constructor Parameters:**
```python
def __init__(
    self,
    llm_provider: BaseLLMProvider,
    tool_registry: ToolRegistry,
    system_prompt: str,
    model: str | None = None,
    config_getter: Callable[[], Settings] | None = None,
)
```

The `config_getter` parameter is crucial for proper permission system integration. It should be a function that returns the current `Settings` object with agent profile overrides applied. This ensures that tool permissions respect the active agent profile's safety settings.

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
- Subagent coordination (explore subagent for codebase exploration)

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
- Delegating complex exploration tasks to the explore subagent

**Example Usage:**
```python
from core.agents.coding_agent import CodingAgent
from core.agents.manager import AgentManager
from core.config.settings import Settings

# Initialize agent manager for profile support
settings = Settings()
agent_manager = AgentManager(
    config_getter=lambda: settings,
    initial_agent="default"
)

# Initialize agent with profile config getter
jarvis = CodingAgent(
    provider,
    tool_registry,
    model="gpt-4o",
    config_getter=lambda: agent_manager.config
)

# Rebuild system prompt with dynamic tool descriptions
jarvis.rebuild_system_prompt()

# Process a task
result = await jarvis.process("Fix the authentication bug")
```

---

### ExploreAgent (`core/agents/explore_agent.py`)

A specialized subagent for comprehensive codebase exploration and analysis.

**Purpose:** Systematic exploration and analysis of codebase structure, architecture, and relationships

**System Prompt:** `EXPLORE_SYSTEM_PROMPT` from `explore_agent.py`

**Key Capabilities:**
- Understanding codebase structure and architecture
- Finding specific files, functions, classes, or patterns
- Analyzing code dependencies and relationships
- Identifying entry points and key components
- Providing comprehensive codebase overviews
- Tracing code flow and execution paths
- Mapping module interactions and dependencies

**Best For:**
- Understanding unfamiliar codebases
- Finding where specific functionality is implemented
- Understanding how different parts of the system interact
- Identifying the impact of potential changes
- Documenting codebase architecture
- Finding bugs or issues through systematic exploration

**Example Usage:**
```python
from core.agents import ExploreAgent
from core.agents.manager import AgentManager
from core.config.settings import Settings

# Initialize agent manager for profile support
settings = Settings()
agent_manager = AgentManager(
    config_getter=lambda: settings,
    initial_agent="default"
)

# Initialize explore subagent (uses same model as main agent)
explore_agent = ExploreAgent(
    llm_provider=provider,
    tool_registry=tool_registry,
    model="gpt-4o",  # Same model as main agent
    config_getter=lambda: agent_manager.config
)

# Explore codebase
result = await explore_agent.process("Explore the authentication module and identify all entry points")
```

**Invoking via Tool:**
The ExploreAgent can be invoked by the main agent using the `invoke_agent` tool:
```python
# Main agent can invoke explore subagent
tool_result = await tool_registry.execute_tool("invoke_agent", {
    "agent_name": "explore",
    "prompt": "Find all files that handle user authentication"
})
```

---

## System Prompts (`core/agents/system_prompts.py`)

### JARVIS_SYSTEM_PROMPT
Comprehensive prompt defining the JARVIS agent's behavior:
- **Core Principles**: Understand before acting, be explicit, think step-by-step, be agentic
- **Capabilities**: Code navigation, editing, execution, testing, git operations, research, documentation, subagent coordination
- **Approach**: 4-phase methodology (Understanding → Planning → Implementation → Verification)
- **Quality Standards**: Clear code, proper naming, docstrings, error handling
- **Tool Instructions**: Specific guidance on when to use various tools
- **Agentic Behavior**: Proactive tool usage, error recovery, iterative improvement
- **Task Decomposition**: Systematic breakdown of complex tasks
- **Tool Result Interpretation**: Clear guidance on analyzing tool outputs
- **Subagent Usage**: When and how to use the explore subagent

### EXPLORE_SYSTEM_PROMPT
Specialized prompt for the ExploreAgent subagent:
- **Core Purpose**: Codebase exploration and analysis
- **Systematic Approach**: Structure → Patterns → Dependencies → Synthesis
- **Pattern Recognition**: Identifying architectural patterns and design patterns
- **Dependency Analysis**: Mapping module relationships and dependencies
- **Output Style**: Structured overviews with clear sections

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

### Recent Improvements

**Enhanced System Prompt** (v2.0):
- Added Task Decomposition Strategy with clear methodology
- Enhanced Tool Result Interpretation guidelines
- Added comprehensive Subagent Usage section
- Improved error recovery and iterative refinement guidance
- Added system context integration (OS, architecture, working directory)

**Improved Tool Descriptions**:
- All tools now have comprehensive usage guidelines
- InvokeAgentTool updated to mention explore subagent
- Tools include success/failure indicators and error handling guidance

**Tool Result Handling**:
- Tool results now explicitly include success/failure information
- Error messages are passed to AI with guidance for recovery
- Metadata includes execution details for better debugging

**Explore Subagent Implementation**:
- New ExploreAgent class with specialized exploration capabilities
- Uses same model as main agent for consistency
- Integrated with InvokeAgentTool for seamless delegation
- ToolRegistry updated to support provider and model injection

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

### FileReadTool (read)

The `read` tool uses the files array format for reading one or more files:

**Files Array Format:**
```json
{
  "files": [
    {"file_path": "/path/to/file1.py", "offset": 1, "limit": 50},
    {"file_path": "/path/to/file2.py", "offset": 10, "limit": 100}
  ],
  "encoding": "utf-8"
}
```
- `files`: Array of file objects (required)
  - `file_path`: Absolute path to the file to read (required)
  - `offset`: 1-based line number to start reading from (default: 1)
  - `limit`: Maximum number of lines to read (default: all lines, max 2000)
- `encoding`: Character encoding for reading files (default: utf-8)

**Behavior:**
- Files are read in parallel for performance
- Each file respects individual offset/limit settings
- Returns concatenated content with `--- {file_path} ---` separators
- Read errors for individual files are reported but don't fail the entire operation

### Tool Access Pattern

```python
# Build messages with proper roles
messages = self._build_messages(user_content, include_memory=True)

# Process with tools (automatically handles tool calling loop)
response = await self._process_with_tools(messages, stream=stream)

# Process without tools
response = await self._process_without_tools(messages, stream=stream)
```

---

## Communication Flow

### Agent Execution

```
User Input
    ↓
JARVIS Agent.process()
    ↓
Build messages with proper roles (system, user, assistant)
    ↓
Process with tools via _process_with_tools()
    ↓
LLM generates response with tool calls
    ↓
Execute tools via ToolRegistry
    ↓
Update message history with tool results
    ↓
Loop until no more tool calls
    ↓
Return final response
```

### Message Structure

All LLM interactions use standard message roles:
- **system**: System prompt with tool descriptions and context
- **user**: User input and tool results
- **assistant**: AI responses and tool calls

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
- Use `_build_messages()` to create properly structured message lists
- Follow standard message role conventions (system, user, assistant)

---

## Configuration

### CLI Configuration

JARVIS now uses CLI flags and optional .env file for configuration. The old config.toml and providers.json files are no longer required.

**CLI Flags:**
```bash
jarvis --cli --model gpt-4o --base_url https://api.openai.com/v1 --apikey YOUR_KEY --sdk openai
```

**Available Flags:**
- `--model, -m`: Model name (e.g., gpt-4o, claude-3-5-sonnet-20241022)
- `--base_url`: Base URL for the LLM API
- `--apikey, --api-key`: API key for the LLM provider
- `--sdk`: SDK mode (openai, anthropic, standard)
- `--cli`: Launch the Rich CLI

**Environment Variables (.env):**
```env
# Model name (e.g., gpt-4o, claude-3-5-sonnet-20241022)
JARVIS_MODEL=gpt-4o

# Base URL for the LLM API (e.g., https://api.openai.com/v1)
JARVIS_BASE_URL=

# API key for the LLM provider
JARVIS_API_KEY=

# SDK mode (openai, anthropic, standard)
JARVIS_SDK=openai
```

CLI flags take precedence over .env values. If neither are provided, sensible defaults are used.

### Agent Model Selection

```python
# Initialize with specific model
jarvis = CodingAgent(provider, tool_registry, model="gpt-4o")
```

---

## Troubleshooting

### Common Issues

**Tool calls not executing:**
- Verify you're using `_process_with_tools()` instead of `_process_without_tools()`
- Check tool is registered in ToolRegistry
- Review tool schema matches expected input

**Memory not persisting:**
- Ensure `add_to_memory()` is called after processing
- Check memory limit hasn't been reached
- Verify context is being passed correctly

**Streaming not working:**
- Set `stream_callback` before execution
- Ensure `stream=True` is passed to processing methods
- Check provider supports streaming

**Tool descriptions not updating:**
- Call `rebuild_system_prompt()` after tool registry changes
- Verify tools have proper `description` attributes
- Check system prompt building is working correctly

**Message roles incorrect:**
- Always use `_build_messages()` to create message lists
- Ensure system prompt is in the first message with role "system"
- User input should have role "user"
- Tool results should be added as role "user" messages

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
- `core/agents/base.py` - BaseAgent class with message building and processing methods
- `core/agents/coding_agent.py` - JARVIS agent implementation
- `core/agents/explore_agent.py` - Explore subagent implementation
- `core/agents/system_prompts.py` - System prompt definitions

### Key Methods

**BaseAgent:**
- `_build_messages(user_content, include_memory)` - Build message list with proper roles
- `_process_with_tools(messages, stream)` - Process with tool calling support
- `_process_without_tools(messages, stream)` - Process without tools
- `_execute_tools_and_update_messages(response, messages)` - Execute tools and update history
- `rebuild_system_prompt()` - Rebuild system prompt with current tool descriptions
