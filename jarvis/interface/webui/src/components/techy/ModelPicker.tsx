import { useState, useEffect, useCallback } from "react";
import { useClient } from "@/providers/ClientProvider";
import { listModels, listProviders, setActiveModel } from "@/lib/api";
import { X, Check, Sparkles, Bot } from "lucide-react";

interface ModelPickerProps {
  open: boolean;
  onClose: () => void;
  currentModel: string | null;
  onModelChange: (model: string) => void;
}

export function ModelPicker({ open, onClose, currentModel, onModelChange }: ModelPickerProps) {
  const { token } = useClient();
  const [models, setModels] = useState<Array<{ id: string; name: string; provider: string; capabilities: { reasoning: boolean; vision: boolean; tool_call: boolean } }>>([]);
  const [, setProviders] = useState<Array<{ provider_id: string; sdk_mode: string; default_model: string }>>([]);
  const [selectedModel, setSelectedModel] = useState(currentModel || "");
  const [selectedProvider, setSelectedProvider] = useState("");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (!open) return;
    listModels(token).then(r => { setModels(r.models); if (!selectedModel) setSelectedModel(r.current_model); });
    listProviders(token).then(r => {
      setProviders(r.providers);
      if (r.providers.length > 0) setSelectedProvider(r.providers[0].provider_id);
    });
  }, [open, token]);

  const handleSave = useCallback(async () => {
    setSaving(true);
    await setActiveModel(token, selectedModel, selectedProvider);
    setSaving(false);
    setSaved(true);
    onModelChange(selectedModel);
    setTimeout(() => { setSaved(false); onClose(); }, 800);
  }, [selectedModel, selectedProvider, token, onModelChange, onClose]);

  if (!open) return null;

  const grouped = models.reduce((acc, m) => {
    if (!acc[m.provider]) acc[m.provider] = [];
    acc[m.provider].push(m);
    return acc;
  }, {} as Record<string, typeof models>);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
      <div className="techy-dialog w-full max-w-lg overflow-hidden rounded-2xl">
        <div className="techy-header flex items-center justify-between px-5 py-4">
          <div className="flex items-center gap-2">
            <Bot className="h-4 w-4" style={{ color: "rgba(var(--text-bright-r), var(--text-bright-g), var(--text-bright-b), 0.8)" }} />
            <span className="text-sm font-bold tracking-wider uppercase" style={{ color: "rgba(var(--text-bright-r), var(--text-bright-g), var(--text-bright-b), 0.9)" }}>
              Model Picker
            </span>
          </div>
          <button onClick={onClose} className="p-1 rounded-lg transition-colors hover:bg-blue-500/10" style={{ color: "rgba(var(--text-muted-r), var(--text-muted-g), var(--text-muted-b), 0.6)" }}>
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="p-5 space-y-4 max-h-[60vh] overflow-y-auto">
          {Object.entries(grouped).map(([provider, providerModels]) => (
            <div key={provider}>
              <div className="flex items-center gap-2 mb-2">
                <span className="text-[10px] font-bold uppercase tracking-widest" style={{ color: "rgba(var(--text-bright-r), var(--text-bright-g), var(--text-bright-b), 0.6)" }}>
                  {provider === "openai" ? "OpenAI" : provider === "anthropic" ? "Anthropic" : provider}
                </span>
              </div>
              <div className="space-y-1">
                {providerModels.map(m => (
                  <button
                    key={m.id}
                    onClick={() => { setSelectedModel(m.id); setSelectedProvider(m.provider); }}
                    className="flex w-full items-center gap-3 px-3 py-2.5 rounded-xl text-left transition-all"
                    style={{
                      background: selectedModel === m.id ? "rgba(var(--brand-r), var(--brand-g), var(--brand-b), 0.12)" : "transparent",
                      border: selectedModel === m.id ? "1px solid rgba(var(--brand-r), var(--brand-g), var(--brand-b), 0.3)" : "1px solid transparent",
                    }}
                  >
                    <div className="flex h-5 w-5 items-center justify-center rounded-full" style={{ border: "1px solid rgba(var(--brand-r), var(--brand-g), var(--brand-b), 0.3)" }}>
                      {selectedModel === m.id && <Check className="h-3 w-3" style={{ color: "rgba(var(--brand-r), var(--brand-g), var(--brand-b), 0.9)" }} />}
                    </div>
                    <div className="flex-1">
                      <div className="text-sm font-medium" style={{ color: selectedModel === m.id ? "rgba(var(--text-bright-r), var(--text-bright-g), var(--text-bright-b), 0.95)" : "rgba(var(--text-body-r), var(--text-body-g), var(--text-body-b), 0.7)" }}>
                        {m.name}
                      </div>
                      <div className="text-[10px]" style={{ color: "rgba(var(--text-muted-r), var(--text-muted-g), var(--text-muted-b), 0.4)" }}>{m.id}</div>
                    </div>
                    <div className="flex gap-1">
                      {m.capabilities.reasoning && <Sparkles className="h-3 w-3" style={{ color: "rgba(var(--warning-r), var(--warning-g), var(--warning-b), 0.6)" }} />}
                    </div>
                  </button>
                ))}
              </div>
            </div>
          ))}
        </div>

        <div className="flex items-center justify-end gap-3 px-5 py-4 border-t border-[rgba(var(--brand-r),var(--brand-g),var(--brand-b),0.15)]">
          <button
            onClick={onClose}
            className="px-4 py-2 text-xs font-medium rounded-xl transition-all"
            style={{ color: "rgba(var(--text-muted-r), var(--text-muted-g), var(--text-muted-b), 0.7)", background: "rgba(var(--brand-r), var(--brand-g), var(--brand-b), 0.05)" }}
          >
            Cancel
          </button>
          <button
            onClick={handleSave}
            disabled={saving || !selectedModel}
            className="flex items-center gap-2 px-5 py-2 text-xs font-medium rounded-xl transition-all disabled:opacity-40"
            style={{
              background: saved ? "rgba(var(--success-r), var(--success-g), var(--success-b), 0.2)" : "linear-gradient(135deg, rgba(var(--brand-r), var(--brand-g), var(--brand-b), 0.3), rgba(var(--brand-r), var(--brand-g), calc(var(--brand-b) - 55), 0.2))",
              border: saved ? "1px solid rgba(var(--success-r), var(--success-g), var(--success-b), 0.3)" : "1px solid rgba(var(--brand-r), var(--brand-g), var(--brand-b), 0.35)",
              color: saved ? "rgba(var(--success-r), var(--success-g), var(--success-b), 0.9)" : "rgba(var(--text-bright-r), var(--text-bright-g), var(--text-bright-b), 0.8)",
            }}
          >
            {saved ? <Check className="h-3 w-3" /> : saving ? "Saving..." : "Apply Model"}
          </button>
        </div>
      </div>
    </div>
  );
}
