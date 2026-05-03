"""Background process management tools"""

import asyncio
from typing import Any

from .base import BaseTool, ToolInput, ToolOutput

# Global registry for background processes
# In a real system, this might be handled by a more robust manager
_background_processes: dict[int, dict[str, Any]] = {}

def register_background_process(process: asyncio.subprocess.Process, command: str) -> int:
    pid = process.pid
    _background_processes[pid] = {
        "process": process,
        "command": command,
        "stdout": [],
        "stderr": []
    }

    # Start background task to capture output
    asyncio.create_task(_capture_output(pid))
    return pid

async def _capture_output(pid: int):
    process_info = _background_processes.get(pid)
    if not process_info:
        return

    process = process_info["process"]

    async def read_stream(stream, target_list):
        while True:
            line = await stream.readline()
            if not line:
                break
            target_list.append(line.decode().strip())

    await asyncio.gather(
        read_stream(process.stdout, process_info["stdout"]),
        read_stream(process.stderr, process_info["stderr"])
    )
    await process.wait()

class ListBackgroundProcessesTool(BaseTool):
    """Tool for listing active background processes"""

    name = "list_background_processes"
    description = """List active and completed background processes.

Parameters: None

Returns PID, command, and status (running/finished) for all background processes
started with the bash tool's is_background option."""
    input_schema = {
        "type": "object",
        "properties": {},
        "description": "Lists all active and recently completed background processes"
    }

    async def execute(self, input_data: ToolInput) -> ToolOutput:
        results = []
        for pid, info in _background_processes.items():
            process = info["process"]
            status = "running" if process.returncode is None else f"finished (code {process.returncode})"
            results.append({
                "pid": pid,
                "command": info["command"],
                "status": status
            })

        return ToolOutput(
            success=True,
            result=results,
            metadata={"count": len(results)}
        )

class ReadBackgroundOutputTool(BaseTool):
    """Tool for reading output of a background process"""

    name = "read_background_output"
    description = """Read stdout/stderr output from background processes.

Parameters:
- pid (required): Process ID (PID) of the background process
- lines (optional): Number of lines from end of output (default: 100)

Returns captured stdout and stderr. Use with list_background_processes to find PIDs."""
    input_schema = {
        "type": "object",
        "properties": {
            "pid": {
                "type": "integer",
                "description": "Process ID (PID) of the background process to read output from",
                "minimum": 1
            },
            "lines": {
                "type": "integer",
                "description": "Number of lines to read from the end of the output log",
                "default": 100,
                "minimum": 1
            }
        },
        "required": ["pid"]
    }

    def _get_param(self, input_data: ToolInput, *names) -> Any:
        """Get parameter using multiple possible names"""
        for name in names:
            value = getattr(input_data, name, None)
            if value is not None:
                return value
        return None

    async def execute(self, input_data: ToolInput) -> ToolOutput:
        # Support both camelCase and snake_case parameter names
        pid = self._get_param(input_data, "pid")
        limit = self._get_param(input_data, "lines", "limit") or 100

        if pid not in _background_processes:
            return ToolOutput(
                success=False,
                result=None,
                error=f"No background process found with PID {pid}. Please use list_background_processes to see available PIDs and ensure the process is still running."
            )

        info = _background_processes[pid]
        stdout = info["stdout"][-limit:]
        stderr = info["stderr"][-limit:]

        output = "\n".join(stdout)
        if stderr:
            output += "\nErrors:\n" + "\n".join(stderr)

        return ToolOutput(
            success=True,
            result=output,
            metadata={
                "pid": pid,
                "command": info["command"],
                "stdout_lines": len(stdout),
                "stderr_lines": len(stderr)
            }
        )
