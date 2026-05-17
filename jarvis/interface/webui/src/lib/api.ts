import type { ChatSummary, SettingsPayload, SettingsUpdate } from "./types";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
    this.name = "ApiError";
  }
}

async function request<T>(
  url: string,
  token: string,
  init?: RequestInit,
): Promise<T> {
  const res = await fetch(url, {
    ...(init ?? {}),
    headers: {
      ...(init?.headers ?? {}),
      Authorization: `Bearer ${token}`,
    },
    credentials: "same-origin",
  });
  if (!res.ok) {
    throw new ApiError(res.status, `HTTP ${res.status}`);
  }
  try {
    return (await res.json()) as T;
  } catch (err) {
    const text = await res.text();
    throw new ApiError(res.status, `Invalid JSON response: ${text.slice(0, 200)}`);
  }
}

function splitKey(key: string): { channel: string; chatId: string } {
  const idx = key.indexOf(":");
  if (idx === -1) return { channel: "", chatId: key };
  return { channel: key.slice(0, idx), chatId: key.slice(idx + 1) };
}

export async function listSessions(
  token: string,
  base: string = "",
): Promise<ChatSummary[]> {
  type Row = {
    key: string;
    created_at: string | null;
    updated_at: string | null;
    preview?: string;
  };
  const body = await request<{ sessions: Row[] }>(
    `${base}/api/sessions`,
    token,
  );
  return body.sessions.map((s) => ({
    key: s.key,
    ...splitKey(s.key),
    createdAt: s.created_at,
    updatedAt: s.updated_at,
    preview: s.preview ?? "",
  }));
}

/** Signed image URL attached to a historical user message. The server
 * emits these in place of raw on-disk paths so the client can render
 * previews without learning where media lives on disk. Each URL is a
 * self-authenticating ``/api/media/...`` route (see backend
 * ``_sign_media_path``) safe to drop into an ``<img src>`` attribute. */
export interface SessionMediaUrl {
  url: string;
  name?: string;
}

export async function fetchSessionMessages(
  token: string,
  key: string,
  base: string = "",
): Promise<{
  key: string;
  created_at: string | null;
  updated_at: string | null;
  messages: Array<{
    role: string;
    content: string;
    timestamp?: string;
    tool_calls?: unknown;
    tool_call_id?: string;
    name?: string;
    /** Present on ``user`` turns that attached images. Paths have already
     * been stripped server-side; only the signed fetch URLs survive. */
    media_urls?: SessionMediaUrl[];
  }>;
}> {
  // Extract the chatId from the key (remove "websocket:" prefix if present)
  const chatId = key.includes(":") ? key.split(":")[1] : key;
  return request(
    `${base}/api/sessions/${encodeURIComponent(chatId)}/messages`,
    token,
  );
}

export async function deleteSession(
  token: string,
  key: string,
  base: string = "",
): Promise<boolean> {
  const body = await request<{ deleted: boolean }>(
    `${base}/api/sessions/${encodeURIComponent(key)}/delete`,
    token,
  );
  return body.deleted;
}

export async function fetchSettings(
  token: string,
  base: string = "",
): Promise<SettingsPayload> {
  return request<SettingsPayload>(`${base}/api/settings`, token);
}

export async function updateSettings(
  token: string,
  update: SettingsUpdate,
  base: string = "",
): Promise<SettingsPayload> {
  const query = new URLSearchParams();
  if (update.model !== undefined) query.set("model", update.model);
  if (update.provider !== undefined) query.set("provider", update.provider);
  return request<SettingsPayload>(`${base}/api/settings/update?${query}`, token);
}

export interface RemoteSession {
  key: string;
  source: string;
  title: string;
  status: string;
  created_at: string | null;
  updated_at: string | null;
}

export interface RemoteSessionsResponse {
  sessions: RemoteSession[];
  error?: string;
}

export async function listRemoteSessions(
  token: string,
  base: string = "",
): Promise<RemoteSessionsResponse> {
  return request<RemoteSessionsResponse>(`${base}/api/sessions/remote`, token);
}

// ── Model Picker API ───────────────────────────────────────────────────

export interface ModelListResponse {
  models: Array<{
    id: string;
    name: string;
    provider: string;
    family: string;
    capabilities: { reasoning: boolean; vision: boolean; tool_call: boolean };
  }>;
  current_model: string;
}

export interface ProviderListResponse {
  providers: Array<{
    provider_id: string;
    sdk_mode: string;
    default_model: string;
    enabled: boolean;
    models: string[];
    has_api_key: boolean;
    base_url: string;
  }>;
}

export async function listModels(token: string, base: string = ""): Promise<ModelListResponse> {
  return request<ModelListResponse>(`${base}/api/models`, token);
}

export async function listProviders(token: string, base: string = ""): Promise<ProviderListResponse> {
  return request<ProviderListResponse>(`${base}/api/providers`, token);
}

export async function setActiveModel(token: string, model: string, provider?: string, base: string = ""): Promise<{ success: boolean }> {
  return request<{ success: boolean }>(`${base}/api/settings/model`, token, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    body: JSON.stringify({ model, provider }),
  });
}

// ── MCP API ────────────────────────────────────────────────────────────

export interface MCPServerListResponse {
  servers: Array<{
    name: string;
    command: string;
    transport: string;
    disabled: boolean;
    lifecycle: string;
    connected: boolean;
    tool_count: number;
  }>;
}

export async function listMCPServers(token: string, base: string = ""): Promise<MCPServerListResponse> {
  return request<MCPServerListResponse>(`${base}/api/mcp/servers`, token);
}

export async function addMCPServer(token: string, config: Record<string, unknown>, base: string = ""): Promise<{ success: boolean }> {
  return request<{ success: boolean }>(`${base}/api/mcp/servers`, token, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    body: JSON.stringify(config),
  });
}

export async function removeMCPServer(token: string, name: string, base: string = ""): Promise<{ success: boolean }> {
  return request<{ success: boolean }>(`${base}/api/mcp/servers/${encodeURIComponent(name)}`, token, {
    method: "DELETE",
  });
}

// ── Heartbeat API ──────────────────────────────────────────────────────

export async function getHeartbeatStatus(token: string, base: string = ""): Promise<{
  enabled: boolean; interval: string; is_running: boolean;
  last_run: string | null; last_result: string | null;
  heartbeat_file: string; has_heartbeat_file: boolean;
}> {
  return request(`${base}/api/heartbeat`, token);
}

export async function startHeartbeat(token: string, base: string = ""): Promise<{ success: boolean }> {
  return request(`${base}/api/heartbeat/start`, token, { method: "POST" });
}

export async function stopHeartbeat(token: string, base: string = ""): Promise<{ success: boolean }> {
  return request(`${base}/api/heartbeat/stop`, token, { method: "POST" });
}

// ── Rewind API ─────────────────────────────────────────────────────────

export async function getSessionCheckpoints(token: string, sessionId: string, base: string = ""): Promise<{
  session_id: string; checkpoints: Array<{ index: number; content: string; timestamp: string; has_file_changes: boolean }>;
}> {
  return request(`${base}/api/sessions/${encodeURIComponent(sessionId)}/checkpoints`, token);
}

export async function rewindSession(token: string, sessionId: string, messageIndex: number, restoreFiles?: boolean, base: string = ""): Promise<{
  success: boolean; rewound_to: number; message_content: string;
}> {
  return request(`${base}/api/sessions/${encodeURIComponent(sessionId)}/rewind`, token, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    body: JSON.stringify({ message_index: messageIndex, restore_files: restoreFiles }),
  });
}

// ── Voice API ──────────────────────────────────────────────────────────

export async function transcribeVoice(token: string, audioBlob: Blob, base: string = ""): Promise<{ success: boolean; text: string }> {
  const formData = new FormData();
  formData.append("audio", audioBlob, "recording.webm");
  const res = await fetch(`${base}/api/voice/transcribe`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    body: formData,
  });
  return res.json();
}

// ── Feedback API ───────────────────────────────────────────────────────

export async function submitFeedback(token: string, data: { rating: number; message?: string; page?: string }, base: string = ""): Promise<{ success: boolean }> {
  return request(`${base}/api/feedback`, token, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    body: JSON.stringify(data),
  });
}

// ── Debug API ──────────────────────────────────────────────────────────

export async function getDebugLogs(token: string, base: string = ""): Promise<{ logs: string[] }> {
  return request(`${base}/api/debug/logs`, token);
}

export async function runDebugCommand(token: string, command: string, args?: Record<string, unknown>, base: string = ""): Promise<{ output: string; success: boolean }> {
  return request(`${base}/api/debug/command`, token, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    body: JSON.stringify({ command, args }),
  });
}

// ── Context / Token Usage API ──────────────────────────────────────────

export async function getContextUsage(token: string, base: string = ""): Promise<{
  usage: { prompt_tokens?: number; completion_tokens?: number; total_tokens?: number };
  limits: { context: number; output: number };
  model: string;
  message_count: number;
}> {
  return request(`${base}/api/context/usage`, token);
}

// ── Connector Auth API ─────────────────────────────────────────────────

export async function listConnectors(token: string, base: string = ""): Promise<{
  connectors: Array<{ id: string; display_name: string; auth_type: string; connected: boolean; auth_configured: boolean; sync_state: string }>;
}> {
  return request(`${base}/api/connectors`, token);
}

export async function setConnectorAuth(token: string, name: string, credentials: Record<string, unknown>, base: string = ""): Promise<{ success: boolean; connected: boolean }> {
  return request(`${base}/api/connectors/${encodeURIComponent(name)}/auth`, token, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    body: JSON.stringify(credentials),
  });
}

// ── Safety Profile API ─────────────────────────────────────────────────

export async function getSafetyProfile(token: string, base: string = ""): Promise<{
  profiles: Array<{ id: number; name: string; desc: string; bypass: boolean; code: string; files: string; dangerous: string }>;
  current: { id: number; name: string; desc: string };
}> {
  return request(`${base}/api/safety/profile`, token);
}

export async function setSafetyProfile(token: string, profileId: number, base: string = ""): Promise<{ success: boolean }> {
  return request(`${base}/api/safety/profile`, token, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    body: JSON.stringify({ profile_id: profileId }),
  });
}
