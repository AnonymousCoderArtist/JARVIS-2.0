"""Extension that replaces bash/file/edit operations with SSH-based backends.

When this extension is loaded, all tool operations (read, write, edit, bash)
are transparently forwarded to a remote server over SSH.

Configuration (in ``.jarvis/settings.json``)::

    {
      "extensions": {
        "ssh_operations": {
          "host": "user@remote-server",
          "key_path": "~/.ssh/id_rsa",
          "remote_root": "/workspace"
        }
      }
    }
"""

from core.tools.operations import BashOperations, FileOperations

__version__ = "1.0.0"
__description__ = "Transparent SSH backend for all file and bash operations"


async def jarvis_extension(api):
    """Swap the operations backends to SSH-forwarded versions."""
    import asyncio
    import os

    # Read config from extension settings
    config = getattr(api, "_config", {})
    host = config.get("host", os.environ.get("JARVIS_SSH_HOST", ""))
    key_path = config.get("key_path", os.environ.get("JARVIS_SSH_KEY", ""))
    remote_root = config.get("remote_root", os.environ.get("JARVIS_SSH_ROOT", "/workspace"))

    if not host:
        # Silently skip — extension loaded but SSH not configured
        return

    # ------------------------------------------------------------------
    # SSH Bash Operations
    # ------------------------------------------------------------------

    class SSHBashOps(BashOperations):
        """Run shell commands via SSH."""

        async def run(self, command, timeout=None, cwd=None, env=None):
            ssh_cmd = self._build_ssh(command, cwd)
            proc = await asyncio.create_subprocess_exec(
                *ssh_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(), timeout=timeout or 60
                )
            except asyncio.TimeoutError:
                proc.kill()
                stdout, stderr = await proc.communicate()
                return {"stdout": "", "stderr": "SSH timeout", "exit_code": -1}

            return {
                "stdout": stdout.decode("utf-8", errors="replace"),
                "stderr": stderr.decode("utf-8", errors="replace"),
                "exit_code": proc.returncode or 0,
            }

        async def spawn(self, command, cwd=None, env=None):
            raise NotImplementedError("SSH spawn not available")

        async def terminate(self, pid):
            pass  # SSH process management not supported

        def _build_ssh(self, command, cwd):
            cmd = ["ssh", host]
            if key_path:
                cmd.extend(["-i", os.path.expanduser(key_path)])
            remote_cd = f"cd {remote_root}"
            if cwd:
                remote_cd = f"cd {cwd}"
            cmd.append(f"{remote_cd} && {command}")
            return cmd

    # ------------------------------------------------------------------
    # SSH File Operations
    # ------------------------------------------------------------------

    class SSHFileOps(FileOperations):
        """Read/write files via SFTP or SSH cat/tee."""

        async def read_file(self, path, offset=1, limit=None):
            abs_path = self._resolve(path)
            proc = await asyncio.create_subprocess_exec(
                "ssh", host, f"cat {abs_path}",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()
            content = stdout.decode("utf-8", errors="replace")

            if offset > 1 or limit is not None:
                lines = content.splitlines(keepends=True)
                start = max(0, offset - 1)
                end = start + limit if limit else None
                content = "".join(lines[start:end])
            return content

        async def write_file(self, path, content):
            abs_path = self._resolve(path)
            escaped = content.replace("'", "'\\''")
            proc = await asyncio.create_subprocess_exec(
                "ssh", host, f"mkdir -p $(dirname {abs_path}) && cat > {abs_path}",
                stdin=asyncio.subprocess.PIPE,
            )
            await proc.communicate(content.encode("utf-8"))

        async def file_exists(self, path):
            abs_path = self._resolve(path)
            proc = await asyncio.create_subprocess_exec(
                "ssh", host, f"test -f {abs_path} && echo yes",
                stdout=asyncio.subprocess.PIPE,
            )
            out, _ = await proc.communicate()
            return out.decode().strip() == "yes"

        async def list_dir(self, path):
            abs_path = self._resolve(path)
            proc = await asyncio.create_subprocess_exec(
                "ssh", host, f"ls -la {abs_path}",
                stdout=asyncio.subprocess.PIPE,
            )
            out, _ = await proc.communicate()
            return [{"name": line, "type": "unknown"} for line in out.decode().splitlines()]

        async def delete_file(self, path):
            abs_path = self._resolve(path)
            await asyncio.create_subprocess_exec("ssh", host, f"rm -f {abs_path}")

        def _resolve(self, path):
            p = str(path)
            if not p.startswith("/"):
                return f"{remote_root}/{p}"
            return p

    # ------------------------------------------------------------------
    # Swap backends via the API
    # ------------------------------------------------------------------

    ops = api.operations_registry
    if ops is not None:
        ops.set_bash_ops(SSHBashOps(), origin="ssh_operations")
        ops.set_file_ops(SSHFileOps(), origin="ssh_operations")
