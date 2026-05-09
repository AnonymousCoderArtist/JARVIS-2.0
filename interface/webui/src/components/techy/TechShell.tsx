import { useCallback, useEffect, useMemo, useState, useRef } from "react";
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
import { useClient } from "@/providers/ClientProvider";
import type { UIMessage, ConnectionStatus } from "@/lib/types";

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
  const { client } = useClient();
  const { sessions, createChat } = useSessions();
  const [activeKey, setActiveKey] = useState<string | null>(null);
  const [chatOpen, setChatOpen] = useState(true);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState<ConnectionStatus>("connecting");
  const hasGreetedRef = useRef(false);
  const isCreatingChatRef = useRef(false);

  useEffect(() => {
    const unsubscribe = client.onStatus((status) => {
      setConnectionStatus(status);
      if (status === "open" && sessions.length === 0 && !isCreatingChatRef.current) {
        isCreatingChatRef.current = true;
        void createChat().then((id) => {
          if (id) {
            const key = `websocket:${id}`;
            setActiveKey(key);
          }
          isCreatingChatRef.current = false;
        });
      }
    });
    return unsubscribe;
  }, [client, sessions.length, createChat]);

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

  useEffect(() => {
    if (connectionStatus === "open" && chatId && !hasGreetedRef.current) {
      hasGreetedRef.current = true;
      setTimeout(() => {
        send("hi", undefined, "medium");
      }, 150);
    }
  }, [connectionStatus, chatId, send]);

  const toolCalls = useMemo(() => extractToolCalls(messages), [messages]);
  const [pendingMessage, setPendingMessage] = useState<{ content: string; thinkingLevel: string } | null>(null);

  const handleSend = useCallback(
    (content: string, thinkingLevel?: string) => {
      if (!chatId) {
        setPendingMessage({ content, thinkingLevel: thinkingLevel || "medium" });
        void createChat().then((id) => {
          if (id) {
            const key = `websocket:${id}`;
            setActiveKey(key);
          }
        });
        return;
      }
      send(content, undefined, thinkingLevel);
    },
    [chatId, createChat, send]
  );

  useEffect(() => {
    if (chatId && pendingMessage) {
      send(pendingMessage.content, undefined, pendingMessage.thinkingLevel);
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

      {/* Connection Status Indicator */}
      {connectionStatus !== "open" && (
        <div className="fixed left-1/2 top-20 z-50 -translate-x-1/2">
          <div
            className="flex items-center gap-3 rounded-full px-4 py-2"
            style={{
              background: "linear-gradient(180deg, rgba(10, 20, 45, 0.95) 0%, rgba(6, 12, 28, 0.95) 100%)",
              border: "1px solid rgba(26, 90, 255, 0.3)",
              boxShadow: "0 4px 20px rgba(0, 0, 0, 0.4)",
            }}
          >
            <div className="relative flex h-3 w-3">
              <span
                className="absolute inline-flex h-full w-full animate-ping rounded-full"
                style={{ background: connectionStatus === "connecting" ? "rgba(26, 90, 255, 0.5)" : "rgba(255, 100, 100, 0.5)" }}
              />
              <span
                className="relative inline-flex h-3 w-3 rounded-full"
                style={{ background: connectionStatus === "connecting" ? "rgba(26, 90, 255, 0.8)" : "rgba(255, 100, 100, 0.8)" }}
              />
            </div>
            <span className="text-xs font-medium tracking-wide" style={{ color: "rgba(120, 160, 255, 0.9)" }}>
              {connectionStatus === "connecting" ? "Connecting to JARVIS..." : 
               connectionStatus === "reconnecting" ? "Reconnecting..." : 
               connectionStatus === "closed" ? "Disconnected" : "Connecting..."}
            </span>
          </div>
        </div>
      )}

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
