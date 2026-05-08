import { useEffect, useRef } from "react";
import { animate, scrambleText } from "animejs";

interface ScrambleTextProps {
  text: string;
  className?: string;
}

export function ScrambleText({ text, className = "" }: ScrambleTextProps) {
  const elRef = useRef<HTMLSpanElement>(null);

  useEffect(() => {
    const el = elRef.current;
    if (!el) return;

    animate(el, {
      innerHTML: scrambleText({
        text,
        duration: 600,
        chars: "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*",
      }),
    });
  }, [text]);

  return <span ref={elRef} className={className} />;
}
