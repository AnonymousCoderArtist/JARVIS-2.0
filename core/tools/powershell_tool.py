"""PowerShell execution tool (OpenClaude style)"""

import asyncio

from .base import BaseTool, ToolInput, ToolOutput


class PowerShellTool(BaseTool):
    """Tool for executing PowerShell commands (OpenClaude style)"""

    name = "powershell"
    description = """Execute a PowerShell command and return the output. Use this for Windows-specific operations and administrative tasks.

Usage:
- Use for running PowerShell commands, scripts, and Windows system operations
- Supports background execution with is_background parameter for long-running processes
- Set timeout parameter to limit execution time (default 30 seconds)
- Use delay_ms parameter to control when background process output is returned
- Background processes can be monitored using list_background_processes and read_background_output tools
- Common uses: Windows system administration, IIS management, Active Directory operations, Windows-specific automation
- Always check command output for errors and handle them appropriately
- This tool is only available on Windows systems"""
    input_schema = {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "PowerShell command to execute",
                "minLength": 1
            },
            "is_background": {
                "type": "boolean",
                "description": "Whether to run the command in the background (non-blocking)",
                "default": False
            },
            "delay_ms": {
                "type": "integer",
                "description": "Delay in milliseconds after starting background process before returning",
                "default": 0,
                "minimum": 0
            },
            "timeout": {
                "type": "integer",
                "description": "Maximum execution time in seconds before timing out",
                "default": 30,
                "minimum": 1
            }
        },
        "required": ["command"]
    }

    async def execute(self, input_data: ToolInput) -> ToolOutput:
        try:
            command = getattr(input_data, "command", None)
            is_background = getattr(input_data, "is_background", False)
            delay_ms = getattr(input_data, "delay_ms", 0)
            timeout = getattr(input_data, "timeout", 30)

            if not isinstance(command, str) or not command:
                return ToolOutput(
                    success=False,
                    result=None,
                    error="Invalid command"
                )

            if not isinstance(delay_ms, int):
                delay_ms = 0

            if not isinstance(timeout, int):
                timeout = 30

            if is_background:
                process = await asyncio.create_subprocess_exec(
                    "powershell",
                    "-Command",
                    command,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )

                # Register background process
                from .background_tools import register_background_process
                pid = register_background_process(process, command)

                if delay_ms > 0:
                    await asyncio.sleep(delay_ms / 1000.0)

                return ToolOutput(
                    success=True,
                    result=f"PowerShell command started in background with PID {pid}",
                    metadata={"pid": pid, "command": command}
                )

            # Standard foreground execution
            process = await asyncio.create_subprocess_exec(
                "powershell",
                "-Command",
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=timeout
                )

                output = stdout.decode() if stdout else ""
                if stderr:
                    output += f"\nErrors:\n{stderr.decode()}"

                return ToolOutput(
                    success=process.returncode == 0,
                    result=output,
                    metadata={"return_code": process.returncode}
                )

            except asyncio.TimeoutError:
                process.kill()
                return ToolOutput(
                    success=False,
                    result=None,
                    error=f"PowerShell execution timed out after {timeout} seconds"
                )

        except FileNotFoundError:
            return ToolOutput(
                success=False,
                result=None,
                error="PowerShell not found. This tool is only available on Windows."
            )
        except Exception as e:
            return ToolOutput(
                success=False,
                result=None,
                error=f"Failed to execute PowerShell command: {str(e)}"
            )
