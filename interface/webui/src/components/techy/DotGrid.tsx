import { useEffect, useRef, useCallback } from "react";

interface DotGridProps {
  offset: { x: number; y: number };
  onOffsetChange: (offset: { x: number; y: number }) => void;
}

const mod = (n: number, m: number) => ((n % m) + m) % m;
const SPACING = 36;
const EXTRA = 2;

export function DotGrid({ offset, onOffsetChange }: DotGridProps) {
  const cvs = useRef<HTMLCanvasElement>(null);
  const container = useRef<HTMLDivElement>(null);
  const drag = useRef(false);
  const vel = useRef({ x: 0, y: 0 });
  const last = useRef({ x: 0, y: 0, t: 0 });
  const glide = useRef<number | null>(null);
  const off = useRef(offset);
  const sz = useRef({ w: 0, h: 0 });

  useEffect(() => { off.current = offset; }, [offset]);

  const draw = useCallback(() => {
    const canvas = cvs.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    const { w, h } = sz.current;
    if (w === 0 || h === 0) return;

    ctx.clearRect(0, 0, w, h);

    const ox = off.current.x;
    const oy = off.current.y;
    const gx = mod(ox, SPACING);
    const gy = mod(oy, SPACING);

    const c0 = Math.floor(-ox / SPACING) - EXTRA;
    const c1 = Math.ceil((w - ox) / SPACING) + EXTRA;
    const r0 = Math.floor(-oy / SPACING) - EXTRA;
    const r1 = Math.ceil((h - oy) / SPACING) + EXTRA;

    for (let c = c0; c <= c1; c++) {
      for (let r = r0; r <= r1; r++) {
        const px = c * SPACING + gx;
        const py = r * SPACING + gy;
        ctx.beginPath();
        ctx.arc(px, py, 1, 0, Math.PI * 2);
        ctx.fillStyle = "rgba(var(--brand-r), var(--brand-g), var(--brand-b), 0.18)";
        ctx.fill();
      }
    }
  }, []);

  useEffect(() => {
    let raf: number;
    const loop = () => { draw(); raf = requestAnimationFrame(loop); };
    raf = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(raf);
  }, [draw]);

  useEffect(() => {
    const sync = () => {
      const el = cvs.current;
      if (!el) return;
      const parent = el.parentElement?.parentElement;
      if (!parent) return;
      const w = parent.clientWidth;
      const h = parent.clientHeight;
      if (w === sz.current.w && h === sz.current.h) return;
      sz.current = { w, h };
      el.width = w;
      el.height = h;
      el.style.width = `${w}px`;
      el.style.height = `${h}px`;
    };
    sync();
    window.addEventListener("resize", sync);
    const obs = new ResizeObserver(sync);
    const parent = cvs.current?.parentElement?.parentElement;
    if (parent) obs.observe(parent);
    return () => { window.removeEventListener("resize", sync); obs.disconnect(); };
  }, []);

  useEffect(() => {
    const canvas = cvs.current;
    if (!canvas) return;

    const onDown = (e: MouseEvent) => {
      if (e.target !== canvas) return;
      drag.current = true;
      if (glide.current) { cancelAnimationFrame(glide.current); glide.current = null; }
      last.current = { x: e.clientX, y: e.clientY, t: Date.now() };
      vel.current = { x: 0, y: 0 };
      canvas.style.cursor = "grabbing";
    };

    const onMove = (e: MouseEvent) => {
      if (!drag.current) return;
      const now = Date.now();
      const dt = Math.max(now - last.current.t, 1);
      const dx = e.clientX - last.current.x;
      const dy = e.clientY - last.current.y;
      vel.current = { x: (dx / dt) * 16, y: (dy / dt) * 16 };
      last.current = { x: e.clientX, y: e.clientY, t: now };
      onOffsetChange({ x: offset.x + dx, y: offset.y + dy });
    };

    const onUp = () => {
      if (!drag.current) return;
      drag.current = false;
      canvas.style.cursor = "grab";
      const v = vel.current;
      if (Math.abs(v.x) > 0.3 || Math.abs(v.y) > 0.3) {
        const momentum = () => {
          vel.current.x *= 0.95;
          vel.current.y *= 0.95;
          if (Math.abs(vel.current.x) < 0.1 && Math.abs(vel.current.y) < 0.1) return;
          onOffsetChange({
            x: off.current.x + vel.current.x,
            y: off.current.y + vel.current.y,
          });
          glide.current = requestAnimationFrame(momentum);
        };
        glide.current = requestAnimationFrame(momentum);
      }
    };

    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      onOffsetChange({
        x: offset.x + e.deltaX,
        y: offset.y + e.deltaY,
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
      if (glide.current) cancelAnimationFrame(glide.current);
    };
  }, [offset, onOffsetChange]);

  return (
    <div ref={container} className="absolute inset-0" style={{ zIndex: 0 }}>
      <canvas
        ref={cvs}
        className="cursor-grab"
        style={{ position: "absolute", top: 0, left: 0, display: "block" }}
      />
    </div>
  );
}
