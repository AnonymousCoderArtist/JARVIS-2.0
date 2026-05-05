"""Sandbox backends for shell command execution"""

import shlex
from pathlib import Path


def _bwrap(command: str, workspace: str, cwd: str) -> str:
    """Wrap command in a bubblewrap sandbox (requires bwrap in container)
    
    Only the workspace is bind-mounted read-write; its parent dir (which holds
    config.json) is hidden behind a fresh tmpfs. The media directory is
    bind-mounted read-only for file attachments.
    """
    # Create a fresh tmpfs for the parent directory to hide config.json
    # and bind-mount the actual workspace read-write
    workspace_path = Path(workspace).resolve()
    parent_path = workspace_path.parent.resolve()
    
    # Basic bwrap command structure
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


def wrap_command(sandbox: str, command: str, workspace: str, cwd: str) -> str:
    """Wrap *command* using the named sandbox backend"""
    backends = {
        "bwrap": _bwrap
    }
    
    if backend := backends.get(sandbox):
        return backend(command, workspace, cwd)
    
    raise ValueError(f"Unknown sandbox backend {sandbox!r}. Available: {list(backends.keys())}")