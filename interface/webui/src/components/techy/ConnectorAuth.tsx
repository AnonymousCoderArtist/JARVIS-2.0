import { useState, useEffect, useCallback } from "react";
import { useClient } from "@/providers/ClientProvider";
import { listConnectors, setConnectorAuth } from "@/lib/api";
import { X, Plug, PlugZap, Key, Globe, Github, CloudSun, Rss, HardDrive } from "lucide-react";

interface ConnectorAuthProps {
  open: boolean;
  onClose: () => void;
}

const CONNECTOR_ICONS: Record<string, typeof Plug> = {
  github: Github,
  weather: CloudSun,
  rss: Rss,
  http: Globe,
  filesystem: HardDrive,
};

function getConnectorIcon(id: string) {
  return CONNECTOR_ICONS[id] ?? Plug;
}

interface ConnectorFormProps {
  connector: { id: string; display_name: string; auth_type: string; connected: boolean };
  onSave: () => void;
}

function ConnectorForm({ connector, onSave }: ConnectorFormProps) {
  const { token } = useClient();
  const [tokenVal, setTokenVal] = useState("");
  const [username, setUsername] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [city, setCity] = useState("");
  const [saving, setSaving] = useState(false);

  const handleSave = useCallback(async () => {
    setSaving(true);
    const creds: Record<string, unknown> = {};
    if (connector.id === "github") { creds.token = tokenVal; creds.username = username; }
    else if (connector.id === "weather") { creds.api_key = apiKey; creds.city = city; }
    else { creds.token = tokenVal; }
    await setConnectorAuth(token, connector.id, creds);
    setSaving(false);
    onSave();
  }, [connector.id, tokenVal, username, apiKey, city, token, onSave]);

  return (
    <div className="space-y-2.5">
      {connector.id === "github" && (
        <>
          <input value={tokenVal} onChange={e => setTokenVal(e.target.value)} placeholder="GitHub Personal Access Token" type="password" className="w-full px-3 py-2 text-xs rounded-lg bg-transparent border focus:outline-none" style={{ borderColor: "rgba(26,90,255,0.2)", color: "rgba(200,220,255,0.8)" }} />
          <input value={username} onChange={e => setUsername(e.target.value)} placeholder="Username" className="w-full px-3 py-2 text-xs rounded-lg bg-transparent border focus:outline-none" style={{ borderColor: "rgba(26,90,255,0.2)", color: "rgba(200,220,255,0.8)" }} />
        </>
      )}
      {connector.id === "weather" && (
        <>
          <input value={apiKey} onChange={e => setApiKey(e.target.value)} placeholder="OpenWeatherMap API Key" type="password" className="w-full px-3 py-2 text-xs rounded-lg bg-transparent border focus:outline-none" style={{ borderColor: "rgba(26,90,255,0.2)", color: "rgba(200,220,255,0.8)" }} />
          <input value={city} onChange={e => setCity(e.target.value)} placeholder="City (default: auto)" className="w-full px-3 py-2 text-xs rounded-lg bg-transparent border focus:outline-none" style={{ borderColor: "rgba(26,90,255,0.2)", color: "rgba(200,220,255,0.8)" }} />
        </>
      )}
      {(connector.id !== "github" && connector.id !== "weather") && (
        <input value={tokenVal} onChange={e => setTokenVal(e.target.value)} placeholder="API Key / Token" type="password" className="w-full px-3 py-2 text-xs rounded-lg bg-transparent border focus:outline-none" style={{ borderColor: "rgba(26,90,255,0.2)", color: "rgba(200,220,255,0.8)" }} />
      )}
      {connector.auth_type !== "none" && (
        <button onClick={handleSave} disabled={saving} className="w-full px-4 py-2 text-xs font-medium rounded-lg transition-all disabled:opacity-40" style={{ background: "rgba(26,90,255,0.15)", border: "1px solid rgba(26,90,255,0.25)", color: "rgba(200,220,255,0.8)" }}>
          {saving ? "Saving..." : connector.connected ? "Update Credentials" : "Connect"}
        </button>
      )}
    </div>
  );
}

export function ConnectorAuth({ open, onClose }: ConnectorAuthProps) {
  const { token } = useClient();
  const [connectors, setConnectors] = useState<Array<{ id: string; display_name: string; auth_type: string; connected: boolean; auth_configured: boolean }>>([]);
  const [expanded, setExpanded] = useState<string | null>(null);

  const load = useCallback(async () => {
    const r = await listConnectors(token);
    setConnectors(r.connectors);
  }, [token]);

  useEffect(() => { if (open) load(); }, [open, load]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
      <div
        className="w-full max-w-md overflow-hidden rounded-2xl"
        style={{
          background: "linear-gradient(180deg, rgba(10, 20, 45, 0.98) 0%, rgba(6, 12, 28, 0.98) 100%)",
          border: "1px solid rgba(26, 90, 255, 0.3)",
          boxShadow: "0 8px 40px rgba(0,0,0,0.6)",
        }}
      >
        <div className="flex items-center justify-between px-5 py-4 border-b" style={{ borderColor: "rgba(26, 90, 255, 0.15)" }}>
          <div className="flex items-center gap-2">
            <Key className="h-4 w-4" style={{ color: "rgba(100, 160, 255, 0.8)" }} />
            <span className="text-sm font-bold tracking-wider uppercase" style={{ color: "rgba(200, 220, 255, 0.9)" }}>
              Connector Auth
            </span>
          </div>
          <button onClick={onClose} className="p-1 rounded-lg hover:bg-blue-500/10" style={{ color: "rgba(100, 140, 220, 0.6)" }}>
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="p-4 space-y-2 max-h-[55vh] overflow-y-auto">
          {connectors.map(c => {
            const Icon = getConnectorIcon(c.id);
            return (
              <div key={c.id} className="rounded-xl overflow-hidden transition-all" style={{ border: "1px solid rgba(26, 90, 255, 0.1)" }}>
                <button
                  onClick={() => setExpanded(expanded === c.id ? null : c.id)}
                  className="flex w-full items-center gap-3 px-4 py-3 text-left"
                  style={{ background: "rgba(26, 90, 255, 0.04)" }}
                >
                  <Icon className="h-4 w-4 shrink-0" style={{ color: c.connected ? "rgba(50, 200, 100, 0.7)" : "rgba(100, 140, 220, 0.4)" }} />
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-medium truncate" style={{ color: "rgba(200, 220, 255, 0.85)" }}>{c.display_name}</div>
                    <div className="text-[9px] mt-0.5" style={{ color: "rgba(100, 140, 220, 0.35)" }}>
                      {c.auth_type !== "none" ? c.auth_type : "No auth required"}
                    </div>
                  </div>
                  <div className="flex items-center gap-1.5">
                    {c.connected ? <PlugZap className="h-3 w-3" style={{ color: "rgba(50, 200, 100, 0.6)" }} /> : <Plug className="h-3 w-3" style={{ color: "rgba(100, 140, 220, 0.3)" }} />}
                  </div>
                </button>
                {expanded === c.id && c.auth_type !== "none" && (
                  <div className="px-4 py-3" style={{ borderTop: "1px solid rgba(26, 90, 255, 0.06)" }}>
                    <ConnectorForm connector={c} onSave={load} />
                  </div>
                )}
              </div>
            );
          })}
        </div>

        <div className="px-5 py-3 border-t text-[9px]" style={{ borderColor: "rgba(26, 90, 255, 0.1)", color: "rgba(100, 140, 220, 0.3)" }}>
          Credentials stored in ~/.jarvis/credentials/
        </div>
      </div>
    </div>
  );
}
