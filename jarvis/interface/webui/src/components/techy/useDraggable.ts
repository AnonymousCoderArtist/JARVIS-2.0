import { useEffect, useRef, useState } from "react";

interface Position {
  x: number;
  y: number;
}

export function useDraggable(initial: Position) {
  const [pos, setPos] = useState<Position>(initial);
  const draggingRef = useRef(false);
  const offsetRef = useRef({ x: 0, y: 0 });
  const elRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = elRef.current;
    if (!el) return;

    const onDown = (e: MouseEvent) => {
      draggingRef.current = true;
      const rect = el.getBoundingClientRect();
      offsetRef.current = { x: e.clientX - rect.left, y: e.clientY - rect.top };
      el.style.cursor = "grabbing";
    };

    const onMove = (e: MouseEvent) => {
      if (!draggingRef.current) return;
      e.preventDefault();
      setPos({
        x: e.clientX - offsetRef.current.x,
        y: e.clientY - offsetRef.current.y,
      });
    };

    const onUp = () => {
      draggingRef.current = false;
      el.style.cursor = "grab";
    };

    el.addEventListener("mousedown", onDown);
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);

    return () => {
      el.removeEventListener("mousedown", onDown);
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };
  }, []);

  return { ref: elRef, pos };
}
