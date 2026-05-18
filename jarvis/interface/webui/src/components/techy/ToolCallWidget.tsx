import { useState, useCallback } from "react";
import type { UIMessage } from "@/lib/types";
import { X } from "lucide-react";

interface ActiveToolCall {
  id: string;
  name: string;
  status: "running" | "completed" | "error";
}

interface ToolCallWidgetProps {
  messages: UIMessage[];
  isStreaming: boolean;
}

function extractActiveToolCalls(messages: UIMessage[]): ActiveToolCall[] {
  const calls: ActiveToolCall[] = [];
  const seen = new Set<string>();

  for (let i = messages.length - 1; i >= 0; i--) {
    const msg = messages[i];
    if (msg.toolCalls) {
      for (const tc of msg.toolCalls) {
        const key = `${msg.id}-${tc.name}`;
        if (seen.has(key)) continue;
        seen.add(key);
        calls.push({
          id: tc.id,
          name: tc.name,
          status: tc.result !== undefined
            ? (tc.success === false ? "error" : "completed")
            : "running",
        });
      }
    }
  }

  return calls;
}

export function ToolCallWidget({ messages, isStreaming }: ToolCallWidgetProps) {
  const activeCalls = useCallback(() => extractActiveToolCalls(messages), [messages]);
  const [closed, setClosed] = useState(false);

  const calls = activeCalls();
  const hasRunning = calls.some(tc => tc.status === "running");
  const displayCalls = [...calls.filter(tc => tc.status === "running"), ...calls.filter(tc => tc.status === "completed").slice(0, 1)].slice(0, 3);

  if (!isStreaming && calls.length === 0) return null;
  if (closed && !hasRunning) return null;

  return (
    <div
      className="flex-shrink-0"
      style={{
        alignSelf: "center",
        marginBottom: "0.5rem",
      }}
    >
      <div
        className="flex items-center gap-2 rounded-full px-3 py-1.5"
        style={{
          background: "rgba(var(--panel-bg-start-r), var(--panel-bg-start-g), var(--panel-bg-start-b), 0.92)",
          backdropFilter: "blur(20px)",
          border: "1px solid rgba(var(--brand-r), var(--brand-g), var(--brand-b), 0.25)",
          boxShadow: "0 4px 20px rgba(0, 0, 0, 0.4), 0 0 15px rgba(var(--brand-r), var(--brand-g), var(--brand-b), 0.08)",
        }}
      >
        <span className="relative flex h-2 w-2 flex-shrink-0">
          <span
            className="absolute inline-flex h-full w-full animate-ping rounded-full"
            style={{ background: "rgba(var(--brand-r), var(--brand-g), var(--brand-b), 0.5)" }}
          />
          <span
            className="relative inline-flex h-2 w-2 rounded-full"
            style={{ background: "rgba(var(--brand-r), var(--brand-g), var(--brand-b), 0.9)" }}
          />
        </span>
        <div className="flex items-center gap-1.5 overflow-hidden max-w-[160px]">
          {displayCalls.map((tc) => (
            <div key={tc.id} className="flex items-center gap-1.5">
              <span
                className="h-1.5 w-1.5 rounded-full flex-shrink-0"
                style={{
                  background:
                    tc.status === "running"
                      ? "rgba(var(--brand-r), var(--brand-g), var(--brand-b), 0.8)"
                      : "rgba(var(--success-r), var(--success-g), var(--success-b), 0.8)",
                  boxShadow:
                    tc.status === "running"
                      ? "0 0 4px rgba(var(--brand-r), var(--brand-g), var(--brand-b), 0.5)"
                      : "none",
                }}
              />
              <span
                className="text-[11px] whitespace-nowrap"
                style={{ color: "rgba(var(--text-body-r), var(--text-body-g), var(--text-body-b), 0.8)" }}
              >
                {tc.name}
              </span>
              {tc !== displayCalls[displayCalls.length - 1] && (
                <span
                  className="text-[10px]"
                  style={{ color: "rgba(var(--text-muted-r), var(--text-muted-g), var(--text-muted-b), 0.3)" }}
                >
                  ·
                </span>
              )}
            </div>
          ))}
        </div>
        <button
          onClick={() => setClosed(true)}
          className="flex items-center justify-center rounded-full hover:bg-red-500/10 p-0.5 ml-1"
          title="Close"
        >
          <X className="h-3 w-3" style={{ color: "rgba(var(--text-muted-r), var(--text-muted-g), var(--text-muted-b), 0.4)" }} />
        </button>
      </div>
    </div>
  );
}
