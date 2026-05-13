# MCP (Model Context Protocol) Integration

JARVIS uses a **lazy MCP** architecture inspired by [pi-mcp-adapter](https://github.com/nicobailon/pi-mcp-adapter). Instead of eagerly connecting to all MCP servers at startup and registering every tool individually (costing thousands of tokens), JARVIS uses a single **`mcp` proxy tool** and **on-demand connections** — reducing token usage from 10k+ to ~200 tokens.

## Architecture Overview

```
┌─────────────────────────────────────────────────────┐
│                    JARVIS Agent                      │
│                                                     │
│  ┌─────────┐    ┌──────────────────────────────┐   │
│  │  mcp    │───▶│  MCPProxyTool                │   │
│  │ (proxy) │    │  status / list / search /    │   │
│  └─────────┘    │  describe / call / connect    │   │
│                 │  resources / prompts / sampling │   │
│                 └──────────┬───────────────────┘   │
│                            │                        │
│                 ┌──────────▼───────────────────┐   │
│                 │  MCPLifecycleManager          │   │
│                 │  lazy / eager / keep-alive    │   │
│                 └──────────┬───────────────────┘   │
│                            │                        │
│                 ┌──────────▼───────────────────┐   │
│                 │  MCPMetadataCache            │   │
│                 │  ~/.jarvis/mcp-cache.json    │   │
│                 └──────────┬───────────────────┘   │
│                            │                        │
│         ┌──────────────────┼──────────────────┐    │
│         ▼                  ▼                  ▼    │
│  ┌───────────┐    ┌───────────┐    ┌───────────┐   │
│  │ MCPClient  │    │ MCPClient  │    │ MCPClient  │   │
│  │ (stdio)    │    │ (http)     │    │ (sse)      │   │
│  └───────────┘    └───────────┘    └───────────┘   │
│                                                     │
│  ┌─────────────────────────────────────────────┐   │
│  │  MCP Authentication (OAuth/Bearer/API Key) │   │
│  └─────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────┘
```

### Key Design Principles

| Principle | How |
|-----------|-----|
| **Token efficiency** | Single `mcp` proxy tool instead of dozens of individual tools |
| **Lazy connections** | Servers connect only when their tools are called |
| **Offline discovery** | Metadata cache enables search/describe without live connections |
| **Authentication** | OAuth2, Bearer tokens, and API key support |
| **Resources/Prompts** | Full support for MCP resources and prompt templates |
| **Sampling** | Server-initiated LLM calls via the sampling protocol |
| **Auto-disconnect** | Idle servers disconnect after a configurable timeout |

---

## Configuration

### Configuration File

MCP servers are configured in `.mcp.json` in your working directory or `~/.jarvis/mcp_servers.json`:

```json
{
  "mcpServers": {
    "server-name": {
      "command": "npx",
      "args": ["-y", "server-package@latest"],
      "lifecycle": "lazy",
      "idleTimeout": 15,
      "directTools": false
    }
  }
}
```

### Configuration Formats

JARVIS supports multiple configuration formats:

**Claude Code style** (`.mcp.json`) — recommended:
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

---

## Authentication

JARVIS supports three authentication mechanisms for MCP servers: **OAuth2**, **Bearer tokens**, and **API keys**. Authentication is configured per-server in the `.mcp.json` file.

### OAuth2 (Full Authorization Code Flow)

OAuth2 provides the most secure authentication with automatic token refresh and PKCE support. Use this for servers that require user authorization.

```json
{
  "mcpServers": {
    "my-oauth-server": {
      "url": "https://api.example.com/mcp",
      "transport": "http",
      "auth": {
        "type": "oauth",
        "clientId": "my-client-id",
        "clientSecret": "your-client-secret",
        "scope": "read write",
        "redirectUri": "http://localhost:8765/callback",
        "clientMetadataUrl": "https://auth.example.com/.well-known/oauth-metadata"
      }
    }
  }
}
```

#### OAuth Configuration Properties

| Property | Type | Description |
|----------|------|-------------|
| `type` | string | Must be `"oauth"` |
| `clientId` | string | OAuth client identifier |
| `clientSecret` | string | OAuth client secret |
| `scope` | string | Space-separated OAuth scopes (default: `openid profile email`) |
| `redirectUri` | string | Callback URL for OAuth flow (default: `http://localhost:8765/callback`) |
| `clientMetadataUrl` | string | URL to fetch dynamic client metadata |

#### How OAuth Works in JARVIS

1. When connecting to an OAuth-protected server, JARVIS initiates the OAuth2 authorization code flow
2. A browser window opens for user authorization
3. A local callback server receives the authorization code
4. Tokens are exchanged and stored in `~/.jarvis/auth/<server-name>.json`
5. Tokens are automatically refreshed when they expire

### Bearer Tokens (Static Token)

For servers that use simple bearer token authentication:

```json
{
  "mcpServers": {
    "my-bearer-server": {
      "url": "https://api.example.com/mcp",
      "transport": "http",
      "auth": {
        "type": "bearer",
        "token": "your-bearer-token-here",
        "headerName": "Authorization",
        "headerPrefix": "Bearer"
      }
    }
  }
}
```

#### Bearer Token from Environment Variable

For security, store the token in an environment variable:

```json
{
  "mcpServers": {
    "my-bearer-server": {
      "url": "https://api.example.com/mcp",
      "transport": "http",
      "auth": {
        "type": "bearer",
        "tokenEnvVar": "MCP_BEARER_TOKEN"
      }
    }
  }
}
```

### API Keys

For servers that use API key authentication in custom headers:

```json
{
  "mcpServers": {
    "my-api-key-server": {
      "url": "https://api.example.com/mcp",
      "transport": "http",
      "auth": {
        "type": "api_key",
        "token": "your-api-key-here",
        "headerName": "X-API-Key"
      }
    }
  }
}
```

#### API Key Configuration Properties

| Property | Type | Default | Description |
|----------|------|---------|-------------|
| `type` | string | — | Must be `"bearer"` or `"api_key"` |
| `token` | string | — | The static token value |
| `tokenEnvVar` | string | — | Environment variable name to read token from |
| `headerName` | string | `"Authorization"` | HTTP header name for the token |
| `headerPrefix` | string | `"Bearer"` | Prefix for the header value (ignored for `api_key`) |

### Auth Configuration Reference

```json
{
  "auth": {
    "type": "oauth|bearer|api_key",
    "clientId": "...",
    "clientSecret": "...",
    "scope": "openid profile email",
    "redirectUri": "http://localhost:8765/callback",
    "clientMetadataUrl": "https://auth.example.com/metadata",
    "token": "static-token-or-empty",
    "tokenEnvVar": "ENV_VAR_NAME",
    "headerName": "Authorization",
    "headerPrefix": "Bearer"
  }
}
```

### Checking Token Status

You can check the authentication status of a server:

```python
from core.tools.mcp_auth import get_token_status

status = get_token_status("my-server")
# Returns: {"has_tokens": True, "is_expired": False, "auth_type": "oauth", "expires_at": 1234567890.0}
```

---

## Transport Types

### stdio (Default)

For local MCP servers that run as subprocesses:

```json
{
  "command": "npx",
  "args": ["-y", "my-mcp-server@latest"]
}
```

### HTTP

For remote MCP servers accessible via HTTP:

```json
{
  "url": "http://localhost:59686/mcp",
  "transport": "http"
}
```

### SSE

For servers using Server-Sent Events:

```json
{
  "url": "https://example.com/sse",
  "transport": "sse"
}
```

---

## Configuration Reference

### Server Properties

| Property | Type | Default | Description |
|----------|------|---------|-------------|
| `name` | string | *required* | Unique server identifier (auto-set from key in `mcpServers`) |
| `command` | string | `""` | Command to execute (stdio transport) |
| `args` | string[] | `[]` | Arguments passed to command |
| `env` | object | `{}` | Environment variables for the subprocess |
| `transport` | string | `"stdio"` | `"stdio"`, `"http"`, or `"sse"` |
| `url` | string | `""` | URL for HTTP/SSE transport |
| `timeout` | number | `30` | Connection timeout in seconds |
| `disabled` | boolean | `false` | Skip this server entirely |
| `disabled_tools` | string[] | `[]` | Tool names to exclude (legacy, prefer `excludeTools`) |

### Lazy MCP Properties

| Property | Type | Default | Description |
|----------|------|---------|-------------|
| `lifecycle` | string | `"lazy"` | Server lifecycle mode (see below) |
| `idleTimeout` | number | `15` | Minutes before idle disconnect (lazy mode only) |
| `directTools` | boolean \| string[] | `false` | Promote tools to first-class (see below) |
| `excludeTools` | string[] | `[]` | Tool names to hide from both proxy and direct tools |
| `autoDiscoverCapabilities` | boolean | `true` | Query resources/prompts on connect |

---

## Lifecycle Modes

JARVIS supports three server lifecycle modes, controlled by the `lifecycle` property:

### `lazy` (Default)

Server connects **only when a tool is called** and disconnects after `idleTimeout` minutes of inactivity. This is the most token-efficient and resource-friendly mode.

```json
{
  "mcpServers": {
    "exa": {
      "url": "https://mcp.exa.ai/mcp",
      "transport": "http",
      "lifecycle": "lazy",
      "idleTimeout": 15
    }
  }
}
```

- ✅ Zero startup cost — server isn't connected until needed
- ✅ Auto-disconnect after idle period frees resources
- ✅ Tools discoverable via metadata cache even when disconnected
- ⚠️ First tool call has a small connection latency

### `eager`

Server connects at **JARVIS startup**. If the connection fails, it stays disconnected — no auto-reconnect.

```json
{
  "mcpServers": {
    "critical-api": {
      "url": "http://localhost:8080/mcp",
      "transport": "http",
      "lifecycle": "eager"
    }
  }
}
```

- ✅ No first-call latency — already connected
- ✅ Immediate feedback if server is unavailable
- ⚠️ Fails silently — no reconnection if the server dies
- ⚠️ Adds startup time

### `keep-alive`

Server connects at startup and **auto-reconnects** if the connection drops. A health check runs every 30 seconds to detect disconnections.

```json
{
  "mcpServers": {
    "database": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-sqlite"],
      "lifecycle": "keep-alive"
    }
  }
}
```

- ✅ Always connected — reconnected automatically on failure
- ✅ Best for critical servers that must always be available
- ⚠️ Highest resource usage — stays connected permanently

---

## The `mcp` Proxy Tool

The `mcp` proxy tool is the **primary interface** for interacting with MCP servers. Instead of registering every tool individually (each costing ~150-300 tokens in the system prompt), a single `mcp` tool is registered (~200 tokens total).

### Mode Reference

The proxy tool routes to different modes based on which parameters are provided. Modes are resolved in **precedence order**:

| Precedence | Mode | Primary Parameter | Description |
|:---:|------|-------------------|-------------|
| 1 | **call** | `tool` | Execute an MCP tool |
| 2 | **connect** | `connect` | Lazy-connect a server + refresh cache |
| 3 | **describe** | `describe` | Show a tool's full schema |
| 4 | **search** | `search` | Find tools by name/description |
| 5 | **list** | `server` | List tools for a server |
| 6 | **resources** | `resources` | List resources from a server |
| 7 | **read_resource** | `read_resource` | Read a specific resource by URI |
| 8 | **prompts** | `prompts` | List prompts from a server |
| 9 | **get_prompt** | `get_prompt` | Render a prompt template |
| 10 | **status** | *(none)* | Show all servers and connection status |

### Status Mode

Show the status of all configured MCP servers:

```
mcp
```

Returns a summary like:
```
## MCP Server Status

  🔴 exa — [12t, 5r, 3p] — lazy, disconnected
  🟢 chrome-devtools — [45t] 🔒oauth — eager, connected
  🔴 my-api-server — [8t] 🔒bearer — lazy, disconnected

  Total: 3 servers, 1 connected, 65 tools, 5 resources, 3 prompts in cache
```

The status shows:
- Connection status (🟢 connected / 🔴 disconnected)
- Capability counts: `[tools, resources, prompts]`
- Auth type: `🔒oauth`, `🔒bearer`, `🔒api_key`
- Lifecycle mode

### List Mode

List all tools from a specific server:

```
mcp server="exa"
```

Returns:
```
## Tools from 'exa'

  - **web_search**: Search the web using Exa
  - **get_contents**: Get full page contents from URLs
  - **find_similar**: Find similar pages to a given URL

  3 tools
```

### Search Mode

Search for tools across all servers (or a specific one):

```
mcp search="web search"
```

With options:
```
mcp search="search" regex=true include_schemas=false server="exa"
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `search` | string | — | Search query (substring match) |
| `regex` | boolean | `false` | Treat query as regex pattern |
| `include_schemas` | boolean | `true` | Include parameter schemas in results |
| `server` | string | — | Filter to a specific server |

### Describe Mode

Show full details and parameter schema for a specific tool:

```
mcp describe="web_search"
```

Returns:
```
## Tool: mcp_exa_web_search

  **Server**: exa
  **Original name**: web_search
  **Description**: Search the web using Exa AI

  **Parameters**:
    - `query` (string) (required): The search query
    - `numResults` (integer): Number of results to return
```

### Call Mode

Execute an MCP tool. The server will be lazy-connected if needed.

```
mcp tool="web_search" args='{"query": "python asyncio patterns"}'
```

With explicit server (disambiguates tools with the same name across servers):
```
mcp tool="web_search" args='{"query": "hello"}' server="exa"
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `tool` | string | — | Tool name to call (original or prefixed name) |
| `args` | string | `"{}"` | JSON string of arguments |
| `server` | string | — | Server name (auto-detected if omitted) |

### Connect Mode

Explicitly connect to a lazy server and refresh its metadata cache:

```
mcp connect="exa"
```

This is useful when you want to ensure a server is connected before making multiple calls, or to refresh the tool cache after a server has been updated.

---

## Resources

MCP servers can expose **resources** — data that clients can read. JARVIS supports discovering, listing, and reading resources via the proxy tool.

### List Resources

List all resources from a server:

```
mcp resources="exa"
```

Returns:
```
## Resources from 'exa'

  - **docs**: [jarvis://docs] (text/markdown): JARVIS documentation
  - **config**: [jarvis://config] (application/json): Current configuration

  2 resources
```

### Read a Resource

Read a specific resource by its URI:

```
mcp read_resource="jarvis://config"
```

Returns:
```
## Resource: jarvis://config

  **MIME Type**: application/json

  {"model": "gpt-4o", "theme": "dark"}
```

### Resource Configuration

Resources are automatically discovered when a server connects (if the server advertises the `resources` capability). The metadata is cached for offline access.

---

## Prompts

MCP servers can expose **prompt templates** — parameterized prompts that clients can render. JARVIS supports discovering, listing, and rendering prompts.

### List Prompts

List all prompts from a server:

```
mcp prompts="my-server"
```

Returns:
```
## Prompts from 'my-server'

  - **analyze_code**: Analyze code structure (args: language, codebase)
  - **review_pr**: Review a pull request (args: pr_url)

  2 prompts
```

### Render a Prompt

Render a prompt with arguments:

```
mcp get_prompt="analyze_code" args='{"language": "python", "codebase": "./src"}'
```

Returns:
```
## Prompt: analyze_code

  👤 **user**: Please analyze the Python codebase in ./src...
  🤖 **assistant**: Here's my analysis of the codebase...
```

---

## Sampling (Server-Initiated LLM Calls)

The **sampling protocol** allows MCP servers to request JARVIS to generate LLM responses. This is useful for servers that need AI assistance to fulfill user requests.

### How It Works

1. An MCP tool on the server calls the `SamplingCapability` 
2. JARVIS intercepts the request and routes it through the configured LLM provider
3. The response is sent back to the server

### Configuration

To enable sampling support, pass an LLM provider when initializing the MCP registry:

```python
from core.tools.mcp_adapter import MCPRegistry, MCPServerConfig

registry = MCPRegistry(tool_registry=tool_registry, use_proxy=True)

configs = [MCPServerConfig.from_dict(d) for d in mcp_config_dicts]

# Pass the LLM provider for sampling support
results = await registry.initialize(
    configs, 
    llm_provider=llm_provider,  # Your LLM provider instance
    model="gpt-4o"
)
```

### Requirements

- The MCP server must advertise `sampling` capability
- An LLM provider must be configured
- The sampling handler supports:
  - Message history from the server
  - System prompts
  - Temperature and max_tokens settings

---

## Direct Tools

While the proxy tool is the default and most token-efficient approach, some tools are used so frequently that they benefit from being **promoted to first-class tools** — registered individually alongside built-in tools.

This is controlled by the `directTools` property:

### All Tools as Direct Tools

```json
{
  "mcpServers": {
    "chrome-devtools": {
      "command": "npx",
      "args": ["-y", "chrome-devtools-mcp@latest"],
      "directTools": true
    }
  }
}
```

This registers every tool from `chrome-devtools` as an individual tool (e.g., `mcp_chrome-devtools_click`, `mcp_chrome-devtools_navigate_page`, etc.).

### Specific Tools as Direct Tools

```json
{
  "mcpServers": {
    "aether-mcp-bridge": {
      "url": "http://localhost:59686/mcp",
      "transport": "http",
      "directTools": [
        "copilot_searchCodebase",
        "copilot_searchWorkspaceSymbols",
        "mcp_deepwiki_ask_question"
      ]
    }
  }
}
```

Only the listed tools are registered individually; all other tools remain accessible through the `mcp` proxy.

### Token Cost Comparison

| Approach | Token Cost | Example |
|----------|-----------|---------|
| All tools via proxy | ~200 tokens total | 50 tools → 200 tokens |
| All tools as direct | ~150-300 tokens **each** | 50 tools → ~10,000 tokens |
| Mix (3 direct + rest proxy) | ~200 + 3×200 = ~800 tokens | Best of both worlds |

### Excluding Tools

Hide tools from both proxy and direct tool registration:

```json
{
  "mcpServers": {
    "my-server": {
      "command": "npx",
      "args": ["-y", "my-server"],
      "directTools": true,
      "excludeTools": ["internal_debug", "admin_reset"]
    }
  }
}
```

---

## Metadata Cache

JARVIS maintains a persistent metadata cache at `~/.jarvis/mcp-cache.json` that stores tool definitions, resources, and prompts from all configured MCP servers. This enables **offline capability discovery** — the LLM can search, list, and describe tools/resources/prompts without needing a live server connection.

### How It Works

1. When a server connects (either eagerly or lazily), its capabilities are saved to the cache
2. The cache includes a config hash for validation — if the server config changes, the cache is invalidated
3. Search, list, describe, and resource/prompt modes work from the cache when the server is disconnected
4. Call mode triggers a lazy connection if the server is offline

### Cache Validation

The cache uses a SHA-256 hash of the server's `command`, `args`, `url`, `transport`, and `env` fields. If any of these change, the cached metadata is considered stale and the server must reconnect to refresh it.

### Cache Contents

The cache stores:
- **Tools**: name, original_name, description, input_schema, server_name
- **Resources**: uri, name, description, mime_type, server_name  
- **Prompts**: name, description, arguments, server_name

---

## Capabilities Negotiation

When an MCP server connects, JARVIS automatically negotiates its capabilities:

| Capability | Description |
|------------|-------------|
| `tools` | Server provides callable tools |
| `resources` | Server provides readable resources |
| `prompts` | Server provides prompt templates |
| `sampling` | Server can request LLM responses |
| `logging` | Server supports logging |
| `completions` | Server supports completion suggestions |
| `tasks` | Server supports background tasks |

The proxy tool's status output shows which capabilities are available for each server.

---

## Example Configurations

### Minimal Lazy Setup

The simplest configuration — servers are lazy by default:

```json
{
  "mcpServers": {
    "exa": {
      "url": "https://mcp.exa.ai/mcp",
      "transport": "http"
    }
  }
}
```

### OAuth-Authenticated Server

```json
{
  "mcpServers": {
    "secure-api": {
      "url": "https://api.secure.example.com/mcp",
      "transport": "http",
      "lifecycle": "keep-alive",
      "auth": {
        "type": "oauth",
        "clientId": "jarvis-client",
        "clientSecret": "secret123",
        "scope": "read write admin",
        "redirectUri": "http://localhost:8765/callback"
      }
    }
  }
}
```

### Bearer Token Server

```json
{
  "mcpServers": {
    "internal-api": {
      "url": "https://internal.example.com/mcp",
      "transport": "http",
      "auth": {
        "type": "bearer",
        "tokenEnvVar": "INTERNAL_API_TOKEN"
      }
    }
  }
}
```

### Full-Featured Setup

```json
{
  "mcpServers": {
    "exa": {
      "url": "https://mcp.exa.ai/mcp",
      "transport": "http",
      "lifecycle": "lazy",
      "idleTimeout": 30,
      "directTools": true
    },
    "chrome-devtools": {
      "command": "npx",
      "args": ["-y", "chrome-devtools-mcp@latest", "--headless"],
      "lifecycle": "eager"
    },
    "database": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-sqlite"],
      "env": { "DB_PATH": "./data.db" },
      "lifecycle": "keep-alive"
    },
    "aether-mcp-bridge": {
      "url": "http://localhost:59686/mcp",
      "transport": "http",
      "directTools": [
        "copilot_searchCodebase",
        "mcp_deepwiki_ask_question"
      ],
      "excludeTools": ["internal_health"]
    }
  }
}
```

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

---

## Tool Naming

MCP tools follow a consistent naming convention:

```
mcp_<server-name>_<tool-name>
```

For example, a `web_search` tool from the `exa` server becomes `mcp_exa_web_search`.

When using the proxy tool, you can reference tools by either their **original name** (`web_search`) or **prefixed name** (`mcp_exa_web_search`). The proxy will auto-detect the server for original names.

---

## How It Works (Startup Flow)

```
1. Load .mcp.json configurations
          │
2. For each server:
          │
          ├── lifecycle=lazy     → Register metadata from cache only
          │                       Don't connect yet
          │
          ├── lifecycle=eager    → Connect immediately
          │                       Fail silently on error
          │
          └── lifecycle=keep-alive → Connect immediately
                                    + Start health check loop
                                    + Auto-reconnect on failure
          │
3. Register the `mcp` proxy tool
          │
4. Register direct tools (if configured)
          │
5. Ready — LLM can now use `mcp` tool to discover and call tools,
   read resources, render prompts, and more
```

### On Tool Call (Lazy Connect)

```
LLM calls: mcp tool="web_search" args='{"query":"hello"}'
          │
          ├── Server "exa" already connected?
          │   └── Yes → Execute tool directly
          │
          └── No (lazy mode)?
              ├── Connect to "exa" server (with auth if configured)
              ├── Refresh metadata cache (tools, resources, prompts)
              ├── Start idle timer
              └── Execute tool
```

### Idle Timeout

```
No tool calls for idleTimeout minutes...
          │
          ├── Idle timer fires
          ├── Server is disconnected
          └── Metadata cache preserved (tools/resources/prompts still discoverable)
```

---

## Built-in MCP Servers

### Official MCP Servers

| Server | Description |
|--------|-------------|
| `@modelcontextprotocol/server-filesystem` | Access to local filesystem |
| `@modelcontextprotocol/server-sqlite` | SQLite database queries |
| `@modelcontextprotocol/server-memory` | Persistent key-value storage |
| `@modelcontextprotocol/server-brave-search` | Web search via Brave |
| `@modelcontextprotocol/server-github` | GitHub repository access |
| `@modelcontextprotocol/server-gitlab` | GitLab repository access |
| `@modelcontextprotocol/server-puppeteer` | Browser automation |

### Installing MCP Servers

Many MCP servers are available as npm packages:

```bash
# Run directly via npx (recommended — no install needed)
npx -y @modelcontextprotocol/server-filesystem ~/docs

# Or install globally
npm install -g @modelcontextprotocol/server-filesystem
```

---

## Disabling Servers

To disable a server without removing its configuration:

```json
{
  "mcpServers": {
    "my-server": {
      "command": "npx",
      "args": ["-y", "my-server"],
      "disabled": true
    }
  }
}
```

---

## Troubleshooting

### Connection Failed

- Verify the server command runs correctly outside JARVIS: `npx -y my-mcp-server`
- Check that required dependencies (Node.js, npm) are installed
- Ensure environment variables are set correctly
- For HTTP servers, verify the URL is accessible: `curl http://localhost:59686/mcp`
- Check authentication configuration if the server requires auth

### Authentication Issues

- For OAuth: Ensure the redirect URI is accessible (no firewall blocking localhost)
- For Bearer/API Key: Verify the token is correct and not expired
- Check `~/.jarvis/auth/<server-name>.json` for token storage status
- Use `get_token_status()` to check token validity

### Tool Not Found

- Use `mcp` (status mode) to check which servers are connected
- Use `mcp search="tool_name"` to search across all servers
- Use `mcp connect="server-name"` to manually connect a lazy server
- Check `.mcp.json` for typos in server names or tool exclusions

### Resource/Prompt Not Found

- Use `mcp resources="server"` to list available resources
- Use `mcp prompts="server"` to list available prompts
- Ensure the server is connected (or use `mcp connect="server"`)
- Check if the server advertises the capability in status output

### Proxy Tool Not Registered

- Ensure `use_proxy=True` (default) when creating `MCPRegistry`
- Check that `.mcp.json` exists and is valid JSON
- Look for error messages during initialization

### Idle Disconnects Too Fast

- Increase `idleTimeout` (in minutes) in your `.mcp.json`
- For servers used frequently, consider `lifecycle: "eager"` or `"keep-alive"`

### Permission Errors

- Check file permissions for stdio servers
- Verify network access for HTTP servers
- Ensure OAuth redirect port (default 8765) is not in use
- Some servers may require additional configuration or API keys

---

## Security Considerations

- MCP servers run with the same permissions as JARVIS
- Be cautious when adding servers from untrusted sources
- Review server code before connecting if possible
- Use `excludeTools` to hide dangerous tools
- Use `disabled: true` to temporarily disable servers without removing configuration
- Store sensitive tokens in environment variables rather than config files
- The metadata cache (`~/.jarvis/mcp-cache.json`) contains tool/resource/prompt schemas but no sensitive data
- OAuth tokens are stored in `~/.jarvis/auth/<server-name>.json` — keep this directory secure

---

## Internal Architecture

### Core Classes

| Class | File | Purpose |
|-------|------|---------|
| `MCPServerConfig` | `core/tools/mcp_adapter.py` | Server configuration with lifecycle and auth fields |
| `MCPClient` | `core/tools/mcp_adapter.py` | Low-level MCP SDK client (stdio/HTTP/SSE) |
| `MCPToolAdapter` | `core/tools/mcp_adapter.py` | Wraps MCP tool as JARVIS `BaseTool` (for direct tools) |
| `MCPRegistry` | `core/tools/mcp_adapter.py` | Orchestrates servers, cache, lifecycle, proxy, and direct tools |
| `MCPProxyTool` | `core/tools/mcp_proxy_tool.py` | The single `mcp` proxy tool with all modes |
| `MCPLifecycleManager` | `core/tools/mcp_lifecycle.py` | Manages lazy/eager/keep-alive modes, idle timers, health checks |
| `MCPMetadataCache` | `core/tools/mcp_metadata_cache.py` | Persistent cache for offline tool/resource/prompt discovery |
| `MCPServerCapabilities` | `core/tools/mcp_capabilities.py` | Server capability negotiation |
| `MCPAuthConfig` | `core/tools/mcp_capabilities.py` | Authentication configuration (OAuth/Bearer/API key) |
| `FileTokenStorage` | `core/tools/mcp_auth.py` | File-based OAuth token storage |
| `create_oauth_client` | `core/tools/mcp_auth.py` | OAuth2 client factory with browser authorization |

### Data Models

| Model | File | Purpose |
|-------|------|---------|
| `ToolMetadata` | `core/tools/mcp_metadata_cache.py` | Cached tool definition |
| `ResourceMetadata` | `core/tools/mcp_metadata_cache.py` | Cached resource definition |
| `PromptMetadata` | `core/tools/mcp_metadata_cache.py` | Cached prompt template definition |
| `ServerMetadata` | `core/tools/mcp_metadata_cache.py` | Complete server cache entry |
| `MCPResourceSpec` | `core/tools/mcp_capabilities.py` | Resource specification from server |
| `MCPPromptSpec` | `core/tools/mcp_capabilities.py` | Prompt specification from server |

### Initialization API

```python
from core.tools.mcp_adapter import MCPRegistry, MCPServerConfig

# Create registry with proxy mode (default)
registry = MCPRegistry(tool_registry=tool_registry, use_proxy=True)

# Load configs from .mcp.json
configs = [MCPServerConfig.from_dict(d) for d in mcp_config_dicts]

# Initialize (lazy by default — only eager/keep-alive connect)
# Pass LLM provider for sampling support
results = await registry.initialize(
    configs, 
    llm_provider=provider, 
    model="gpt-4o"
)

# Backward-compatible eager mode (connects all servers immediately)
results = await registry.connect_all(configs, llm_provider=provider, model="gpt-4o")
```

### Cache Locations

```
~/.jarvis/mcp-cache.json          # Tool/resource/prompt metadata cache
~/.jarvis/auth/                   # OAuth tokens (one file per server)
~/.jarvis/mcp.json                # Global MCP server config (fallback)
.mcp.json                         # Project-level MCP server config (primary)
```