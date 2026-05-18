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
      <div className="techy-dialog w-full max-w-lg overflow-hidden rounded-2xl">
        <div className="techy-header flex items-center justify-between px-5 py-4">
          <div className="flex items-center gap-2">
            <Activity className="h-4 w-4" style={{ color: "rgba(var(--text-bright-r), var(--text-bright-g), var(--text-bright-b), 0.8)" }} />
            <span className="text-sm font-bold tracking-wider uppercase" style={{ color: "rgba(var(--text-bright-r), var(--text-bright-g), var(--text-bright-b), 0.9)" }}>
              Heartbeat Monitor
            </span>
          </div>
          <button onClick={onClose} className="p-1 rounded-lg hover:bg-blue-500/10" style={{ color: "rgba(var(--text-muted-r), var(--text-muted-g), var(--text-muted-b), 0.6)" }}>
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="p-5 space-y-4">
          {status && (
            <>
              <div className="flex items-center justify-between">
                <span className="text-xs" style={{ color: "rgba(var(--text-muted-r), var(--text-muted-g), var(--text-muted-b), 0.6)" }}>Status</span>
                <div className="flex items-center gap-2">
                  <span className={`inline-flex h-2 w-2 rounded-full ${status.is_running ? "animate-pulse" : ""}`}
                    style={{ background: status.is_running ? "rgba(var(--success-r), var(--success-g), var(--success-b), 0.8)" : "rgba(var(--warning-r), var(--warning-g), var(--warning-b), 0.5)" }} />
                  <span className="text-xs font-medium" style={{ color: status.is_running ? "rgba(var(--success-r), var(--success-g), var(--success-b), 0.8)" : "rgba(var(--warning-r), var(--warning-g), var(--warning-b), 0.6)" }}>
                    {status.is_running ? "Running" : "Stopped"}
                  </span>
                </div>
              </div>

              <div className="flex items-center justify-between">
                <span className="text-xs" style={{ color: "rgba(var(--text-muted-r), var(--text-muted-g), var(--text-muted-b), 0.6)" }}>Interval</span>
                <div className="flex items-center gap-1">
                  <Clock className="h-3 w-3" style={{ color: "rgba(var(--text-muted-r), var(--text-muted-g), var(--text-muted-b), 0.5)" }} />
                  <span className="text-xs font-mono" style={{ color: "rgba(var(--text-bright-r), var(--text-bright-g), var(--text-bright-b), 0.7)" }}>{status.interval}</span>
                </div>
              </div>

              <div className="flex items-center justify-between">
                <span className="text-xs" style={{ color: "rgba(var(--text-muted-r), var(--text-muted-g), var(--text-muted-b), 0.6)" }}>Heartbeat File</span>
                <span className="text-xs" style={{ color: status.has_heartbeat_file ? "rgba(var(--success-r), var(--success-g), var(--success-b), 0.7)" : "rgba(var(--warning-r), var(--warning-g), var(--warning-b), 0.5)" }}>
                  {status.has_heartbeat_file ? "Present" : "Not found"}
                </span>
              </div>

              {status.heartbeat_file && (
                <div className="p-3 rounded-xl max-h-32 overflow-y-auto" style={{ background: "rgba(0,0,0,0.3)", border: "1px solid rgba(var(--brand-r),var(--brand-g),var(--brand-b),0.1)" }}>
                  <pre className="text-[10px] leading-relaxed whitespace-pre-wrap font-mono" style={{ color: "rgba(var(--text-body-r), var(--text-body-g), var(--text-body-b), 0.6)" }}>{status.heartbeat_file}</pre>
                </div>
              )}

              {status.last_result && (
                <div>
                  <span className="text-[10px] font-medium" style={{ color: "rgba(var(--text-muted-r), var(--text-muted-g), var(--text-muted-b), 0.5)" }}>Last Result</span>
                  <div className="mt-1 p-3 rounded-xl max-h-24 overflow-y-auto" style={{ background: "rgba(0,0,0,0.3)", border: "1px solid rgba(var(--brand-r),var(--brand-g),var(--brand-b),0.1)" }}>
                    <pre className="text-[10px] leading-relaxed whitespace-pre-wrap font-mono" style={{ color: "rgba(var(--text-body-r), var(--text-body-g), var(--text-body-b), 0.5)" }}>{status.last_result}</pre>
                  </div>
                </div>
              )}

              <div className="flex items-center gap-3 pt-2">
                {status.is_running ? (
                  <button onClick={handleStop} className="flex items-center gap-2 px-4 py-2 text-xs font-medium rounded-xl transition-all" style={{ background: "rgba(var(--error-r), var(--error-g), var(--error-b), 0.15)", border: "1px solid rgba(var(--error-r), var(--error-g), var(--error-b), 0.25)", color: "rgba(var(--error-r), var(--error-g), var(--error-b), 0.8)" }}>
                    <Square className="h-3 w-3" /> Stop
                  </button>
                ) : (
                  <button onClick={handleStart} className="flex items-center gap-2 px-4 py-2 text-xs font-medium rounded-xl transition-all" style={{ background: "rgba(var(--success-r), var(--success-g), var(--success-b), 0.15)", border: "1px solid rgba(var(--success-r), var(--success-g), var(--success-b), 0.25)", color: "rgba(var(--success-r), var(--success-g), var(--success-b), 0.8)" }}>
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
