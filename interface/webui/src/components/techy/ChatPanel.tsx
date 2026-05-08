import { useEffect, useRef } from "react";
import type { UIMessage } from "@/lib/types";
import { ScrambleText } from "./ScrambleText";
import { cn } from "@/lib/utils";

interface ChatPanelProps {
  open: boolean;
  messages: UIMessage[];
  isStreaming: boolean;
  onClose: () => void;
  pos: { x: number; y: number };
  onPosChange?: (pos: { x: number; y: number }) => void;
  canvasOffset: { x: number; y: number };
}

export function ChatPanel({ open, messages, isStreaming, onClose, pos, onPosChange, canvasOffset }: ChatPanelProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const draggingRef = useRef(false);
  const grabRef = useRef({ x: 0, y: 0 });

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  useEffect(() => {
    const panel = panelRef.current;
    if (!panel) return;

    const onDown = (e: MouseEvent) => {
      const header = panel.firstElementChild;
      if (!header || !header.contains(e.target as Node)) return;
      draggingRef.current = true;
      // Store offset from mouse to widget top-left in screen coords
      grabRef.current = {
        x: e.clientX - (canvasOffset.x + pos.x),
        y: e.clientY - (canvasOffset.y + pos.y),
      };
      panel.style.cursor = "grabbing";
    };

    const onMove = (e: MouseEvent) => {
      if (!draggingRef.current) return;
      e.preventDefault();
      // New container-relative position
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
        width: 480,
        height: 520,
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
        <div className="flex items-center gap-2">
          <span
            className="h-2 w-2 rounded-full"
            style={{
              background: isStreaming
                ? "rgba(26, 90, 255, 0.9)"
                : "rgba(60, 180, 100, 0.9)",
              boxShadow: isStreaming
                ? "0 0 10px rgba(26, 90, 255, 0.7)"
                : "0 0 10px rgba(60, 180, 100, 0.7)",
            }}
          />
          <span className="text-[10px] font-semibold tracking-[0.2em] uppercase text-blue-200/80">
            {isStreaming ? "Processing" : "Online"}
          </span>
        </div>
        <button
          onClick={onClose}
          className="text-[10px] tracking-[0.15em] uppercase text-slate-500 transition-colors hover:text-blue-300"
        >
          [ close ]
        </button>
      </div>

      {/* Messages */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto p-5 space-y-5">
        {messages.length === 0 && (
          <div className="flex h-full items-center justify-center">
            <p className="text-sm text-slate-600 tracking-wider">
              NO ACTIVE TRANSMISSION
            </p>
          </div>
        )}

        {messages.map((msg, i) => (
          <div
            key={msg.id}
            className={cn(
              "flex flex-col gap-1",
              msg.role === "user" ? "items-end" : "items-start"
            )}
          >
            <div
              className="text-[10px] tracking-widest uppercase text-slate-600"
            >
              {msg.role === "user" ? "You" : "Jarvis"}
              {" "}
              <span className="text-slate-700">
                {new Date(msg.createdAt).toLocaleTimeString([], {
                  hour: "2-digit",
                  minute: "2-digit",
                })}
              </span>
            </div>

            {/* Reasoning badge */}
            {msg.reasoning && (
              <div
                className="max-w-[85%] rounded-xl px-3 py-1.5"
                style={{
                  background: "rgba(26, 90, 255, 0.06)",
                  border: "1px solid rgba(26, 90, 255, 0.12)",
                }}
              >
                <span className="text-[9px] font-semibold tracking-[0.15em] uppercase text-blue-400/60">
                  Reasoning
                </span>
                <p className="mt-0.5 text-[11px] leading-relaxed text-slate-500">
                  {msg.reasoning}
                </p>
              </div>
            )}

            <div
              className={cn(
                "max-w-[85%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed",
                msg.role === "user"
                  ? "text-blue-100"
                  : "text-slate-300"
              )}
              style={{
                background:
                  msg.role === "user"
                    ? "rgba(26, 90, 255, 0.12)"
                    : "rgba(15, 25, 45, 0.6)",
                border:
                  msg.role === "user"
                    ? "1px solid rgba(26, 90, 255, 0.2)"
                    : "1px solid rgba(40, 70, 120, 0.2)",
              }}
            >
              {msg.role === "assistant" && msg.isStreaming && i === messages.length - 1 ? (
                <ScrambleText text={msg.content} />
              ) : (
                msg.content
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
