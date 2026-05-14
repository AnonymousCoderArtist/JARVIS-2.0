import { useState, useCallback } from "react";
import { HelpCircle, Send, X } from "lucide-react";

interface QuestionDialogProps {
  open: boolean;
  question: string;
  options?: string[];
  onSubmit: (answer: string) => void;
  onDismiss: () => void;
}

export function QuestionDialog({ open, question, options, onSubmit, onDismiss }: QuestionDialogProps) {
  const [customText, setCustomText] = useState("");
  const [selected, setSelected] = useState<string | null>(null);

  const handleSubmit = useCallback(() => {
    if (selected) {
      onSubmit(selected);
      setSelected(null);
    } else if (customText.trim()) {
      onSubmit(customText.trim());
      setCustomText("");
    }
  }, [selected, customText, onSubmit]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
      <div className="techy-dialog w-full max-w-md overflow-hidden rounded-2xl">
        <div className="techy-header flex items-center justify-between px-5 py-4">
          <div className="flex items-center gap-2">
            <HelpCircle className="h-4 w-4" style={{ color: "rgba(var(--text-bright-r), var(--text-bright-g), var(--text-bright-b), 0.8)" }} />
            <span className="text-sm font-bold tracking-wider uppercase" style={{ color: "rgba(var(--text-bright-r), var(--text-bright-g), var(--text-bright-b), 0.9)" }}>
              Question
            </span>
          </div>
          <button onClick={onDismiss} className="p-1 rounded-lg hover:bg-blue-500/10" style={{ color: "rgba(var(--text-muted-r), var(--text-muted-g), var(--text-muted-b), 0.6)" }}>
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="p-5">
          <p className="text-sm leading-relaxed mb-4" style={{ color: "rgba(var(--text-bright-r), var(--text-bright-g), var(--text-bright-b), 0.85)" }}>{question}</p>

          {options && options.length > 0 && (
            <div className="space-y-1 mb-4">
              {options.map((opt, i) => (
                <button
                  key={i}
                  onClick={() => { setSelected(opt); setCustomText(""); }}
                  className="flex w-full items-center gap-3 px-4 py-2.5 rounded-xl text-left transition-all"
                  style={{
                    background: selected === opt ? "rgba(var(--brand-r), var(--brand-g), var(--brand-b), 0.12)" : "rgba(var(--brand-r), var(--brand-g), var(--brand-b), 0.04)",
                    border: selected === opt ? "1px solid rgba(var(--brand-r), var(--brand-g), var(--brand-b), 0.3)" : "1px solid rgba(var(--brand-r), var(--brand-g), var(--brand-b), 0.1)",
                  }}
                >
                  <div className="flex h-4 w-4 shrink-0 items-center justify-center rounded-full text-[9px] font-mono" style={{ border: "1px solid rgba(var(--brand-r), var(--brand-g), var(--brand-b), 0.2)", color: "rgba(var(--text-muted-r), var(--text-muted-g), var(--text-muted-b), 0.5)" }}>
                    {i + 1}
                  </div>
                  <span className="text-xs" style={{ color: selected === opt ? "rgba(var(--text-bright-r), var(--text-bright-g), var(--text-bright-b), 0.85)" : "rgba(var(--text-body-r), var(--text-body-g), var(--text-body-b), 0.6)" }}>{opt}</span>
                </button>
              ))}
            </div>
          )}

          {(!options || options.length === 0) && (
            <textarea
              value={customText}
              onChange={e => setCustomText(e.target.value)}
              placeholder="Type your answer..."
              rows={3}
              className="w-full px-4 py-3 text-xs rounded-xl bg-transparent border resize-none focus:outline-none mb-4"
              style={{ borderColor: "rgba(var(--brand-r), var(--brand-g), var(--brand-b), 0.15)", color: "rgba(var(--text-bright-r), var(--text-bright-g), var(--text-bright-b), 0.7)" }}
            />
          )}

          <div className="flex justify-end gap-2">
            <button onClick={onDismiss} className="px-4 py-2 text-xs font-medium rounded-xl" style={{ color: "rgba(var(--text-muted-r), var(--text-muted-g), var(--text-muted-b), 0.7)", background: "rgba(var(--brand-r), var(--brand-g), var(--brand-b), 0.05)" }}>
              Dismiss
            </button>
            <button
              onClick={handleSubmit}
              disabled={!selected && !customText.trim()}
              className="flex items-center gap-2 px-5 py-2 text-xs font-medium rounded-xl disabled:opacity-40"
              style={{
                background: "linear-gradient(135deg, rgba(var(--brand-r), var(--brand-g), var(--brand-b), 0.25), rgba(var(--brand-r), var(--brand-g), calc(var(--brand-b) - 55), 0.15))",
                border: "1px solid rgba(var(--brand-r), var(--brand-g), var(--brand-b), 0.3)",
                color: "rgba(var(--text-bright-r), var(--text-bright-g), var(--text-bright-b), 0.8)",
              }}
            >
              <Send className="h-3 w-3" /> Submit
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
