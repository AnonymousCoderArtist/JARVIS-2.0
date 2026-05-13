import { useCallback, useEffect, useMemo, useState, useRef } from "react";
import { DotGrid } from "./DotGrid";
import { TopMenu } from "./TopMenu";
import { TechSphere } from "./TechSphere";
import { ChatPanel } from "./ChatPanel";
import { ChatInput } from "./ChatInput";
import { ToolCallBox } from "./ToolCallBox";
import { ChatHistory } from "./ChatHistory";
import { SphereResponse } from "./SphereResponse";

import { useDraggable } from "./useDraggable";
import { useSessions, useSessionHistory } from "@/hooks/useSessions";
import { useJarvisStream } from "@/hooks/useJarvisStream";
import { useClient } from "@/providers/ClientProvider";
import type { UIMessage, ConnectionStatus } from "@/lib/types";

// New feature components
import { Bot, Activity, Undo2, Bug, ThumbsUp, Wifi, BarChart3, Key, Shield } from "lucide-react";
import { ModelPicker } from "./ModelPicker";
import { McpPanel } from "./McpPanel";
import { HeartbeatPanel } from "./HeartbeatPanel";
import { RewindDialog } from "./RewindDialog";
import { ConfigPanel } from "./ConfigPanel";
import { DebugConsole } from "./DebugConsole";
import { FeedbackWidget } from "./FeedbackWidget";
import { ContextProgress } from "./ContextProgress";
import { ConnectorAuth } from "./ConnectorAuth";
import { SafetyProfile } from "./SafetyProfile";
import { QuestionDialog } from "./QuestionDialog";
import { ApprovalDialog } from "./ApprovalDialog";

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
  const { client, token } = useClient();
  const { sessions, createChat } = useSessions();
  const [activeKey, setActiveKey] = useState<string | null>(null);
  const [chatOpen, setChatOpen] = useState(true);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState<ConnectionStatus>("connecting");
  const hasGreetedRef = useRef(false);
  const isCreatingChatRef = useRef(false);

  // Panel visibility states
  const [modelPickerOpen, setModelPickerOpen] = useState(false);
  const [mcpPanelOpen, setMcpPanelOpen] = useState(false);
  const [heartbeatOpen, setHeartbeatOpen] = useState(false);
  const [rewindOpen, setRewindOpen] = useState(false);
  const [configOpen, setConfigOpen] = useState(false);
  const [debugOpen, setDebugOpen] = useState(false);
  const [feedbackOpen, setFeedbackOpen] = useState(false);
  const [contextOpen, setContextOpen] = useState(false);
  const [connectorOpen, setConnectorOpen] = useState(false);
  const [safetyOpen, setSafetyOpen] = useState(false);

  // Current model name
  const [currentModel, setCurrentModel] = useState<string | null>(null);
  const [safetyProfileId, setSafetyProfileId] = useState<number>(3);

  // Shift+Tab cycles safety profiles
  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.shiftKey && e.key === "Tab") {
        e.preventDefault();
        const next = safetyProfileId >= 5 ? 1 : safetyProfileId + 1;
        setSafetyProfileId(next);
        import("@/lib/api").then(m => m.setSafetyProfile(token, next));
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [safetyProfileId]);

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

  const sessionId = useMemo(() => {
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
    pendingQuestion,
    answerQuestion,
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

  // Canvas offset
  const [canvasOffset, setCanvasOffset] = useState({ x: 0, y: 0 });

  // Sphere drag
  const sphereDrag = useDraggable({ x: 40, y: window.innerHeight - 260 });

  // Widget positions
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
      {/* === CANVAS + WIDGETS (no container transform — each element handles its own offset) === */}
      <DotGrid offset={canvasOffset} onOffsetChange={setCanvasOffset} />

      {/* Widgets wrapped in screen-space positioning shells */}
      <div
        className="absolute z-30"
        style={{ left: chatPanelPos.x + canvasOffset.x, top: chatPanelPos.y + canvasOffset.y }}
      >
        <ChatPanel
          open={chatOpen}
          messages={messages}
          isStreaming={isStreaming}
          onClose={() => setChatOpen(false)}
          pos={chatPanelPos}
          onPosChange={setChatPanelPos}
          canvasOffset={canvasOffset}
        />
      </div>

      <div
        className="absolute z-30"
        style={{ left: toolBoxPos.x + canvasOffset.x, top: toolBoxPos.y + canvasOffset.y }}
      >
        <ToolCallBox
          toolCalls={toolCalls}
          pos={toolBoxPos}
          onPosChange={setToolBoxPos}
          canvasOffset={canvasOffset}
        />
      </div>

      <div
        className="absolute z-30"
        style={{ left: historyPos.x + canvasOffset.x, top: historyPos.y + canvasOffset.y }}
      >
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

      {/* Center glow */}
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
        hasActiveQuestion={pendingQuestion !== null}
        hasPendingApproval={pendingApproval !== null}
      />

      {/* Connection Status */}
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

      {/* Sphere response */}
      <SphereResponse
        thinking={thinking}
        messages={messages}
        isStreaming={isStreaming}
        sphereX={sphereDrag.pos.x}
        sphereY={sphereDrag.pos.y}
      />

      {/* Draggable Sphere */}
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

      {/* Chat Input */}
      <ChatInput
        onSend={handleSend}
        disabled={isStreaming && !chatId}
        onOpenModelPicker={() => setModelPickerOpen(true)}
        onOpenMcpPanel={() => setMcpPanelOpen(true)}
        onOpenHeartbeat={() => setHeartbeatOpen(true)}
        onOpenRewind={() => setRewindOpen(true)}
        onOpenConfig={() => setConfigOpen(true)}
        onOpenDebug={() => setDebugOpen(true)}
        onOpenFeedback={() => setFeedbackOpen(true)}
      />

      {/* ===== FIXED RIGHT SIDEBAR ===== */}
      <div
        className="fixed right-0 top-1/2 z-50 -translate-y-1/2 flex flex-col items-center gap-3 py-3 px-2 rounded-l-2xl"
        style={{
          background: "linear-gradient(180deg, rgba(8, 16, 35, 0.85) 0%, rgba(5, 10, 22, 0.8) 100%)",
          backdropFilter: "blur(12px)",
          border: "1px solid rgba(26, 90, 255, 0.15)",
          borderRight: "none",
        }}
      >
        {[
          { icon: Bot, label: "Model", action: () => setModelPickerOpen(true) },
          { icon: Wifi, label: "MCP", action: () => setMcpPanelOpen(true) },
          { icon: Activity, label: "Heartbeat", action: () => setHeartbeatOpen(true) },
          { icon: Undo2, label: "Rewind", action: () => setRewindOpen(true) },
          { icon: Bug, label: "Debug", action: () => setDebugOpen(true) },
          { icon: BarChart3, label: "Context", action: () => setContextOpen(true) },
          { icon: Key, label: "Connectors", action: () => setConnectorOpen(true) },
          { icon: Shield, label: "Safety", action: () => setSafetyOpen(true) },
          { icon: ThumbsUp, label: "Feedback", action: () => setFeedbackOpen(true) },
        ].map(({ icon: Icon, label, action }) => (
          <button
            key={label}
            onClick={action}
            className="group relative flex h-9 w-9 items-center justify-center rounded-xl transition-all hover:bg-blue-500/10"
            style={{ color: "rgba(100, 160, 255, 0.5)" }}
            title={label}
          >
            <Icon className="h-4 w-4" />
            <span
              className="absolute right-full mr-2 top-1/2 -translate-y-1/2 px-2 py-1 rounded-md text-[10px] whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none"
              style={{
                background: "rgba(5, 10, 22, 0.95)",
                border: "1px solid rgba(26, 90, 255, 0.2)",
                color: "rgba(180, 200, 240, 0.8)",
              }}
            >
              {label}
            </span>
          </button>
        ))}
      </div>

      {/* ===== NEW FEATURE PANELS ===== */}

      <ModelPicker
        open={modelPickerOpen}
        onClose={() => setModelPickerOpen(false)}
        currentModel={currentModel}
        onModelChange={setCurrentModel}
      />

      <McpPanel
        open={mcpPanelOpen}
        onClose={() => setMcpPanelOpen(false)}
      />

      <HeartbeatPanel
        open={heartbeatOpen}
        onClose={() => setHeartbeatOpen(false)}
      />

      <RewindDialog
        open={rewindOpen}
        onClose={() => setRewindOpen(false)}
        sessionId={sessionId}
      />

      <ConfigPanel
        open={configOpen}
        onClose={() => setConfigOpen(false)}
        onOpenModelPicker={() => { setConfigOpen(false); setModelPickerOpen(true); }}
      />

      <DebugConsole
        open={debugOpen}
        onClose={() => setDebugOpen(false)}
      />

      <ContextProgress
        open={contextOpen}
        onClose={() => setContextOpen(false)}
      />

      <ConnectorAuth
        open={connectorOpen}
        onClose={() => setConnectorOpen(false)}
      />

      <SafetyProfile
        open={safetyOpen}
        onClose={() => setSafetyOpen(false)}
        onProfileChange={setSafetyProfileId}
      />

      <FeedbackWidget
        open={feedbackOpen}
        onClose={() => setFeedbackOpen(false)}
      />

      <QuestionDialog
        open={pendingQuestion !== null}
        question={pendingQuestion?.question || ""}
        options={pendingQuestion?.options}
        onSubmit={(answer) => {
          answerQuestion(answer);
        }}
        onDismiss={() => {
          answerQuestion("");
        }}
      />

      <ApprovalDialog
        open={pendingApproval !== null}
        toolName={pendingApproval?.toolName || ""}
        toolArgs={pendingApproval?.toolArgs || {}}
        requiredPermissions={pendingApproval?.requiredPermissions || []}
        onResponse={(approved, alwaysAllow) => {
          sendApprovalResponse(approved, alwaysAllow);
        }}
      />
    </div>
  );
}
