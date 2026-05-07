import { useMemo } from "react";
import type { UIMessage } from "@/lib/types";
import { ScrambleText } from "./ScrambleText";

interface SphereResponseProps {
  thinking: string;
  messages: UIMessage[];
  isStreaming: boolean;
  sphereX: number;
  sphereY: number;
}

export function SphereResponse({ thinking, messages, isStreaming, sphereX, sphereY }: SphereResponseProps) {
  const latestAssistant = useMemo(() => {
    // Find the most recent assistant message that has content
    for (let i = messages.length - 1; i >= 0; i--) {
      if (messages[i].role === "assistant" && messages[i].content) {
        return messages[i];
      }
    }
    return null;
  }, [messages]);

  // If nothing to show, hide
  if (!thinking && !latestAssistant) return null;

  const isThinking = isStreaming && !!thinking;
  const text = isThinking ? thinking : (latestAssistant?.content || "");
  const label = isThinking ? "Reasoning" : "Response";
  const color = isThinking ? "rgba(100, 160, 255, 0.7)" : "rgba(140, 200, 255, 0.9)";

  return (
    <div
      className="fixed z-40 rounded-2xl px-4 py-3"
      style={{
        left: sphereX + 160,
        top: sphereY - 30,
        width: 260,
        display: "flex",
        flexDirection: "column",
        maxHeight: 180,
        background:
          "linear-gradient(180deg, rgba(8, 16, 38, 0.57), rgba(5, 10, 24, 0.47))",
        backdropFilter: "blur(20px)",
        border: "1px solid rgba(26, 90, 255, 0.3)",
        boxShadow:
          "0 8px 30px rgba(0, 0, 0, 0.4), 0 0 25px rgba(26, 90, 255, 0.1), inset 0 1px 0 rgba(255,255,255,0.05)",
      }}
    >
      <span
        className="text-[9px] font-semibold tracking-[0.2em] uppercase"
        style={{ color: isThinking ? "rgba(100,160,255,0.6)" : "rgba(140,200,255,0.7)" }}
      >
        {label}
      </span>
      <div className="mt-1.5 max-h-32 overflow-hidden">
        <p className="text-[15px] leading-relaxed" style={{ color }}>
          {isThinking ? (
            <ScrambleText text={text} />
          ) : (
            text
          )}
        </p>
      </div>
    </div>
  );
}
