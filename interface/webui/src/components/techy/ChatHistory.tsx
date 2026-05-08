import { useEffect, useRef } from "react";
import type { ChatSummary } from "@/lib/types";

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
      className="absolute z-30 flex flex-col overflow-hidden rounded-2xl"
      style={{
        left: pos.x,
        top: pos.y,
        width: 300,
        height: 420,
        background:
          "linear-gradient(180deg, rgba(8, 16, 38, 0.92) 0%, rgba(5, 10, 24, 0.92) 100%)",
        backdropFilter: "blur(20px)",
        border: "1px solid rgba(26, 90, 255, 0.3)",
        boxShadow:
          "0 8px 40px rgba(0, 0, 0, 0.4), 0 0 40px rgba(26, 90, 255, 0.1), inset 0 1px 0 rgba(255,255,255,0.05)",
      }}
    >
      {/* Header / drag handle */}
      <div
        className="flex items-center justify-between px-5 py-3 rounded-t-2xl"
        style={{
          borderBottom: "1px solid rgba(30, 80, 180, 0.25)",
          background:
            "linear-gradient(180deg, rgba(26,90,255,0.06) 0%, transparent 100%)",
          cursor: "grab",
        }}
      >
        <span className="text-[10px] font-semibold tracking-[0.2em] uppercase text-blue-200/80">
          Conversations
        </span>
        <button
          onClick={onClose}
          className="text-[10px] tracking-[0.15em] uppercase text-slate-500 transition-colors hover:text-blue-300"
        >
          [ close ]
        </button>
      </div>

      {/* Session list */}
      <div className="flex-1 overflow-y-auto p-3 space-y-1.5">
        {sessions.length === 0 && (
          <div className="flex h-full items-center justify-center">
            <span className="text-[10px] tracking-widest text-slate-700 uppercase">
              NO CHATS
            </span>
          </div>
        )}
        {sessions.map((s) => {
          const isActive = s.key === activeKey;
          return (
            <button
              key={s.key}
              onClick={() => onSelect(s.key)}
              className="w-full rounded-xl px-4 py-2.5 text-left transition-all duration-200"
              style={{
                background: isActive
                  ? "linear-gradient(135deg, rgba(26,90,255,0.15), rgba(0,100,255,0.05))"
                  : "rgba(10, 20, 40, 0.4)",
                border: isActive
                  ? "1px solid rgba(26, 90, 255, 0.35)"
                  : "1px solid rgba(26, 90, 255, 0.08)",
                boxShadow: isActive
                  ? "0 0 15px rgba(26, 90, 255, 0.1)"
                  : "none",
              }}
            >
              <span
                className="block text-xs leading-relaxed"
                style={{
                  color: isActive ? "#c8d8ff" : "#8899bb",
                }}
              >
                {s.preview || `Chat ${s.chatId.slice(0, 8)}`}
              </span>
              <span className="block text-[9px] tracking-wider text-slate-600 uppercase">
                {s.updatedAt ? new Date(s.updatedAt).toLocaleDateString() : "New"}
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
