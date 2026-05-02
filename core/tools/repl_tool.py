"""REPL tool for interactive Python execution (OpenClaude style)"""

import asyncio
from typing import Any

from .base import BaseTool, ToolInput, ToolOutput


class REPLTool(BaseTool):
    """Tool for interactive Python REPL execution (OpenClaude style)"""

    name = "repl"
    description = """Execute Python code in an interactive REPL context with state persistence. Use this for testing code snippets, data analysis, and interactive Python work.

Usage:
- Execute Python code with state persistence across calls
- Use session_id to maintain separate REPL sessions
- State (variables, imports, functions) persists within a session
- Use timeout parameter to limit execution time (default 30 seconds)
- Useful for testing code, data analysis, quick prototyping
- Print statements and output are captured and returned
- Multiple sessions can be maintained for different contexts
- Use clear_session to reset a session when needed"""
    input_schema = {
        "type": "object",
        "properties": {
            "code": {"type": "string", "description": "Python code to execute"},
            "session_id": {"type": "string", "description": "Session ID for state persistence (optional)"},
            "timeout": {"type": "integer", "description": "Execution timeout in seconds (default: 30)"}
        },
        "required": ["code"]
    }

    # Class-level session storage
    _sessions: dict[str, dict] = {}

    def _get_param(self, input_data: ToolInput, *names) -> Any:
        """Get parameter using multiple possible names"""
        for name in names:
            value = getattr(input_data, name, None)
            if value is not None:
                return value
        return None

    async def execute(self, input_data: ToolInput) -> ToolOutput:
        try:
            # Support both camelCase and snake_case parameter names
            code = self._get_param(input_data, "code")
            session_id = self._get_param(input_data, "session_id", "sessionId") or "default"
            timeout = self._get_param(input_data, "timeout") or 30

            if not isinstance(code, str) or not code:
                return ToolOutput(
                    success=False,
                    result=None,
                    error="Invalid code: code parameter must be a non-empty string. Please provide valid Python code to execute."
                )

            if not isinstance(session_id, str) or not session_id:
                session_id = "default"

            if not isinstance(timeout, int):
                timeout = 30

            # Get or create session
            if session_id not in self._sessions:
                self._sessions[session_id] = {
                    "globals": {},
                    "locals": {}
                }

            session = self._sessions[session_id]

            # Execute code in session context
            exec_globals = session["globals"]
            exec_locals = session["locals"]

            try:
                # Capture output
                output_buffer = []

                # Custom print function to capture output
                def custom_print(*args, **kwargs):
                    output_buffer.append(' '.join(str(arg) for arg in args))

                exec_globals['print'] = custom_print

                # Execute code with timeout
                await asyncio.wait_for(
                    asyncio.to_thread(exec, code, exec_globals, exec_locals),
                    timeout=timeout
                )

                output = '\n'.join(output_buffer) if output_buffer else "Code executed successfully (no output)"

                return ToolOutput(
                    success=True,
                    result=output,
                    metadata={"session_id": session_id}
                )

            except asyncio.TimeoutError:
                return ToolOutput(
                    success=False,
                    result=None,
                    error=f"REPL execution timed out after {timeout} seconds"
                )
            except Exception as e:
                return ToolOutput(
                    success=False,
                    result=None,
                    error=f"REPL execution error: {str(e)}"
                )

        except Exception as e:
            return ToolOutput(
                success=False,
                result=None,
                error=f"Failed to execute REPL code: {str(e)}. Please check if your Python code is syntactically correct and if required modules are installed."
            )

    def clear_session(self, session_id: str = "default"):
        """Clear a REPL session"""
        if session_id in self._sessions:
            del self._sessions[session_id]

    def list_sessions(self) -> list[str]:
        """List all active REPL sessions"""
        return list(self._sessions.keys())
