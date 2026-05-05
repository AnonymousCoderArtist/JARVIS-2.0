import { useState } from "react";
import { ChevronDown, ChevronUp, Brain } from "lucide-react";
import { cn } from "@/lib/utils";
import { MarkdownTextRenderer } from "@/components/MarkdownTextRenderer";

interface ThinkingBlockProps {
  content: string;
  isStreaming?: boolean;
}

export function ThinkingBlock({ content, isStreaming }: ThinkingBlockProps) {
  const [isExpanded, setIsExpanded] = useState(true);

  if (!content && !isStreaming) return null;

  return (
    <div className="mb-4 flex flex-col gap-2 overflow-hidden rounded-xl border border-border/40 bg-muted/20">
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="flex items-center justify-between px-4 py-2.5 text-xs font-medium text-muted-foreground transition-colors hover:bg-muted/30"
      >
        <div className="flex items-center gap-2">
          <Brain className={cn("h-3.5 w-3.5", isStreaming && "animate-pulse text-primary")} />
          <span>{isStreaming ? "Thinking..." : "Thought for a few seconds"}</span>
        </div>
        {isExpanded ? (
          <ChevronUp className="h-3.5 w-3.5 opacity-60" />
        ) : (
          <ChevronDown className="h-3.5 w-3.5 opacity-60" />
        )}
      </button>

      {isExpanded && (
        <div className="border-t border-border/20 px-4 py-3">
          <div className="prose prose-sm prose-neutral dark:prose-invert max-w-none text-xs text-muted-foreground/90 italic">
            <MarkdownTextRenderer content={content} />
          </div>
          {isStreaming && (
            <div className="mt-2 flex gap-1">
              <div className="h-1 w-1 animate-bounce rounded-full bg-muted-foreground/40 [animation-delay:-0.3s]"></div>
              <div className="h-1 w-1 animate-bounce rounded-full bg-muted-foreground/40 [animation-delay:-0.15s]"></div>
              <div className="h-1 w-1 animate-bounce rounded-full bg-muted-foreground/40"></div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
