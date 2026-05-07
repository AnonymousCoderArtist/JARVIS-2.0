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
      className="absolute z-30 flex flex-col overflow-hidden rounded-2xl"
      style={{
        left: pos.x,
        top: pos.y,
        width: size.width,
        height: size.height,
        background:
          "linear-gradient(180deg, rgba(8, 16, 38, 0.92) 0%, rgba(5, 10, 24, 0.92) 100%)",
        backdropFilter: "blur(20px)",
        border: "1px solid rgba(26, 90, 255, 0.3)",
        boxShadow:
          "0 8px 40px rgba(0, 0, 0, 0.4), 0 0 30px rgba(26, 90, 255, 0.1), inset 0 1px 0 rgba(255,255,255,0.05)",
      }}
    >
      {/* Header / drag handle */}
      <div
        className="flex items-center justify-between px-4 py-2 rounded-t-2xl"
        style={{
          borderBottom: "1px solid rgba(30, 80, 180, 0.25)",
          background:
            "linear-gradient(180deg, rgba(26,90,255,0.06) 0%, transparent 100%)",
          cursor: "grab",
        }}
      >
        <div className="flex items-center gap-2">
          <span className="relative flex h-2 w-2">
            <span
              className="absolute inline-flex h-full w-full animate-ping rounded-full"
              style={{ background: "rgba(26, 90, 255, 0.5)" }}
            />
            <span
              className="relative inline-flex h-2 w-2 rounded-full"
              style={{ background: "rgba(26, 90, 255, 0.9)" }}
            />
          </span>
          <span className="text-[10px] font-semibold tracking-[0.2em] uppercase text-blue-200/80">
            Tool Calls
          </span>
        </div>
        <span className="text-[10px] text-slate-500">
          {toolCalls.length} total
        </span>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-3 space-y-2">
        {visibleCalls.length === 0 && (
          <div className="flex h-full items-center justify-center">
            <span className="text-[10px] tracking-widest text-slate-700 uppercase">
              IDLE
            </span>
          </div>
        )}
        {visibleCalls.map((tc) => (
          <div
            key={tc.id}
            className="flex items-center gap-3 rounded-xl px-3 py-2"
            style={{
              background: "rgba(10, 20, 40, 0.5)",
              border: "1px solid rgba(26, 90, 255, 0.1)",
            }}
          >
            <span
              className="h-1.5 w-1.5 rounded-full"
              style={{
                background:
                  tc.status === "running"
                    ? "rgba(26, 90, 255, 0.8)"
                    : tc.status === "completed"
                      ? "rgba(60, 180, 100, 0.8)"
                      : "rgba(220, 60, 60, 0.8)",
                boxShadow:
                  tc.status === "running"
                    ? "0 0 6px rgba(26, 90, 255, 0.6)"
                    : "none",
              }}
            />
            <div className="flex flex-1 flex-col">
              <span className="text-[11px] text-blue-200/90">{tc.name}</span>
              <span className="text-[9px] tracking-wider uppercase text-slate-600">
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
            "linear-gradient(135deg, transparent 45%, rgba(26,90,255,0.3) 50%)",
        }}
      />
    </div>
  );
}
