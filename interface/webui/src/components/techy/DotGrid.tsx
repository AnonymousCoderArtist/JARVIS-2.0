import { useEffect, useRef, useCallback, useState } from "react";

interface DotGridProps {
  offset: { x: number; y: number };
  onOffsetChange: (offset: { x: number; y: number }) => void;
}

export function DotGrid({ offset, onOffsetChange }: DotGridProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const draggingRef = useRef(false);
  const velocityRef = useRef({ x: 0, y: 0 });
  const lastPosRef = useRef({ x: 0, y: 0, time: 0 });
  const animationRef = useRef<number | null>(null);

  const spacing = 48;
  const dotRadius = 1.2;
  const [canvasSize, setCanvasSize] = useState({ width: 0, height: 0 });

  const draw = useCallback((ctx: CanvasRenderingContext2D) => {
    const { width, height } = canvasSize;
    if (width === 0 || height === 0) return;

    ctx.clearRect(0, 0, width, height);

    const worldX = offset.x;
    const worldY = offset.y;

    const startCol = Math.floor(-worldX / spacing) - 3;
    const endCol = Math.floor((width - worldX) / spacing) + 3;
    const startRow = Math.floor(-worldY / spacing) - 3;
    const endRow = Math.floor((height - worldY) / spacing) + 3;

    const maxDist = Math.max(width, height) * 0.7;
    const centerX = width / 2;
    const centerY = height / 2;

    for (let col = startCol; col <= endCol; col++) {
      for (let row = startRow; row <= endRow; row++) {
        const x = col * spacing + (worldX % spacing);
        const y = row * spacing + (worldY % spacing);

        const distFromCenter = Math.sqrt(
          Math.pow(x - centerX, 2) + Math.pow(y - centerY, 2)
        );
        
        let alpha = 0.5;
        if (distFromCenter > maxDist * 0.5) {
          const fadeStart = maxDist * 0.5;
          alpha = Math.max(0.1, 0.5 * (1 - (distFromCenter - fadeStart) / (maxDist * 0.5)));
        }

        ctx.beginPath();
        ctx.arc(x, y, dotRadius, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(100, 170, 255, ${alpha})`;
        ctx.fill();

        ctx.beginPath();
        ctx.arc(x, y, dotRadius * 3, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(26, 90, 255, ${alpha * 0.12})`;
        ctx.fill();
      }
    }

    ctx.strokeStyle = "rgba(26, 90, 255, 0.05)";
    ctx.lineWidth = 1;

    for (let col = startCol; col <= endCol; col++) {
      const x = col * spacing + (worldX % spacing);
      if (x >= -spacing && x <= width + spacing) {
        ctx.beginPath();
        ctx.moveTo(x, 0);
        ctx.lineTo(x, height);
        ctx.stroke();
      }
    }

    for (let row = startRow; row <= endRow; row++) {
      const y = row * spacing + (worldY % spacing);
      if (y >= -spacing && y <= height + spacing) {
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(width, y);
        ctx.stroke();
      }
    }
  }, [offset, canvasSize, spacing, dotRadius]);

  useEffect(() => {
    const updateSize = () => {
      if (containerRef.current) {
        const width = containerRef.current.clientWidth;
        const height = containerRef.current.clientHeight;
        setCanvasSize({ width, height });
        if (canvasRef.current) {
          canvasRef.current.width = width;
          canvasRef.current.height = height;
        }
      }
    };

    updateSize();
    window.addEventListener("resize", updateSize);
    return () => window.removeEventListener("resize", updateSize);
  }, []);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let raf = 0;
    const render = () => {
      draw(ctx);
      raf = requestAnimationFrame(render);
    };
    raf = requestAnimationFrame(render);

    return () => cancelAnimationFrame(raf);
  }, [draw]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const onDown = (e: MouseEvent) => {
      if (e.target !== canvas) return;
      draggingRef.current = true;
      lastPosRef.current = { x: e.clientX, y: e.clientY, time: Date.now() };
      velocityRef.current = { x: 0, y: 0 };
      canvas.style.cursor = "grabbing";
      document.body.style.userSelect = "none";
    };

    const onMove = (e: MouseEvent) => {
      if (!draggingRef.current) return;
      
      const now = Date.now();
      const dt = Math.max(now - lastPosRef.current.time, 1);
      const dx = e.clientX - lastPosRef.current.x;
      const dy = e.clientY - lastPosRef.current.y;
      
      velocityRef.current = {
        x: dx / dt * 16,
        y: dy / dt * 16,
      };
      
      lastPosRef.current = { x: e.clientX, y: e.clientY, time: now };
      
      onOffsetChange({
        x: offset.x + dx,
        y: offset.y + dy,
      });
    };

    const onUp = () => {
      if (!draggingRef.current) return;
      draggingRef.current = false;
      canvas.style.cursor = "grab";
      document.body.style.userSelect = "";
      
      const vel = velocityRef.current;
      if (Math.abs(vel.x) > 0.3 || Math.abs(vel.y) > 0.3) {
        const momentum = () => {
          const newVel = { ...velocityRef.current };
          newVel.x *= 0.95;
          newVel.y *= 0.95;
          
          if (Math.abs(newVel.x) < 0.1 && Math.abs(newVel.y) < 0.1) {
            return;
          }
          
          velocityRef.current = newVel;
          onOffsetChange({
            x: offset.x + newVel.x,
            y: offset.y + newVel.y,
          });
          
          animationRef.current = requestAnimationFrame(momentum);
        };
        animationRef.current = requestAnimationFrame(momentum);
      }
    };

    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      const deltaX = e.deltaX * 0.8;
      const deltaY = e.deltaY * 0.8;
      onOffsetChange({
        x: offset.x + deltaX,
        y: offset.y + deltaY,
      });
    };

    canvas.addEventListener("mousedown", onDown);
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
    canvas.addEventListener("wheel", onWheel, { passive: false });

    return () => {
      canvas.removeEventListener("mousedown", onDown);
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
      canvas.removeEventListener("wheel", onWheel);
      if (animationRef.current) {
        cancelAnimationFrame(animationRef.current);
      }
    };
  }, [offset, onOffsetChange]);

  return (
    <div
      ref={containerRef}
      className="absolute inset-0 overflow-hidden"
      style={{ zIndex: 0 }}
    >
      <canvas
        ref={canvasRef}
        className="cursor-grab"
        width={canvasSize.width}
        height={canvasSize.height}
        style={{ 
          position: "absolute",
          top: 0,
          left: 0,
          width: "100%",
          height: "100%"
        }}
      />
    </div>
  );
}