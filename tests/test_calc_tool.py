
import pytest

from jarvis.core.tools.base import BaseTool, ToolInput, ToolOutput
from jarvis.core.tools.registry import ToolRegistry


class CalcTool(BaseTool):
    """A simple calculator tool for testing"""

    name = "calc"
    description = "A simple calculator tool"
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
        expression = self._get_param(input_data, "expression") or ""
        try:
            # Simple restricted eval for testing
            # We use a clean globals dict and no builtins to be safe
            result = eval(expression, {"__builtins__": {}}, {})
            return ToolOutput(success=True, result=str(result))
        except Exception as e:
            return ToolOutput(success=False, result=None, error=str(e))


@pytest.mark.asyncio
async def test_calc_tool():
    # Initialize registry
    registry = ToolRegistry()

    # Register the tool using proper registration
    calc_tool = CalcTool()
    registry.register(calc_tool)

    # Verify the tool is registered
    assert "calc" in registry._tools

    # Execute the tool
    output = await registry.execute_tool("calc", {"expression": "2 + 3"})

    # Verify the result
    assert output.success
    assert output.result == "5"

    # Test error handling
    output_error = await registry.execute_tool("calc", {"expression": "1 / 0"})
    assert not output_error.success
    assert output_error.error is not None
    assert "division by zero" in output_error.error.lower()
