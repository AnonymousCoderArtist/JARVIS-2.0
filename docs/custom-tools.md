# Custom Tools

JARVIS supports registering custom tools that extend its capabilities. Custom tools are sent to the LLM via the native `tools` API parameter alongside built-in tools.

## Auto-Loading from `.jarvis/tools/`

JARVIS automatically discovers and registers custom tools from `.jarvis/tools/` directories at startup.

It searches these locations (in order, global has lower priority):

1. `~/.jarvis/tools/` — global user tools
2. `./.jarvis/tools/` — project-level tools (overrides globals with same name)

Any Python class in these files that inherits from `BaseTool` (and is not `BaseTool` itself) is automatically instantiated and registered. There is no need to manually register anything.

### Example: Calculator Tool

Save as `.jarvis/tools/calc_plugin.py`:

```python
from core.tools.base import BaseTool, ToolInput, ToolOutput


class CalcTool(BaseTool):
    name = "calc"
    description = "A simple calculator tool that evaluates mathematical expressions."
    input_schema = {
        "type": "object",
        "properties": {
            "expression": {
                "type": "string",
                "description": "Mathematical expression to evaluate (e.g., '2 + 2')"
            }
        },
        "required": ["expression"]
    }

    async def execute(self, input_data: ToolInput) -> ToolOutput:
        try:
            params = input_data.model_dump()
            expression = params.get("expression")
            if not expression:
                return ToolOutput(success=False, result=None, error="Expression is required")
            result = eval(expression, {"__builtins__": {}}, {})
            return ToolOutput(success=True, result=str(result))
        except Exception as e:
            return ToolOutput(success=False, result=None, error=str(e))
```

## Tool Template

```python
"""Description of what this tool does."""

from core.tools.base import BaseTool, ToolInput, ToolOutput


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

## Tips

- Tool descriptions should mention **when to use** the tool so the LLM can decide correctly
- Use snake_case for tool names
- Make `input_schema` `required` lists minimal — only truly mandatory parameters
- The `name` must be unique across all tools (built-in, custom, and MCP)
- Restart JARVIS after adding or modifying tools to reload them
- Project-level tools (`.jarvis/tools/`) override global tools (`~/.jarvis/tools/`) with the same name

## See Also

- [Custom Agents](custom-agents.md) — Creating specialized agent profiles with tool restrictions
- [BaseTool](../core/tools/base.py) — The base class for all tools
- [ToolOutput](../core/tools/base.py) — The return type for tools
