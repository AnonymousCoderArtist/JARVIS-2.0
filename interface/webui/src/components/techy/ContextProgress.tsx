import { useState, useEffect, useCallback } from "react";
import { useClient } from "@/providers/ClientProvider";
import { getContextUsage } from "@/lib/api";
import { BarChart3 } from "lucide-react";

interface ContextProgressProps {
  open: boolean;
  onClose: () => void;
}

export function ContextProgress({ open, onClose }: ContextProgressProps) {
  const { token } = useClient();
  const [data, setData] = useState<{
    usage: { prompt_tokens?: number; completion_tokens?: number; total_tokens?: number };
    limits: { context: number; output: number };
    model: string;
  } | null>(null);

  const load = useCallback(async () => {
    const r = await getContextUsage(token);
    setData(r);
  }, [token]);

  useEffect(() => { if (open) { load(); const id = setInterval(load, 3000); return () => clearInterval(id); } }, [open, load]);

  if (!open) return null;

  const usage = data?.usage?.total_tokens ?? 0;
  const limit = data?.limits?.context ?? 128000;
  const pct = Math.min(100, (usage / limit) * 100);
  const outPct = data?.limits?.output ? Math.min(100, ((data?.usage?.completion_tokens ?? 0) / data.limits.output) * 100) : 0;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
      <div
        className="w-full max-w-sm overflow-hidden rounded-2xl"
        style={{
          background: "linear-gradient(180deg, rgba(10, 20, 45, 0.98) 0%, rgba(6, 12, 28, 0.98) 100%)",
          border: "1px solid rgba(26, 90, 255, 0.3)",
          boxShadow: "0 8px 40px rgba(0,0,0,0.6)",
        }}
      >
        <div className="flex items-center justify-between px-5 py-4 border-b" style={{ borderColor: "rgba(26, 90, 255, 0.15)" }}>
          <div className="flex items-center gap-2">
            <BarChart3 className="h-4 w-4" style={{ color: "rgba(100, 160, 255, 0.8)" }} />
            <span className="text-sm font-bold tracking-wider uppercase" style={{ color: "rgba(200, 220, 255, 0.9)" }}>
              Context Usage
            </span>
          </div>
          <button onClick={onClose} className="p-1 rounded-lg hover:bg-blue-500/10" style={{ color: "rgba(100, 140, 220, 0.6)" }}>
            <XIcon className="h-4 w-4" />
          </button>
        </div>

        <div className="p-5 space-y-4">
          <div className="flex items-center justify-between text-xs" style={{ color: "rgba(100, 140, 220, 0.5)" }}>
            <span>Model</span>
            <span className="font-mono" style={{ color: "rgba(200, 220, 255, 0.7)" }}>{data?.model ?? "—"}</span>
          </div>

          <div>
            <div className="flex items-center justify-between text-xs mb-1.5" style={{ color: "rgba(100, 140, 220, 0.5)" }}>
              <span>Context Window</span>
              <span className="font-mono" style={{ color: "rgba(200, 220, 255, 0.7)" }}>{usage.toLocaleString()} / {limit.toLocaleString()}</span>
            </div>
            <div className="h-2 rounded-full overflow-hidden" style={{ background: "rgba(26, 90, 255, 0.1)" }}>
              <div className="h-full rounded-full transition-all duration-500" style={{ width: `${pct}%`, background: pct > 80 ? "rgba(255, 180, 50, 0.6)" : "rgba(26, 90, 255, 0.4)" }} />
            </div>
          </div>

          <div>
            <div className="flex items-center justify-between text-xs mb-1.5" style={{ color: "rgba(100, 140, 220, 0.5)" }}>
              <span>Output Budget</span>
              <span className="font-mono" style={{ color: "rgba(200, 220, 255, 0.7)" }}>
                {(data?.usage?.completion_tokens ?? 0).toLocaleString()} / {(data?.limits?.output ?? 0).toLocaleString()}
              </span>
            </div>
            <div className="h-2 rounded-full overflow-hidden" style={{ background: "rgba(26, 90, 255, 0.1)" }}>
              <div className="h-full rounded-full transition-all duration-500" style={{ width: `${outPct}%`, background: "rgba(100, 200, 255, 0.4)" }} />
            </div>
          </div>

          <div className="grid grid-cols-3 gap-3 pt-2">
            {[
              { label: "Input", value: data?.usage?.prompt_tokens ?? 0, color: "rgba(26, 90, 255, 0.6)" },
              { label: "Output", value: data?.usage?.completion_tokens ?? 0, color: "rgba(100, 200, 255, 0.6)" },
              { label: "Total", value: data?.usage?.total_tokens ?? 0, color: "rgba(180, 150, 255, 0.6)" },
            ].map(s => (
              <div key={s.label} className="text-center p-2 rounded-xl" style={{ background: "rgba(26, 90, 255, 0.05)" }}>
                <div className="text-[9px] uppercase tracking-wider" style={{ color: "rgba(100, 140, 220, 0.4)" }}>{s.label}</div>
                <div className="text-sm font-mono font-bold mt-0.5" style={{ color: s.color }}>{s.value.toLocaleString()}</div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function XIcon(props: React.SVGProps<SVGSVGElement>) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" {...props}>
      <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
    </svg>
  );
}
