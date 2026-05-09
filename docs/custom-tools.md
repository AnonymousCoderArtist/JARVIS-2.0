# Custom Tools

JARVIS supports registering custom tools that extend its capabilities. Custom tools appear in the SDK tools flag and can be called by the LLM.

## Auto-Loading from `.jarvis/tools/`

JARVIS supports automatically loading custom tools from the `.jarvis/tools/` directory. This allows you to add tools without modifying any initialization files.

When JARVIS starts (in either TUI or CLI mode), it searches for Python files in the following directories:
1.  `~/.jarvis/tools/`
2.  `~/.jarvis/tool/`
3.  `./.jarvis/tools/`
4.  `./.jarvis/tool/`

Any class in these files that inherits from `BaseTool` (and is not `BaseTool` itself) will be automatically instantiated and registered.

### Example

Save the following as `.jarvis/tools/calc_plugin.py`:

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

## Quick Start

Use `tool_registry.tool()` to add a custom tool:

```python
from core.tools.registry import ToolRegistry
from core.tools.base import ToolOutput

async def my_tool(param: str, count: int = 0) -> ToolOutput:
    return ToolOutput(success=True, result=f"param={param}, count={count}")

tool_registry.tool(
    name="my_tool",
    description="Does something useful",
    parameters={
        "type": "object",
        "properties": {
            "param": {"type": "string"},
            "count": {"type": "integer"},
        },
    },
    handler=my_tool,
    guidelines=["Use my_tool for custom operations"],
)
```

## Tool Definition Fields

| Field | Required | Description |
|-------|----------|-------------|
| `name` | Yes | Unique tool identifier |
| `description` | Yes | Description shown to the LLM |
| `parameters` | Yes | JSON Schema for parameters |
| `handler` | Yes | Async function that executes the tool |
| `guidelines` | No | Tool-specific bullets for Guidelines section |

## Tool Template

```python
"""Description of what this tool does."""

import os
from typing import Any

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

    def _get_param(self, input_data: ToolInput, *names) -> Any:
        """Get parameter using multiple possible names."""
        for name in names:
            value = getattr(input_data, name, None)
            if value is not None:
                return value
        return None

    async def execute(self, input_data: ToolInput) -> ToolOutput:
        try:
            param1 = self._get_param(input_data, "param1")
            # Tool logic here
            return ToolOutput(success=True, result="Done")
        except Exception as e:
            return ToolOutput(success=False, result=None, error=str(e))


# Register the tool
tool_registry.register(MyTool())
```

## Return Format

Tools must return a `ToolOutput` instance:

```python
ToolOutput(
    success=True,          # True if successful
    result="Done",         # Result data for the LLM
    error=None,            # Error message if failed
    metadata={"key": "value"},  # Additional metadata
)
```

## Guidelines

Each guideline should name the tool explicitly:

```python
guidelines=["Use my_tool when user asks for custom operations"]
```

Not: `"Use this tool when..."` (ambiguous)

## Example: Todo List Tool

```python
import json
from pathlib import Path
from core.tools.base import ToolOutput

TODO_FILE = Path.home() / ".jarvis" / "todo.json"

async def todo(action: str, text: str | None = None) -> ToolOutput:
    if not TODO_FILE.exists():
        TODO_FILE.parent.mkdir(parents=True, exist_ok=True)
        TODO_FILE.write_text("[]")

    todos = json.loads(TODO_FILE.read_text())

    if action == "list":
        return ToolOutput(success=True, result="\n".join(f"- {t}" for t in todos) or "No todos")
    elif action == "add" and text:
        todos.append(text)
        TODO_FILE.write_text(json.dumps(todos))
        return ToolOutput(success=True, result=f"Added: {text}")

    return ToolOutput(success=False, result="Invalid action")

tool_registry.tool(
    name="todo",
    description="Manage todo list",
    parameters={"type": "object", "properties": {"action": {"type": "string"}, "text": {"type": "string"}}},
    handler=todo,
    guidelines=["Use todo when user asks for a task list"],
)
```

## See Also

- [Custom Agents](custom-agents.md) - Creating specialized agent profiles