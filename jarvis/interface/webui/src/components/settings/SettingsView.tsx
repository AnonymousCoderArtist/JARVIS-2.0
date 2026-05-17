import { useCallback, useEffect, useState } from "react";
import { ChevronLeft, Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { LanguageSwitcher } from "@/components/LanguageSwitcher";
import { Input } from "@/components/ui/input";
import { fetchSettings, updateSettings } from "@/lib/api";
import { cn } from "@/lib/utils";
import { useClient } from "@/providers/ClientProvider";
import type { SettingsPayload } from "@/lib/types";

interface SettingsViewProps {
  onBackToChat: () => void;
  onModelNameChange: (modelName: string | null) => void;
}

export function SettingsView({
  onBackToChat,
  onModelNameChange,
}: SettingsViewProps) {
  const { token } = useClient();
  const [settings, setSettings] = useState<SettingsPayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState({
    model: "",
    provider: "auto",
  });
  const [permissionMode, setPermissionMode] = useState<string>("neutral");
  const [isAutoSaving, setIsAutoSaving] = useState(false);
  // Track original settings from the server to compare against
  const [originalSettings, setOriginalSettings] = useState<SettingsPayload | null>(null);

  const applyPayload = useCallback((payload: SettingsPayload) => {
    setSettings(payload);
    setForm({
      model: payload.agent.model,
      provider: payload.agent.provider,
    });
    // Set original settings for comparison
    setOriginalSettings(payload);
  }, []);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    fetchSettings(token)
      .then((payload) => {
        if (!cancelled) {
          applyPayload(payload);
          setError(null);
        }
      })
      .catch((err) => {
        if (!cancelled) setError((err as Error).message);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [applyPayload, token]);

  const saveSettings = useCallback(async (formToSave: typeof form) => {
    console.log("[AUTO-SAVE] Starting save with:", formToSave);
    try {
      setIsAutoSaving(true);
      const payload = await updateSettings(token, formToSave);
      console.log("[AUTO-SAVE] Save successful, response:", payload);
      applyPayload(payload);
      setOriginalSettings(payload);
      onModelNameChange(payload.agent.model || null);
      setError(null);
    } catch (err) {
      console.error("[AUTO-SAVE] Error:", err);
      setError((err as Error).message);
    } finally {
      setIsAutoSaving(false);
    }
  }, [token, applyPayload, onModelNameChange, setError]);

  // Auto-save when form changes
  useEffect(() => {
    if (!originalSettings) {
      console.log("[AUTO-SAVE] No original settings yet");
      return;
    }
    
    // Check if form is different from original settings
    const isDifferent = 
      form.model !== originalSettings.agent.model ||
      form.provider !== originalSettings.agent.provider;
    
    console.log("[AUTO-SAVE] Check: form=", form, "original=", originalSettings, "isDifferent=", isDifferent);
    
    if (isDifferent) {
      console.log("[AUTO-SAVE] Scheduling save in 1s");
      // Use a simple timeout for auto-save
      const timer = setTimeout(() => {
        console.log("[AUTO-SAVE] Executing save");
        saveSettings(form);
      }, 1000);
      
      return () => {
        console.log("[AUTO-SAVE] Clearing timeout");
        clearTimeout(timer);
      };
    } else {
      console.log("[AUTO-SAVE] No changes detected");
    }
  }, [form, originalSettings, saveSettings]);

  return (
    <div className="min-h-0 flex-1 overflow-y-auto bg-background">
      <main className="mx-auto w-full max-w-[1000px] px-6 py-6">
        <button
          type="button"
          onClick={onBackToChat}
          className="mb-4 inline-flex items-center gap-1.5 text-xs font-medium text-muted-foreground hover:text-foreground"
        >
          <ChevronLeft className="h-3.5 w-3.5" />
          Back to chat
        </button>

        <h1 className="mb-6 text-base font-semibold tracking-tight">General</h1>

        {loading ? (
          <div className="flex h-48 items-center justify-center text-sm text-muted-foreground">
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            Loading settings...
          </div>
        ) : error ? (
          <SettingsGroup>
            <SettingsRow title="Could not load settings">
              <span className="max-w-[520px] text-sm text-muted-foreground">{error}</span>
            </SettingsRow>
          </SettingsGroup>
        ) : settings ? (
          <SettingsSection
            form={form}
            setForm={setForm}
            settings={settings}
            isAutoSaving={isAutoSaving}
            permissionMode={permissionMode}
            setPermissionMode={setPermissionMode}
            onSave={saveSettings}
          />
        ) : null}
      </main>
    </div>
  );
}

function SettingsSection({
  form,
  setForm,
  settings,
  isAutoSaving,
  permissionMode,
  setPermissionMode,
  onSave,
}: {
  form: {
    model: string;
    provider: string;
  };
  setForm: React.Dispatch<React.SetStateAction<{
    model: string;
    provider: string;
  }>>;
  settings: SettingsPayload;
  isAutoSaving: boolean;
  permissionMode: string;
  setPermissionMode: React.Dispatch<React.SetStateAction<string>>;
  onSave: (form: { model: string; provider: string }) => void;
}) {
  return (
    <div className="space-y-7">
      <section>
        <h2 className="mb-2 px-2 text-xs font-medium text-muted-foreground">AI</h2>
        <SettingsGroup>
          <SettingsRow title="Provider">
            <select
              value={form.provider}
              onChange={(event) => setForm((prev) => ({ ...prev, provider: event.target.value }))}
              className={cn(
                "h-8 w-[210px] rounded-md border border-input bg-background px-2 text-sm",
                "outline-none transition-colors hover:bg-accent focus-visible:ring-2 focus-visible:ring-ring",
              )}
            >
              {settings.providers.map((provider) => (
                <option key={provider.name} value={provider.name}>
                  {provider.label}
                </option>
              ))}
            </select>
          </SettingsRow>

          <SettingsRow title="Model">
            <Input
              value={form.model}
              onChange={(event) => setForm((prev) => ({ ...prev, model: event.target.value }))}
              className="h-8 w-[280px]"
            />
          </SettingsRow>

          {(isAutoSaving) ? (
            <SettingsGroup>
              <SettingsRow title="">
                <div className="flex w-full items-center justify-center gap-2 text-sm text-muted-foreground">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Auto-saving...
                </div>
              </SettingsRow>
            </SettingsGroup>
          ) : null}
          <SettingsGroup>
            <SettingsRow>
              <Button
                onClick={() => onSave(form)}
                className="w-full"
              >
                Save Now
              </Button>
            </SettingsRow>
          </SettingsGroup>
        </SettingsGroup>
      </section>

      <section>
        <h2 className="mb-2 px-2 text-xs font-medium text-muted-foreground">Interface</h2>
        <SettingsGroup>
          <SettingsRow title="Language">
            <LanguageSwitcher />
          </SettingsRow>
        </SettingsGroup>
      </section>

      <section>
        <h2 className="mb-2 px-2 text-xs font-medium text-muted-foreground">Permissions</h2>
        <SettingsGroup>
          <SettingsRow title="Permission Mode">
            <select
              value={permissionMode}
              onChange={(event) => setPermissionMode(event.target.value)}
              className={cn(
                "h-8 w-[210px] rounded-md border border-input bg-background px-2 text-sm",
                "outline-none transition-colors hover:bg-accent focus-visible:ring-2 focus-visible:ring-ring",
              )}
            >
              <option value="neutral">Default (Ask)</option>
              <option value="safe">Safe (Read-only)</option>
              <option value="destructive">Accept Edits</option>
              <option value="yolo">Auto Approve (YOLO)</option>
            </select>
          </SettingsRow>
          <SettingsRow title="Description">
            <span className="max-w-[400px] text-sm text-muted-foreground">
              {permissionMode === "neutral" && "Requires approval for tool executions"}
              {permissionMode === "safe" && "Read-only mode - can only explore and read files"}
              {permissionMode === "destructive" && "Auto-approves file edits"}
              {permissionMode === "yolo" && "Auto-approves all tool executions"}
            </span>
          </SettingsRow>
        </SettingsGroup>
      </section>
    </div>
  );
}

function SettingsGroup({ children }: { children: React.ReactNode }) {
  return (
    <div className="overflow-hidden rounded-xl border border-border/60 bg-card/80">
      <div className="divide-y divide-border/50">{children}</div>
    </div>
  );
}

function SettingsRow({
  title,
  children,
}: {
  title?: string;
  children?: React.ReactNode;
}) {
  return (
    <div className="flex min-h-[52px] flex-col gap-3 px-3 py-2.5 sm:flex-row sm:items-center sm:justify-between">
      <div className="min-w-0">
        <div className="text-sm font-medium leading-5">{title}</div>
      </div>
      {children ? <div className="shrink-0 sm:ml-6">{children}</div> : null}
    </div>
  );
}
