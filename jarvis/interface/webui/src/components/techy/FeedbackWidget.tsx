import { useState, useCallback } from "react";
import { useClient } from "@/providers/ClientProvider";
import { submitFeedback } from "@/lib/api";
import { X, ThumbsUp, ThumbsDown, Meh, Send } from "lucide-react";

interface FeedbackWidgetProps {
  open: boolean;
  onClose: () => void;
}

export function FeedbackWidget({ open, onClose }: FeedbackWidgetProps) {
  const { token } = useClient();
  const [rating, setRating] = useState<number | null>(null);
  const [message, setMessage] = useState("");
  const [sent, setSent] = useState(false);
  const [sending, setSending] = useState(false);

  const handleSubmit = useCallback(async () => {
    if (rating === null) return;
    setSending(true);
    await submitFeedback(token, { rating, message: message || undefined, page: window.location.pathname });
    setSending(false);
    setSent(true);
    setTimeout(() => { setSent(false); setRating(null); setMessage(""); onClose(); }, 1200);
  }, [rating, message, token, onClose]);

  if (!open) return null;

  return (
    <div className="techy-feedback fixed bottom-24 right-6 z-50 w-72 overflow-hidden rounded-2xl">
      <div className="techy-header flex items-center justify-between px-4 py-3">
        <span className="text-[10px] font-bold uppercase tracking-widest" style={{ color: "rgba(var(--text-muted-r), var(--text-muted-g), var(--text-muted-b), 0.5)" }}>Feedback</span>
        <button onClick={onClose} className="p-0.5" style={{ color: "rgba(var(--text-muted-r), var(--text-muted-g), var(--text-muted-b), 0.4)" }}>
          <X className="h-3 w-3" />
        </button>
      </div>

      <div className="p-4">
        {sent ? (
          <div className="text-center py-4">
            <div className="text-xs font-medium" style={{ color: "rgba(var(--success-r), var(--success-g), var(--success-b), 0.8)" }}>Thanks for your feedback!</div>
          </div>
        ) : (
          <>
            <div className="flex justify-center gap-3 mb-4">
              {[
                { value: 1, icon: ThumbsDown, color: "rgba(var(--error-r), var(--error-g), var(--error-b), 0.6)" },
                { value: 2, icon: Meh, color: "rgba(var(--warning-r), var(--warning-g), var(--warning-b), 0.6)" },
                { value: 3, icon: ThumbsUp, color: "rgba(var(--success-r), var(--success-g), var(--success-b), 0.6)" },
              ].map(({ value, icon: Icon, color }) => (
                <button key={value} onClick={() => setRating(value)}
                  className="flex h-10 w-10 items-center justify-center rounded-xl transition-all"
                  style={{
                    background: rating === value ? `${color}20` : "rgba(var(--brand-r), var(--brand-g), var(--brand-b), 0.05)",
                    border: rating === value ? `1px solid ${color}` : "1px solid rgba(var(--brand-r), var(--brand-g), var(--brand-b), 0.1)",
                    color: rating === value ? color : "rgba(var(--text-muted-r), var(--text-muted-g), var(--text-muted-b), 0.4)",
                  }}
                >
                  <Icon className="h-4 w-4" />
                </button>
              ))}
            </div>
            <textarea value={message} onChange={e => setMessage(e.target.value)}
              placeholder="Optional details..." rows={2}
              className="w-full px-3 py-2 text-xs rounded-lg bg-transparent border resize-none focus:outline-none"
              style={{ borderColor: "rgba(var(--brand-r), var(--brand-g), var(--brand-b), 0.15)", color: "rgba(var(--text-bright-r), var(--text-bright-g), var(--text-bright-b), 0.7)" }}
            />
            <button onClick={handleSubmit} disabled={rating === null || sending}
              className="flex w-full items-center justify-center gap-2 mt-3 px-4 py-2 text-xs font-medium rounded-xl transition-all disabled:opacity-40"
              style={{
                background: "linear-gradient(135deg, rgba(var(--brand-r), var(--brand-g), var(--brand-b), 0.2), rgba(var(--brand-r), var(--brand-g), calc(var(--brand-b) - 55), 0.15))",
                border: "1px solid rgba(var(--brand-r), var(--brand-g), var(--brand-b), 0.25)",
                color: "rgba(var(--text-bright-r), var(--text-bright-g), var(--text-bright-b), 0.7)",
              }}
            >
              {sending ? "Sending..." : <><Send className="h-3 w-3" /> Send Feedback</>}
            </button>
          </>
        )}
      </div>
    </div>
  );
}
