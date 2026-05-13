import { useState, useRef, useCallback, useEffect, useMemo } from "react";
import { Send } from "lucide-react";
import { ThinkingPicker } from "./ThinkingPicker";
import { COMMANDS, type Command } from "./SlashCommands";
import { VoiceInput } from "./VoiceInput";

interface ChatInputProps {
  onSend: (content: string, thinkingLevel?: string) => void;
  disabled?: boolean;
  initialThinkingLevel?: string;
  onOpenModelPicker?: () => void;
  onOpenMcpPanel?: () => void;
  onOpenHeartbeat?: () => void;
  onOpenRewind?: () => void;
  onOpenConfig?: () => void;
  onOpenDebug?: () => void;
  onOpenFeedback?: () => void;
}

export function ChatInput({
  onSend, disabled, initialThinkingLevel = "medium",
  onOpenModelPicker, onOpenMcpPanel, onOpenHeartbeat,
  onOpenRewind, onOpenConfig, onOpenDebug, onOpenFeedback,
}: ChatInputProps) {
  const [value, setValue] = useState("");
  const [thinkingLevel, setThinkingLevel] = useState(initialThinkingLevel);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [wasCommandSelected, setWasCommandSelected] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const getCurrentWord = useCallback(() => {
    const cursorPosition = textareaRef.current?.selectionStart ?? value.length;
    const textBeforeCursor = value.slice(0, cursorPosition);
    const match = textBeforeCursor.match(/(\/[\w]*)$/);
    if (match) {
      return {
        word: match[1],
        start: match.index ?? 0,
      };
    }
    return null;
  }, [value]);

  const matchingCommands = useMemo(() => {
    const current = getCurrentWord();
    if (!current || !current.word.startsWith("/")) return [];

    const searchTerm = current.word.toLowerCase();
    return COMMANDS.filter(cmd => 
      cmd.name.toLowerCase().includes(searchTerm) ||
      cmd.aliases.some(alias => alias.toLowerCase().startsWith(searchTerm))
    ).slice(0, 8);
  }, [getCurrentWord]);

  useEffect(() => {
    const current = getCurrentWord();
    if (current && current.word.startsWith("/") && current.word.length > 0) {
      const matches = matchingCommands;
      setShowSuggestions(matches.length > 0);
      setSelectedIndex(0);
    } else {
      setShowSuggestions(false);
    }
  }, [value, getCurrentWord, matchingCommands]);

  const selectCommand = useCallback((command: Command) => {
    const current = getCurrentWord();
    if (!current) return;
    const newValue = value.slice(0, current.start) + command.aliases[0] + " ";
    setValue(newValue);
    setShowSuggestions(false);
    setWasCommandSelected(true);
    textareaRef.current?.focus();
  }, [value, getCurrentWord]);

  const handleCommand = useCallback((command: string, args: string) => {
    switch (command) {
      case "clear":
        window.location.reload();
        break;
      case "help":
        onSend("Please list all available commands with descriptions.", thinkingLevel);
        break;
      case "status":
        onSend("Show system status", thinkingLevel);
        break;
      case "profile":
        onSend(args ? `Switch to profile: ${args}` : "Show available profiles", thinkingLevel);
        break;
      case "tools":
        onSend("List all available tools", thinkingLevel);
        break;
      case "skills":
        onSend(args ? `Activate skill: ${args}` : "List all skills", thinkingLevel);
        break;
      case "config":
        onOpenConfig?.();
        break;
      case "mcp":
        onOpenMcpPanel?.();
        break;
      case "rewind":
        onOpenRewind?.();
        break;
      case "model":
        onOpenModelPicker?.();
        break;
      case "debug":
        onOpenDebug?.();
        break;
      case "feedback":
        onOpenFeedback?.();
        break;
      case "heartbeat":
        onOpenHeartbeat?.();
        break;
      default:
        onSend(value.trim(), thinkingLevel);
    }
  }, [onSend, thinkingLevel, value, onOpenConfig, onOpenMcpPanel, onOpenRewind, onOpenModelPicker, onOpenDebug, onOpenFeedback, onOpenHeartbeat]);

  const submit = useCallback(() => {
    const trimmed = value.trim();
    if (!trimmed || disabled) return;

    if (trimmed.startsWith("/") && showSuggestions && matchingCommands[selectedIndex]) {
      selectCommand(matchingCommands[selectedIndex]);
      return;
    }

    if (wasCommandSelected) {
      setWasCommandSelected(false);
      onSend(trimmed, thinkingLevel);
      setValue("");
      setShowSuggestions(false);
      return;
    }
    
    if (trimmed.startsWith("/")) {
      const parts = trimmed.split(" ");
      const command = parts[0].toLowerCase();
      const args = parts.slice(1).join(" ");
      
      const matchedCmd = COMMANDS.find(cmd => 
        cmd.aliases.map(a => a.toLowerCase()).includes(command)
      );
      
      if (matchedCmd) {
        handleCommand(matchedCmd.name, args);
        setValue("");
        setWasCommandSelected(false);
        return;
      }
    }
    
    onSend(trimmed, thinkingLevel);
    setValue("");
    setShowSuggestions(false);
    setWasCommandSelected(false);
    requestAnimationFrame(() => {
      const el = textareaRef.current;
      if (el) {
        el.style.height = "auto";
      }
    });
  }, [disabled, onSend, value, thinkingLevel, showSuggestions, matchingCommands, selectedIndex, selectCommand, wasCommandSelected, handleCommand]);

  const onKeyDown: React.KeyboardEventHandler<HTMLTextAreaElement> = (e) => {
    if (!showSuggestions) return;

    switch (e.key) {
      case "ArrowDown":
        e.preventDefault();
        e.stopPropagation();
        setSelectedIndex(i => (i + 1) % matchingCommands.length);
        break;
      case "ArrowUp":
        e.preventDefault();
        e.stopPropagation();
        setSelectedIndex(i => (i - 1 + matchingCommands.length) % matchingCommands.length);
        break;
      case "Enter":
        if (matchingCommands[selectedIndex]) {
          e.preventDefault();
          e.stopPropagation();
          selectCommand(matchingCommands[selectedIndex]);
        }
        break;
      case "Escape":
        e.preventDefault();
        e.stopPropagation();
        setShowSuggestions(false);
        break;
      case "Tab":
        if (matchingCommands[selectedIndex]) {
          e.preventDefault();
          e.stopPropagation();
          selectCommand(matchingCommands[selectedIndex]);
        }
        break;
    }
  };

  const onInput: React.FormEventHandler<HTMLTextAreaElement> = (e) => {
    const el = e.currentTarget;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 120)}px`;
  };

  const handleTranscript = useCallback((text: string) => {
    if (text.trim()) {
      setValue(prev => prev + text);
    }
  }, []);

  return (
    <div
      className="fixed bottom-5 left-1/2 z-50 w-full max-w-xl -translate-x-1/2 px-4"
    >
      {showSuggestions && matchingCommands.length > 0 && (
        <div
          className="absolute bottom-full left-0 mb-2 w-72 overflow-hidden rounded-xl"
          style={{
            background: "linear-gradient(180deg, rgba(10, 20, 45, 0.98) 0%, rgba(6, 12, 28, 0.98) 100%)",
            border: "1px solid rgba(26, 90, 255, 0.35)",
            boxShadow: "0 8px 32px rgba(0, 0, 0, 0.6), 0 0 20px rgba(26, 90, 255, 0.15)",
          }}
        >
          <div className="px-3 py-2 text-[10px] uppercase tracking-wider" style={{ color: "rgba(100, 140, 220, 0.6)" }}>
            Commands
          </div>
          {matchingCommands.map((cmd, index) => (
            <button
              key={cmd.name}
              onClick={() => selectCommand(cmd)}
              className="flex w-full items-center gap-3 px-3 py-2 text-left transition-colors hover:bg-blue-500/10"
              style={{
                background: index === selectedIndex ? "rgba(26, 90, 255, 0.1)" : "transparent",
              }}
            >
              <div className="flex flex-1 flex-col">
                <span className="text-sm font-medium" style={{ color: "rgba(200, 220, 255, 0.95)" }}>
                  {cmd.aliases[0]}
                </span>
                <span className="text-[10px]" style={{ color: "rgba(100, 140, 220, 0.6)" }}>
                  {cmd.description}
                </span>
              </div>
              {cmd.usage && (
                <span className="text-[10px]" style={{ color: "rgba(100, 140, 220, 0.4)" }}>
                  {cmd.usage}
                </span>
              )}
            </button>
          ))}
          <div className="flex items-center justify-between px-3 py-1.5" style={{ borderTop: "1px solid rgba(26, 90, 255, 0.1)" }}>
            <span className="text-[9px]" style={{ color: "rgba(100, 140, 220, 0.4)" }}>
              ↑↓ Navigate
            </span>
            <span className="text-[9px]" style={{ color: "rgba(100, 140, 220, 0.4)" }}>
              Enter Select
            </span>
            <span className="text-[9px]" style={{ color: "rgba(100, 140, 220, 0.4)" }}>
              Esc Close
            </span>
          </div>
        </div>
      )}
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
        <div className="flex flex-1 flex-col gap-2">
          <div className="flex items-center gap-2">
            <ThinkingPicker
              currentLevel={thinkingLevel}
              onLevelChange={setThinkingLevel}
            />
            <span className="text-[10px]" style={{ color: "rgba(100, 140, 220, 0.5)" }}>
              │
            </span>
            <span className="text-[10px]" style={{ color: "rgba(100, 140, 220, 0.4)" }}>
              Type / for commands
            </span>
          </div>
          <textarea
            ref={textareaRef}
            value={value}
            onChange={(e) => {
              setValue(e.target.value);
              if (wasCommandSelected) setWasCommandSelected(false);
            }}
            onInput={onInput}
            onKeyDown={onKeyDown}
            rows={1}
            placeholder="Enter command..."
            disabled={disabled}
            className="min-h-[24px] max-h-[120px] w-full resize-none bg-transparent text-sm leading-relaxed text-blue-100 placeholder:text-slate-500 focus:outline-none disabled:cursor-not-allowed"
          />
        </div>
        <div className="flex items-center gap-2 pb-0.5">
          <VoiceInput onTranscript={handleTranscript} />
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
