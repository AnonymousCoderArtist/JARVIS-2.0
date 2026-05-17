import { useEffect, useState, useRef } from "react";
import { cn } from "@/lib/utils";

interface ThinkingIndicatorProps {
  isVisible: boolean;
  text?: string;
  className?: string;
}

/**
 * Thinking indicator component that shows animated dots
 * similar to the typing indicator but with a "thinking" label.
 * Displays reasoning content when provided.
 */
export function ThinkingIndicator({
  isVisible,
  text,
  className,
}: ThinkingIndicatorProps) {
  const [displayText, setDisplayText] = useState(text || "");
  const [showCursor, setShowCursor] = useState(true);
  const textRef = useRef(text || "");

  useEffect(() => {
    textRef.current = text || "";
    setDisplayText(textRef.current);
  }, [text]);

  useEffect(() => {
    if (isVisible && text) {
      // Blinking cursor effect for thinking
      const cursorInterval = setInterval(() => {
        setShowCursor((prev) => !prev);
      }, 500);
      return () => clearInterval(cursorInterval);
    }
  }, [isVisible, text]);

  if (!isVisible && !text) return null;

  return (
    <div
      className={cn(
        "flex items-start gap-2 px-4 py-2",
        "transition-all duration-200",
        isVisible ? "max-h-40 opacity-100" : "max-h-0 opacity-0",
        className
      )}
    >
      <div className="flex-shrink-0 w-6 h-6 rounded-full bg-primary/10 flex items-center justify-center">
        <svg
          className="w-4 h-4 text-primary animate-spin"
          viewBox="0 0 24 24"
          fill="none"
        >
          <circle
            className="opacity-25"
            cx="12"
            cy="12"
            r="10"
            stroke="currentColor"
            strokeWidth="4"
          />
          <path
            className="opacity-75"
            d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938"
            fill="currentColor"
          />
        </svg>
      </div>

      <div className="flex-1 text-sm text-muted-foreground">
        {text && (
          <div className="whitespace-pre-wrap break-words">
            {displayText}
            {isVisible && showCursor && (
              <span className="animate-pulse">|</span>
            )}
          </div>
        )}
        {!text && (
          <div className="flex items-center gap-1">
            <span className="text-xs font-medium text-muted-foreground/70">
              Thinking
            </span>
            <ThinkingDots />
          </div>
        )}
      </div>
    </div>
  );
}

/**
 * Three animated dots for thinking indicator.
 */
function ThinkingDots() {
  return (
    <span className="inline-flex items-center gap-1">
      <Dot delay="0ms" />
      <Dot delay="150ms" />
      <Dot delay="300ms" />
    </span>
  );
}

interface DotProps {
  delay: string;
}

function Dot({ delay }: DotProps) {
  return (
    <span
      style={{ animationDelay: delay }}
      className={cn(
        "inline-block w-1.5 h-1.5 rounded-full bg-muted-foreground/60",
        "animate-bounce"
      )}
    />
  );
}