"""Calculator tool — migrated from .jarvis/tools/calc_plugin.py to extension system.

Evaluates mathematical expressions using a restricted eval sandbox.
"""

from jarvis.api import BaseTool, ExtensionAPI, ToolInput, ToolOutput

__version__ = "1.0.0"
__description__ = "Calculator tool for evaluating mathematical expressions"


async def jarvis(api: ExtensionAPI):
    """Register the calculator tool via the extension API."""

    class CalcTool(BaseTool):
        name = "calc"
        description = """Evaluate mathematical expressions.

WHEN TO USE:
- Performing arithmetic calculations
- Evaluating mathematical expressions
- Converting units or computing formulas

Parameters:
- expression (REQUIRED): Mathematical expression to evaluate (e.g., '2 + 2', 'sqrt(144)', '3 * 7')

Returns: String result of the evaluated expression.
Uses a restricted eval sandbox for safety."""

        input_schema = {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "Mathematical expression to evaluate (e.g., '2 + 2', 'sqrt(144)', '3 * 7')",
                }
            },
            "required": ["expression"],
        }

        async def execute(self, input_data: ToolInput) -> ToolOutput:
            try:
                params = input_data.model_dump()
                expression = params.get("expression")
                if not expression:
                    return ToolOutput(
                        success=False,
                        result=None,
                        error="Expression is required. Please provide a mathematical expression like '2 + 2'.",
                    )

                # Simple restricted eval sandbox
                result = eval(expression, {"__builtins__": {}}, {})
                return ToolOutput(success=True, result=str(result))
            except Exception as e:
                return ToolOutput(
                    success=False,
                    result=None,
                    error=f"Failed to evaluate expression: {str(e)}. Please check the syntax and try again.",
                )

    api.tools(CalcTool())
