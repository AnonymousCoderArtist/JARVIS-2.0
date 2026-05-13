import { useState, useEffect, useCallback } from "react";
import { useClient } from "@/providers/ClientProvider";
import { getSafetyProfile, setSafetyProfile } from "@/lib/api";
import { Shield, ShieldAlert, ShieldCheck, ShieldX, Zap } from "lucide-react";

interface SafetyProfileProps {
  open: boolean;
  onClose: () => void;
  onProfileChange?: (profileId: number) => void;
}

const PROFILE_ICONS = [ShieldX, ShieldAlert, Shield, ShieldCheck, Zap];
const PROFILE_COLORS = [
  "rgba(255, 80, 80, 0.7)",
  "rgba(255, 160, 50, 0.7)",
  "rgba(100, 180, 255, 0.7)",
  "rgba(80, 200, 120, 0.7)",
  "rgba(180, 100, 255, 0.7)",
];

export function SafetyProfile({ open, onClose, onProfileChange }: SafetyProfileProps) {
  const { token } = useClient();
  const [profiles, setProfiles] = useState<Array<{ id: number; name: string; desc: string }>>([]);
  const [currentId, setCurrentId] = useState<number>(3);

  const load = useCallback(async () => {
    const r = await getSafetyProfile(token);
    setProfiles(r.profiles);
    setCurrentId(r.current.id);
  }, [token]);

  useEffect(() => { if (open) load(); }, [open, load]);

  const switchProfile = useCallback(async (id: number) => {
    await setSafetyProfile(token, id);
    setCurrentId(id);
    onProfileChange?.(id);
  }, [token, onProfileChange]);

  if (!open) return null;
  const current = profiles.find(p => p.id === currentId);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
      <div
        className="w-full max-w-sm overflow-hidden rounded-2xl"
        style={{
          background: "linear-gradient(180deg, rgba(10, 20, 45, 0.98) 0%, rgba(6, 12, 28, 0.98) 100%)",
          border: "1px solid rgba(26, 90, 255, 0.3)",
          boxShadow: "0 8px 40px rgba(0,0,0,0.6)",
        }}
      >
        <div className="flex items-center justify-between px-5 py-4 border-b" style={{ borderColor: "rgba(26, 90, 255, 0.15)" }}>
          <div className="flex items-center gap-2">
            <Shield className="h-4 w-4" style={{ color: "rgba(100, 160, 255, 0.8)" }} />
            <span className="text-sm font-bold tracking-wider uppercase" style={{ color: "rgba(200, 220, 255, 0.9)" }}>
              Safety Profile
            </span>
          </div>
          <button onClick={onClose} className="p-1 rounded-lg hover:bg-blue-500/10" style={{ color: "rgba(100, 140, 220, 0.6)" }}>
            <XIcon className="h-4 w-4" />
          </button>
        </div>

        <div className="p-5 space-y-2">
          {profiles.map((p, i) => {
            const Icon = PROFILE_ICONS[i] ?? Shield;
            const active = p.id === currentId;
            return (
              <button
                key={p.id}
                onClick={() => switchProfile(p.id)}
                className="flex w-full items-center gap-3 px-4 py-3 rounded-xl text-left transition-all"
                style={{
                  background: active ? "rgba(26, 90, 255, 0.1)" : "rgba(26, 90, 255, 0.03)",
                  border: active ? `1px solid ${PROFILE_COLORS[i]}40` : "1px solid rgba(26, 90, 255, 0.08)",
                }}
              >
                <div className="flex h-8 w-8 items-center justify-center rounded-full" style={{ background: `${PROFILE_COLORS[i]}15` }}>
                  <Icon className="h-4 w-4" style={{ color: PROFILE_COLORS[i] }} />
                </div>
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-bold" style={{ color: active ? "rgba(200, 230, 255, 0.9)" : "rgba(150, 180, 220, 0.6)" }}>
                      {p.name}
                    </span>
                    <span className="text-[9px] font-mono px-1.5 py-0.5 rounded" style={{ background: "rgba(26, 90, 255, 0.08)", color: "rgba(100, 140, 220, 0.4)" }}>
                      L{p.id}
                    </span>
                  </div>
                  <div className="text-[10px] mt-0.5" style={{ color: "rgba(100, 140, 220, 0.4)" }}>{p.desc}</div>
                </div>
                {active && (
                  <div className="flex h-5 w-5 items-center justify-center rounded-full" style={{ background: "rgba(26, 90, 255, 0.2)" }}>
                    <CheckIcon className="h-3 w-3" style={{ color: "rgba(100, 180, 255, 0.8)" }} />
                  </div>
                )}
              </button>
            );
          })}
        </div>

        {current && (
          <div className="px-5 py-3 border-t text-[9px] text-center" style={{ borderColor: "rgba(26, 90, 255, 0.1)", color: "rgba(100, 140, 220, 0.35)" }}>
            Press Shift+Tab to cycle profiles · Current: {current.name}
          </div>
        )}
      </div>
    </div>
  );
}

function XIcon(props: React.SVGProps<SVGSVGElement>) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" {...props}>
      <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
    </svg>
  );
}

function CheckIcon(props: React.SVGProps<SVGSVGElement>) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" {...props}>
      <polyline points="20 6 9 17 4 12" />
    </svg>
  );
}
