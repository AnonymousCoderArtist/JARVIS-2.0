import { cn } from "@/lib/utils";

interface TopMenuProps {
  activeTab: "chat" | "user";
  onTabChange?: (tab: "chat" | "user") => void;
}

export function TopMenu({ activeTab, onTabChange }: TopMenuProps) {
  return (
    <nav
      className="fixed top-4 left-1/2 z-50 -translate-x-1/2"
      style={{
        background:
          "linear-gradient(180deg, rgba(8, 16, 35, 0.9) 0%, rgba(5, 10, 22, 0.85) 100%)",
        backdropFilter: "blur(16px)",
        border: "1px solid rgba(26, 90, 255, 0.25)",
        borderRadius: "20px",
        boxShadow:
          "0 4px 30px rgba(0, 0, 0, 0.3), 0 0 20px rgba(26, 90, 255, 0.1), inset 0 1px 0 rgba(255,255,255,0.05)",
      }}
    >
      <div
        className="flex items-center gap-6 rounded-full px-6 py-2"
        style={{
          background:
            "radial-gradient(ellipse at 50% 0%, rgba(26,90,255,0.08) 0%, transparent 60%)",
        }}
      >
        {/* Chat tab */}
        <button
          onClick={() => onTabChange?.("chat")}
          className={cn(
            "relative px-4 py-1 text-xs font-medium tracking-[0.2em] uppercase transition-all duration-300",
            activeTab === "chat"
              ? "text-blue-200"
              : "text-slate-500 hover:text-slate-300"
          )}
        >
          {activeTab === "chat" && (
            <span
              className="absolute inset-0 rounded-full"
              style={{
                background:
                  "linear-gradient(135deg, rgba(26,90,255,0.2), rgba(0,100,255,0.08))",
                border: "1px solid rgba(26,90,255,0.35)",
                boxShadow: "0 0 20px rgba(26,90,255,0.15), inset 0 0 10px rgba(26,90,255,0.05)",
              }}
            />
          )}
          <span className="relative z-10">chat</span>
        </button>

        {/* Divider */}
        <span
          className="h-4 w-px"
          style={{
            background:
              "linear-gradient(180deg, transparent, rgba(26,90,255,0.3), transparent)",
          }}
        />

        {/* Jarvis center */}
        <div className="relative px-3 py-0.5">
          <span
            className="text-sm font-bold tracking-[0.35em] uppercase"
            style={{
              color: "#e0e8ff",
              textShadow:
                "0 0 15px rgba(26,90,255,0.5), 0 0 30px rgba(26,90,255,0.2)",
            }}
          >
            Jarvis
          </span>
        </div>

        {/* Divider */}
        <span
          className="h-4 w-px"
          style={{
            background:
              "linear-gradient(180deg, transparent, rgba(26,90,255,0.3), transparent)",
          }}
        />

        {/* User tab */}
        <button
          onClick={() => onTabChange?.("user")}
          className={cn(
            "relative px-4 py-1 text-xs font-medium tracking-[0.2em] uppercase transition-all duration-300",
            activeTab === "user"
              ? "text-blue-200"
              : "text-slate-500 hover:text-slate-300"
          )}
        >
          {activeTab === "user" && (
            <span
              className="absolute inset-0 rounded-full"
              style={{
                background:
                  "linear-gradient(135deg, rgba(26,90,255,0.2), rgba(0,100,255,0.08))",
                border: "1px solid rgba(26,90,255,0.35)",
                boxShadow: "0 0 20px rgba(26,90,255,0.15), inset 0 0 10px rgba(26,90,255,0.05)",
              }}
            />
          )}
          <span className="relative z-10">user</span>
        </button>
      </div>
    </nav>
  );
}
