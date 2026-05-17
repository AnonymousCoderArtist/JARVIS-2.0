import { Brain, ChevronDown } from "lucide-react";
import { useState, useRef, useEffect } from "react";

interface ThinkingLevel {
  name: string;
  label: string;
  description: string;
}

interface ThinkingPickerProps {
  currentLevel: string;
  onLevelChange: (level: string) => void;
  levels?: ThinkingLevel[];
}

const DEFAULT_LEVELS: ThinkingLevel[] = [
  { name: "low", label: "Low", description: "Minimal reasoning" },
  { name: "medium", label: "Medium", description: "Balanced reasoning" },
  { name: "high", label: "High", description: "Detailed reasoning" },
];

export function ThinkingPicker({ 
  currentLevel = "medium", 
  onLevelChange,
  levels = DEFAULT_LEVELS 
}: ThinkingPickerProps) {
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  const current = levels.find(l => l.name === currentLevel) || levels[1];

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  return (
    <div ref={dropdownRef} className="relative">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs transition-all"
        style={{
          background: "rgba(var(--brand-r), var(--brand-g), var(--brand-b), 0.15)",
          border: "1px solid rgba(var(--brand-r), var(--brand-g), var(--brand-b), 0.25)",
          color: "rgba(var(--text-bright-r), var(--text-bright-g), var(--text-bright-b), 0.9)",
        }}
      >
        <Brain className="h-3 w-3" />
        <span className="font-medium">{current.label}</span>
        <ChevronDown className="h-3 w-3 opacity-60" />
      </button>

      {isOpen && (
        <div
          className="absolute bottom-full left-0 mb-2 min-w-[160px] overflow-hidden rounded-xl techy-suggestions"
        >
          <div className="px-3 py-2 text-[10px] uppercase tracking-wider" style={{ color: "rgba(var(--text-muted-r), var(--text-muted-g), var(--text-muted-b), 0.6)" }}>
            Thinking Level
          </div>
          {levels.map((level) => (
            <button
              key={level.name}
              onClick={() => {
                onLevelChange(level.name);
                setIsOpen(false);
              }}
              className="flex w-full items-center gap-2 px-3 py-2 text-left transition-colors hover:bg-blue-500/10"
            >
              <div className="flex flex-1 flex-col">
                <span
                  className="text-sm font-medium"
                  style={{ color: level.name === currentLevel ? "rgba(var(--brand-r), var(--brand-g), var(--brand-b), 1)" : "rgba(var(--text-bright-r), var(--text-bright-g), var(--text-bright-b), 0.9)" }}
                >
                  {level.label}
                </span>
                <span className="text-[10px]" style={{ color: "rgba(var(--text-muted-r), var(--text-muted-g), var(--text-muted-b), 0.6)" }}>
                  {level.description}
                </span>
              </div>
              {level.name === currentLevel && (
                <div
                  className="h-1.5 w-1.5 rounded-full"
                  style={{ background: "rgba(var(--brand-r), var(--brand-g), var(--brand-b), 0.8)" }}
                />
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
