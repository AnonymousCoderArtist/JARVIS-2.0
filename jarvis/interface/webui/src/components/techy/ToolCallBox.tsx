import { useEffect, useRef, useState } from "react";

interface ToolCall {
  id: string;
  name: string;
  status: "running" | "completed" | "error";
  timestamp: number;
}

interface ToolCallBoxProps {
  toolCalls: ToolCall[];
  pos: { x: number; y: number };
  onPosChange?: (pos: { x: number; y: number }) => void;
  canvasOffset: { x: number; y: number };
}

export function ToolCallBox({ toolCalls, pos, onPosChange, canvasOffset }: ToolCallBoxProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState({ width: 260, height: 160 });
  const resizingRef = useRef(false);
  const startRef = useRef({ x: 0, y: 0, w: 0, h: 0 });
  const draggingRef = useRef(false);
  const grabRef = useRef({ x: 0, y: 0 });

  const visibleCalls = toolCalls.slice(-2).reverse();

  const onResizeDown = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    resizingRef.current = true;
    startRef.current = { x: e.clientX, y: e.clientY, w: size.width, h: size.height };
  };

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const onDown = (e: MouseEvent) => {
      const header = container.firstElementChild;
      if (!header || !header.contains(e.target as Node)) return;
      draggingRef.current = true;
      grabRef.current = {
        x: e.clientX - (canvasOffset.x + pos.x),
        y: e.clientY - (canvasOffset.y + pos.y),
      };
      container.style.cursor = "grabbing";
    };

    const onMove = (e: MouseEvent) => {
      if (resizingRef.current) {
        const dx = e.clientX - startRef.current.x;
        const dy = e.clientY - startRef.current.y;
        setSize({
          width: Math.max(200, startRef.current.w + dx),
          height: Math.max(100, startRef.current.h + dy),
        });
        return;
      }
      if (!draggingRef.current) return;
      e.preventDefault();
      onPosChange?.({
        x: e.clientX - canvasOffset.x - grabRef.current.x,
        y: e.clientY - canvasOffset.y - grabRef.current.y,
      });
    };

    const onUp = () => {
      resizingRef.current = false;
      draggingRef.current = false;
      container.style.cursor = "default";
    };

    container.addEventListener("mousedown", onDown);
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
    return () => {
      container.removeEventListener("mousedown", onDown);
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };
  }, [pos, onPosChange, canvasOffset]);

  return (
    <div
      ref={containerRef}
      className="absolute z-30 flex flex-col overflow-hidden rounded-2xl techy-panel"
      style={{
        left: pos.x,
        top: pos.y,
        width: size.width,
        height: size.height,
      }}
    >
      {/* Header / drag handle */}
      <div
        className="flex items-center justify-between px-4 py-2 rounded-t-2xl techy-header"
        style={{
          cursor: "grab",
        }}
      >
        <div className="flex items-center gap-2">
          <span className="relative flex h-2 w-2">
            <span
              className="absolute inline-flex h-full w-full animate-ping rounded-full"
              style={{ background: "rgba(var(--brand-r), var(--brand-g), var(--brand-b), 0.5)" }}
            />
            <span
              className="relative inline-flex h-2 w-2 rounded-full"
              style={{ background: "rgba(var(--brand-r), var(--brand-g), var(--brand-b), 0.9)" }}
            />
          </span>
          <span className="text-[10px] font-semibold tracking-[0.2em] uppercase" style={{ color: "rgba(var(--text-bright-r), var(--text-bright-g), var(--text-bright-b), 0.8)" }}>
            Tool Calls
          </span>
        </div>
        <span className="text-[10px]" style={{ color: "rgba(var(--text-muted-r), var(--text-muted-g), var(--text-muted-b), 0.5)" }}>
          {toolCalls.length} total
        </span>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-3 space-y-2">
        {visibleCalls.length === 0 && (
          <div className="flex h-full items-center justify-center">
            <span className="text-[10px] tracking-widest uppercase" style={{ color: "rgba(var(--text-body-r), var(--text-body-g), var(--text-body-b), 0.35)" }}>
              IDLE
            </span>
          </div>
        )}
        {visibleCalls.map((tc) => (
          <div
            key={tc.id}
            className="flex items-center gap-3 rounded-xl px-3 py-2"
            style={{
              background: "rgba(var(--dialog-bg-start-r), var(--dialog-bg-start-g), var(--dialog-bg-start-b), 0.5)",
              border: "1px solid rgba(var(--brand-r), var(--brand-g), var(--brand-b), 0.1)",
            }}
          >
            <span
              className="h-1.5 w-1.5 rounded-full"
              style={{
                background:
                  tc.status === "running"
                    ? "rgba(var(--brand-r), var(--brand-g), var(--brand-b), 0.8)"
                    : tc.status === "completed"
                      ? "rgba(var(--success-r), var(--success-g), var(--success-b), 0.8)"
                      : "rgba(var(--error-r), var(--error-g), var(--error-b), 0.8)",
                boxShadow:
                  tc.status === "running"
                    ? "0 0 6px rgba(var(--brand-r), var(--brand-g), var(--brand-b), 0.6)"
                    : "none",
              }}
            />
            <div className="flex flex-1 flex-col">
              <span className="text-[11px]" style={{ color: "rgba(var(--text-bright-r), var(--text-bright-g), var(--text-bright-b), 0.9)" }}>{tc.name}</span>
              <span className="text-[9px] tracking-wider uppercase" style={{ color: "rgba(var(--text-body-r), var(--text-body-g), var(--text-body-b), 0.4)" }}>
                {tc.status}
              </span>
            </div>
          </div>
        ))}
      </div>

      {/* Resize handle */}
      <div
        onMouseDown={onResizeDown}
        className="absolute bottom-0 right-0 h-4 w-4 cursor-se-resize"
        style={{
          background:
            "linear-gradient(135deg, transparent 45%, rgba(var(--brand-r), var(--brand-g), var(--brand-b), 0.3) 50%)",
        }}
      />
    </div>
  );
}
