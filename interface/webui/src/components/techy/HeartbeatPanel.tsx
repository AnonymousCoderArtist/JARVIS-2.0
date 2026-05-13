import { useState, useEffect, useCallback } from "react";
import { useClient } from "@/providers/ClientProvider";
import { getHeartbeatStatus, startHeartbeat, stopHeartbeat } from "@/lib/api";
import { X, Play, Square, Activity, Clock } from "lucide-react";

interface HeartbeatPanelProps {
  open: boolean;
  onClose: () => void;
}

export function HeartbeatPanel({ open, onClose }: HeartbeatPanelProps) {
  const { token } = useClient();
  const [status, setStatus] = useState<{ enabled: boolean; interval: string; is_running: boolean; last_result: string | null; heartbeat_file: string; has_heartbeat_file: boolean } | null>(null);

  const load = useCallback(async () => {
    const r = await getHeartbeatStatus(token);
    setStatus(r);
  }, [token]);

  useEffect(() => { if (open) load(); }, [open, load]);

  const handleStart = useCallback(async () => {
    await startHeartbeat(token);
    load();
  }, [token, load]);

  const handleStop = useCallback(async () => {
    await stopHeartbeat(token);
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
            <Activity className="h-4 w-4" style={{ color: "rgba(100, 160, 255, 0.8)" }} />
            <span className="text-sm font-bold tracking-wider uppercase" style={{ color: "rgba(200, 220, 255, 0.9)" }}>
              Heartbeat Monitor
            </span>
          </div>
          <button onClick={onClose} className="p-1 rounded-lg hover:bg-blue-500/10" style={{ color: "rgba(100, 140, 220, 0.6)" }}>
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="p-5 space-y-4">
          {status && (
            <>
              <div className="flex items-center justify-between">
                <span className="text-xs" style={{ color: "rgba(100, 140, 220, 0.6)" }}>Status</span>
                <div className="flex items-center gap-2">
                  <span className={`inline-flex h-2 w-2 rounded-full ${status.is_running ? "animate-pulse" : ""}`}
                    style={{ background: status.is_running ? "rgba(50, 200, 100, 0.8)" : "rgba(200, 100, 50, 0.5)" }} />
                  <span className="text-xs font-medium" style={{ color: status.is_running ? "rgba(100, 220, 150, 0.8)" : "rgba(200, 150, 100, 0.6)" }}>
                    {status.is_running ? "Running" : "Stopped"}
                  </span>
                </div>
              </div>

              <div className="flex items-center justify-between">
                <span className="text-xs" style={{ color: "rgba(100, 140, 220, 0.6)" }}>Interval</span>
                <div className="flex items-center gap-1">
                  <Clock className="h-3 w-3" style={{ color: "rgba(100, 140, 220, 0.5)" }} />
                  <span className="text-xs font-mono" style={{ color: "rgba(200, 220, 255, 0.7)" }}>{status.interval}</span>
                </div>
              </div>

              <div className="flex items-center justify-between">
                <span className="text-xs" style={{ color: "rgba(100, 140, 220, 0.6)" }}>Heartbeat File</span>
                <span className="text-xs" style={{ color: status.has_heartbeat_file ? "rgba(100, 220, 150, 0.7)" : "rgba(200, 150, 100, 0.5)" }}>
                  {status.has_heartbeat_file ? "Present" : "Not found"}
                </span>
              </div>

              {status.heartbeat_file && (
                <div className="p-3 rounded-xl max-h-32 overflow-y-auto" style={{ background: "rgba(0,0,0,0.3)", border: "1px solid rgba(26,90,255,0.1)" }}>
                  <pre className="text-[10px] leading-relaxed whitespace-pre-wrap font-mono" style={{ color: "rgba(150, 190, 240, 0.6)" }}>{status.heartbeat_file}</pre>
                </div>
              )}

              {status.last_result && (
                <div>
                  <span className="text-[10px] font-medium" style={{ color: "rgba(100, 140, 220, 0.5)" }}>Last Result</span>
                  <div className="mt-1 p-3 rounded-xl max-h-24 overflow-y-auto" style={{ background: "rgba(0,0,0,0.3)", border: "1px solid rgba(26,90,255,0.1)" }}>
                    <pre className="text-[10px] leading-relaxed whitespace-pre-wrap font-mono" style={{ color: "rgba(150, 190, 240, 0.5)" }}>{status.last_result}</pre>
                  </div>
                </div>
              )}

              <div className="flex items-center gap-3 pt-2">
                {status.is_running ? (
                  <button onClick={handleStop} className="flex items-center gap-2 px-4 py-2 text-xs font-medium rounded-xl transition-all" style={{ background: "rgba(200, 80, 80, 0.15)", border: "1px solid rgba(200, 80, 80, 0.25)", color: "rgba(220, 150, 150, 0.8)" }}>
                    <Square className="h-3 w-3" /> Stop
                  </button>
                ) : (
                  <button onClick={handleStart} className="flex items-center gap-2 px-4 py-2 text-xs font-medium rounded-xl transition-all" style={{ background: "rgba(50, 200, 100, 0.15)", border: "1px solid rgba(50, 200, 100, 0.25)", color: "rgba(100, 220, 150, 0.8)" }}>
                    <Play className="h-3 w-3" /> Start
                  </button>
                )}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
