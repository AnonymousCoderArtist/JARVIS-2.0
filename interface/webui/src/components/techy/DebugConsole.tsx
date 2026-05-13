import { useState, useCallback, useRef, useEffect } from "react";
import { useClient } from "@/providers/ClientProvider";
import { getDebugLogs, runDebugCommand } from "@/lib/api";
import { X, Send, Bug } from "lucide-react";

interface DebugConsoleProps {
  open: boolean;
  onClose: () => void;
}

export function DebugConsole({ open, onClose }: DebugConsoleProps) {
  const { token } = useClient();
  const [logs, setLogs] = useState<string[]>([]);
  const [command, setCommand] = useState("");
  const [history, setHistory] = useState<Array<{ cmd: string; output: string; success: boolean }>>([]);
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const loadLogs = useCallback(async () => {
    const r = await getDebugLogs(token);
    setLogs(r.logs);
  }, [token]);

  useEffect(() => { if (open) { loadLogs(); inputRef.current?.focus(); } }, [open, loadLogs]);
  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: "smooth" }); }, [history]);

  const handleCommand = useCallback(async () => {
    if (!command.trim()) return;
    const cmd = command.trim();
    setCommand("");
    const result = await runDebugCommand(token, cmd);
    setHistory(prev => [...prev, { cmd, output: result.output, success: result.success }]);
  }, [command, token]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4">
      <div
        className="w-full max-w-2xl overflow-hidden rounded-2xl"
        style={{
          background: "linear-gradient(180deg, rgba(5, 10, 25, 0.99) 0%, rgba(2, 5, 15, 0.99) 100%)",
          border: "1px solid rgba(26, 90, 255, 0.25)",
          boxShadow: "0 8px 40px rgba(0,0,0,0.7)",
        }}
      >
        <div className="flex items-center justify-between px-5 py-3 border-b" style={{ borderColor: "rgba(26, 90, 255, 0.12)" }}>
          <div className="flex items-center gap-2">
            <Bug className="h-4 w-4" style={{ color: "rgba(100, 200, 100, 0.7)" }} />
            <span className="text-sm font-bold tracking-wider uppercase" style={{ color: "rgba(100, 220, 100, 0.8)" }}>
              Debug Console
            </span>
          </div>
          <div className="flex items-center gap-2">
            <button onClick={loadLogs} className="px-3 py-1 text-[9px] font-medium rounded-lg" style={{ background: "rgba(26, 90, 255, 0.08)", color: "rgba(100, 140, 220, 0.5)" }}>
              Refresh
            </button>
            <button onClick={onClose} className="p-1 rounded-lg hover:bg-blue-500/10" style={{ color: "rgba(100, 140, 220, 0.6)" }}>
              <X className="h-4 w-4" />
            </button>
          </div>
        </div>

        <div className="h-72 overflow-y-auto p-4 space-y-1 font-mono" style={{ background: "rgba(0, 0, 0, 0.3)" }}>
          {history.length === 0 && logs.length === 0 && (
            <div className="py-8 text-center text-[10px]" style={{ color: "rgba(100, 140, 220, 0.25)" }}>
              Type a command to begin debugging
            </div>
          )}

          {history.map((h, i) => (
            <div key={i}>
              <div className="flex items-start gap-2">
                <span style={{ color: "rgba(100, 220, 100, 0.6)" }}>$</span>
                <span className="text-xs" style={{ color: "rgba(200, 255, 200, 0.8)" }}>{h.cmd}</span>
              </div>
              <div className="ml-4 text-[11px] leading-relaxed whitespace-pre-wrap" style={{ color: h.success ? "rgba(150, 190, 240, 0.6)" : "rgba(255, 100, 100, 0.6)" }}>
                {h.output}
              </div>
            </div>
          ))}
          {history.length > 0 && logs.length > 0 && <div className="border-t my-2" style={{ borderColor: "rgba(26, 90, 255, 0.06)" }} />}
          {logs.slice(-10).map((log, i) => (
            <div key={i} className="text-[9px] leading-relaxed" style={{ color: "rgba(100, 140, 220, 0.3)" }}>{log}</div>
          ))}
          <div ref={bottomRef} />
        </div>

        <div className="flex items-center gap-2 px-4 py-3 border-t" style={{ borderColor: "rgba(26, 90, 255, 0.12)" }}>
          <span className="text-xs font-mono" style={{ color: "rgba(100, 220, 100, 0.5)" }}>$</span>
          <input
            ref={inputRef}
            value={command}
            onChange={e => setCommand(e.target.value)}
            onKeyDown={e => { if (e.key === "Enter") handleCommand(); }}
            placeholder="Type debug command..."
            className="flex-1 bg-transparent text-xs font-mono focus:outline-none"
            style={{ color: "rgba(200, 255, 200, 0.7)" }}
          />
          <button onClick={handleCommand} className="p-1.5 rounded-lg" style={{ color: "rgba(100, 220, 100, 0.5)" }}>
            <Send className="h-3 w-3" />
          </button>
        </div>

        <div className="px-4 py-2 text-[9px] font-mono" style={{ color: "rgba(100, 140, 220, 0.2)" }}>
          Available: ping, agent_status, health, clear_logs
        </div>
      </div>
    </div>
  );
}
