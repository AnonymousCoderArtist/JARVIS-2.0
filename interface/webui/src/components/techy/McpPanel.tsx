import { useState, useEffect, useCallback } from "react";
import { useClient } from "@/providers/ClientProvider";
import { listMCPServers, addMCPServer, removeMCPServer } from "@/lib/api";
import { X, Plus, Server, Trash2, Wifi, WifiOff } from "lucide-react";

interface McpPanelProps {
  open: boolean;
  onClose: () => void;
}

export function McpPanel({ open, onClose }: McpPanelProps) {
  const { token } = useClient();
  const [servers, setServers] = useState<Array<{ name: string; command: string; transport: string; disabled: boolean; connected: boolean; tool_count: number }>>([]);
  const [showAdd, setShowAdd] = useState(false);
  const [newName, setNewName] = useState("");
  const [newCommand, setNewCommand] = useState("");
  const [newTransport, setNewTransport] = useState("stdio");

  const load = useCallback(async () => {
    const r = await listMCPServers(token);
    setServers(r.servers);
  }, [token]);

  useEffect(() => { if (open) load(); }, [open, load]);

  const handleAdd = useCallback(async () => {
    if (!newName.trim()) return;
    await addMCPServer(token, { name: newName, command: newCommand, transport: newTransport });
    setNewName(""); setNewCommand(""); setShowAdd(false);
    load();
  }, [newName, newCommand, newTransport, token, load]);

  const handleRemove = useCallback(async (name: string) => {
    await removeMCPServer(token, name);
    load();
  }, [token, load]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
      <div
        className="w-full max-w-lg overflow-hidden rounded-2xl"
        style={{
          background: "linear-gradient(180deg, rgba(10, 20, 45, 0.98) 0%, rgba(6, 12, 28, 0.98) 100%)",
          border: "1px solid rgba(26, 90, 255, 0.3)",
          boxShadow: "0 8px 40px rgba(0,0,0,0.6)",
        }}
      >
        <div className="flex items-center justify-between px-5 py-4 border-b" style={{ borderColor: "rgba(26, 90, 255, 0.15)" }}>
          <div className="flex items-center gap-2">
            <Server className="h-4 w-4" style={{ color: "rgba(100, 160, 255, 0.8)" }} />
            <span className="text-sm font-bold tracking-wider uppercase" style={{ color: "rgba(200, 220, 255, 0.9)" }}>
              MCP Servers
            </span>
          </div>
          <div className="flex items-center gap-2">
            <button onClick={() => setShowAdd(!showAdd)} className="flex items-center gap-1 px-3 py-1.5 text-[10px] font-medium rounded-lg transition-all hover:bg-blue-500/10" style={{ color: "rgba(100, 160, 255, 0.7)", border: "1px solid rgba(26,90,255,0.2)" }}>
              <Plus className="h-3 w-3" /> Add
            </button>
            <button onClick={onClose} className="p-1 rounded-lg hover:bg-blue-500/10" style={{ color: "rgba(100, 140, 220, 0.6)" }}>
              <X className="h-4 w-4" />
            </button>
          </div>
        </div>

        <div className="p-5 max-h-[55vh] overflow-y-auto space-y-2">
          {showAdd && (
            <div className="p-4 rounded-xl mb-3" style={{ background: "rgba(26, 90, 255, 0.06)", border: "1px solid rgba(26, 90, 255, 0.2)" }}>
              <input value={newName} onChange={e => setNewName(e.target.value)} placeholder="Server name" className="w-full mb-2 px-3 py-2 text-xs rounded-lg bg-transparent border focus:outline-none" style={{ borderColor: "rgba(26,90,255,0.2)", color: "rgba(200,220,255,0.8)" }} />
              <input value={newCommand} onChange={e => setNewCommand(e.target.value)} placeholder="Command (e.g. npx)" className="w-full mb-2 px-3 py-2 text-xs rounded-lg bg-transparent border focus:outline-none" style={{ borderColor: "rgba(26,90,255,0.2)", color: "rgba(200,220,255,0.8)" }} />
              <div className="flex gap-2">
                <select value={newTransport} onChange={e => setNewTransport(e.target.value)} className="flex-1 px-3 py-2 text-xs rounded-lg bg-transparent border focus:outline-none" style={{ borderColor: "rgba(26,90,255,0.2)", color: "rgba(200,220,255,0.8)" }}>
                  <option value="stdio">stdio</option>
                  <option value="http">HTTP</option>
                  <option value="sse">SSE</option>
                </select>
                <button onClick={handleAdd} className="px-4 py-2 text-xs font-medium rounded-lg" style={{ background: "rgba(26,90,255,0.2)", color: "rgba(200,220,255,0.8)" }}>Save</button>
              </div>
            </div>
          )}

          {servers.length === 0 && !showAdd && (
            <div className="py-8 text-center text-xs" style={{ color: "rgba(100, 140, 220, 0.4)" }}>
              No MCP servers configured. Click Add to connect one.
            </div>
          )}

          {servers.map(s => (
            <div key={s.name} className="flex items-center gap-3 px-4 py-3 rounded-xl" style={{ background: "rgba(26, 90, 255, 0.04)", border: "1px solid rgba(26, 90, 255, 0.1)" }}>
              {s.connected ? <Wifi className="h-3 w-3 shrink-0" style={{ color: "rgba(50, 200, 100, 0.7)" }} /> : <WifiOff className="h-3 w-3 shrink-0" style={{ color: "rgba(200, 100, 50, 0.5)" }} />}
              <div className="flex-1 min-w-0">
                <div className="text-sm font-medium truncate" style={{ color: "rgba(200, 220, 255, 0.85)" }}>{s.name}</div>
                <div className="flex gap-2 text-[10px]" style={{ color: "rgba(100, 140, 220, 0.5)" }}>
                  <span>{s.transport}</span>
                  {s.tool_count > 0 && <span>{s.tool_count} tools</span>}
                </div>
              </div>
              <button onClick={() => handleRemove(s.name)} className="p-1.5 rounded-lg hover:bg-red-500/10 transition-colors" style={{ color: "rgba(200, 100, 100, 0.5)" }}>
                <Trash2 className="h-3 w-3" />
              </button>
            </div>
          ))}
        </div>

        <div className="px-5 py-3 border-t text-[9px]" style={{ borderColor: "rgba(26, 90, 255, 0.1)", color: "rgba(100, 140, 220, 0.3)" }}>
          MCP servers provide tools, resources, and prompts to the agent
        </div>
      </div>
    </div>
  );
}
