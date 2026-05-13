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
    <div className="fixed bottom-24 right-6 z-50 w-72 overflow-hidden rounded-2xl"
      style={{
        background: "linear-gradient(180deg, rgba(10, 20, 45, 0.98) 0%, rgba(6, 12, 28, 0.98) 100%)",
        border: "1px solid rgba(26, 90, 255, 0.3)",
        boxShadow: "0 8px 32px rgba(0,0,0,0.5)",
      }}
    >
      <div className="flex items-center justify-between px-4 py-3 border-b" style={{ borderColor: "rgba(26, 90, 255, 0.12)" }}>
        <span className="text-[10px] font-bold uppercase tracking-widest" style={{ color: "rgba(100, 140, 220, 0.5)" }}>Feedback</span>
        <button onClick={onClose} className="p-0.5" style={{ color: "rgba(100, 140, 220, 0.4)" }}>
          <X className="h-3 w-3" />
        </button>
      </div>

      <div className="p-4">
        {sent ? (
          <div className="text-center py-4">
            <div className="text-xs font-medium" style={{ color: "rgba(100, 220, 150, 0.8)" }}>Thanks for your feedback!</div>
          </div>
        ) : (
          <>
            <div className="flex justify-center gap-3 mb-4">
              {[
                { value: 1, icon: ThumbsDown, color: "rgba(255, 100, 100, 0.6)" },
                { value: 2, icon: Meh, color: "rgba(255, 200, 50, 0.6)" },
                { value: 3, icon: ThumbsUp, color: "rgba(50, 200, 100, 0.6)" },
              ].map(({ value, icon: Icon, color }) => (
                <button key={value} onClick={() => setRating(value)}
                  className="flex h-10 w-10 items-center justify-center rounded-xl transition-all"
                  style={{
                    background: rating === value ? `${color}20` : "rgba(26, 90, 255, 0.05)",
                    border: rating === value ? `1px solid ${color}` : "1px solid rgba(26, 90, 255, 0.1)",
                    color: rating === value ? color : "rgba(100, 140, 220, 0.4)",
                  }}
                >
                  <Icon className="h-4 w-4" />
                </button>
              ))}
            </div>
            <textarea value={message} onChange={e => setMessage(e.target.value)}
              placeholder="Optional details..." rows={2}
              className="w-full px-3 py-2 text-xs rounded-lg bg-transparent border resize-none focus:outline-none"
              style={{ borderColor: "rgba(26, 90, 255, 0.15)", color: "rgba(200, 220, 255, 0.7)" }}
            />
            <button onClick={handleSubmit} disabled={rating === null || sending}
              className="flex w-full items-center justify-center gap-2 mt-3 px-4 py-2 text-xs font-medium rounded-xl transition-all disabled:opacity-40"
              style={{
                background: "linear-gradient(135deg, rgba(26,90,255,0.2), rgba(0,80,200,0.15))",
                border: "1px solid rgba(26,90,255,0.25)",
                color: "rgba(200, 220, 255, 0.7)",
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
