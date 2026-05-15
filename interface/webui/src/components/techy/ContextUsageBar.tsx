import { useState, useEffect, useCallback, useRef } from "react";
import { useClient } from "@/providers/ClientProvider";
import { getContextUsage } from "@/lib/api";

export function ContextUsageBar() {
  const { token } = useClient();
  const [usage, setUsage] = useState(0);
  const [limit, setLimit] = useState(128000);
  const mountedRef = useRef(true);

  const load = useCallback(async () => {
    try {
      const r = await getContextUsage(token);
      if (!mountedRef.current) return;
      setUsage(r.usage.total_tokens ?? 0);
      setLimit(r.limits.context ?? 128000);
    } catch {
      // silently ignore polling errors
    }
  }, [token]);

  useEffect(() => {
    mountedRef.current = true;
    load();
    const id = setInterval(load, 5000);
    return () => {
      mountedRef.current = false;
      clearInterval(id);
    };
  }, [load]);

  const pct = Math.min(100, (usage / limit) * 100);
  const color =
    pct > 90 ? "rgba(var(--error-r), var(--error-g), var(--error-b), 0.6)" :
    pct > 80 ? "rgba(var(--warning-r), var(--warning-g), var(--warning-b), 0.6)" :
    pct > 70 ? "rgba(var(--warning-r), var(--warning-g), var(--warning-b), 0.4)" :
    "rgba(var(--brand-r), var(--brand-g), var(--brand-b), 0.4)";

  return (
    <div
      className="flex items-center gap-2 rounded-full px-3 py-1"
      style={{
        background: "rgba(var(--panel-bg-start-r), var(--panel-bg-start-g), var(--panel-bg-start-b), 0.92)",
        backdropFilter: "blur(20px)",
        border: "1px solid rgba(var(--brand-r), var(--brand-g), var(--brand-b), 0.15)",
      }}
    >
      <span className="relative flex h-2 w-2 flex-shrink-0">
        <span
          className="absolute inline-flex h-full w-full animate-ping rounded-full"
          style={{ background: color }}
        />
        <span
          className="relative inline-flex h-2 w-2 rounded-full"
          style={{ background: color }}
        />
      </span>
      <div className="h-1.5 w-16 rounded-full overflow-hidden" style={{ background: "rgba(var(--brand-r), var(--brand-g), var(--brand-b), 0.1)" }}>
        <div
          className="h-full rounded-full transition-all duration-500"
          style={{ width: `${pct}%`, background: color }}
        />
      </div>
      <span
        className="text-[10px] font-mono whitespace-nowrap"
        style={{ color: "rgba(var(--text-body-r), var(--text-body-g), var(--text-body-b), 0.7)" }}
      >
        {pct.toFixed(0)}%
      </span>
    </div>
  );
}
