"""REPL tool for interactive Python execution (OpenClaude style)"""

import asyncio
from typing import Dict, List, Optional
from .base import BaseTool, ToolInput, ToolOutput


class REPLTool(BaseTool):
    """Tool for interactive Python REPL execution (OpenClaude style)"""

    name = "repl"
    description = "Execute Python code in an interactive REPL context with state persistence"
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
    _sessions: Dict[str, Dict] = {}

    async def execute(self, input_data: ToolInput) -> ToolOutput:
        try:
            code = input_data.code
            session_id = getattr(input_data, "session_id", "default")
            timeout = getattr(input_data, "timeout", 30)

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
                error=f"Failed to execute REPL code: {str(e)}"
            )

    def clear_session(self, session_id: str = "default"):
        """Clear a REPL session"""
        if session_id in self._sessions:
            del self._sessions[session_id]

    def list_sessions(self) -> List[str]:
        """List all active REPL sessions"""
        return list(self._sessions.keys())
