import { useMemo } from "react";
import type { UIMessage } from "@/lib/types";

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
  const activeCalls = useMemo(() => extractActiveToolCalls(messages), [messages]);
  const hasRunning = activeCalls.some(tc => tc.status === "running");

  if (!isStreaming && activeCalls.length === 0) return null;
  if (!hasRunning && activeCalls.every(tc => tc.status === "completed")) return null;

  const runningCalls = activeCalls.filter(tc => tc.status === "running");
  const recentCompleted = activeCalls.filter(tc => tc.status === "completed").slice(0, 1);
  const displayCalls = [...runningCalls, ...recentCompleted].slice(0, 3);

  return (
    <div
      className="fixed bottom-24 left-1/2 z-40 -translate-x-1/2"
    >
      <div
        className="flex items-center gap-2 rounded-full px-4 py-2"
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
        <div className="flex items-center gap-1.5 overflow-hidden">
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
      </div>
    </div>
  );
}
