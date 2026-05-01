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
    description = """List all active and recently completed background processes. Use this to monitor long-running commands started with the bash tool's is_background parameter.

Usage:
- Lists all background processes with their PID, command, and status
- Shows running processes and recently completed ones
- Use this to check the status of background tasks
- Combine with read_background_output to see process output
- Useful for monitoring servers, builds, tests, and other long-running operations"""
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
    description = """Read the output log of a background shell process. Use this to check the progress and results of long-running commands.

Usage:
- Provide the PID of the background process to read output from
- Use the lines parameter to control how many lines to read from the end of the output
- Returns both stdout and stderr output
- Use this to monitor progress of background tasks
- Combine with list_background_processes to find process PIDs
- Useful for checking build logs, test results, server output, etc."""
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

    async def execute(self, input_data: ToolInput) -> ToolOutput:
        pid = getattr(input_data, "pid", None)
        limit = getattr(input_data, "lines", 100)

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
