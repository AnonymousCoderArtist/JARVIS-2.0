import { useState, useEffect, useCallback } from "react";
import { useClient } from "@/providers/ClientProvider";
import { fetchSettings, updateSettings } from "@/lib/api";
import { X, Settings, Sliders, Brain, Shield, Check } from "lucide-react";

interface ConfigPanelProps {
  open: boolean;
  onClose: () => void;
  onOpenModelPicker: () => void;
}

const PREFERENCES = [
  { key: "code_execution", label: "Code Execution", desc: "Allow running bash and code tools" },
  { key: "file_operations", label: "File Operations", desc: "Allow file read/write operations" },
  { key: "git_operations", label: "Git Operations", desc: "Allow git commands" },
];

export function ConfigPanel({ open, onClose, onOpenModelPicker }: ConfigPanelProps) {
  const { token } = useClient();
  const [settings, setSettings] = useState<{
    agent: { model: string; provider: string; thinking_level?: string };
    thinking_levels?: Array<{ name: string; label: string; description: string }>;
  } | null>(null);
  const [prefs, setPrefs] = useState<Record<string, boolean>>({
    code_execution: true,
    file_operations: true,
    git_operations: true,
  });

  const load = useCallback(async () => {
    const r = await fetchSettings(token);
    setSettings(r);
  }, [token]);

  useEffect(() => { if (open) load(); }, [open, load]);

  const handleThinkingChange = useCallback(async (level: string) => {
    await updateSettings(token, { thinking_level: level });
    load();
  }, [token, load]);

  const togglePref = useCallback((key: string) => {
    setPrefs(prev => ({ ...prev, [key]: !prev[key] }));
  }, []);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
      <div className="techy-dialog w-full max-w-lg overflow-hidden rounded-2xl">
        <div className="techy-header flex items-center justify-between px-5 py-4">
          <div className="flex items-center gap-2">
            <Settings className="h-4 w-4" style={{ color: "rgba(var(--text-bright-r), var(--text-bright-g), var(--text-bright-b), 0.8)" }} />
            <span className="text-sm font-bold tracking-wider uppercase" style={{ color: "rgba(var(--text-bright-r), var(--text-bright-g), var(--text-bright-b), 0.9)" }}>
              Settings
            </span>
          </div>
          <button onClick={onClose} className="p-1 rounded-lg hover:bg-blue-500/10" style={{ color: "rgba(var(--text-muted-r), var(--text-muted-g), var(--text-muted-b), 0.6)" }}>
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="p-5 space-y-5 max-h-[60vh] overflow-y-auto">
          {settings && (
            <>
              <div>
                <div className="flex items-center gap-2 mb-3">
                  <Sliders className="h-3 w-3" style={{ color: "rgba(var(--text-bright-r), var(--text-bright-g), var(--text-bright-b), 0.6)" }} />
                  <span className="text-[10px] font-bold uppercase tracking-widest" style={{ color: "rgba(var(--text-muted-r), var(--text-muted-g), var(--text-muted-b), 0.5)" }}>Model</span>
                </div>
                <button
                  onClick={onOpenModelPicker}
                  className="flex w-full items-center justify-between px-4 py-3 rounded-xl transition-all hover:bg-blue-500/8"
                  style={{ background: "rgba(var(--brand-r), var(--brand-g), var(--brand-b), 0.06)", border: "1px solid rgba(var(--brand-r), var(--brand-g), var(--brand-b), 0.15)" }}
                >
                  <div className="text-left">
                    <div className="text-sm font-medium" style={{ color: "rgba(var(--text-bright-r), var(--text-bright-g), var(--text-bright-b), 0.85)" }}>{settings.agent.model}</div>
                    <div className="text-[10px]" style={{ color: "rgba(var(--text-muted-r), var(--text-muted-g), var(--text-muted-b), 0.4)" }}>Provider: {settings.agent.provider}</div>
                  </div>
                  <span className="text-[10px]" style={{ color: "rgba(var(--text-muted-r), var(--text-muted-g), var(--text-muted-b), 0.4)" }}>Change →</span>
                </button>
              </div>

              <div>
                <div className="flex items-center gap-2 mb-3">
                  <Brain className="h-3 w-3" style={{ color: "rgba(var(--text-bright-r), var(--text-bright-g), var(--text-bright-b), 0.6)" }} />
                  <span className="text-[10px] font-bold uppercase tracking-widest" style={{ color: "rgba(var(--text-muted-r), var(--text-muted-g), var(--text-muted-b), 0.5)" }}>Thinking Level</span>
                </div>
                <div className="space-y-1">
                  {(settings.thinking_levels || []).map(tl => (
                    <button
                      key={tl.name}
                      onClick={() => handleThinkingChange(tl.name)}
                      className="flex w-full items-center gap-3 px-4 py-2.5 rounded-xl text-left transition-all"
                      style={{
                        background: settings.agent.thinking_level === tl.name ? "rgba(var(--brand-r), var(--brand-g), var(--brand-b), 0.12)" : "transparent",
                        border: settings.agent.thinking_level === tl.name ? "1px solid rgba(var(--brand-r), var(--brand-g), var(--brand-b), 0.3)" : "1px solid transparent",
                      }}
                    >
                      <div className="flex h-4 w-4 items-center justify-center rounded-full" style={{ border: "1px solid rgba(var(--brand-r), var(--brand-g), var(--brand-b), 0.3)" }}>
                        {settings.agent.thinking_level === tl.name && <div className="h-2 w-2 rounded-full" style={{ background: "rgba(var(--brand-r), var(--brand-g), var(--brand-b), 0.8)" }} />}
                      </div>
                      <div>
                        <div className="text-xs font-medium" style={{ color: settings.agent.thinking_level === tl.name ? "rgba(var(--text-bright-r), var(--text-bright-g), var(--text-bright-b), 0.85)" : "rgba(var(--text-body-r), var(--text-body-g), var(--text-body-b), 0.6)" }}>
                          {tl.label}
                        </div>
                        <div className="text-[9px]" style={{ color: "rgba(var(--text-muted-r), var(--text-muted-g), var(--text-muted-b), 0.35)" }}>{tl.description}</div>
                      </div>
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <div className="flex items-center gap-2 mb-3">
                  <Shield className="h-3 w-3" style={{ color: "rgba(var(--text-bright-r), var(--text-bright-g), var(--text-bright-b), 0.6)" }} />
                  <span className="text-[10px] font-bold uppercase tracking-widest" style={{ color: "rgba(var(--text-muted-r), var(--text-muted-g), var(--text-muted-b), 0.5)" }}>Preferences</span>
                </div>
                <div className="space-y-2">
                  {PREFERENCES.map(pref => {
                    const on = prefs[pref.key];
                    return (
                      <div
                        key={pref.key}
                        onClick={() => togglePref(pref.key)}
                        className="flex items-center justify-between px-4 py-2.5 rounded-xl cursor-pointer transition-all hover:bg-blue-500/6"
                        style={{ background: "rgba(var(--brand-r), var(--brand-g), var(--brand-b), 0.04)", border: "1px solid rgba(var(--brand-r), var(--brand-g), var(--brand-b), 0.08)" }}
                      >
                        <div>
                          <div className="text-xs font-medium" style={{ color: "rgba(var(--text-bright-r), var(--text-bright-g), var(--text-bright-b), 0.7)" }}>{pref.label}</div>
                          <div className="text-[9px]" style={{ color: "rgba(var(--text-muted-r), var(--text-muted-g), var(--text-muted-b), 0.35)" }}>{pref.desc}</div>
                        </div>
                        <div
                          className="relative flex h-5 w-9 cursor-pointer rounded-full transition-all duration-200"
                          style={{
                            background: on ? "rgba(var(--success-r), var(--success-g), var(--success-b), 0.3)" : "rgba(var(--brand-r), var(--brand-g), var(--brand-b), 0.15)",
                            border: on ? "1px solid rgba(var(--success-r), var(--success-g), var(--success-b), 0.3)" : "1px solid rgba(var(--brand-r), var(--brand-g), var(--brand-b), 0.15)",
                          }}
                        >
                          <div
                            className="flex h-4 w-4 items-center justify-center rounded-full transition-all duration-200"
                            style={{
                              background: on ? "rgba(var(--success-r), var(--success-g), var(--success-b), 0.9)" : "rgba(var(--text-muted-r), var(--text-muted-g), var(--text-muted-b), 0.4)",
                              transform: on ? "translateX(18px)" : "translateX(2px)",
                              margin: "1px",
                            }}
                          >
                            {on && <Check className="h-2.5 w-2.5 text-white" />}
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
