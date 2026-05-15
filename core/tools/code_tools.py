"""Code execution and analysis tools"""

import asyncio
import os
import platform
import re
from pathlib import Path
from typing import Any

from core.tools.permissions import (
    PermissionContext,
    PermissionScope,
    RequiredPermission,
    ToolPermission,
)

from .base import BaseTool, ToolInput, ToolOutput
from .sandbox import get_backend, SandboxBackend, wrap_command
from core.config import Settings


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
- isBackground (OPTIONAL): Run non-blocking (default: false)
- delayMs (OPTIONAL): Delay before returning for background processes

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
            "isBackground": {
                "type": "boolean",
                "description": "Whether to run the command in the background (non-blocking)",
                "default": False
            },
            "delayMs": {
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

    def resolve_permission(self, args: dict, bypass_mode: bool = False) -> PermissionContext | None:
        """Resolve permission for bash command with dangerous pattern detection"""
        if bypass_mode:
            return None

        command = args.get("command", "")
        if not command:
            return None

        # Dangerous command patterns that ALWAYS require approval
        dangerous_patterns = [
            r"\brm\s+-[rf]{1,2}\b",          # rm -r, rm -rf, rm -fr
            r"\bdel\s+/[fq]\b",              # del /f, del /q
            r"\brmdir\s+/s\b",               # rmdir /s
            r"(?:^|[;&|]\s*)format\b",       # format (as standalone command only)
            r"\b(mkfs|diskpart)\b",          # disk operations
            r"\bdd\s+if=",                   # dd
            r">\s*/dev/sd",                  # write to disk
            r"\b(shutdown|reboot|poweroff)\b",  # system power
            r":\(\)\s*\{.*\};\s*:",          # fork bomb
            r"\bchmod\s+777\b",             # chmod 777
            r"\bchown\b",                   # chown
            r"\bsudo\s+rm\b",               # sudo rm
            r"\bsudo\s+dd\b",               # sudo dd
            r"\bsudo\s+mkfs\b",             # sudo mkfs
        ]

        for pattern in dangerous_patterns:
            if re.search(pattern, command.lower()):
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
        self.deny_patterns = [
            r"\brm\s+-[rf]{1,2}\b",          # rm -r, rm -rf, rm -fr
            r"\bdel\s+/[fq]\b",              # del /f, del /q
            r"\brmdir\s+/s\b",               # rmdir /s
            r"(?:^|[;&|]\s*)format\b",       # format (as standalone command only)
            r"\b(mkfs|diskpart)\b",          # disk operations
            r"\bdd\s+if=",                   # dd
            r">\s*/dev/sd",                  # write to disk
            r"\b(shutdown|reboot|poweroff)\b",  # system power
            r":\(\)\s*\{.*\};\s*:",          # fork bomb
            r"\bchmod\s+777\b",             # chmod 777
            r"\bchown\b",                   # chown
            r"\bsudo\s+rm\b",               # sudo rm
            r"\bsudo\s+dd\b",               # sudo dd
            r"\bsudo\s+mkfs\b",             # sudo mkfs
        ]
        self.allow_patterns = []
        self.restrict_to_workspace = False
        # Read sandbox setting from configuration
        settings = Settings()
        self._sandbox_backend: SandboxBackend | None = None
        self._backend_name = settings.sandbox_backend if settings.sandbox_enabled else ""
        self._backend_initialized = False
        self.path_append = ""
        self.allowed_env_keys = []
        self.working_dir = None

    def _get_sandbox_backend(self) -> SandboxBackend | None:
        """Get or create the sandbox backend"""
        if not self._backend_initialized:
            if self._backend_name:
                settings = Settings()
                kwargs = {}
                if self._backend_name == "opensandbox":
                    kwargs = {
                        "base_url": settings.sandbox_base_url,
                        "timeout": settings.sandbox_timeout,
                        "runtime": settings.sandbox_runtime
                    }
                self._sandbox_backend = get_backend(self._backend_name, **kwargs)
            self._backend_initialized = True
        return self._sandbox_backend

    async def execute(self, input_data: ToolInput) -> ToolOutput:
        try:
            # Support both camelCase and snake_case parameter names
            command = self._get_param(input_data, "command")
            isBackground = self._get_param(input_data, "isBackground") or False
            delayMs = self._get_param(input_data, "delayMs") or 0
            timeout = self._get_param(input_data, "timeout") or 30

            if not isinstance(command, str) or not command:
                return ToolOutput(
                    success=False,
                    result=None,
                    error="Invalid command: command parameter must be a non-empty string. Please provide a valid shell command."
                )

            if not isinstance(delayMs, int):
                delayMs = 0

            if not isinstance(timeout, int):
                timeout = 30

            # Check if we should bypass safety checks
            bypass_mode = False  # This would be set based on configuration/settings

            # Safety guard check
            guard_error = self._guard_command(command, bypass_mode)
            if guard_error:
                return ToolOutput(
                    success=False,
                    result=None,
                    error=guard_error
                )

            if isBackground:
                # Apply sandboxing for background processes
                backend = self._get_sandbox_backend()
                if backend:
                    if self.is_windows:
                        print(f"Warning: Sandbox backend is not supported on Windows; running unsandboxed")
                    else:
                        workspace = self.working_dir or os.getcwd()
                        command = wrap_command(self._backend_name, command, workspace, os.getcwd())

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

                if delayMs > 0:
                    await asyncio.sleep(delayMs / 1000.0)

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

        except FileNotFoundError:
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

    def _guard_command(self, command: str, bypass_mode: bool = False) -> str | None:
        """Best-effort safety guard for potentially destructive commands"""
        if bypass_mode:
            return None

        cmd = command.strip()
        lower = cmd.lower()

        # Check allow patterns first (they take priority)
        explicitly_allowed = bool(self.allow_patterns) and any(
            re.search(p, lower) for p in self.allow_patterns
        )

        if not explicitly_allowed:
            # Check deny patterns - these should always require approval
            for pattern in self.deny_patterns:
                if re.search(pattern, lower):
                    # Instead of blocking, we'll require approval
                    # This will be handled by the permission system
                    return None  # Let permission system handle this

        # Workspace restriction check
        if self.restrict_to_workspace:
            if "..\\" in cmd or "../" in cmd:
                return "Error: Command blocked by safety guard (path traversal detected)"

            # Extract absolute paths and check if they're outside workspace
            for raw_path in self._extract_absolute_paths(cmd):
                try:
                    expanded = os.path.expandvars(raw_path.strip())
                    p = Path(expanded).expanduser().resolve()

                    # Check if path is outside current working directory
                    cwd = Path.cwd()
                    if p.is_absolute() and cwd not in p.parents and p != cwd:
                        return "Error: Command blocked by safety guard (path outside working directory)"
                except Exception:
                    continue

        return None

    @staticmethod
    def _extract_absolute_paths(command: str) -> list[str]:
        """Extract absolute paths from command"""
        # Windows: match drive-root paths like `C:\` as well as `C:\path\to\file`
        win_paths = re.findall(r"[A-Za-z]:\\[^\s\"'|><;]*", command)
        # POSIX: /absolute only
        posix_paths = re.findall(r"(?:^|[\s|>'\"])(/[^\s\"'>;|<]+)", command)
        # POSIX/Windows home shortcut: ~
        home_paths = re.findall(r"(?:^|[\s>'\"])(~[^\s\"'>;|<]*)", command)
        return win_paths + posix_paths + home_paths


class RunTestsTool(BaseTool):
    """Tool for running tests"""

    def __init__(self):
        super().__init__()
        settings = Settings()
        self._sandbox_backend: SandboxBackend | None = None
        self._backend_name = settings.sandbox_backend if settings.sandbox_enabled else ""
        self._backend_initialized = False

    def _get_sandbox_backend(self) -> SandboxBackend | None:
        """Get or create the sandbox backend"""
        if not self._backend_initialized:
            if self._backend_name:
                settings = Settings()
                kwargs = {}
                if self._backend_name == "opensandbox":
                    kwargs = {
                        "base_url": settings.sandbox_base_url,
                        "timeout": settings.sandbox_timeout,
                        "runtime": settings.sandbox_runtime
                    }
                self._sandbox_backend = get_backend(self._backend_name, **kwargs)
            self._backend_initialized = True
        return self._sandbox_backend

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

            # Apply sandboxing if enabled
            is_windows = platform.system() == "Windows"
            backend = self._get_sandbox_backend()
            if backend:
                if is_windows:
                    print(f"Warning: Sandbox backend is not supported on Windows; running unsandboxed")
                else:
                    workspace = os.getcwd()
                    command = wrap_command(self._backend_name, command, workspace, os.getcwd())

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
