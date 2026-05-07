import { useState, useRef, useCallback } from "react";
import { Mic, Send } from "lucide-react";

interface ChatInputProps {
  onSend: (content: string) => void;
  disabled?: boolean;
}

export function ChatInput({ onSend, disabled }: ChatInputProps) {
  const [value, setValue] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const submit = useCallback(() => {
    const trimmed = value.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setValue("");
    requestAnimationFrame(() => {
      const el = textareaRef.current;
      if (el) {
        el.style.height = "auto";
      }
    });
  }, [disabled, onSend, value]);

  const onKeyDown: React.KeyboardEventHandler<HTMLTextAreaElement> = (e) => {
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      submit();
    }
  };

  const onInput: React.FormEventHandler<HTMLTextAreaElement> = (e) => {
    const el = e.currentTarget;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 120)}px`;
  };

  return (
    <div
      className="fixed bottom-5 left-1/2 z-50 w-full max-w-xl -translate-x-1/2 px-4"
    >
      <div
        className="flex items-end gap-3 rounded-2xl px-5 py-3"
        style={{
          background:
            "linear-gradient(180deg, rgba(10, 20, 45, 0.9) 0%, rgba(6, 12, 28, 0.9) 100%)",
          backdropFilter: "blur(20px)",
          border: "1px solid rgba(26, 90, 255, 0.3)",
          boxShadow:
            "0 8px 32px rgba(0, 0, 0, 0.4), 0 0 30px rgba(26, 90, 255, 0.08), inset 0 1px 0 rgba(255,255,255,0.05)",
        }}
      >
        <textarea
          ref={textareaRef}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onInput={onInput}
          onKeyDown={onKeyDown}
          rows={1}
          placeholder="Enter command..."
          disabled={disabled}
          className="min-h-[24px] max-h-[120px] w-full flex-1 resize-none bg-transparent text-sm leading-relaxed text-blue-100 placeholder:text-slate-500 focus:outline-none disabled:cursor-not-allowed"
        />
        <div className="flex items-center gap-2 pb-0.5">
          <button
            type="button"
            disabled={disabled}
            className="flex h-8 w-8 items-center justify-center rounded-lg text-slate-500 transition-colors hover:bg-blue-500/10 hover:text-blue-300 disabled:opacity-40"
          >
            <Mic className="h-4 w-4" />
          </button>
          <button
            onClick={submit}
            disabled={disabled || !value.trim()}
            className="flex h-8 w-8 items-center justify-center rounded-lg text-blue-300 transition-all hover:bg-blue-500/20 hover:shadow-[0_0_10px_rgba(26,90,255,0.3)] disabled:opacity-40"
          >
            <Send className="h-4 w-4" />
          </button>
        </div>
      </div>
    </div>
  );
}
