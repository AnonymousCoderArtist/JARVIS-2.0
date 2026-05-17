import { cn } from "@/lib/utils";

interface TopMenuProps {
  activeTab: "chat" | "user";
  onTabChange?: (tab: "chat" | "user") => void;
  hasActiveQuestion?: boolean;
  hasPendingApproval?: boolean;
}

export function TopMenu({
  activeTab, onTabChange,
  hasActiveQuestion, hasPendingApproval,
}: TopMenuProps) {
  return (
    <div className="fixed left-1/2 top-4 z-50 -translate-x-1/2 techy-topmenu">
      <div className="flex items-center gap-6 rounded-full px-6 py-2 techy-topmenu-inner">
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
            <span className="absolute inset-0 rounded-full techy-btn-active" />
          )}
          <span className="relative z-10 flex items-center gap-1.5">
            <ChatIcon />
            chat
          </span>
        </button>

        <span className="h-4 w-px" style={{ background: "linear-gradient(180deg, transparent, rgba(var(--brand-r), var(--brand-g), var(--brand-b), 0.3), transparent)" }} />

        <div className="relative px-3 py-0.5">
          <span
            className="text-sm font-bold tracking-[0.35em] uppercase"
            style={{
              color: "hsl(var(--foreground))",
              textShadow: "0 0 15px rgba(var(--brand-r), var(--brand-g), var(--brand-b), 0.5), 0 0 30px rgba(var(--brand-r), var(--brand-g), var(--brand-b), 0.2)",
            }}
          >
            Jarvis
          </span>
        </div>

        <span className="h-4 w-px" style={{ background: "linear-gradient(180deg, transparent, rgba(var(--brand-r), var(--brand-g), var(--brand-b), 0.3), transparent)" }} />

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
            <span className="absolute inset-0 rounded-full techy-btn-active" />
          )}
          <span className="relative z-10 flex items-center gap-1.5">
            <BotIcon />
            tools
          </span>
        </button>
      </div>

      {(hasActiveQuestion || hasPendingApproval) && (
        <div className="absolute -bottom-6 left-1/2 flex -translate-x-1/2 gap-2 mt-1">
          {hasActiveQuestion && (
            <div className="techy-badge techy-badge-question">
              Question pending
            </div>
          )}
          {hasPendingApproval && (
            <div className="techy-badge techy-badge-approval animate-pulse">
              Approval needed
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function ChatIcon(props: React.SVGProps<SVGSVGElement>) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" {...props}>
      <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
    </svg>
  );
}

function BotIcon(props: React.SVGProps<SVGSVGElement>) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" {...props}>
      <rect x="3" y="11" width="18" height="10" rx="2" /><circle cx="12" cy="5" r="2" /><path d="M12 7v4" /><line x1="8" y1="16" x2="8" y2="16" /><line x1="16" y1="16" x2="16" y2="16" />
    </svg>
  );
}
