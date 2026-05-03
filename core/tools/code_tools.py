"""Code execution and analysis tools"""

import asyncio
import platform
import sys
from typing import Any

from .base import BaseTool, ToolInput, ToolOutput
from core.tools.permissions import PermissionContext, PermissionScope, RequiredPermission, ToolPermission


class BashTool(BaseTool):
    """Tool for executing shell commands (bash on Unix, PowerShell on Windows)"""

    name = "bash"
    description = """Execute shell commands with timeout and background support.

WHEN TO USE:
- Running build/test commands: "pytest tests/"
- Git operations: "git status", "git diff"
- System commands: "ls -la", "pwd"
- Installing packages: "pip install package"

Parameters:
- command (REQUIRED): Shell command to execute
- timeout (OPTIONAL): Max execution time in seconds (default: 30)
- is_background (OPTIONAL): Run non-blocking (default: false)
- delay_ms (OPTIONAL): Delay before returning for background processes

Platform: Uses bash on Unix/Linux/macOS, PowerShell on Windows.
Returns stdout/stderr. Dangerous commands (rm -rf, etc.) require approval."""
    input_schema = {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "Shell command to execute (bash syntax on Unix, PowerShell syntax on Windows)",
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

    def _get_param(self, input_data: ToolInput, *names) -> Any:
        """Get parameter using multiple possible names"""
        for name in names:
            value = getattr(input_data, name, None)
            if value is not None:
                return value
        return None

    def resolve_permission(self, args: dict) -> PermissionContext | None:
        """Resolve permission for bash command with dangerous pattern detection"""
        command = args.get("command", "")
        if not command:
            return None

        # Dangerous command patterns that require special approval
        dangerous_patterns = [
            "rm -rf",
            "rm -r",
            "delete",
            "format",
            "truncate",
            "dd if=",
            "mkfs",
            "fdisk",
            "shred",
            "wipe",
            "> /dev/",
            "chmod 777",
            "chown",
            "sudo rm",
            "sudo dd",
            "sudo mkfs",
        ]

        for pattern in dangerous_patterns:
            if pattern in command.lower():
                return PermissionContext(
                    permission=ToolPermission.ASK,
                    required_permissions=[
                        RequiredPermission(
                            scope=PermissionScope.COMMAND_PATTERN,
                            invocation_pattern=pattern,
                            session_pattern=command,
                            label=f"execute dangerous command '{command}'",
                        )
                    ],
                )

        return None

    def __init__(self):
        super().__init__()
        self.is_windows = platform.system() == "Windows"
        self.shell = "powershell" if self.is_windows else "/bin/bash"

    async def execute(self, input_data: ToolInput) -> ToolOutput:
        try:
            # Support both camelCase and snake_case parameter names
            command = self._get_param(input_data, "command")
            is_background = self._get_param(input_data, "is_background") or False
            delay_ms = self._get_param(input_data, "delay_ms") or 0
            timeout = self._get_param(input_data, "timeout") or 30

            if not isinstance(command, str) or not command:
                return ToolOutput(
                    success=False,
                    result=None,
                    error="Invalid command: command parameter must be a non-empty string. Please provide a valid shell command."
                )

            if not isinstance(delay_ms, int):
                delay_ms = 0

            if not isinstance(timeout, int):
                timeout = 30

            if is_background:
                if self.is_windows:
                    process = await asyncio.create_subprocess_exec(
                        "powershell",
                        "-Command",
                        command,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE
                    )
                else:
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
                    metadata={"pid": pid, "command": command, "shell": self.shell}
                )

            # Standard foreground execution
            if self.is_windows:
                process = await asyncio.create_subprocess_exec(
                    "powershell",
                    "-Command",
                    command,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
            else:
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
                stderr_output = stderr.decode() if stderr else ""
                
                # Set error field when command fails
                error_msg = None
                if process.returncode != 0:
                    error_msg = stderr_output if stderr_output else f"Command failed with return code {process.returncode}"
                    if output:
                        output += f"\nErrors:\n{stderr_output}"

                return ToolOutput(
                    success=process.returncode == 0,
                    result=output,
                    error=error_msg,
                    metadata={"return_code": process.returncode, "shell": self.shell}
                )

            except asyncio.TimeoutError:
                process.kill()
                return ToolOutput(
                    success=False,
                    result=None,
                    error=f"Command execution timed out after {timeout} seconds"
                )

        except FileNotFoundError as e:
            shell_name = "PowerShell" if self.is_windows else "bash"
            return ToolOutput(
                success=False,
                result=None,
                error=f"{shell_name} not found on this system. Please ensure the required shell is installed and available in your PATH."
            )
        except Exception as e:
            return ToolOutput(
                success=False,
                result=None,
                error=f"Failed to execute command: {str(e)}. Please check if the command syntax is correct for your shell ({'PowerShell' if self.is_windows else 'bash'}) and if you have the necessary permissions."
            )


class RunTestsTool(BaseTool):
    """Tool for running tests"""

    name = "run_tests"
    description = """Run tests using pytest or unittest framework.

WHEN TO USE:
- After making code changes to verify correctness
- Before committing code
- To catch regressions

Parameters:
- path (REQUIRED): Path to test file or directory
- framework (OPTIONAL): 'pytest' (default) or 'unittest'
- args (OPTIONAL): Additional CLI arguments like '-v', '-k test_name'

Returns: Test output with pass/fail results.
Example: {"path": "tests/", "framework": "pytest", "args": "-v"}"""
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
            path = self._get_param(input_data, "path")
            framework = self._get_param(input_data, "framework") or "pytest"
            args = self._get_param(input_data, "args") or ""

            if not isinstance(path, str) or not path:
                return ToolOutput(
                    success=False,
                    result=None,
                    error="Invalid test path: path parameter must be a non-empty string. Please provide a valid path to test file or directory."
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
                    error=f"Unsupported test framework: {framework}. Please use 'pytest' or 'unittest'. Ensure the test framework is installed in your environment."
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
                error=f"Failed to run tests: {str(e)}. Please ensure the test framework is installed, the test path is correct, and you have permission to execute tests."
            )
