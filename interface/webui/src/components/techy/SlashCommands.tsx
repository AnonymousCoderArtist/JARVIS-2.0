import { useState, useRef, useEffect, useCallback } from "react";

export interface Command {
  name: string;
  aliases: string[];
  description: string;
  usage: string;
}

export const COMMANDS: Command[] = [
  {
    name: "help",
    aliases: ["/help", "/h"],
    description: "Show available commands",
    usage: "",
  },
  {
    name: "status",
    aliases: ["/status", "/st"],
    description: "Show system status",
    usage: "",
  },
  {
    name: "clear",
    aliases: ["/clear"],
    description: "Clear the screen",
    usage: "",
  },
  {
    name: "exit",
    aliases: ["/exit", "/quit"],
    description: "Exit JARVIS",
    usage: "",
  },
  {
    name: "profile",
    aliases: ["/profile"],
    description: "Switch or list agent profiles",
    usage: "[<profile>]",
  },
  {
    name: "tools",
    aliases: ["/tools"],
    description: "List available tools",
    usage: "",
  },
  {
    name: "skills",
    aliases: ["/skills"],
    description: "List and manage skills",
    usage: "[activate <name>]",
  },
  {
    name: "rewind",
    aliases: ["/rewind", "/rw"],
    description: "Rewind conversation to a previous message",
    usage: "",
  },
  {
    name: "config",
    aliases: ["/config", "/settings"],
    description: "Edit config settings",
    usage: "",
  },
  {
    name: "mcp",
    aliases: ["/mcp"],
    description: "Display available MCP servers",
    usage: "[server_name]",
  },
];

interface SlashCommandsProps {
  value: string;
  onChange: (value: string) => void;
  onCommand: (command: string, args: string) => void;
  inputRef: React.RefObject<HTMLTextAreaElement | null>;
}

export function SlashCommands({ value, onChange, onCommand, inputRef }: SlashCommandsProps) {
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [matchStart, setMatchStart] = useState(0);
  const suggestionsRef = useRef<HTMLDivElement>(null);

  const getCurrentWord = useCallback(() => {
    const cursorPosition = inputRef.current?.selectionStart ?? value.length;
    const textBeforeCursor = value.slice(0, cursorPosition);
    const match = textBeforeCursor.match(/(\/[\w]*)$/);
    if (match) {
      return {
        word: match[1],
        start: match.index ?? 0,
      };
    }
    return null;
  }, [value, inputRef]);

  const matchingCommands = useCallback(() => {
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
      const matches = matchingCommands();
      setShowSuggestions(matches.length > 0);
      setSelectedIndex(0);
      setMatchStart(current.start);
    } else {
      setShowSuggestions(false);
    }
  }, [value, getCurrentWord, matchingCommands]);

  const selectCommand = useCallback((command: Command) => {
    const newValue = value.slice(0, matchStart) + command.aliases[0] + " ";
    onChange(newValue);
    setShowSuggestions(false);
    inputRef.current?.focus();
  }, [value, matchStart, onChange, inputRef]);

  const handleKeyDown: React.KeyboardEventHandler<HTMLTextAreaElement> = (e) => {
    if (!showSuggestions) return;

    const matches = matchingCommands();

    switch (e.key) {
      case "ArrowDown":
        e.preventDefault();
        setSelectedIndex(i => (i + 1) % matches.length);
        break;
      case "ArrowUp":
        e.preventDefault();
        setSelectedIndex(i => (i - 1 + matches.length) % matches.length);
        break;
      case "Enter":
        if (matches[selectedIndex]) {
          e.preventDefault();
          selectCommand(matches[selectedIndex]);
        }
        break;
      case "Escape":
        setShowSuggestions(false);
        break;
      case "Tab":
        if (matches[selectedIndex]) {
          e.preventDefault();
          selectCommand(matches[selectedIndex]);
        }
        break;
    }
  };

  if (!showSuggestions || matchingCommands().length === 0) return null;

  const matches = matchingCommands();

  return (
    <div
      ref={suggestionsRef}
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
      {matches.map((cmd, index) => (
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
  );
}