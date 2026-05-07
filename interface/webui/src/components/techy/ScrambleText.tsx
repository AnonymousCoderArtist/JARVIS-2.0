import { useEffect, useRef, useState } from "react";

interface ScrambleTextProps {
  text: string;
  className?: string;
  chars?: string;
}

export function ScrambleText({
  text,
  className = "",
  chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*",
}: ScrambleTextProps) {
  const [display, setDisplay] = useState(text);
  const prevTextRef = useRef(text);
  const frameRef = useRef(0);

  useEffect(() => {
    const prev = prevTextRef.current;
    const next = text;
    prevTextRef.current = next;

    if (prev === next) return;

    const maxLen = Math.max(prev.length, next.length);
    const startTime = performance.now();
    const duration = 600; // ms per character reveal roughly

    const animate = (now: number) => {
      const elapsed = now - startTime;
      const progress = Math.min(elapsed / duration, 1);

      let result = "";
      for (let i = 0; i < maxLen; i++) {
        if (i < next.length && elapsed > i * (duration / next.length)) {
          result += next[i];
        } else if (i < prev.length && elapsed > i * (duration / prev.length)) {
          result += next[i] ?? prev[i];
        } else {
          result += chars[Math.floor(Math.random() * chars.length)];
        }
      }

      setDisplay(result);

      if (progress < 1) {
        frameRef.current = requestAnimationFrame(animate);
      } else {
        setDisplay(next);
      }
    };

    frameRef.current = requestAnimationFrame(animate);

    return () => cancelAnimationFrame(frameRef.current);
  }, [text, chars]);

  return <span className={className}>{display}</span>;
}
