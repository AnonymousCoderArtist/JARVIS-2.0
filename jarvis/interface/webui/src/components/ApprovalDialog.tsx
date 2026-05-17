import { useState } from "react";
import { AlertTriangle, CheckCircle, XCircle } from "lucide-react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface ApprovalDialogProps {
  isOpen: boolean;
  toolName: string;
  toolArgs: Record<string, unknown>;
  requiredPermissions: string[];
  onApprove: (alwaysAllow: boolean) => void;
  onReject: () => void;
}

export function ApprovalDialog({
  isOpen,
  toolName,
  toolArgs,
  requiredPermissions,
  onApprove,
  onReject,
}: ApprovalDialogProps) {
  const [showOptions, setShowOptions] = useState(false);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div
        className={cn(
          "w-full max-w-md rounded-lg border border-border/60 bg-background p-6 shadow-lg",
          "animate-in zoom-in-95 duration-200",
        )}
      >
        <div className="flex items-start gap-4">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-warning/10">
            <AlertTriangle className="h-5 w-5 text-warning" />
          </div>
          <div className="flex-1">
            <h3 className="text-base font-semibold">Tool Execution Request</h3>
            <p className="mt-1 text-sm text-muted-foreground">
              The assistant wants to execute the following tool:
            </p>
          </div>
        </div>

        <div className="mt-4 rounded-md bg-muted/50 p-3">
          <div className="text-sm font-medium">{toolName}</div>
          {Object.keys(toolArgs).length > 0 && (
            <pre className="mt-2 max-h-32 overflow-auto text-xs text-muted-foreground">
              {JSON.stringify(toolArgs, null, 2)}
            </pre>
          )}
        </div>

        {requiredPermissions.length > 0 && (
          <div className="mt-3">
            <div className="text-xs font-medium text-muted-foreground">
              Required permissions:
            </div>
            <div className="mt-1 flex flex-wrap gap-1">
              {requiredPermissions.map((perm) => (
                <span
                  key={perm}
                  className="inline-flex items-center rounded-full bg-secondary px-2 py-0.5 text-xs font-medium"
                >
                  {perm}
                </span>
              ))}
            </div>
          </div>
        )}

        {!showOptions ? (
          <div className="mt-6 flex justify-end gap-2">
            <Button variant="outline" size="sm" onClick={onReject}>
              <XCircle className="mr-1.5 h-4 w-4" />
              Reject
            </Button>
            <Button
              size="sm"
              onClick={() => setShowOptions(true)}
              className="bg-warning text-warning-foreground hover:bg-warning/90"
            >
              <CheckCircle className="mr-1.5 h-4 w-4" />
              Approve
            </Button>
          </div>
        ) : (
          <div className="mt-6 flex justify-end gap-2">
            <Button variant="outline" size="sm" onClick={onReject}>
              Cancel
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                onApprove(false);
                setShowOptions(false);
              }}
            >
              Approve Once
            </Button>
            <Button
              size="sm"
              onClick={() => {
                onApprove(true);
                setShowOptions(false);
              }}
              className="bg-warning text-warning-foreground hover:bg-warning/90"
            >
              Always Allow
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}