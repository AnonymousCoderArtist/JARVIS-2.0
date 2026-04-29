"""Code execution and analysis tools"""

import asyncio

from .base import BaseTool, ToolInput, ToolOutput


class BashTool(BaseTool):
    """Tool for executing bash commands (OpenClaude style)"""

    name = "bash"
    description = """Execute a bash shell command and return the output. Use this for running commands, scripts, and system operations.

Usage:
- Use for running shell commands, scripts, and system operations
- Supports background execution with is_background parameter for long-running processes
- Set timeout parameter to limit execution time (default 30 seconds)
- Use delay_ms parameter to control when background process output is returned
- Background processes can be monitored using list_background_processes and read_background_output tools
- Common uses: running tests, building projects, installing dependencies, git operations
- Always check command output for errors and handle them appropriately
- Use absolute paths or ensure you're in the correct working directory"""
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
    """Tool for running tests (OpenClaude style)"""

    name = "run_tests"
    description = """Run tests using pytest or unittest frameworks. Use this to execute test suites and verify code correctness.

Usage:
- Specify the path to test file or directory to run tests on
- Choose framework: pytest (default) or unittest
- Use args parameter for additional command-line arguments (e.g., -v for verbose, -k for keyword filtering)
- Common pytest args: -v (verbose), -k (keyword filter), -x (stop on first failure), --cov (coverage)
- Common unittest args: -v (verbose), -k (keyword filter)
- Analyze test failures systematically to identify and fix issues
- Re-run tests after making fixes to verify the changes"""
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
            path = getattr(input_data, "path", None)
            framework = getattr(input_data, "framework", "pytest")
            args = getattr(input_data, "args", "")

            if not isinstance(path, str) or not path:
                return ToolOutput(
                    success=False,
                    result=None,
                    error="Invalid test path"
                )

            if not isinstance(framework, str):
                framework = "pytest"

            if not isinstance(args, str):
                args = ""

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
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await process.communicate()

            output = stdout.decode() if stdout else ""
            if stderr:
                output += f"\nErrors:\n{stderr.decode()}"

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
