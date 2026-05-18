import { useState } from "react";
import { Shield, AlertTriangle, Check, X, Lock } from "lucide-react";

interface ApprovalDialogProps {
  open: boolean;
  toolName: string;
  toolArgs: Record<string, unknown>;
  requiredPermissions: string[];
  onResponse: (approved: boolean, alwaysAllow?: boolean) => void;
}

export function ApprovalDialog({ open, toolName, toolArgs, requiredPermissions, onResponse }: ApprovalDialogProps) {
  const [alwaysAllow, setAlwaysAllow] = useState(false);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
      <div className="techy-dialog-amber w-full max-w-md overflow-hidden rounded-2xl">
        <div className="techy-header-amber flex items-center gap-3 px-5 py-4">
          <div className="flex h-8 w-8 items-center justify-center rounded-full" style={{ background: "rgba(var(--amber-r), var(--amber-g), var(--amber-b), 0.12)" }}>
            <Shield className="h-4 w-4" style={{ color: "rgba(var(--amber-text-r), var(--amber-text-g), var(--amber-text-b), 0.8)" }} />
          </div>
          <div>
            <div className="text-sm font-bold" style={{ color: "rgba(var(--amber-text-r), var(--amber-text-g), var(--amber-text-b), 0.9)" }}>Tool Approval Required</div>
            <div className="text-[10px]" style={{ color: "rgba(var(--amber-muted-r), var(--amber-muted-g), var(--amber-muted-b), 0.5)" }}>
              The agent needs permission to execute this tool
            </div>
          </div>
        </div>

        <div className="p-5 space-y-3">
          <div className="flex items-center gap-2">
            <AlertTriangle className="h-3.5 w-3.5" style={{ color: "rgba(var(--amber-r), var(--amber-g), var(--amber-b), 0.6)" }} />
            <span className="text-sm font-mono font-bold" style={{ color: "rgba(var(--amber-text-r), var(--amber-text-g), var(--amber-text-b), 0.9)" }}>{toolName}</span>
          </div>

          {Object.keys(toolArgs).length > 0 && (
            <div className="p-3 rounded-xl font-mono" style={{ background: "rgba(0,0,0,0.3)", border: "1px solid rgba(var(--amber-r), var(--amber-g), var(--amber-b), 0.1)" }}>
              <pre className="text-[10px] leading-relaxed whitespace-pre-wrap max-h-32 overflow-y-auto" style={{ color: "rgba(var(--amber-muted-r), var(--amber-muted-g), var(--amber-muted-b), 0.6)" }}>
                {JSON.stringify(toolArgs, null, 2)}
              </pre>
            </div>
          )}

          {requiredPermissions.length > 0 && (
            <div className="flex flex-wrap gap-1">
              {requiredPermissions.map((perm, i) => (
                <span key={i} className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[9px]" style={{ background: "rgba(var(--amber-r), var(--amber-g), var(--amber-b), 0.08)", border: "1px solid rgba(var(--amber-r), var(--amber-g), var(--amber-b), 0.15)", color: "rgba(var(--amber-muted-r), var(--amber-muted-g), var(--amber-muted-b), 0.6)" }}>
                  <Lock className="h-2.5 w-2.5" /> {perm}
                </span>
              ))}
            </div>
          )}

          <label className="flex items-center gap-2 cursor-pointer">
            <button
              type="button"
              onClick={() => setAlwaysAllow(!alwaysAllow)}
              className="flex h-4 w-4 items-center justify-center rounded transition-colors"
              style={{
                background: alwaysAllow ? "rgba(var(--amber-r), var(--amber-g), var(--amber-b), 0.2)" : "transparent",
                border: alwaysAllow ? "1px solid rgba(var(--amber-r), var(--amber-g), var(--amber-b), 0.5)" : "1px solid rgba(var(--amber-r), var(--amber-g), var(--amber-b), 0.2)",
              }}
            >
              {alwaysAllow && <Check className="h-3 w-3" style={{ color: "rgba(var(--amber-text-r), var(--amber-text-g), var(--amber-text-b), 0.8)" }} />}
            </button>
            <span className="text-[10px]" style={{ color: "rgba(var(--amber-muted-r), var(--amber-muted-g), var(--amber-muted-b), 0.5)" }}>Always allow this tool this session</span>
          </label>
        </div>

        <div className="flex items-center justify-end gap-3 px-5 py-4 border-t" style={{ borderColor: "rgba(var(--amber-r), var(--amber-g), var(--amber-b), 0.12)" }}>
          <button
            onClick={() => onResponse(false)}
            className="flex items-center gap-2 px-4 py-2 text-xs font-medium rounded-xl transition-all hover:bg-red-500/10"
            style={{ color: "rgba(var(--error-r), var(--error-g), var(--error-b), 0.7)", border: "1px solid rgba(var(--error-r), var(--error-g), var(--error-b), 0.2)" }}
          >
            <X className="h-3 w-3" /> Deny
          </button>
          <button
            onClick={() => onResponse(true, alwaysAllow)}
            className="flex items-center gap-2 px-5 py-2 text-xs font-medium rounded-xl transition-all"
            style={{
              background: "linear-gradient(135deg, rgba(var(--amber-r), var(--amber-g), var(--amber-b), 0.2), rgba(var(--amber-r), calc(var(--amber-g) - 60), calc(var(--amber-b) - 30), 0.15))",
              border: "1px solid rgba(var(--amber-r), var(--amber-g), var(--amber-b), 0.3)",
              color: "rgba(var(--amber-text-r), var(--amber-text-g), var(--amber-text-b), 0.8)",
            }}
          >
            <Check className="h-3 w-3" /> Approve
          </button>
        </div>
      </div>
    </div>
  );
}
