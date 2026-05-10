"""Sandbox backends for shell command execution"""

import asyncio
import shlex
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path


@dataclass
class SandboxResult:
    """Result from sandbox execution"""
    stdout: str
    stderr: str
    exit_code: int
    success: bool


class SandboxBackend(ABC):
    """Abstract base class for sandbox backends"""

    @abstractmethod
    async def execute(
        self,
        command: str,
        cwd: str,
        timeout: int = 30,
        workspace: str = ""
    ) -> SandboxResult:
        """Execute a command in the sandbox"""
        pass

    @abstractmethod
    async def cleanup(self) -> None:
        """Clean up sandbox resources"""
        pass


class LocalSandboxBackend(SandboxBackend):
    """Local sandbox using bubblewrap (bwrap)"""

    def __init__(self):
        self._process = None

    def _wrap_command(self, command: str, workspace: str, cwd: str) -> str:
        """Wrap command in a bubblewrap sandbox (requires bwrap in container)"""
        workspace_path = Path(workspace).resolve()

        bwrap_cmd = [
            "bwrap",
            "--dev", "/dev",
            "--proc", "/proc",
            "--ro-bind", "/usr", "/usr",
            "--ro-bind", "/lib", "/lib",
            "--ro-bind", "/lib64", "/lib64",
            "--tmpfs", "/tmp",
            "--bind", f"{workspace_path}", f"{workspace_path}",
            "--chdir", cwd,
            "/bin/sh", "-c", command
        ]
        return shlex.join(bwrap_cmd)

    async def execute(
        self,
        command: str,
        cwd: str,
        timeout: int = 30,
        workspace: str = ""
    ) -> SandboxResult:
        """Execute command using bubblewrap"""
        wrapped = self._wrap_command(command, workspace, cwd)

        try:
            proc = await asyncio.create_subprocess_shell(
                wrapped,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            self._process = proc

            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=timeout
                )
                return SandboxResult(
                    stdout=stdout.decode() if stdout else "",
                    stderr=stderr.decode() if stderr else "",
                    exit_code=proc.returncode or 0,
                    success=proc.returncode == 0
                )
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                return SandboxResult(
                    stdout="",
                    stderr="Command timed out",
                    exit_code=-1,
                    success=False
                )
        except FileNotFoundError:
            # bwrap not found, fall back to direct execution
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd
            )
            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=timeout
                )
                return SandboxResult(
                    stdout=stdout.decode() if stdout else "",
                    stderr=stderr.decode() if stderr else "",
                    exit_code=proc.returncode or 0,
                    success=proc.returncode == 0
                )
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                return SandboxResult(
                    stdout="",
                    stderr="Command timed out",
                    exit_code=-1,
                    success=False
                )

    async def cleanup(self) -> None:
        """Clean up resources"""
        if self._process and self._process.returncode is None:
            self._process.kill()
            await self._process.wait()


class OpenSandboxBackend(SandboxBackend):
    """OpenSandbox backend (requires local OpenSandbox server)"""

    def __init__(self, base_url: str = "http://localhost:8080", timeout: int = 30, runtime: str = "opensandbox/code-interpreter:v1.0.2"):
        self.base_url = base_url
        self.timeout = timeout
        self.runtime = runtime
        self._sandbox = None
        self._sdk_available = self._check_sdk()

    def _check_sdk(self) -> bool:
        """Check if OpenSandbox SDK is available"""
        try:
            import opensandbox  # type: ignore
            return True
        except ImportError:
            return False

    async def _get_sandbox(self):
        """Create or get the OpenSandbox sandbox"""
        if not self._sdk_available:
            raise RuntimeError(
                "OpenSandbox backend requires the opensandbox SDK. "
                "Install with: pip install opensandbox"
            )
        import opensandbox  # type: ignore

        if self._sandbox is None:
            self._sandbox = await opensandbox.Sandbox.create(
                self.runtime,
                timeout=timedelta(minutes=self.timeout // 60) if self.timeout >= 60 else None,
            )
        return self._sandbox

    async def execute(
        self,
        command: str,
        cwd: str,
        timeout: int = 30,
        workspace: str = ""
    ) -> SandboxResult:
        """Execute command using OpenSandbox"""
        try:
            sandbox = await self._get_sandbox()

            # Execute command
            result = await sandbox.commands.run(
                command,
                timeout=timeout or self.timeout
            )

            return SandboxResult(
                stdout=result.get("stdout", ""),
                stderr=result.get("stderr", ""),
                exit_code=result.get("exit_code", 0),
                success=result.get("exit_code", 1) == 0
            )
        except Exception as e:
            return SandboxResult(
                stdout="",
                stderr=str(e),
                exit_code=-1,
                success=False
            )

    async def cleanup(self) -> None:
        """Clean up sandbox resources"""
        if self._sandbox is not None:
            try:
                await self._sandbox.kill()
            except Exception:
                pass
            self._sandbox = None


def get_backend(backend_name: str, **kwargs) -> SandboxBackend | None:
    """Factory function to create sandbox backends"""
    backends: dict[str, type[SandboxBackend] | None] = {
        "bwrap": LocalSandboxBackend,
        "opensandbox": OpenSandboxBackend,
        "disabled": None
    }

    if backend_name not in backends:
        raise ValueError(
            f"Unknown sandbox backend {backend_name!r}. "
            f"Available: {list(backends.keys())}"
        )

    backend_cls = backends[backend_name]
    if backend_cls is None:
        return None
    return backend_cls(**kwargs)


def wrap_command(sandbox: str, command: str, workspace: str, cwd: str) -> str:
    """Legacy function - now wraps command locally for direct execution"""
    # This is kept for backwards compatibility but now just returns the command
    # The actual sandboxing is handled by the async backend
    _ = sandbox, workspace, cwd  # suppress unused warnings
    return command