"""Extension that overrides the bash tool to run via SSH.

When the ``--ssh-host`` flag is set, this extension replaces the
built-in ``bash`` tool with one that executes commands on a remote
server instead of locally.
"""

__version__ = "1.0.0"
__description__ = "Replaces bash tool with SSH-based execution"


async def jarvis(api):
    """Register an SSH-based bash tool override."""
    import asyncio

    class SSHBashTool:
        name = "bash"
        description = "Execute shell commands on a remote server (SSH)"
        input_schema = {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The command to execute on the remote server",
                },
                "timeout": {
                    "type": "integer",
                    "description": "Timeout in seconds",
                    "default": 30,
                },
            },
            "required": ["command"],
        }

        def __init__(self):
            self.host = None  # Set via settings

        async def execute(self, input_data: dict) -> dict:
            command = input_data.get("command", "")
            timeout = input_data.get("timeout", 30)

            if not self.host:
                return {
                    "success": False,
                    "result": None,
                    "error": "SSH host not configured. Set 'extensions.ssh_tools.host' in .jarvis/settings.json",
                }

            try:
                ssh_cmd = [
                    "ssh", self.host,
                    "cd", "/workspace", "&&", command,
                ]
                proc = await asyncio.create_subprocess_exec(
                    *ssh_cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                try:
                    stdout, stderr = await asyncio.wait_for(
                        proc.communicate(), timeout=timeout,
                    )
                except asyncio.TimeoutError:
                    proc.kill()
                    return {
                        "success": False,
                        "result": None,
                        "error": f"Command timed out after {timeout}s",
                    }

                output = stdout.decode("utf-8", errors="replace")
                error = stderr.decode("utf-8", errors="replace")

                return {
                    "success": proc.returncode == 0,
                    "result": output,
                    "error": error if proc.returncode != 0 else None,
                }
            except Exception as e:
                return {
                    "success": False,
                    "result": None,
                    "error": str(e),
                }

    # When registered, this overrides the built-in 'bash' tool
    api.tools(SSHBashTool())
