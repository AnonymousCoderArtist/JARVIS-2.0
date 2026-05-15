# JARVIS API Reference

Base URL: `http://<host>:8765`

The JARVIS server serves a FastAPI application on port **8765** by default. It provides REST endpoints for session management, settings, tool configuration, and system control, plus a WebSocket endpoint for real-time chat streaming. The WebUI static build is served automatically from `interface/jarvis/web/dist/` when available.

---

## Authentication

### Bootstrapping

The server uses a simple token-based auth flow. The first call any client should make is to the bootstrap endpoint, which generates a short-lived token used for subsequent requests (in practice the token is stored in memory — no external auth provider is required):

```
GET /jarvis/bootstrap
```

Response:

```json
{
  "token": "abc123...",
  "ws_path": "/jarvis/ws",
  "model_name": "gpt-4o",
  "expires_in": 3600
}
```

| Field        | Type   | Description                           |
|--------------|--------|---------------------------------------|
| `token`      | string | Opaque bearer token, 43 chars         |
| `ws_path`    | string | WebSocket path to connect to          |
| `model_name` | string | Currently configured model            |
| `expires_in` | int    | Token TTL in seconds (currently 3600) |

> **Note**: The token store is in-memory (`_tokens` dict). In production, you must replace this with Redis or a similar store. Currently, rate limiting and token revocation on the REST side are not enforced — the token is a convenience for the WebUI bootstrap flow.

### WebSocket Authentication

The WebSocket endpoint (`/jarvis/ws`) authenticates implicitly via the connection lifecycle. On connect the server sends a `ready` event. The client then sends either:

- `{"type": "new_chat"}` — creates a new session and auto-authenticates
- `{"type": "attach", "chat_id": "..."}` — resumes an existing session, auto-authenticates

There is no explicit `auth` message type. Both `new_chat` and `attach` generate a server-side token on first use.

---

## Health Check

```
GET /jarvis/health
```

Response:

```json
{
  "status": "ok",
  "timestamp": "2026-05-14T12:00:00"
}
```

---

## Session Management

Sessions are persisted as JSON files in `~/.jarvis/sessions/`.

### List Sessions

```
GET /api/sessions
```

Returns all local sessions sorted by `updated_at` descending.

```json
[
  {
    "key": "websocket:chat_a1b2c3d4",
    "channel": "websocket",
    "chatId": "chat_a1b2c3d4",
    "createdAt": "2026-05-14T12:00:00",
    "updatedAt": "2026-05-14T12:30:00",
    "preview": "How do I refactor this function?"
  }
]
```

### Create Session

```
POST /api/sessions
```

Response:

```json
{
  "id": "a1b2c3d4",
  "created": "2026-05-14T12:00:00"
}
```

### Get Session

```
GET /api/sessions/{session_id}
```

Returns the full session data (messages included):

```json
{
  "id": "a1b2c3d4",
  "created_at": "2026-05-14T12:00:00",
  "updated_at": "2026-05-14T12:30:00",
  "preview": "How do I refactor this function?",
  "messages": [],
  "session_id": "uuid..."
}
```

### Delete Session

```
DELETE /api/sessions/{session_id}
POST   /api/sessions/{session_id}/delete
```

Both methods are supported (FastAPI route aliases).

```json
{
  "deleted": true
}
```

### Get Session Messages

```
GET /api/sessions/{session_id}/messages
```

```json
{
  "key": "websocket:a1b2c3d4",
  "created_at": "2026-05-14T12:00:00",
  "updated_at": "2026-05-14T12:30:00",
  "messages": []
}
```

### Get Conversation History (Deep History)

```
GET /api/history/{chat_id}
```

Reads the underlying `ConversationHistory` from the session's `session_id` field. Returns structured messages with role/content metadata.

```json
{
  "session_id": "uuid...",
  "chat_id": "chat_a1b2c3d4",
  "messages": [
    {
      "role": "user",
      "content": "Hello",
      "timestamp": "..."
    }
  ]
}
```

### Rewind Checkpoints

```
GET /api/sessions/{session_id}/checkpoints
```

Returns all user messages as rewindable checkpoints:

```json
{
  "session_id": "a1b2c3d4",
  "checkpoints": [
    {
      "index": 0,
      "content": "How do I refactor this function?",
      "timestamp": "2026-05-14T12:00:00",
      "has_file_changes": false
    }
  ]
}
```

### Rewind to Checkpoint

```
POST /api/sessions/{session_id}/rewind
```

Request body:

```json
{
  "message_index": 0,
  "restore_files": false
}
```

Truncates the session's message list at the given index and persists.

```json
{
  "success": true,
  "rewound_to": 0,
  "message_content": "How do I refactor this function?"
}
```

### Remote Sessions

```
GET /api/sessions/remote
```

Proxies through to a remote JARVIS instance (configured via `JARVIS_REMOTE_URL` env var).

```json
{
  "sessions": [],
  "error": "No remote URL configured. Set JARVIS_REMOTE_URL to enable remote sessions."
}
```

### Legacy Session Endpoints

All `/api/sessions/*` endpoints have `/jarvis/api/sessions/*` aliases for backward compatibility with older WebUI builds.

| REST endpoint                   | Legacy alias                            |
|---------------------------------|-----------------------------------------|
| `GET /api/sessions`             | `GET /jarvis/api/sessions`              |
| `POST /api/sessions`            | `POST /jarvis/api/sessions`             |
| `DELETE /api/sessions/{id}`     | `DELETE /jarvis/api/sessions/{id}`      |
| `POST /api/sessions/{id}/delete`| `POST /jarvis/api/sessions/{id}/delete` |

---

## Chat WebSocket

### Connection

```
ws://<host>:8765/jarvis/ws
```

The server accepts immediately and sends a `ready` event. All messages are JSON-encoded.

### Client → Server Message Types

| `type`              | Required Fields                     | Description                                          |
|---------------------|-------------------------------------|------------------------------------------------------|
| `new_chat`          | —                                   | Create a new conversation, receive `attached`        |
| `attach`            | `chat_id`                           | Resume existing conversation, receive `attached`     |
| `message`           | `content`, `chat_id`                | Send a user message; triggers streaming response     |
| `approval_response` | `tool_call_id`, `approved`          | Approve/deny a pending tool execution                |

#### `approval_response` fields

| Field          | Type    | Description                                    |
|----------------|---------|------------------------------------------------|
| `tool_call_id` | string  | Matches `tool_call_id` from `approval_request` |
| `approved`     | boolean | `true` to allow, `false` to deny               |
| `always_allow` | boolean | If `true`, persists the approval (not yet implemented) |

### Server → Client Event Types

| Event                | Direction    | Description                                    |
|----------------------|--------------|------------------------------------------------|
| `ready`              | init         | Connection established, ready for auth         |
| `attached`           | init         | Chat session is active and ready for messages  |
| `delta`              | streaming    | Token-by-token text delta                      |
| `reasoning`          | streaming    | Model reasoning/thinking tokens                |
| `reasoning_end`      | streaming    | Reasoning phase complete                       |
| `tool_call`          | streaming    | Agent invoked a tool                           |
| `tool_result`        | streaming    | Tool execution result                          |
| `user_input`         | streaming    | Agent asks user a question                     |
| `approval_request`   | streaming    | Agent requests permission for a tool           |
| `message`            | terminal     | Final complete assistant message               |
| `stream_end`         | terminal     | Token stream finished, awaiting final message  |
| `turn_end`           | terminal     | Full turn complete, ready for next message     |
| `error`              | terminal     | An error occurred                              |

### Streaming Flow

```
Client                          Server
  │                               │
  │── new_chat ──────────────────>│
  │<── attached ─────────────────│
  │── message ──────────────────>│
  │<── delta (N times) ──────────│  token-by-token
  │<── reasoning ────────────────│  (if model supports it)
  │<── reasoning_end ────────────│
  │<── tool_call ────────────────│  (zero or more)
  │<── tool_result ──────────────│
  │<── delta (more tokens) ──────│
  │<── approval_request ────────>│  (if tool needs approval)
  │── approval_response ────────>│  user responds
  │<── stream_end ───────────────│
  │<── message ──────────────────│  final text
  │<── turn_end ─────────────────│  ready for next input
```

### Concurrency

The server uses an `agent_lock` (asyncio.Lock) to ensure only one agent turn processes at a time per WebSocket connection. Multiple `message` events sent before a `turn_end` will queue and execute sequentially.

---

## Settings & Configuration

### Get Settings

```
GET /api/settings
```

Returns the current agent configuration:

```json
{
  "agent": {
    "model": "gpt-4o",
    "provider": "openai",
    "resolved_provider": "openai",
    "has_api_key": true
  },
  "providers": [
    {"name": "auto", "label": "Auto"},
    {"name": "openai", "label": "OpenAI"},
    {"name": "anthropic", "label": "Anthropic"}
  ],
  "runtime": {
    "config_path": "/home/user/.jarvis/config.json"
  },
  "requires_restart": false
}
```

### Update Settings

```
GET /api/settings/update?model=gpt-4o&provider=openai
```

Query parameters:

| Parameter        | Values                     |
|------------------|----------------------------|
| `model`          | Any model ID (see below)   |
| `provider`       | `auto`, `openai`, `anthropic` |

> **Note**: This is a GET endpoint for historical reasons. `POST /api/settings` is canonical for write operations. Model changes take effect immediately in environment variables but require a server restart to change the actual LLM provider instance.

Returns the same shape as `GET /api/settings`.

### List Models

```
GET /api/models
```

```json
{
  "models": [
    {"id": "gpt-4o", "name": "GPT-4o", "provider": "openai", "family": "openai", "capabilities": {"reasoning": true, "vision": true, "tool_call": true}},
    {"id": "gpt-4o-mini", "name": "GPT-4o Mini", "provider": "openai", "family": "openai", "capabilities": {"reasoning": true, "vision": true, "tool_call": true}},
    {"id": "gpt-4-turbo", "name": "GPT-4 Turbo", "provider": "openai", "family": "openai", "capabilities": {"reasoning": false, "vision": true, "tool_call": true}},
    {"id": "gpt-4", "name": "GPT-4", "provider": "openai", "family": "openai", "capabilities": {"reasoning": false, "vision": false, "tool_call": true}},
    {"id": "gpt-3.5-turbo", "name": "GPT-3.5 Turbo", "provider": "openai", "family": "openai", "capabilities": {"reasoning": false, "vision": false, "tool_call": true}},
    {"id": "claude-sonnet-4-20250514", "name": "Claude Sonnet 4", "provider": "anthropic", "family": "anthropic", "capabilities": {"reasoning": true, "vision": true, "tool_call": true}},
    {"id": "claude-3-5-sonnet-20241022", "name": "Claude 3.5 Sonnet", "provider": "anthropic", "family": "anthropic", "capabilities": {"reasoning": true, "vision": true, "tool_call": true}},
    {"id": "claude-3-5-haiku-20241022", "name": "Claude 3.5 Haiku", "provider": "anthropic", "family": "anthropic", "capabilities": {"reasoning": false, "vision": true, "tool_call": true}}
  ],
  "current_model": "gpt-4o"
}
```

### List Providers

```
GET /api/providers
```

```json
{
  "providers": [
    {
      "provider_id": "openai",
      "sdk_mode": "openai",
      "default_model": "gpt-4o",
      "enabled": true,
      "models": [],
      "has_api_key": true,
      "base_url": ""
    }
  ]
}
```

Uses `ProviderManager` from the provider system. Falls back to hardcoded defaults if no providers are registered.

### Switch Active Model

```
POST /api/settings/model
```

Request body:

```json
{
  "model": "claude-sonnet-4-20250514",
  "provider": "anthropic"
}
```

Response:

```json
{
  "success": true,
  "model": "claude-sonnet-4-20250514",
  "provider": "anthropic"
}
```

Only modifies environment variables (`JARVIS_MODEL`, `JARVIS_SDK`). The agent instance itself is not hot-reloaded — this requires a restart.

---

## Tools & Integrations

### MCP Servers

#### List MCP Servers

```
GET /api/mcp/servers
```

```json
{
  "servers": [
    {
      "name": "filesystem",
      "command": "npx",
      "transport": "stdio",
      "disabled": false,
      "lifecycle": "lazy",
      "connected": false,
      "tool_count": 0
    }
  ]
}
```

#### Add MCP Server

```
POST /api/mcp/servers
```

Request body:

```json
{
  "name": "filesystem",
  "command": "npx",
  "args": ["-y", "@modelcontextprotocol/server-filesystem"],
  "env": {},
  "transport": "stdio",
  "url": "",
  "lifecycle": "eager"
}
```

Response:

```json
{
  "success": true,
  "server": {
    "name": "filesystem",
    "command": "npx",
    "transport": "stdio",
    "disabled": false,
    "lifecycle": "eager"
  }
}
```

| Field       | Type   | Default    | Description                           |
|-------------|--------|------------|---------------------------------------|
| `name`      | string | `mcp-server` | Server identifier                    |
| `command`   | string | `""`       | Executable to launch                  |
| `args`      | array  | `[]`       | CLI arguments                         |
| `env`       | object | `{}`       | Environment variables                 |
| `transport` | string | `stdio`    | `stdio` or `sse`                      |
| `url`       | string | `""`       | URL for SSE transport                 |
| `lifecycle` | string | `eager`    | `eager` (connect on add) or `lazy` (connect on use) |

#### Remove MCP Server

```
DELETE /api/mcp/servers/{name}
```

```json
{
  "success": true,
  "server": "filesystem"
}
```

#### List MCP Tools

```
GET /api/mcp/tools
```

```json
{
  "tools": []
}
```

Currently returns an empty array — actual MCP tool discovery is pending.

### Heartbeat

The heartbeat system is a periodic self-check mechanism that runs the agent against a `HEARTBEAT.md` prompt file.

#### Get Heartbeat Status

```
GET /api/heartbeat
```

```json
{
  "enabled": true,
  "interval": "30m",
  "is_running": true,
  "last_run": null,
  "last_result": "...",
  "heartbeat_file": "...",
  "has_heartbeat_file": true
}
```

| Field              | Type    | Description                                     |
|--------------------|---------|-------------------------------------------------|
| `enabled`           | boolean | Whether heartbeat is active                     |
| `interval`          | string  | Human-readable interval (e.g. `30m`)            |
| `is_running`        | boolean | Whether the scheduler is currently running      |
| `last_run`          | string? | ISO timestamp of last heartbeat execution       |
| `last_result`       | string? | First 500 chars of `HEARTBEAT_RESULTS.md`       |
| `heartbeat_file`    | string  | First 1000 chars of `HEARTBEAT.md`              |
| `has_heartbeat_file`| boolean | Whether HEARTBEAT.md exists                     |

#### Start Heartbeat

```
POST /api/heartbeat/start
```

```json
{
  "success": true,
  "status": "running"
}
```

#### Stop Heartbeat

```
POST /api/heartbeat/stop
```

```json
{
  "success": true,
  "status": "stopped"
}
```

### Connectors

Connectors are external service integrations (GitHub, Weather, HTTP, etc.).

#### List Connectors

```
GET /api/connectors
```

```json
{
  "connectors": [
    {
      "id": "github",
      "display_name": "github",
      "auth_type": "token",
      "connected": false,
      "auth_configured": true,
      "sync_state": "idle"
    }
  ]
}
```

| Field             | Type    | Description                                |
|-------------------|---------|--------------------------------------------|
| `id`              | string  | Connector identifier                       |
| `display_name`    | string  | Human-readable label                       |
| `auth_type`       | string  | `token`, `api_key`, `headers`, or `none`   |
| `connected`       | boolean | Whether the connector can reach its service|
| `auth_configured` | boolean | Whether credentials have been set          |
| `sync_state`      | string  | `idle`, `syncing`, `error`                 |

#### Set Connector Credentials

```
POST /api/connectors/{name}/auth
```

Request body varies by connector:

**GitHub** (`name: github`):

```json
{
  "token": "ghp_...",
  "username": "octocat",
  "repos": ["owner/repo"]
}
```

**Weather** (`name: weather`):

```json
{
  "api_key": "...",
  "city": "San Francisco"
}
```

**HTTP** (`name: http`):

```json
{
  "headers": {
    "Authorization": "Bearer ..."
  }
}
```

Response:

```json
{
  "success": true,
  "connector": "github",
  "connected": true
}
```

---

## Monitoring

### Context / Token Usage

```
GET /api/context/usage
```

Returns current token consumption and context window limits:

```json
{
  "usage": {
    "input_tokens": 1234,
    "output_tokens": 567,
    "total_tokens": 1801
  },
  "limits": {
    "context": 128000,
    "output": 16000
  },
  "model": "gpt-4o",
  "message_count": 0
}
```

Usage data is fetched via `provider.get_and_clear_usage()` (destructive read — resets counters). Limits come from `context_length_manager.get_token_limits(model)`.

### Debug Logs

```
GET /api/debug/logs
```

Returns the last 200 in-memory debug log entries:

```json
{
  "logs": [
    "DEBUG: WebSocket accepted successfully",
    "DEBUG: Created new chat_id: chat_a1b2c3d4"
  ],
  "note": "Debug console showing last 200 log entries."
}
```

### Debug Command

```
POST /api/debug/command
```

Request body:

```json
{
  "command": "agent_status",
  "args": {}
}
```

Built-in commands:

| Command         | Description                                |
|-----------------|--------------------------------------------|
| `ping`          | Returns `"pong"`                           |
| `agent_status`  | Agent class name and memory/tool status    |
| `clear_logs`    | Clears the debug log buffer                |
| `health`        | Returns JSON health status                 |
| *(any other)*   | Returns `"Unknown command: {cmd}"`         |

Response:

```json
{
  "output": "Agent: JarvisV2, Memory: active, Tools: available",
  "success": true
}
```

### Feedback

```
POST /api/feedback
```

Request body:

```json
{
  "rating": 5,
  "message": "Really helpful response!",
  "page": "chat"
}
```

Response:

```json
{
  "success": true
}
```

Feedback is persisted to `~/.jarvis/feedback.jsonl` (one JSON object per line).

---

## Voice

### Transcribe Audio

```
POST /api/voice/transcribe
```

Request body (JSON):

```json
{
  "audio": "..."
}
```

Response:

```json
{
  "success": true,
  "text": "",
  "note": "Voice transcription requires a speech-to-text backend (Whisper/Whisper.cpp) to be installed."
}
```

> **Note**: This is a placeholder endpoint. Integration with Whisper or Whisper.cpp is required for actual transcription.

---

## Safety & Permissions

### Safety Profiles

The server defines five built-in safety profiles:

| ID | Name          | Code   | Files  | Dangerous | Bypass |
|----|---------------|--------|--------|-----------|--------|
| 1  | Lockdown      | never  | ask    | ask       | false  |
| 2  | Restricted    | ask    | ask    | ask       | false  |
| 3  | **Balanced**  | ask    | always | ask       | false  |
| 4  | Permissive    | always | always | ask       | false  |
| 5  | Unrestricted  | always | always | always    | true   |

### Get Safety Profile

```
GET /api/safety/profile
```

```json
{
  "profiles": [
    {"id": 1, "name": "Lockdown", "desc": "Everything asks. No code execution.", ...},
    ...
  ],
  "current": {
    "id": 3,
    "name": "Balanced",
    "desc": "Default. File ops allowed, code asks.",
    "bypass": false,
    "code": "ask",
    "files": "always",
    "dangerous": "ask"
  }
}
```

### Set Safety Profile

```
POST /api/safety/profile
```

Request body:

```json
{
  "profile_id": 4
}
```

Response:

```json
{
  "success": true,
  "profile": {
    "id": 4,
    "name": "Permissive",
    ...
  }
}
```

Modifies environment variables `JARVIS_BYPASS_PERMISSIONS` and `JARVIS_CODE_PERMISSION`.

### Tool Approval Flow (WebSocket)

When `bypass_tool_permissions` is `false` (default), every tool invocation requires user approval. The flow is:

1. Agent invokes a tool
2. Server sends `{"event": "approval_request", "tool_call_id": "...", "tool_name": "...", "tool_args": {...}}`
3. Client sends `{"type": "approval_response", "tool_call_id": "...", "approved": true}`
4. Agent resumes execution

When `JARVIS_BYPASS_PERMISSIONS=1`, all tools auto-approve silently.

When the agent needs to ask the user a question (via `AskUserQuestionTool`), it sends a `user_input` event:

```json
{
  "event": "user_input",
  "chat_id": "chat_...",
  "question": "Which file should I edit?",
  "options": ["src/main.py", "src/utils.py"]
}
```

Currently the response is handled server-side with an empty answer — interactive Q&A requires additional client support.

---

## WebSocket Event Reference

### init → `ready`

Sent immediately after WebSocket accept.

```json
{
  "event": "ready",
  "chat_id": "temp_abcd1234",
  "client_id": "ef567890"
}
```

### init → `attached`

Sent after `new_chat` or `attach` succeeds. Signals the session is ready for messages.

```json
{
  "event": "attached",
  "chat_id": "chat_a1b2c3d4",
  "session_id": "uuid..."
}
```

### streaming → `delta`

Token-by-token text output from the model.

```json
{
  "event": "delta",
  "chat_id": "chat_a1b2c3d4",
  "text": "To refactor"
}
```

### streaming → `reasoning`

Model's chain-of-thought / reasoning tokens (when supported by the model).

```json
{
  "event": "reasoning",
  "chat_id": "chat_a1b2c3d4",
  "text": "The user wants to extract a function..."
}
```

### streaming → `reasoning_end`

Signals reasoning phase is complete.

```json
{
  "event": "reasoning_end",
  "chat_id": "chat_a1b2c3d4"
}
```

### streaming → `tool_call`

Emitted when the agent invokes a tool.

```json
{
  "event": "tool_call",
  "chat_id": "chat_a1b2c3d4",
  "tool_name": "FileReadTool",
  "tool_args": {"path": "src/main.py"}
}
```

### streaming → `tool_result`

Emitted after a tool finishes execution.

```json
{
  "event": "tool_result",
  "chat_id": "chat_a1b2c3d4",
  "tool_name": "FileReadTool",
  "result": "file contents...",
  "success": true
}
```

The `result` field is always stringified via `str()` to avoid serialization errors with complex objects like `ToolOutput`.

### streaming → `user_input`

Emitted when the agent needs to ask the user a question.

```json
{
  "event": "user_input",
  "chat_id": "chat_a1b2c3d4",
  "question": "Which approach should I use?",
  "options": ["Option A", "Option B"]
}
```

### streaming → `approval_request`

Emitted when a tool requires user permission before executing.

```json
{
  "event": "approval_request",
  "chat_id": "chat_a1b2c3d4",
  "tool_name": "BashTool",
  "tool_args": {"command": "rm -rf /tmp/test"},
  "required_permissions": ["dangerous"],
  "tool_call_id": "call_abc123"
}
```

The client must respond with `{"type": "approval_response", "tool_call_id": "call_abc123", "approved": true|false}`.

### terminal → `stream_end`

All token deltas have been sent. The final complete message follows.

```json
{
  "event": "stream_end",
  "chat_id": "chat_a1b2c3d4"
}
```

### terminal → `message`

The complete assistant response text.

```json
{
  "event": "message",
  "chat_id": "chat_a1b2c3d4",
  "text": "To refactor that function, you can extract the loop body into..."
}
```

### terminal → `turn_end`

The agent has finished its turn. The client may now send another `message`.

```json
{
  "event": "turn_end",
  "chat_id": "chat_a1b2c3d4"
}
```

### terminal → `error`

An error occurred during message processing.

```json
{
  "event": "error",
  "chat_id": "chat_a1b2c3d4",
  "detail": "Something went wrong"
}
```

---

## Error Handling

### HTTP Status Codes

| Code | Meaning                      | Common Causes                                     |
|------|------------------------------|---------------------------------------------------|
| 200  | OK                           | Request succeeded                                 |
| 400  | Bad Request                  | Invalid `message_index` in rewind, malformed JSON |
| 404  | Not Found                    | Session or resource does not exist                |
| 503  | Service Unavailable          | WebUI not built, `npm run build` required         |

Error responses follow this shape:

```json
{
  "error": "not found"
}
```

### WebSocket Error Handling

| Scenario                         | Behavior                                                    |
|----------------------------------|-------------------------------------------------------------|
| Invalid JSON message             | Logged and silently skipped                                 |
| Unknown `type` field             | Logged and silently skipped                                 |
| Agent processing error           | Sends `{"event": "error", "detail": "..."}`, callbacks restored|
| WebSocket disconnect (client)    | Clean shutdown, approval task cancelled                     |
| WebSocket disconnect (server)    | Client receives close frame with no code                    |

---

## Rate Limits

There are **no enforced rate limits** in the current implementation. The token store and approval queues are in-memory. For production use, you should add:

- **Connection limits**: one WebSocket connection per user (the server tracks `active_connections` on `app.state` but does not enforce a cap)
- **Request throttling**: add `slowapi` or similar middleware to REST endpoints
- **Token rate limiting**: limit bootstrap calls to prevent token exhaustion

---

## Environment Variables

| Variable                    | Default     | Description                                  |
|-----------------------------|-------------|----------------------------------------------|
| `JARVIS_MODEL`              | `gpt-4o`    | Active model ID                              |
| `JARVIS_BASE_URL`           | `""`        | Custom API base URL for LLM provider         |
| `JARVIS_API_KEY`            | `""`        | API key for LLM provider                     |
| `JARVIS_SDK`                | `openai`    | SDK mode: `openai` or `anthropic`            |
| `JARVIS_BYPASS_PERMISSIONS` | `""`        | Set to `1` to auto-approve all tools         |
| `JARVIS_THINKING_LEVEL`     | `medium`    | `low`, `medium`, or `high` reasoning depth   |
| `JARVIS_CODE_PERMISSION`    | `ask`       | `always`, `ask`, or `never` for code tools   |
| `JARVIS_HEARTBEAT_ENABLED`  | `true`      | Enable/disable heartbeat scheduler           |
| `JARVIS_HEARTBEAT_EVERY`    | `30m`       | Heartbeat interval                           |
| `JARVIS_REMOTE_URL`         | `""`        | Remote JARVIS instance URL for session sync  |

---

## SPA Fallback

Any unmatched `GET` route (`/{path}`) serves `index.html` from the WebUI dist directory. This enables client-side routing in the React/Vue frontend without server-side URL rewriting. If the dist directory does not exist:

```json
{
  "error": "Web UI not built. Run 'npm run build' in interface/webui/"
}
```

Returns status `503`.
