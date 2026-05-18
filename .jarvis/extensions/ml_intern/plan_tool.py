"""Plan tool — todo list tracking for multi-step tasks.

Ported from huggingface/ml-intern agent/tools/plan_tool.py.
"""

from __future__ import annotations

from jarvis.api import BaseTool, ToolInput, ToolOutput


class PlanTool(BaseTool):
    name = "plan_tool"
    description = (
        "Track progress on multi-step tasks with a todo list (pending/in_progress/completed).\n\n"
        "Use for tasks with 3+ steps. Each call replaces the entire plan (send full list).\n\n"
        "Rules: exactly ONE task in_progress at a time. Mark completed immediately after finishing. "
        "Only mark completed when the task fully succeeded — keep in_progress if there are errors. "
        "Update frequently so the user sees progress."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "todos": {
                "type": "array",
                "description": "List of todo items",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {
                            "type": "string",
                            "description": "Unique identifier for the todo",
                        },
                        "content": {
                            "type": "string",
                            "description": "Description of the todo task",
                        },
                        "status": {
                            "type": "string",
                            "enum": ["pending", "in_progress", "completed"],
                            "description": "Current status of the todo",
                        },
                    },
                    "required": ["id", "content", "status"],
                },
            }
        },
        "required": ["todos"],
    }

    def __init__(self) -> None:
        super().__init__()
        self._current_plan: list[dict[str, str]] = []

    async def execute(self, input_data: ToolInput) -> ToolOutput:
        todos = getattr(input_data, "todos", None)
        if not isinstance(todos, list):
            return ToolOutput(success=False, result=None, error="todos must be an array.")

        valid_statuses = {"pending", "in_progress", "completed"}
        for todo in todos:
            if not isinstance(todo, dict):
                return ToolOutput(success=False, result=None, error="Each todo must be an object.")
            for field in ("id", "content", "status"):
                if field not in todo:
                    return ToolOutput(success=False, result=None, error=f"Todo missing '{field}'.")
            if todo["status"] not in valid_statuses:
                return ToolOutput(
                    success=False, result=None,
                    error=f"Invalid status '{todo['status']}'. Must be one of: {', '.join(valid_statuses)}",
                )

        self._current_plan = [dict(t) for t in todos]

        lines = ["## Current Plan\n"]
        for t in todos:
            icon = {"pending": "[ ]", "in_progress": "[~]", "completed": "[x]"}.get(t["status"], "[ ]")
            lines.append(f"- {icon} {t['id']}: {t['content']}")
        return ToolOutput(success=True, result="\n".join(lines))

    @property
    def current_plan(self) -> list[dict[str, str]]:
        return self._current_plan
