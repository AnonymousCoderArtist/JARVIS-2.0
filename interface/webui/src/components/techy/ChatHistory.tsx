import { useEffect, useRef } from "react";
import { Cloud, CloudOff } from "lucide-react";
import type { ChatSummary } from "@/lib/types";
import { cn } from "@/lib/utils";

interface ChatHistoryProps {
  open: boolean;
  sessions: ChatSummary[];
  activeKey: string | null;
  onSelect: (key: string) => void;
  onClose: () => void;
  pos: { x: number; y: number };
  onPosChange?: (pos: { x: number; y: number }) => void;
  canvasOffset: { x: number; y: number };
}

export function ChatHistory({
  open,
  sessions,
  activeKey,
  onSelect,
  onClose,
  pos,
  onPosChange,
  canvasOffset,
}: ChatHistoryProps) {
  const panelRef = useRef<HTMLDivElement>(null);
  const draggingRef = useRef(false);
  const grabRef = useRef({ x: 0, y: 0 });

  useEffect(() => {
    const panel = panelRef.current;
    if (!panel) return;

    const onDown = (e: MouseEvent) => {
      const header = panel.firstElementChild;
      if (!header || !header.contains(e.target as Node)) return;
      draggingRef.current = true;
      grabRef.current = {
        x: e.clientX - (canvasOffset.x + pos.x),
        y: e.clientY - (canvasOffset.y + pos.y),
      };
      panel.style.cursor = "grabbing";
    };

    const onMove = (e: MouseEvent) => {
      if (!draggingRef.current) return;
      e.preventDefault();
      onPosChange?.({
        x: e.clientX - canvasOffset.x - grabRef.current.x,
        y: e.clientY - canvasOffset.y - grabRef.current.y,
      });
    };

    const onUp = () => {
      draggingRef.current = false;
      panel.style.cursor = "default";
    };

    panel.addEventListener("mousedown", onDown);
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
    return () => {
      panel.removeEventListener("mousedown", onDown);
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };
  }, [pos, onPosChange, canvasOffset]);

  if (!open) return null;

  return (
    <div
      ref={panelRef}
      className="techy-panel absolute z-30 flex flex-col overflow-hidden rounded-2xl"
      style={{
        left: pos.x,
        top: pos.y,
        width: 300,
        height: 420,
      }}
    >
      {/* Header / drag handle */}
      <div
        className="techy-header flex items-center justify-between px-5 py-3 rounded-t-2xl"
        style={{
          cursor: "grab",
        }}
      >
        <span className="text-[10px] font-semibold tracking-[0.2em] uppercase text-[rgba(var(--text-bright-r),var(--text-bright-g),var(--text-bright-b),0.8)]">
          Conversations
        </span>
        <button
          onClick={onClose}
          className="text-[10px] tracking-[0.15em] uppercase text-[rgba(var(--text-body-r),var(--text-body-g),var(--text-body-b),0.5)] hover:text-[rgba(var(--brand-r),var(--brand-g),var(--brand-b),0.7)] transition-colors"
        >
          [ close ]
        </button>
      </div>

      {/* Local sessions */}
      <div className="flex-1 overflow-y-auto p-3 space-y-1.5">
        {sessions.filter(s => s.source !== "remote").length === 0 && (
          <div className="flex h-full items-center justify-center">
            <span className="text-[10px] tracking-widest text-[rgba(var(--text-body-r),var(--text-body-g),var(--text-body-b),0.35)] uppercase">
              NO LOCAL CHATS
            </span>
          </div>
        )}
        {sessions.filter(s => s.source !== "remote").map((s) => {
          const isActive = s.key === activeKey;
          return (
            <button
              key={s.key}
              onClick={() => onSelect(s.key)}
              className={cn(
                "w-full rounded-xl px-4 py-2.5 text-left transition-all duration-200",
                isActive ? "techy-session-active" : "techy-session-inactive"
              )}
            >
              <span
                className={cn(
                  "block text-xs leading-relaxed",
                  isActive
                    ? "text-[rgba(var(--text-bright-r),var(--text-bright-g),var(--text-bright-b),0.9)]"
                    : "text-[rgba(var(--text-body-r),var(--text-body-g),var(--text-body-b),0.6)]"
                )}
              >
                {s.preview || `Chat ${s.chatId.slice(0, 8)}`}
              </span>
              <span className="block text-[9px] tracking-wider text-[rgba(var(--text-body-r),var(--text-body-g),var(--text-body-b),0.4)] uppercase">
                {s.updatedAt ? new Date(s.updatedAt).toLocaleDateString() : "New"}
              </span>
            </button>
          );
        })}
      </div>

      {/* Remote sessions section */}
      {sessions.some(s => s.source === "remote") && (
        <>
          <div
            className="flex items-center gap-2 px-5 py-2"
            style={{ borderTop: "1px solid rgba(var(--brand-r), var(--brand-g), var(--brand-b), 0.15)" }}
          >
            <Cloud className="h-3 w-3 text-cyan-400" />
            <span className="text-[10px] font-semibold tracking-[0.15em] uppercase text-cyan-400/80">
              Remote Sessions
            </span>
          </div>
          <div className="flex-1 overflow-y-auto p-3 space-y-1.5 pb-4">
            {sessions.filter(s => s.source === "remote").map((s) => {
              const isActive = s.key === activeKey;
              return (
                <button
                  key={s.key}
                  onClick={() => onSelect(s.key)}
                  className={cn(
                    "w-full rounded-xl px-4 py-2.5 text-left transition-all duration-200",
                    isActive ? "techy-session-active-remote" : "techy-session-inactive-remote"
                  )}
                >
                  <span
                    className={cn(
                      "block text-xs leading-relaxed",
                      isActive
                        ? "text-[rgba(34,211,238,0.9)]"
                        : "text-[rgba(var(--text-body-r),var(--text-body-g),var(--text-body-b),0.6)]"
                    )}
                  >
                    {s.title || s.preview || `Remote ${s.chatId.slice(0, 8)}`}
                  </span>
                  <div className="flex items-center gap-2 mt-1">
                    <span className="text-[9px] tracking-wider text-[rgba(6,182,212,0.6)] uppercase">
                      {s.status || "remote"}
                    </span>
                    {s.updatedAt && (
                      <span className="text-[9px] tracking-wider text-[rgba(var(--text-body-r),var(--text-body-g),var(--text-body-b),0.4)] uppercase">
                        {new Date(s.updatedAt).toLocaleDateString()}
                      </span>
                    )}
                  </div>
                </button>
              );
            })}
          </div>
        </>
      )}

      {/* No remote sessions hint */}
      {sessions.filter(s => s.source === "remote").length === 0 && (
        <div
          className="flex items-center gap-2 px-5 py-2"
          style={{ borderTop: "1px solid rgba(var(--brand-r), var(--brand-g), var(--brand-b), 0.15)" }}
        >
          <CloudOff className="h-3 w-3 text-[rgba(var(--text-body-r),var(--text-body-g),var(--text-body-b),0.4)]" />
          <span className="text-[9px] tracking-wider text-[rgba(var(--text-body-r),var(--text-body-g),var(--text-body-b),0.4)] uppercase">
            No remote sessions
          </span>
          <span className="text-[8px] text-[rgba(var(--text-body-r),var(--text-body-g),var(--text-body-b),0.35)]">
            (set JARVIS_REMOTE_URL)
          </span>
        </div>
      )}
    </div>
  );
}
