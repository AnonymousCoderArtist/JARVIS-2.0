# MCP (Model Context Protocol) Integration

JARVIS supports MCP (Model Context Protocol) servers to extend its capabilities with external tools. MCP is an open protocol developed by Anthropic that allows applications to securely connect to external data sources and tools.

## Configuration

### Configuration File

MCP servers are configured in `.mcp.json` in your working directory or `~/.jarvis/mcp_servers.json`:

```json
{
  "mcpServers": {
    "server-name": {
      "name": "server-name",
      "command": "npx",
      "args": ["-y", "server-package@latest"],
      "transport": "stdio"
    }
  }
}
```

### Configuration Formats

JARVIS supports multiple configuration formats:

**Claude Code style** (`.mcp.json`):
```json
{
  "mcpServers": {
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/home/user/docs"]
    }
  }
}
```

**Array style** (`.mcp.json` or `mcp_servers.json`):
```json
[
  {
    "name": "filesystem",
    "command": "npx",
    "args": ["-y", "@modelcontextprotocol/server-filesystem", "/home/user/docs"]
  }
]
```

## Transport Types

### stdio (Default)

For local MCP servers that run as subprocesses:

```json
{
  "name": "my-server",
  "command": "npx",
  "args": ["-y", "my-mcp-server@latest"]
}
```

### HTTP/SSE

For remote MCP servers accessible via HTTP:

```json
{
  "name": "my-server",
  "url": "http://localhost:59686/mcp",
  "transport": "http"
}
```

## Configuration Options

| Property | Type | Default | Description |
|----------|------|---------|-------------|
| `name` | string | required | Unique server identifier |
| `command` | string | "" | Command to execute (stdio transport) |
| `args` | string[] | `[]` | Arguments passed to command |
| `env` | object | `{}` | Environment variables |
| `transport` | string | `"stdio"` | `"stdio"`, `"http"`, or `"sse"` |
| `url` | string | `"" | URL for HTTP/SSE transport |
| `timeout` | number | `30` | Connection timeout in seconds |
| `disabled` | boolean | `false` | Skip this server |
| `disabled_tools` | string[] | `[]` | Tool names to exclude |

## Example Configurations

### Filesystem Server

```json
{
  "mcpServers": {
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/home/user/docs", "/home/user/projects"]
    }
  }
}
```

### Database Server

```json
{
  "mcpServers": {
    "sqlite": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-sqlite"],
      "env": {
        "DB_PATH": "./data.db"
      }
    }
  }
}
```

### Remote HTTP Server

```json
{
  "mcpServers": {
    "my-api": {
      "url": "http://localhost:8080/mcp",
      "transport": "http"
    }
  }
}
```

### Multiple Servers

```json
{
  "mcpServers": {
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/home/user"]
    },
    "sqlite": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-sqlite"]
    },
    "memory": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-memory"]
    }
  }
}
```

## How It Works

1. **Discovery**: On startup, JARVIS loads MCP configurations from `.mcp.json`
2. **Connection**: Each server is connected via stdio or HTTP transport
3. **Tool Registration**: Available tools are wrapped as JARVIS tools with `mcp_` prefix
4. **Execution**: Tools are called through the MCP client with arguments passed through

## Tool Naming

MCP tools are named with a server prefix:

```
mcp_<server-name>_<tool-name>
```

For example, a `read_resource` tool from a `filesystem` server becomes `mcp_filesystem_read_resource`.

## Built-in MCP Servers

### Official MCP Servers

- `@modelcontextprotocol/server-filesystem` - Access to local filesystem
- `@modelcontextprotocol/server-sqlite` - SQLite database queries
- `@modelcontextprotocol/server-memory` - Persistent key-value storage
- `@modelcontextprotocol/server-brave-search` - Web search via Brave
- `@modelcontextprotocol/server-github` - GitHub repository access
- `@modelcontextprotocol/server-gitlab` - GitLab repository access
- `@modelcontextprotocol/server-puppeteer` - Browser automation

### Installing MCP Servers

Many MCP servers are available as npm packages:

```bash
# Install globally for use with JARVIS
npm install -g @modelcontextprotocol/server-filesystem

# Or run directly via npx (recommended)
npx -y @modelcontextprotocol/server-filesystem ~/docs
```

## Troubleshooting

### Connection Failed

- Verify the server command runs correctly outside JARVIS
- Check that required dependencies are installed
- Ensure environment variables are set correctly

### Tool Not Found

- Verify the server name matches the configuration
- Check the tool is exposed by the MCP server
- Restart JARVIS to reload MCP configurations

### Permission Errors

- Check file permissions for stdio servers
- Verify network access for HTTP servers
- Some servers may require additional configuration

## Security Considerations

- MCP servers run with the same permissions as JARVIS
- Be cautious when adding servers from untrusted sources
- Review server code before connecting if possible
- Use `disabled_tools` to restrict specific tools per server

## Disabling Servers

To disable a server without removing its configuration:

```json
{
  "mcpServers": {
    "my-server": {
      "name": "my-server",
      "command": "npx",
      "args": ["-y", "my-server"],
      "disabled": true
    }
  }
}
```

## Disabling Specific Tools

To disable specific tools from a server:

```json
{
  "mcpServers": {
    "my-server": {
      "name": "my-server",
      "command": "npx",
      "args": ["-y", "my-server"],
      "disabled_tools": ["dangerous_tool", "write_file"]
    }
  }
}
```