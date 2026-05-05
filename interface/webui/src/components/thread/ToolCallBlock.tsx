import { useState } from "react";
import { ChevronDown, ChevronUp, Terminal, CheckCircle2, XCircle, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";
import type { UIToolCall } from "@/lib/types";

interface ToolCallBlockProps {
  toolCall: UIToolCall;
}

export function ToolCallBlock({ toolCall }: ToolCallBlockProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const isPending = toolCall.result === undefined;
  const isSuccess = toolCall.success === true;
  const isError = toolCall.success === false;

  return (
    <div className={cn(
      "mb-2 flex flex-col overflow-hidden rounded-lg border text-xs transition-all",
      isPending && "border-blue-200/50 bg-blue-50/10 dark:border-blue-900/30 dark:bg-blue-950/5",
      isSuccess && "border-emerald-200/50 bg-emerald-50/10 dark:border-emerald-900/30 dark:bg-emerald-950/5",
      isError && "border-rose-200/50 bg-rose-50/10 dark:border-rose-900/30 dark:bg-rose-950/5"
    )}>
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="flex items-center justify-between px-3 py-2 transition-colors hover:bg-black/5 dark:hover:bg-white/5"
      >
        <div className="flex items-center gap-2">
          {isPending ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin text-blue-500" />
          ) : isSuccess ? (
            <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500" />
          ) : (
            <XCircle className="h-3.5 w-3.5 text-rose-500" />
          )}
          <span className="font-mono font-medium tracking-tight">
            {toolCall.name}
            {isPending && <span className="ml-2 font-sans text-[10px] font-normal opacity-60">Running...</span>}
          </span>
        </div>
        {isExpanded ? (
          <ChevronUp className="h-3.5 w-3.5 opacity-60" />
        ) : (
          <ChevronDown className="h-3.5 w-3.5 opacity-60" />
        )}
      </button>

      {isExpanded && (
        <div className="flex flex-col gap-3 border-t border-black/5 bg-black/5 px-3 py-3 dark:border-white/5 dark:bg-white/5">
          <div className="flex flex-col gap-1.5">
            <div className="flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wider opacity-50">
              <Terminal className="h-3 w-3" />
              Arguments
            </div>
            <pre className="overflow-x-auto rounded-md bg-black/10 p-2 font-mono text-[10px] dark:bg-black/40">
              {JSON.stringify(toolCall.args, null, 2)}
            </pre>
          </div>

          {!isPending && (
            <div className="flex flex-col gap-1.5">
              <div className="flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wider opacity-50">
                <CheckCircle2 className={cn("h-3 w-3", isSuccess ? "text-emerald-500" : "text-rose-500")} />
                Output
              </div>
              <pre className={cn(
                "max-h-60 overflow-auto rounded-md p-2 font-mono text-[10px]",
                isSuccess ? "bg-emerald-500/5" : "bg-rose-500/5"
              )}>
                {toolCall.result}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
EOF
