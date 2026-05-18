import { useState, useEffect, useCallback } from "react";
import { useClient } from "@/providers/ClientProvider";
import { getSessionCheckpoints, rewindSession } from "@/lib/api";
import { X, Undo2, FileText } from "lucide-react";

interface RewindDialogProps {
  open: boolean;
  onClose: () => void;
  sessionId: string | null;
}

export function RewindDialog({ open, onClose, sessionId }: RewindDialogProps) {
  const { token } = useClient();
  const [checkpoints, setCheckpoints] = useState<Array<{ index: number; content: string; timestamp: string; has_file_changes: boolean }>>([]);
  const [selectedIndex, setSelectedIndex] = useState<number | null>(null);
  const [rewinding, setRewinding] = useState(false);
  const [result, setResult] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!sessionId) return;
    const r = await getSessionCheckpoints(token, sessionId);
    setCheckpoints(r.checkpoints);
  }, [token, sessionId]);

  useEffect(() => { if (open && sessionId) load(); }, [open, sessionId, load]);

  const handleRewind = useCallback(async () => {
    if (selectedIndex === null || !sessionId) return;
    setRewinding(true);
    const r = await rewindSession(token, sessionId, selectedIndex);
    setRewinding(false);
    if (r.success) {
      setResult(`Rewound to message #${selectedIndex + 1}.`);
      setTimeout(() => { setResult(null); onClose(); }, 1500);
    }
  }, [selectedIndex, sessionId, token, onClose]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
      <div className="techy-dialog w-full max-w-lg overflow-hidden rounded-2xl">
        <div className="techy-header flex items-center justify-between px-5 py-4">
          <div className="flex items-center gap-2">
            <Undo2 className="h-4 w-4" style={{ color: "rgba(var(--text-bright-r), var(--text-bright-g), var(--text-bright-b), 0.8)" }} />
            <span className="text-sm font-bold tracking-wider uppercase" style={{ color: "rgba(var(--text-bright-r), var(--text-bright-g), var(--text-bright-b), 0.9)" }}>
              Rewind Conversation
            </span>
          </div>
          <button onClick={onClose} className="p-1 rounded-lg hover:bg-blue-500/10" style={{ color: "rgba(var(--text-muted-r), var(--text-muted-g), var(--text-muted-b), 0.6)" }}>
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="p-5 max-h-[55vh] overflow-y-auto space-y-1">
          {checkpoints.length === 0 && (
            <div className="py-8 text-center text-xs" style={{ color: "rgba(var(--text-muted-r), var(--text-muted-g), var(--text-muted-b), 0.4)" }}>
              No checkpoints available for this session.
            </div>
          )}

          {checkpoints.map((cp, i) => (
            <button
              key={cp.index}
              onClick={() => setSelectedIndex(cp.index)}
              className="flex w-full items-start gap-3 px-3 py-2.5 rounded-xl text-left transition-all"
              style={{
                background: selectedIndex === cp.index ? "rgba(var(--brand-r), var(--brand-g), var(--brand-b), 0.12)" : "transparent",
                border: selectedIndex === cp.index ? "1px solid rgba(var(--brand-r), var(--brand-g), var(--brand-b), 0.3)" : "1px solid transparent",
              }}
            >
              <div className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-[9px] font-mono" style={{ border: "1px solid rgba(var(--brand-r), var(--brand-g), var(--brand-b), 0.2)", color: "rgba(var(--text-muted-r), var(--text-muted-g), var(--text-muted-b), 0.5)" }}>
                {checkpoints.length - i}
              </div>
              <div className="flex-1 min-w-0">
                <div className="text-xs truncate" style={{ color: selectedIndex === cp.index ? "rgba(var(--text-bright-r), var(--text-bright-g), var(--text-bright-b), 0.85)" : "rgba(var(--text-body-r), var(--text-body-g), var(--text-body-b), 0.6)" }}>
                  {cp.content || "(empty)"}
                </div>
                {cp.timestamp && <div className="text-[9px] mt-0.5" style={{ color: "rgba(var(--text-muted-r), var(--text-muted-g), var(--text-muted-b), 0.35)" }}>{cp.timestamp}</div>}
              </div>
              {cp.has_file_changes && <FileText className="h-3 w-3 shrink-0" style={{ color: "rgba(var(--warning-r), var(--warning-g), var(--warning-b), 0.5)" }} />}
            </button>
          ))}
        </div>

        {result && (
          <div className="mx-5 mb-2 px-3 py-2 rounded-lg text-xs text-center" style={{ background: "rgba(var(--success-r), var(--success-g), var(--success-b), 0.1)", color: "rgba(var(--success-r), var(--success-g), var(--success-b), 0.8)" }}>
            {result}
          </div>
        )}

        <div className="flex items-center justify-end gap-3 px-5 py-4 border-t border-[rgba(var(--brand-r),var(--brand-g),var(--brand-b),0.15)]">
          <button onClick={onClose} className="px-4 py-2 text-xs font-medium rounded-xl" style={{ color: "rgba(var(--text-muted-r), var(--text-muted-g), var(--text-muted-b), 0.7)", background: "rgba(var(--brand-r), var(--brand-g), var(--brand-b), 0.05)" }}>
            Cancel
          </button>
          <button
            onClick={handleRewind}
            disabled={selectedIndex === null || rewinding}
            className="flex items-center gap-2 px-5 py-2 text-xs font-medium rounded-xl transition-all disabled:opacity-40"
            style={{
              background: "linear-gradient(135deg, rgba(var(--warning-r), var(--warning-g), var(--warning-b), 0.2), rgba(var(--warning-r), calc(var(--warning-g) - 60), calc(var(--warning-b) - 20), 0.15))",
              border: "1px solid rgba(var(--warning-r), var(--warning-g), var(--warning-b), 0.3)",
              color: "rgba(var(--amber-text-r), var(--amber-text-g), var(--amber-text-b), 0.8)",
            }}
          >
            {rewinding ? "Rewinding..." : <><Undo2 className="h-3 w-3" /> Rewind Here</>}
          </button>
        </div>
      </div>
    </div>
  );
}
