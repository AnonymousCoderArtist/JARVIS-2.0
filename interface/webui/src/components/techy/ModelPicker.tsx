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
      <div
        className="w-full max-w-lg overflow-hidden rounded-2xl"
        style={{
          background: "linear-gradient(180deg, rgba(10, 20, 45, 0.98) 0%, rgba(6, 12, 28, 0.98) 100%)",
          border: "1px solid rgba(26, 90, 255, 0.3)",
          boxShadow: "0 8px 40px rgba(0,0,0,0.6), 0 0 30px rgba(26,90,255,0.1)",
        }}
      >
        <div className="flex items-center justify-between px-5 py-4 border-b" style={{ borderColor: "rgba(26, 90, 255, 0.15)" }}>
          <div className="flex items-center gap-2">
            <Bot className="h-4 w-4" style={{ color: "rgba(100, 160, 255, 0.8)" }} />
            <span className="text-sm font-bold tracking-wider uppercase" style={{ color: "rgba(200, 220, 255, 0.9)" }}>
              Model Picker
            </span>
          </div>
          <button onClick={onClose} className="p-1 rounded-lg transition-colors hover:bg-blue-500/10" style={{ color: "rgba(100, 140, 220, 0.6)" }}>
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="p-5 space-y-4 max-h-[60vh] overflow-y-auto">
          {Object.entries(grouped).map(([provider, providerModels]) => (
            <div key={provider}>
              <div className="flex items-center gap-2 mb-2">
                <span className="text-[10px] font-bold uppercase tracking-widest" style={{ color: "rgba(100, 160, 255, 0.6)" }}>
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
                      background: selectedModel === m.id ? "rgba(26, 90, 255, 0.12)" : "transparent",
                      border: selectedModel === m.id ? "1px solid rgba(26, 90, 255, 0.3)" : "1px solid transparent",
                    }}
                  >
                    <div className="flex h-5 w-5 items-center justify-center rounded-full" style={{ border: "1px solid rgba(26, 90, 255, 0.3)" }}>
                      {selectedModel === m.id && <Check className="h-3 w-3" style={{ color: "rgba(100, 180, 255, 0.9)" }} />}
                    </div>
                    <div className="flex-1">
                      <div className="text-sm font-medium" style={{ color: selectedModel === m.id ? "rgba(200, 230, 255, 0.95)" : "rgba(150, 180, 220, 0.7)" }}>
                        {m.name}
                      </div>
                      <div className="text-[10px]" style={{ color: "rgba(100, 140, 220, 0.4)" }}>{m.id}</div>
                    </div>
                    <div className="flex gap-1">
                      {m.capabilities.reasoning && <Sparkles className="h-3 w-3" style={{ color: "rgba(255, 200, 50, 0.6)" }} />}
                    </div>
                  </button>
                ))}
              </div>
            </div>
          ))}
        </div>

        <div className="flex items-center justify-end gap-3 px-5 py-4 border-t" style={{ borderColor: "rgba(26, 90, 255, 0.15)" }}>
          <button
            onClick={onClose}
            className="px-4 py-2 text-xs font-medium rounded-xl transition-all"
            style={{ color: "rgba(100, 140, 220, 0.7)", background: "rgba(26, 90, 255, 0.05)" }}
          >
            Cancel
          </button>
          <button
            onClick={handleSave}
            disabled={saving || !selectedModel}
            className="flex items-center gap-2 px-5 py-2 text-xs font-medium rounded-xl transition-all disabled:opacity-40"
            style={{
              background: saved ? "rgba(50, 200, 100, 0.2)" : "linear-gradient(135deg, rgba(26,90,255,0.3), rgba(0,80,200,0.2))",
              border: saved ? "1px solid rgba(50, 200, 100, 0.3)" : "1px solid rgba(26,90,255,0.35)",
              color: saved ? "rgba(100, 220, 150, 0.9)" : "rgba(200, 220, 255, 0.8)",
            }}
          >
            {saved ? <Check className="h-3 w-3" /> : saving ? "Saving..." : "Apply Model"}
          </button>
        </div>
      </div>
    </div>
  );
}
