# Sandbox Execution

JARVIS provides optional sandboxed command execution for improved security when running shell commands.

## Configuration

Enable sandbox in `.jarvis/settings.json`:

```json
{
  "sandbox": {
    "enabled": true,
    "backend": "opensandbox",
    "base_url": "http://localhost:8080",
    "timeout": 30,
    "runtime": "opensandbox/code-interpreter:v1.0.2"
  }
}
```

### Settings

| Property | Type | Default | Description |
|----------|------|---------|-------------|
| `sandbox.enabled` | bool | `false` | Enable/disable sandbox execution |
| `sandbox.backend` | string | `"bwrap"` | Sandbox backend (`bwrap`, `opensandbox`, `disabled`) |
| `sandbox.base_url` | string | `"http://localhost:8080"` | OpenSandbox server URL |
| `sandbox.timeout` | int | `30` | Execution timeout in minutes |
| `sandbox.runtime` | string | `"opensandbox/code-interpreter:v1.0.2"` | Runtime image for OpenSandbox |

## Available Backends

| Backend | Description | Requirements |
|---------|-------------|--------------|
| `bwrap` | Local bubblewrap (default) | Linux, bubblewrap installed |
| `opensandbox` | Local OpenSandbox server | Python SDK, local server running |
| `disabled` | No sandboxing | None |

### Using OpenSandbox Backend

1. Install OpenSandbox SDK:
   ```bash
   pip install opensandbox
   ```

2. Start the local server:
   ```bash
   osb server start  # runs on http://localhost:8080
   ```

3. Configure JARVIS to use OpenSandbox in `.jarvis/settings.json`:
   ```json
   {
     "sandbox": {
       "enabled": true,
       "backend": "opensandbox"
     }
   }
   ```

## How It Works

When sandbox is enabled, shell commands executed via the `bash` tool and `run_tests` tool are wrapped using the configured backend:

### Bubblewrap (bwrap)

Creates a lightweight container namespace with:
- Isolated `/proc` and `/dev` mounts
- Read-only system directories (`/usr`, `/bin`, `/lib`, etc.)
- Workspace bind-mounted as read-write
- Isolated `/tmp` and parent directory

### OpenSandbox

Connects to a local OpenSandbox server which:
- Manages Docker/Kubernetes containers
- Provides pre-built runtime images
- Handles file operations and command execution
- Enforces network policies

### Windows

Sandbox is not supported on Windows. Commands run unsandboxed with a warning.

## Supported Tools

| Tool | Description | Sandbox Support | Notes |
|------|-------------|-----------------|-------|
| `bash` | Execute shell commands | ✓ | Shell commands wrapped with backend |
| `run_tests` | Run test suites | ✓ | Shell commands wrapped with backend |
| `grep` | Search files (ripgrep) | ✗ | Uses `exec` with arg list, not shell |
| `worktree` | Git worktree operations | ✗ | Uses `exec` with arg list, not shell |
| `repl` | Python REPL | N/A | Uses in-process `eval`/`exec`, has own security |

### Why `repl` doesn't need sandbox

The `repl` tool executes Python code directly in-process via `eval()`/`exec()` with its own security model:
- Pattern blocklist prevents dangerous operations
- Restricted builtins remove dangerous functions
- Safe import allowlist only allows whitelisted modules

This is appropriate for its use case and provides equivalent security isolation.

## Security Considerations

- Sandbox provides isolation but does not replace proper security practices
- `bwrap` backend requires Linux and bubblewrap to be installed
- `opensandbox` backend requires a local server (not a cloud service)
- May not work in all environments (e.g., restricted containers)

## Troubleshooting

- **"command not found" for `bwrap`**: Install bubblewrap (`sudo apt install bubblewrap` on Debian/Ubuntu)
- **Permission denied**: Check if your user has access to `/dev` and network devices
- **OpenSandbox SDK not found**: Install with `pip install opensandbox`
- **OpenSandbox connection failed**: Ensure `osb server start` is running
- **Windows warning**: Sandbox is not supported on Windows; commands run unsandboxed