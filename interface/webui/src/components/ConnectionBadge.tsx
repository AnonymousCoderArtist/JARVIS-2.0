import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { cn } from "@/lib/utils";
import { useClient } from "@/providers/ClientProvider";
import type { ConnectionStatus } from "@/lib/types";

const COPY: Record<ConnectionStatus, { color: string }> = {
  idle: { color: "bg-card/40 text-muted-foreground" },
  connecting: {
    color: "bg-[rgba(var(--warning-r),var(--warning-g),var(--warning-b),0.1)] text-[rgba(var(--warning-r),var(--warning-g),var(--warning-b),0.7)]",
  },
  open: {
    color: "bg-[rgba(var(--success-r),var(--success-g),var(--success-b),0.1)] text-[rgba(var(--success-r),var(--success-g),var(--success-b),0.7)]",
  },
  reconnecting: {
    color: "bg-[rgba(var(--warning-r),var(--warning-g),var(--warning-b),0.1)] text-[rgba(var(--warning-r),var(--warning-g),var(--warning-b),0.7)]",
  },
  closed: {
    color: "bg-card/40 text-muted-foreground",
  },
  error: {
    color: "bg-destructive/10 text-destructive",
  },
};

export function ConnectionBadge() {
  const { t } = useTranslation();
  const { client } = useClient();
  const [status, setStatus] = useState<ConnectionStatus>(client.status);

  useEffect(() => client.onStatus(setStatus), [client]);

  const meta = COPY[status];
  const pulsing =
    status === "connecting" ||
    status === "reconnecting" ||
    status === "error";
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-md border border-border/60 px-2 py-1 text-[11px] font-medium transition-colors",
        meta.color,
      )}
      aria-live="polite"
    >
      <span className="relative flex h-1.5 w-1.5" aria-hidden>
        {pulsing && (
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-current opacity-75" />
        )}
        <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-current" />
      </span>
      {t(`connection.${status}`)}
    </span>
  );
}
