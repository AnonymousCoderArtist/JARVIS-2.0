import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { preloadMarkdownText } from "@/components/MarkdownText";
import { TechShell } from "@/components/techy/TechShell";
import { deriveWsUrl, fetchBootstrap } from "@/lib/bootstrap";
import { JarvisClient } from "@/lib/jarvis-client";
import { ClientProvider } from "@/providers/ClientProvider";

type BootState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | {
      status: "ready";
      client: JarvisClient;
      token: string;
      modelName: string | null;
    };

export default function App() {
  const { t } = useTranslation();
  const [state, setState] = useState<BootState>({ status: "loading" });

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const boot = await fetchBootstrap();
        if (cancelled) return;
        const url = deriveWsUrl(boot.ws_path, boot.token);
        const client = new JarvisClient({
          url,
          onReauth: async () => {
            try {
              const refreshed = await fetchBootstrap();
              return deriveWsUrl(refreshed.ws_path, refreshed.token);
            } catch {
              return null;
            }
          },
        });
        client.connect();
        setState({
          status: "ready",
          client,
          token: boot.token,
          modelName: boot.model_name ?? null,
        });
      } catch (e) {
        if (cancelled) return;
        const message = e instanceof Error ? e.message : String(e);
        if (message.includes("Failed to fetch") || message.includes("ECONNREFUSED")) {
          setState({ 
            status: "error", 
            message: "Cannot connect to backend server. Make sure the JARVIS backend is running on port 8765." 
          });
        } else if (message.includes("bootstrap failed")) {
          setState({ 
            status: "error", 
            message: "Backend server responded with an error. Check if all dependencies are installed (fastapi, uvicorn)." 
          });
        } else {
          setState({ status: "error", message });
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    const warm = () => preloadMarkdownText();
    const win = globalThis as typeof globalThis & {
      requestIdleCallback?: (
        callback: IdleRequestCallback,
        options?: IdleRequestOptions,
      ) => number;
      cancelIdleCallback?: (handle: number) => void;
    };
    if (typeof win.requestIdleCallback === "function") {
      const id = win.requestIdleCallback(warm, { timeout: 1500 });
      return () => win.cancelIdleCallback?.(id);
    }
    const id = globalThis.setTimeout(warm, 250);
    return () => globalThis.clearTimeout(id);
  }, []);

  if (state.status === "loading") {
    return (
      <div 
        className="flex h-full w-full items-center justify-center"
        style={{ background: "#050a14" }}
      >
        <div className="flex flex-col items-center gap-4">
          <div 
            className="h-10 w-10 animate-pulse rounded-full"
            style={{
              background: "radial-gradient(circle, rgba(26,90,255,0.4), transparent)",
              boxShadow: "0 0 30px rgba(26,90,255,0.3)",
            }}
          />
          <div className="flex items-center gap-2 text-xs tracking-[0.2em] uppercase" style={{ color: "rgba(120, 160, 255, 0.6)" }}>
            <span 
              className="relative flex h-2 w-2"
            >
              <span 
                className="absolute inline-flex h-full w-full animate-ping rounded-full"
                style={{ background: "rgba(26, 90, 255, 0.5)" }}
              />
              <span 
                className="relative inline-flex h-2 w-2 rounded-full"
                style={{ background: "rgba(26, 90, 255, 0.8)" }}
              />
            </span>
            {t("app.loading.connecting")}
          </div>
        </div>
      </div>
    );
  }

  if (state.status === "error") {
    return (
      <div 
        className="flex h-full w-full items-center justify-center px-4 text-center"
        style={{ background: "#050a14" }}
      >
        <div className="flex max-w-md flex-col items-center gap-3">
          <div 
            className="h-10 w-10 rounded-full opacity-60"
            style={{
              background: "radial-gradient(circle, rgba(26,90,255,0.3), transparent)",
              filter: "grayscale(1)",
            }}
          />
          <p className="text-lg font-semibold tracking-wider" style={{ color: "#e0e8ff" }}>
            {t("app.error.title")}
          </p>
          <p className="text-sm" style={{ color: "rgba(120, 160, 255, 0.5)" }}>
            {state.message}
          </p>
          <p className="text-xs" style={{ color: "rgba(100, 140, 220, 0.4)" }}>
            {t("app.error.gatewayHint")}
          </p>
        </div>
      </div>
    );
  }

  return (
    <ClientProvider
      client={state.client}
      token={state.token}
      modelName={state.modelName}
    >
      <TechShell />
    </ClientProvider>
  );
}
