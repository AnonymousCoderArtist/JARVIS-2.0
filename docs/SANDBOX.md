# Sandbox Execution

JARVIS provides optional sandboxed command execution for improved security when running shell commands.

## Configuration

Enable sandbox in `.jarvis/settings.json`:

```json
{
  "sandbox": {
    "enabled": true,
    "backend": "bwrap"
  }
}
```

### Settings

| Property | Type | Default | Description |
|----------|------|---------|-------------|
| `enabled` | bool | `false` | Enable/disable sandbox execution |
| `backend` | string | `"bwrap"` | Sandbox backend (`bwrap` for bubblewrap) |

## How It Works

When sandbox is enabled, shell commands executed via the `bash` tool and `run_tests` tool are wrapped using the configured backend:

1. **Bubblewrap (bwrap)**: Creates a lightweight container namespace with:
   - Isolated `/proc` and `/dev` mounts
   - Read-only system directories (`/usr`, `/bin`, `/lib`, etc.)
   - Workspace bind-mounted as read-write
   - Isolated `/tmp` and parent directory

2. **Windows**: Sandbox is not supported on Windows. Commands run unsandboxed with a warning.

## Supported Tools

| Tool | Description | Sandbox Support | Notes |
|------|-------------|-----------------|-------|
| `bash` | Execute shell commands | ✓ | Shell commands wrapped with bwrap |
| `run_tests` | Run test suites | ✓ | Shell commands wrapped with bwrap |
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
- Currently only `bwrap` backend is implemented
- Requires bubblewrap to be installed on the system
- May not work in all environments (e.g., restricted containers)

## Example

```bash
# With sandbox enabled, this command runs in an isolated environment
jarvis --cli
> # Run a build command
> Make some changes to a file
```

## Troubleshooting

- **"command not found" for `bwrap`**: Install bubblewrap (`sudo apt install bubblewrap` on Debian/Ubuntu)
- **Permission denied**: Check if your user has access to `/dev` and network devices
- **Windows warning**: Sandbox is not supported on Windows; commands run unsandboxed