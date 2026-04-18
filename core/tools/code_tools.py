"""Code execution and analysis tools"""

import subprocess
import asyncio
from typing import Dict, List
from .base import BaseTool, ToolInput, ToolOutput


class BashTool(BaseTool):
    """Tool for executing bash commands"""

    name = "bash"
    description = "Execute a bash command and return the output. Supports background execution."
    input_schema = {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "Bash shell command to execute",
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
            command = input_data.command
            is_background = getattr(input_data, "is_background", False)
            delay_ms = getattr(input_data, "delay_ms", 0)
            timeout = getattr(input_data, "timeout", 30)

            if is_background:
                process = await asyncio.create_subprocess_shell(
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
                    result=f"Command started in background with PID {pid}",
                    metadata={"pid": pid, "command": command}
                )

            # Standard foreground execution
            process = await asyncio.create_subprocess_shell(
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
                    error=f"Command execution timed out after {timeout} seconds"
                )

        except Exception as e:
            return ToolOutput(
                success=False,
                result=None,
                error=f"Failed to execute bash command: {str(e)}"
            )


class RunTestsTool(BaseTool):
    """Tool for running tests"""

    name = "run_tests"
    description = "Run tests using pytest or unittest"
    input_schema = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to test file or directory to run tests on",
                "minLength": 1
            },
            "framework": {
                "type": "string",
                "description": "Test framework to use for running tests",
                "enum": ["pytest", "unittest"],
                "default": "pytest"
            },
            "args": {
                "type": "string",
                "description": "Additional command-line arguments to pass to the test runner"
            }
        },
        "required": ["path"]
    }

    async def execute(self, input_data: ToolInput) -> ToolOutput:
        try:
            path = input_data.path
            framework = getattr(input_data, "framework", "pytest")
            args = getattr(input_data, "args", "")

            if framework == "pytest":
                command = f"pytest {path} {args}"
            elif framework == "unittest":
                command = f"python -m unittest {path} {args}"
            else:
                return ToolOutput(
                    success=False,
                    result=None,
                    error=f"Unsupported test framework: {framework}"
                )

            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                text=True
            )

            stdout, stderr = await process.communicate()

            output = stdout
            if stderr:
                output += f"\nErrors:\n{stderr}"

            return ToolOutput(
                success=process.returncode == 0,
                result=output,
                metadata={"return_code": process.returncode, "framework": framework}
            )

        except Exception as e:
            return ToolOutput(
                success=False,
                result=None,
                error=f"Failed to run tests: {str(e)}"
            )
