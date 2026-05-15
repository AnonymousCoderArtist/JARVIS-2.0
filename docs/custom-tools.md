# Custom Tools

JARVIS supports registering custom tools that extend its capabilities. Custom tools are sent to the LLM via the native `tools` API parameter alongside built-in tools.

The recommended way to add custom tools is via the **extension system** — Python files in `.jarvis/extensions/`. This replaces the old `register_plugin()` / `.jarvis/tools/` mechanism, which has been removed.

## Quick Start: Extension-Based Custom Tools

Save a `.py` file in `.jarvis/extensions/` (project-local) or `~/.jarvis/extensions/` (global):

### Example: Calculator Tool

Save as `.jarvis/extensions/calc_tool.py`:

```python
"""Calculator tool extension."""
from core.tools.base import BaseTool, ToolInput, ToolOutput


async def jarvis_extension(api):
    """Register a calculator tool via the extension API."""

    class CalcTool(BaseTool):
        name = "calc"
        description = "Evaluate mathematical expressions."
        input_schema = {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "Expression to evaluate (e.g., '2 + 2')"
                }
            },
            "required": ["expression"]
        }

        async def execute(self, input_data: ToolInput) -> ToolOutput:
            try:
                expr = input_data.model_dump().get("expression", "")
                result = eval(expr, {"__builtins__": {}}, {})
                return ToolOutput(success=True, result=str(result))
            except Exception as e:
                return ToolOutput(success=False, result=None, error=str(e))

    api.register_tool(CalcTool())
```

## Tool Template

```python
"""Description of what this tool does."""

from core.events.hooks import HookResult, HookStage
from core.tools.base import BaseTool, ToolInput, ToolOutput


async def jarvis_extension(api):
    """Register a custom tool using the extension API."""

    class MyTool(BaseTool):
        """Tool description shown to the LLM."""

        name = "my_tool"
        description = """Full description with WHEN TO USE and Parameters sections."""

        input_schema = {
            "type": "object",
            "properties": {
                "param1": {
                    "type": "string",
                    "description": "Description of param1",
                },
            },
            "required": ["param1"],
        }

        async def execute(self, input_data: ToolInput) -> ToolOutput:
            try:
                # Tool logic here
                return ToolOutput(success=True, result="Done")
            except Exception as e:
                return ToolOutput(success=False, result=None, error=str(e))

    api.register_tool(MyTool())
```

## Required Fields

Every tool must define these three class attributes:

| Field | Description |
|-------|-------------|
| `name` | Unique tool name (snake_case). Used by the LLM to call it. |
| `description` | Full description. Include WHEN TO USE and parameter details. The LLM uses this to decide if the tool is relevant. |
| `input_schema` | JSON Schema dict defining the parameters the tool accepts. |

## Return Format

Every tool must return a `ToolOutput` instance:

```python
ToolOutput(
    success=True,          # True if successful
    result="Done",         # Result data returned to the LLM
    error=None,            # Error message if failed
    metadata={"key": "value"},  # Optional additional data
)
```

On failure, set `success=False` and provide a descriptive `error` message. The LLM sees this and retries with corrected parameters.

## Overriding Built-in Tools

Extensions can override built-in tools by registering a tool with the same name. This enables patterns like:

- Wrapping `read` with access logging
- Replacing `bash` with SSH-based execution
- Adding extra permission checks around `write`/`edit`

```python
async def jarvis_extension(api):
    """Override the 'read' tool with an audited version."""
    from core.tools.base import BaseTool, ToolInput, ToolOutput

    class AuditedReadTool(BaseTool):
        name = "read"
        description = "Read file contents (audited)."
        # ... same input_schema as built-in ...

        async def execute(self, input_data: ToolInput) -> ToolOutput:
            # Log the access
            file_path = input_data.model_dump().get("files", [{}])[0].get("filePath", "?")
            print(f"[AUDIT] Reading: {file_path}")
            # Use the default backend to do the actual read
            content = await self.file_ops.read_file(file_path)
            return ToolOutput(success=True, result=content)

    api.register_tool(AuditedReadTool())
```

## Using Operation Backends in Custom Tools

Custom tools can use the operations backends (file, bash, edit) just like built-in tools:

```python
class MyTool(BaseTool):
    name = "my_tool"
    # ...

    async def execute(self, input_data: ToolInput) -> ToolOutput:
        # Use the active operations backend (local, SSH, sandbox, etc.)
        content = await self.file_ops.read_file("/path/to/file")
        result = await self.bash_ops.run("echo hello")
        return ToolOutput(success=True, result=content)
```

## Tips

- Tool descriptions should mention **when to use** the tool so the LLM can decide correctly
- Use snake_case for tool names
- Make `input_schema` `required` lists minimal — only truly mandatory parameters
- The `name` must be unique across all tools (built-in, custom, and MCP)
- Extensions are auto-discovered on startup — no registration needed
- Use `/reload` in TUI to reload extensions without restarting
- Project-level extensions (`.jarvis/extensions/`) override global ones (`~/.jarvis/extensions/`) with the same name

## See Also

- [Custom Agents](custom-agents.md) — Creating specialized agent profiles with tool restrictions
- [Architecture: Extension System](ARCHITECTURE.md#7-extension-system) — Full extension API documentation
- [Architecture: Operation Backends](ARCHITECTURE.md#operations-backend) — Pluggable file/bash/edit backends
- [Extension Examples](../examples/extensions/) — Hello world, safety gate, SSH tools, event logger
- [BaseTool](../core/tools/base.py) — The base class for all tools
- [ToolOutput](../core/tools/base.py) — The return type for tools
