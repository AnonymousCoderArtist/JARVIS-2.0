import { useCallback, useEffect, useMemo, useState } from "react";
import { DotGrid } from "./DotGrid";
import { TopMenu } from "./TopMenu";
import { TechSphere } from "./TechSphere";
import { ChatPanel } from "./ChatPanel";
import { ChatInput } from "./ChatInput";
import { ToolCallBox } from "./ToolCallBox";
import { ChatHistory } from "./ChatHistory";
import { SphereResponse } from "./SphereResponse";
import { ToolApprovalPrompt } from "@/components/thread/ToolApprovalPrompt";
import { useDraggable } from "./useDraggable";
import { useSessions, useSessionHistory } from "@/hooks/useSessions";
import { useJarvisStream } from "@/hooks/useJarvisStream";
import type { UIMessage } from "@/lib/types";

function extractToolCalls(messages: UIMessage[]) {
  const seen = new Set<string>();
  const calls: {
    id: string;
    name: string;
    status: "running" | "completed" | "error";
    timestamp: number;
  }[] = [];

  messages.forEach((msg) => {
    if (msg.toolCalls) {
      msg.toolCalls.forEach((tc) => {
        const key = `${msg.id}-${tc.name}`;
        if (seen.has(key)) return;
        seen.add(key);
        
        calls.push({
          id: crypto.randomUUID(),
          name: tc.name,
          status: tc.result !== undefined 
            ? (tc.success === false ? "error" : "completed") 
            : "running",
          timestamp: Date.now(),
        });
      });
    }
  });

  return calls;
}

export function TechShell() {
  const { sessions, createChat } = useSessions();
  const [activeKey, setActiveKey] = useState<string | null>(null);
  const [chatOpen, setChatOpen] = useState(true);
  const [historyOpen, setHistoryOpen] = useState(false);

  useEffect(() => {
    if (!activeKey && sessions.length > 0) {
      setActiveKey(sessions[0].key);
    }
  }, [sessions, activeKey]);

  const activeSession = useMemo(() => {
    if (!activeKey) return null;
    return sessions.find((s) => s.key === activeKey) ?? null;
  }, [sessions, activeKey]);

  const chatId = useMemo(() => {
    if (!activeSession) return null;
    return activeSession.chatId;
  }, [activeSession]);

  const { messages: historyMessages, hasPendingToolCalls } = useSessionHistory(activeKey);

  const {
    messages,
    isStreaming,
    thinking,
    send,
    pendingApproval,
    sendApprovalResponse,
  } = useJarvisStream(chatId, historyMessages, hasPendingToolCalls);

  const toolCalls = useMemo(() => extractToolCalls(messages), [messages]);
  const [pendingMessage, setPendingMessage] = useState<string | null>(null);

  const handleSend = useCallback(
    (content: string) => {
      if (!chatId) {
        setPendingMessage(content);
        void createChat().then((id) => {
          if (id) {
            const key = `websocket:${id}`;
            setActiveKey(key);
          }
        });
        return;
      }
      send(content);
    },
    [chatId, createChat, send]
  );

  useEffect(() => {
    if (chatId && pendingMessage) {
      send(pendingMessage);
      setPendingMessage(null);
    }
  }, [chatId, pendingMessage, send]);

  // Canvas offset — shared between grid and widgets
  const [canvasOffset, setCanvasOffset] = useState({ x: 0, y: 0 });

  // Sphere — fixed on screen, NOT attached to canvas
  const sphereDrag = useDraggable({ x: 40, y: window.innerHeight - 260 });

// Widget positions — relative to canvas container
  const [chatPanelPos, setChatPanelPos] = useState({
    x: typeof window !== "undefined" ? window.innerWidth / 2 - 240 : 100,
    y: 90,
  });
  const [toolBoxPos, setToolBoxPos] = useState({
    x: typeof window !== "undefined" ? window.innerWidth - 340 : 500,
    y: 90,
  });
  const [historyPos, setHistoryPos] = useState({
    x: typeof window !== "undefined" ? 60 : 60,
    y: 90,
  });

  return (
    <div
      className="relative h-full w-full overflow-hidden"
      style={{
        background:
          "radial-gradient(ellipse at 50% 50%, rgba(10, 22, 50, 1) 0%, rgba(5, 10, 20, 1) 70%)",
      }}
    >
      {/* ===== CANVAS CONTAINER (moves with pan) ===== */}
      <div
        className="absolute inset-0"
        style={{
          transform: `translate(${canvasOffset.x}px, ${canvasOffset.y}px)`,
        }}
      >
        <DotGrid offset={canvasOffset} onOffsetChange={setCanvasOffset} />

        {/* Widgets attached to canvas */}
        <ChatPanel
          open={chatOpen}
          messages={messages}
          isStreaming={isStreaming}
          onClose={() => setChatOpen(false)}
          pos={chatPanelPos}
          onPosChange={setChatPanelPos}
          canvasOffset={canvasOffset}
        />

        <ToolCallBox
          toolCalls={toolCalls}
          pos={toolBoxPos}
          onPosChange={setToolBoxPos}
          canvasOffset={canvasOffset}
        />

        <ChatHistory
          open={historyOpen}
          sessions={sessions}
          activeKey={activeKey}
          onSelect={(key) => {
            setActiveKey(key);
            setChatOpen(true);
          }}
          onClose={() => setHistoryOpen(false)}
          pos={historyPos}
          onPosChange={setHistoryPos}
          canvasOffset={canvasOffset}
        />
      </div>

      {/* ===== FIXED ELEMENTS (outside canvas) ===== */}

      {/* Subtle center glow */}
      <div
        className="pointer-events-none absolute inset-0"
        style={{
          background:
            "radial-gradient(circle at 50% 50%, rgba(26, 90, 255, 0.04) 0%, transparent 60%)",
        }}
      />

      {/* Top menu */}
      <TopMenu
        activeTab={chatOpen ? "chat" : "user"}
        onTabChange={(tab) => {
          if (tab === "chat") {
            setChatOpen(true);
            setHistoryOpen(false);
          } else {
            setHistoryOpen(true);
            setChatOpen(false);
          }
        }}
      />

      {/* Sphere response bubble — top-right of sphere (thinking → response) */}
      <SphereResponse
        thinking={thinking}
        messages={messages}
        isStreaming={isStreaming}
        sphereX={sphereDrag.pos.x}
        sphereY={sphereDrag.pos.y}
      />

      {/* Draggable Sphere — FIXED on screen */}
      <div
        ref={sphereDrag.ref}
        className="fixed z-30"
        style={{
          left: sphereDrag.pos.x,
          top: sphereDrag.pos.y,
        }}
      >
        <TechSphere
          onClick={() => setChatOpen((v) => !v)}
          className="transition-transform duration-300 hover:scale-110"
        />
      </div>

      {/* Bottom Chat Input — floating, NOT draggable */}
      <ChatInput onSend={handleSend} disabled={isStreaming && !chatId} />
      
      {/* Tool Approval Prompt — fixed overlay when approval is pending */}
      {pendingApproval && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <ToolApprovalPrompt
            toolName={pendingApproval.toolName}
            toolArgs={pendingApproval.toolArgs}
            requiredPermissions={pendingApproval.requiredPermissions}
            onResponse={(approved, alwaysAllow) => {
              sendApprovalResponse(approved, alwaysAllow);
            }}
          />
        </div>
      )}
    </div>
  );
}
