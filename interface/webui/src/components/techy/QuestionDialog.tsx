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
      <div
        className="w-full max-w-md overflow-hidden rounded-2xl"
        style={{
          background: "linear-gradient(180deg, rgba(10, 20, 45, 0.98) 0%, rgba(6, 12, 28, 0.98) 100%)",
          border: "1px solid rgba(100, 160, 255, 0.3)",
          boxShadow: "0 8px 40px rgba(0,0,0,0.6), 0 0 30px rgba(26, 90, 255, 0.1)",
        }}
      >
        <div className="flex items-center justify-between px-5 py-4 border-b" style={{ borderColor: "rgba(26, 90, 255, 0.15)" }}>
          <div className="flex items-center gap-2">
            <HelpCircle className="h-4 w-4" style={{ color: "rgba(100, 160, 255, 0.8)" }} />
            <span className="text-sm font-bold tracking-wider uppercase" style={{ color: "rgba(200, 220, 255, 0.9)" }}>
              Question
            </span>
          </div>
          <button onClick={onDismiss} className="p-1 rounded-lg hover:bg-blue-500/10" style={{ color: "rgba(100, 140, 220, 0.6)" }}>
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="p-5">
          <p className="text-sm leading-relaxed mb-4" style={{ color: "rgba(200, 220, 255, 0.85)" }}>{question}</p>

          {options && options.length > 0 && (
            <div className="space-y-1 mb-4">
              {options.map((opt, i) => (
                <button
                  key={i}
                  onClick={() => { setSelected(opt); setCustomText(""); }}
                  className="flex w-full items-center gap-3 px-4 py-2.5 rounded-xl text-left transition-all"
                  style={{
                    background: selected === opt ? "rgba(26, 90, 255, 0.12)" : "rgba(26, 90, 255, 0.04)",
                    border: selected === opt ? "1px solid rgba(26, 90, 255, 0.3)" : "1px solid rgba(26, 90, 255, 0.1)",
                  }}
                >
                  <div className="flex h-4 w-4 shrink-0 items-center justify-center rounded-full text-[9px] font-mono" style={{ border: "1px solid rgba(26, 90, 255, 0.2)", color: "rgba(100, 140, 220, 0.5)" }}>
                    {i + 1}
                  </div>
                  <span className="text-xs" style={{ color: selected === opt ? "rgba(200, 230, 255, 0.85)" : "rgba(150, 180, 220, 0.6)" }}>{opt}</span>
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
              style={{ borderColor: "rgba(26, 90, 255, 0.15)", color: "rgba(200, 220, 255, 0.7)" }}
            />
          )}

          <div className="flex justify-end gap-2">
            <button onClick={onDismiss} className="px-4 py-2 text-xs font-medium rounded-xl" style={{ color: "rgba(100, 140, 220, 0.7)", background: "rgba(26, 90, 255, 0.05)" }}>
              Dismiss
            </button>
            <button
              onClick={handleSubmit}
              disabled={!selected && !customText.trim()}
              className="flex items-center gap-2 px-5 py-2 text-xs font-medium rounded-xl disabled:opacity-40"
              style={{
                background: "linear-gradient(135deg, rgba(26,90,255,0.25), rgba(0,80,200,0.15))",
                border: "1px solid rgba(26,90,255,0.3)",
                color: "rgba(200, 220, 255, 0.8)",
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
