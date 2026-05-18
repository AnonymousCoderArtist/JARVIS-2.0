"""Notify tool — out-of-band notifications.

Ported from huggingface/ml-intern agent/tools/notify_tool.py.

NOTE: In the JARVIS extension context this is a simplified version that
logs notifications rather than sending them via a messaging gateway.
"""

from __future__ import annotations

import logging

from jarvis.api import BaseTool, ToolInput, ToolOutput

logger = logging.getLogger(__name__)


class NotifyTool(BaseTool):
    name = "notify"
    description = (
        "Send an out-of-band notification to configured messaging destinations. "
        "Use this only when the user explicitly asked for proactive notifications "
        "or when the task requires reporting progress outside the chat. "
        "Destinations must be named server-side configs such as 'slack.ops'."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "destinations": {
                "type": "array",
                "description": "Named messaging destinations to notify.",
                "items": {"type": "string"},
                "minItems": 1,
            },
            "message": {
                "type": "string",
                "description": "Main notification body.",
            },
            "title": {
                "type": "string",
                "description": "Optional short title line.",
            },
            "severity": {
                "type": "string",
                "enum": ["info", "success", "warning", "error"],
                "description": "Notification severity label.",
            },
        },
        "required": ["destinations", "message"],
    }

    async def execute(self, input_data: ToolInput) -> ToolOutput:
        destinations = getattr(input_data, "destinations", None)
        message = getattr(input_data, "message", None)
        title = getattr(input_data, "title", None)
        severity = getattr(input_data, "severity", "info")

        if not isinstance(destinations, list) or not destinations:
            return ToolOutput(success=False, result=None, error="destinations must be a non-empty array.")
        if not message or not isinstance(message, str):
            return ToolOutput(success=False, result=None, error="message must be a non-empty string.")

        # In the JARVIS extension context we log the notification.
        # A full implementation would route to a messaging gateway.
        for dest in destinations:
            prefix = f"[{severity.upper()}]"
            if title:
                prefix += f" {title}"
            logger.info("Notify %s: %s %s", dest, prefix, message)

        return ToolOutput(
            success=True,
            result=f"Notification sent to {', '.join(destinations)}: {message}",
        )
