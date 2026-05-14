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
      className="techy-panel absolute z-30 flex flex-col overflow-hidden rounded-2xl"
      style={{
        left: pos.x,
        top: pos.y,
        width: 480,
        height: 520,
      }}
    >
      {/* Header / drag handle */}
      <div
        className="techy-header flex items-center justify-between px-5 py-3 rounded-t-2xl"
        style={{
          cursor: "grab",
        }}
      >
        <div className="flex items-center gap-2">
          <span
            className="h-2 w-2 rounded-full"
            style={{
              background: isStreaming
                ? "rgba(var(--brand-r), var(--brand-g), var(--brand-b), 0.9)"
                : "rgba(var(--success-r), var(--success-g), var(--success-b), 0.9)",
              boxShadow: isStreaming
                ? "0 0 10px rgba(var(--brand-r), var(--brand-g), var(--brand-b), 0.7)"
                : "0 0 10px rgba(var(--success-r), var(--success-g), var(--success-b), 0.7)",
            }}
          />
          <span className="text-[10px] font-semibold tracking-[0.2em] uppercase text-[rgba(var(--text-bright-r),var(--text-bright-g),var(--text-bright-b),0.8)]">
            {isStreaming ? "Processing" : "Online"}
          </span>
        </div>
        <button
          onClick={onClose}
          className="text-[10px] tracking-[0.15em] uppercase text-[rgba(var(--text-body-r),var(--text-body-g),var(--text-body-b),0.5)] hover:text-[rgba(var(--brand-r),var(--brand-g),var(--brand-b),0.7)] transition-colors"
        >
          [ close ]
        </button>
      </div>

      {/* Messages */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto p-5 space-y-5">
        {messages.length === 0 && (
          <div className="flex h-full items-center justify-center">
            <p className="text-sm text-[rgba(var(--text-body-r),var(--text-body-g),var(--text-body-b),0.4)] tracking-wider">
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
            <div className="text-[10px] tracking-widest uppercase text-[rgba(var(--text-body-r),var(--text-body-g),var(--text-body-b),0.4)]">
              {msg.role === "user" ? "You" : "Jarvis"}
              {" "}
              <span className="text-[rgba(var(--text-body-r),var(--text-body-g),var(--text-body-b),0.35)]">
                {new Date(msg.createdAt).toLocaleTimeString([], {
                  hour: "2-digit",
                  minute: "2-digit",
                })}
              </span>
            </div>

            {/* Reasoning badge */}
            {msg.reasoning && (
              <div className="techy-bubble-reasoning max-w-[85%] rounded-xl px-3 py-1.5">
                <span className="text-[9px] font-semibold tracking-[0.15em] uppercase text-[rgba(var(--brand-r),var(--brand-g),var(--brand-b),0.5)]">
                  Reasoning
                </span>
                <p className="mt-0.5 text-[11px] leading-relaxed text-[rgba(var(--text-body-r),var(--text-body-g),var(--text-body-b),0.5)]">
                  {msg.reasoning}
                </p>
              </div>
            )}

            <div
              className={cn(
                "max-w-[85%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed",
                msg.role === "user"
                  ? "techy-bubble-user text-[rgba(var(--text-bright-r),var(--text-bright-g),var(--text-bright-b),0.9)]"
                  : "techy-bubble-assistant text-[rgba(var(--text-body-r),var(--text-body-g),var(--text-body-b),0.7)]"
              )}
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
