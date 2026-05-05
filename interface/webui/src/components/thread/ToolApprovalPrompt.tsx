import { Check, Shield, X } from "lucide-react";
import { useTranslation } from "react-i18next";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface ToolApprovalPromptProps {
  toolName: string;
  toolArgs: Record<string, unknown>;
  requiredPermissions: string[];
  onResponse: (approved: boolean, alwaysAllow?: boolean) => void;
}

export function ToolApprovalPrompt({
  toolName,
  toolArgs,
  requiredPermissions,
  onResponse,
}: ToolApprovalPromptProps) {
  const { t } = useTranslation();
  const [alwaysAllow, setAlwaysAllow] = useState(false);

  return (
    <div className={cn(
      "mb-4 overflow-hidden rounded-lg border border-amber-200 bg-amber-50/50 shadow-sm",
      "dark:border-amber-900/50 dark:bg-amber-950/20"
    )}>
      <div className="border-b border-amber-200/50 px-4 py-3 dark:border-amber-900/30">
        <div className="flex items-center gap-2 text-sm font-semibold text-amber-800 dark:text-amber-400">
          <Shield className="h-4 w-4" />
          {t("thread.approval.title", { defaultValue: "Tool Approval Requested" })}
        </div>
        <p className="mt-0.5 text-[11px] text-amber-700/70 dark:text-amber-500/60">
          {t("thread.approval.description", {
            defaultValue: "Jarvis wants to execute a tool that requires your permission.",
          })}
        </p>
      </div>
      
      <div className="px-4 py-3">
        <div className="rounded-md border border-amber-200/50 bg-white/80 p-2 font-mono dark:border-amber-800/30 dark:bg-black/40">
          <div className="text-xs font-bold text-amber-900 dark:text-amber-300">{toolName}</div>
          <pre className="mt-1 max-h-40 overflow-auto whitespace-pre-wrap text-[10px] text-muted-foreground">
            {JSON.stringify(toolArgs, null, 2)}
          </pre>
        </div>
        
        {requiredPermissions.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1">
            {requiredPermissions.map((perm) => (
              <span
                key={perm}
                className="inline-flex items-center rounded-full bg-amber-100 px-2 py-0.5 text-[10px] font-medium text-amber-800 dark:bg-amber-900/40 dark:text-amber-300"
              >
                {perm}
              </span>
            ))}
          </div>
        )}

        <div className="mt-3 flex items-center gap-2">
          <button
            type="button"
            onClick={() => setAlwaysAllow(!alwaysAllow)}
            className="flex items-center gap-2 outline-none"
          >
            <div className={cn(
              "flex h-4 w-4 items-center justify-center rounded border transition-colors",
              alwaysAllow 
                ? "border-amber-600 bg-amber-600 text-white dark:border-amber-700 dark:bg-amber-700" 
                : "border-amber-300 bg-white dark:border-amber-800 dark:bg-black/40"
            )}>
              {alwaysAllow && <Check className="h-3 w-3" />}
            </div>
            <span className="text-[11px] font-medium text-amber-900/80 dark:text-amber-300/80">
              {t("thread.approval.alwaysAllow", { defaultValue: "Always allow this tool" })}
            </span>
          </button>
        </div>
      </div>

      <div className="flex justify-end gap-2 bg-amber-100/30 px-4 py-3 dark:bg-amber-900/10">
        <Button
          size="sm"
          variant="outline"
          className="h-8 border-amber-200 bg-transparent text-[11px] hover:bg-amber-100 hover:text-amber-900 dark:border-amber-800 dark:hover:bg-amber-900/30 dark:hover:text-amber-300"
          onClick={() => onResponse(false)}
        >
          <X className="mr-1 h-3 w-3" />
          {t("common.deny", { defaultValue: "Deny" })}
        </Button>
        <Button
          size="sm"
          className="h-8 bg-amber-600 text-[11px] text-white hover:bg-amber-700 dark:bg-amber-700 dark:hover:bg-amber-600"
          onClick={() => onResponse(true, alwaysAllow)}
        >
          <Check className="mr-1 h-3 w-3" />
          {t("common.approve", { defaultValue: "Approve" })}
        </Button>
      </div>
    </div>
  );
}
