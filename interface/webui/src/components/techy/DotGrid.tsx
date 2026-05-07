import { useEffect, useRef } from "react";

interface DotGridProps {
  offset: { x: number; y: number };
  onOffsetChange: (offset: { x: number; y: number }) => void;
}

export function DotGrid({ offset, onOffsetChange }: DotGridProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const draggingRef = useRef(false);
  const startRef = useRef({ mx: 0, my: 0, ox: 0, oy: 0 });

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let raf = 0;

    const resize = () => {
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
    };

    const draw = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      const spacing = 48;
      const dotRadius = 1.2;

      const startX = offset.x % spacing;
      const startY = offset.y % spacing;

      // Draw faint grid lines
      ctx.strokeStyle = "rgba(26, 90, 255, 0.08)";
      ctx.lineWidth = 1;

      for (let x = startX - spacing; x < canvas.width + spacing; x += spacing) {
        ctx.beginPath();
        ctx.moveTo(x, 0);
        ctx.lineTo(x, canvas.height);
        ctx.stroke();
      }
      for (let y = startY - spacing; y < canvas.height + spacing; y += spacing) {
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(canvas.width, y);
        ctx.stroke();
      }

      // Draw dots — uniform brightness, no edge fade = infinite feel
      for (let x = startX - spacing; x < canvas.width + spacing; x += spacing) {
        for (let y = startY - spacing; y < canvas.height + spacing; y += spacing) {
          const alpha = 0.45;

          ctx.beginPath();
          ctx.arc(x, y, dotRadius, 0, Math.PI * 2);
          ctx.fillStyle = `rgba(100, 170, 255, ${alpha})`;
          ctx.fill();

          // Soft glow
          ctx.beginPath();
          ctx.arc(x, y, dotRadius * 4, 0, Math.PI * 2);
          ctx.fillStyle = `rgba(26, 90, 255, 0.08)`;
          ctx.fill();
        }
      }

      raf = requestAnimationFrame(draw);
    };

    const onDown = (e: MouseEvent) => {
      if (e.target !== canvas) return;
      draggingRef.current = true;
      startRef.current = { mx: e.clientX, my: e.clientY, ox: offset.x, oy: offset.y };
      canvas.style.cursor = "grabbing";
    };

    const onMove = (e: MouseEvent) => {
      if (!draggingRef.current) return;
      const dx = e.clientX - startRef.current.mx;
      const dy = e.clientY - startRef.current.my;
      onOffsetChange({
        x: startRef.current.ox + dx,
        y: startRef.current.oy + dy,
      });
    };

    const onUp = () => {
      draggingRef.current = false;
      canvas.style.cursor = "grab";
    };

    resize();
    window.addEventListener("resize", resize);
    canvas.addEventListener("mousedown", onDown);
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);

    raf = requestAnimationFrame(draw);

    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", resize);
      canvas.removeEventListener("mousedown", onDown);
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };
  }, [offset, onOffsetChange]);

  return (
    <canvas
      ref={canvasRef}
      className="absolute inset-0 cursor-grab"
      style={{ zIndex: 0 }}
    />
  );
}
