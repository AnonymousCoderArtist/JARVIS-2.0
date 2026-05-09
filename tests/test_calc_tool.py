import pytest
import asyncio
from core.tools.registry import ToolRegistry
from core.tools.base import ToolOutput

@pytest.mark.asyncio
async def test_calc_tool():
    # Initialize registry
    registry = ToolRegistry()
    
    # Define the handler
    async def calc_handler(expression: str) -> ToolOutput:
        try:
            # Simple restricted eval for testing
            # We use a clean globals dict and no builtins to be safe
            result = eval(expression, {"__builtins__": {}}, {})
            return ToolOutput(success=True, result=str(result))
        except Exception as e:
            return ToolOutput(success=False, result=None, error=str(e))
            
    # Register the tool using the "custom tool thing" (registry.tool method)
    registry.tool(
        name="calc",
        description="A simple calculator tool",
        parameters={
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "Mathematical expression to evaluate (e.g., '2 + 2')"
                }
            },
            "required": ["expression"]
        },
        handler=calc_handler
    )
    
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
    assert "division by zero" in output_error.error.lower()
