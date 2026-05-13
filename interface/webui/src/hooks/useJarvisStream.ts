import { useCallback, useEffect, useRef, useState } from "react";

import { useClient } from "@/providers/ClientProvider";
import { toMediaAttachment } from "@/lib/media";
import type { StreamError } from "@/lib/jarvis-client";
import type {
  InboundEvent,
  OutboundMedia,
  UIImage,
  UIMessage,
} from "@/lib/types";

interface StreamBuffer {
  messageId: string;
  parts: string[];
}

export interface SendImage {
  media: OutboundMedia;
  preview: UIImage;
}

interface PendingQuestion {
  question: string;
  options?: string[];
  resolve: (answer: string) => void;
}

export function useJarvisStream(
  chatId: string | null,
  initialMessages: UIMessage[] = [],
  hasPendingToolCalls = false,
): {
  messages: UIMessage[];
  isStreaming: boolean;
  thinking: string;
  send: (content: string, images?: SendImage[], thinkingLevel?: string) => void;
  setMessages: React.Dispatch<React.SetStateAction<UIMessage[]>>;
  streamError: StreamError | null;
  dismissStreamError: () => void;
  pendingApproval: {
    toolName: string;
    toolArgs: Record<string, unknown>;
    requiredPermissions: string[];
    toolCallId: string;
  } | null;
  sendApprovalResponse: (approved: boolean, alwaysAllow?: boolean) => void;
  pendingQuestion: {
    question: string;
    options?: string[];
  } | null;
  answerQuestion: (answer: string) => void;
} {
  const { client } = useClient();
  const [messages, setMessages] = useState<UIMessage[]>(initialMessages);
  const initialStreaming = initialMessages.length > 0
    ? initialMessages[initialMessages.length - 1].kind === "trace"
    : false;
  const [isStreaming, setIsStreaming] = useState(initialStreaming || hasPendingToolCalls);
  const [streamError, setStreamError] = useState<StreamError | null>(null);
  const [pendingApproval, setPendingApproval] = useState<{
    toolName: string;
    toolArgs: Record<string, unknown>;
    requiredPermissions: string[];
    toolCallId: string;
  } | null>(null);
  const [pendingQuestion, setPendingQuestion] = useState<{
    question: string;
    options?: string[];
  } | null>(null);
  const pendingQuestionRef = useRef<PendingQuestion | null>(null);
  const buffer = useRef<StreamBuffer | null>(null);
  const streamEndTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [thinking, setThinking] = useState<string>("");

  useEffect(() => {
    return client.onError((err) => setStreamError(err));
  }, [client]);

  const dismissStreamError = useCallback(() => setStreamError(null), []);

  const answerQuestion = useCallback((answer: string) => {
    if (pendingQuestionRef.current) {
      pendingQuestionRef.current.resolve(answer);
      pendingQuestionRef.current = null;
    }
    setPendingQuestion(null);
    // Send the answer as a regular message so the agent gets it
    if (chatId && answer.trim()) {
      client.sendMessage(chatId, answer, undefined, { type: "message_options" });
    }
  }, [chatId, client]);

  useEffect(() => {
    setMessages(initialMessages);
    setIsStreaming(
      initialMessages.length > 0
        ? initialMessages[initialMessages.length - 1].kind === "trace"
        : false,
    );
    if (hasPendingToolCalls) {
      setIsStreaming(true);
    }
    setStreamError(null);
    buffer.current = null;
    if (streamEndTimerRef.current !== null) {
      clearTimeout(streamEndTimerRef.current);
      streamEndTimerRef.current = null;
    }
  }, [chatId, initialMessages, hasPendingToolCalls]);

  useEffect(() => {
    if (!chatId) return;

    const handle = (ev: InboundEvent) => {
      if (streamEndTimerRef.current !== null) {
        clearTimeout(streamEndTimerRef.current);
        streamEndTimerRef.current = null;
      }

      const getActiveAssistantId = () => {
        if (buffer.current?.messageId) return buffer.current.messageId;
        for (let i = messages.length - 1; i >= 0; i--) {
          if (messages[i].role === "assistant" && messages[i].isStreaming) {
            return messages[i].id;
          }
        }
        return null;
      };

      const ensureAssistantMessage = () => {
        let id = getActiveAssistantId();
        if (!id) {
          id = crypto.randomUUID();
          buffer.current = { messageId: id, parts: [] };
          setMessages((prev) => [
            ...prev,
            {
              id: id!,
              role: "assistant",
              content: "",
              isStreaming: true,
              createdAt: Date.now(),
            },
          ]);
          setIsStreaming(true);
        }
        return id;
      };

      if (ev.event === "delta") {
        const id = ensureAssistantMessage();
        if (buffer.current && buffer.current.messageId === id) {
          buffer.current.parts.push(ev.text);
          const combined = buffer.current!.parts.join("");
          setMessages((prev) =>
            prev.map((m) => (m.id === id ? { ...m, content: combined } : m)),
          );
        }
        return;
      }

      if (ev.event === "reasoning") {
        const id = ensureAssistantMessage();
        setThinking((prev) => prev + (ev.text || ""));
        setMessages((prev) =>
          prev.map((m) => (m.id === id ? { ...m, reasoning: (m.reasoning || "") + ev.text } : m)),
        );
        return;
      }

      if (ev.event === "reasoning_end") {
        setThinking("");
        return;
      }

      if (ev.event === "tool_call") {
        const id = ensureAssistantMessage();
        setMessages((prev) =>
          prev.map((m) => {
            if (m.id !== id) return m;
            const toolCalls = [...(m.toolCalls || [])];
            toolCalls.push({
              id: crypto.randomUUID(),
              name: ev.tool_name,
              args: ev.tool_args,
            });
            return { ...m, toolCalls };
          }),
        );
        return;
      }

      if (ev.event === "tool_result") {
        const id = getActiveAssistantId();
        if (id) {
          setMessages((prev) =>
            prev.map((m) => {
              if (m.id !== id) return m;
              const toolCalls = (m.toolCalls || []).map(tc => {
                if (tc.name === ev.tool_name && tc.result === undefined) {
                  return { ...tc, result: ev.result, success: ev.success };
                }
                return tc;
              });
              return { ...m, toolCalls };
            }),
          );
        }
        return;
      }

      if (ev.event === "stream_end") {
        return;
      }

      if (ev.event === "turn_end") {
        setIsStreaming(false);
        setThinking("");
        setMessages((prev) =>
          prev.map((m) => (m.isStreaming ? { ...m, isStreaming: false } : m)),
        );
        buffer.current = null;
        return;
      }

      if (ev.event === "user_input") {
        const question = ev.question;
        const options = ev.options;
        pendingQuestionRef.current = { question, options, resolve: () => {} };
        setPendingQuestion({ question, options });
        return;
      }

      if (ev.event === "approval_request") {
        setPendingApproval({
          toolName: ev.tool_name,
          toolArgs: ev.tool_args,
          requiredPermissions: ev.required_permissions,
          toolCallId: ev.tool_call_id,
        });
        return;
      }

      if (ev.event === "message") {
        if (ev.kind === "tool_hint" || ev.kind === "progress") {
          const line = ev.text;
          setMessages((prev) => {
            const last = prev[prev.length - 1];
            if (last && last.kind === "trace" && !last.isStreaming) {
              const merged: UIMessage = {
                ...last,
                traces: [...(last.traces ?? [last.content]), line],
                content: line,
              };
              return [...prev.slice(0, -1), merged];
            }
            return [
              ...prev,
              {
                id: crypto.randomUUID(),
                role: "tool",
                kind: "trace",
                content: line,
                traces: [line],
                createdAt: Date.now(),
              },
            ];
          });
          return;
        }

        const media = ev.media_urls?.length
          ? ev.media_urls.map((m) => toMediaAttachment(m))
          : ev.media?.map((url) => toMediaAttachment({ url }));

        const activeId = getActiveAssistantId();
        const content = ev.buttons?.length ? (ev.button_prompt ?? ev.text) : ev.text;

        setMessages((prev) => {
          if (activeId) {
            return prev.map((m) =>
              m.id === activeId
                ? {
                    ...m,
                    content: content || m.content,
                    isStreaming: false,
                    createdAt: Date.now(),
                    ...(ev.buttons && ev.buttons.length > 0 ? { buttons: ev.buttons } : {}),
                    ...(media && media.length > 0 ? { media } : {}),
                  }
                : m
            );
          }
          
          return [
            ...prev,
            {
              id: crypto.randomUUID(),
              role: "assistant",
              content,
              createdAt: Date.now(),
              ...(ev.buttons && ev.buttons.length > 0 ? { buttons: ev.buttons } : {}),
              ...(media && media.length > 0 ? { media } : {}),
            },
          ];
        });
        
        buffer.current = null;
        return;
      }
    };

    const unsub = client.onChat(chatId, handle);
    return () => {
      unsub();
      buffer.current = null;
    };
  }, [chatId, client, messages.length]);

  const send = useCallback(
    (content: string, images?: SendImage[], thinkingLevel?: string) => {
      if (!chatId) return;
      const hasImages = !!images && images.length > 0;
      if (!hasImages && !content.trim()) return;

      const previews = hasImages ? images!.map((i) => i.preview) : undefined;
      setMessages((prev) => [
        ...prev,
        {
          id: crypto.randomUUID(),
          role: "user",
          content,
          createdAt: Date.now(),
          ...(previews ? { images: previews } : {}),
        },
      ]);
      setIsStreaming(true);
      const wireMedia = hasImages ? images!.map((i) => i.media) : undefined;
      client.sendMessage(chatId, content, wireMedia, { type: "message_options", thinking_level: thinkingLevel });
    },
    [chatId, client],
  );

  const sendApprovalResponse = useCallback(
    (approved: boolean, alwaysAllow?: boolean) => {
      if (!chatId || !pendingApproval) return;
      client.sendMessage(chatId, "", undefined, {
        type: "approval_response",
        tool_call_id: pendingApproval.toolCallId,
        approved,
        always_allow: alwaysAllow,
      });
      setPendingApproval(null);
    },
    [chatId, client, pendingApproval],
  );

  return {
    messages,
    isStreaming,
    thinking,
    send,
    setMessages,
    streamError,
    dismissStreamError,
    pendingApproval,
    sendApprovalResponse,
    pendingQuestion,
    answerQuestion,
  };
}
