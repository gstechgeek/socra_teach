import { useCallback, useEffect, useRef, useState } from "react";
import { fetchEventSource } from "@microsoft/fetch-event-source";

export interface Message {
  role: "user" | "assistant";
  content: string;
  id: string;
}

export interface StreamMetadata {
  tier: "local" | "dialogue" | "reasoning" | "fast";
  model: string;
}

interface UseChatReturn {
  messages: Message[];
  isStreaming: boolean;
  metadata: StreamMetadata | null;
  send: (text: string) => Promise<void>;
  reset: () => void;
}

/**
 * Manages chat state and SSE streaming from the FastAPI backend.
 *
 * Sends the full message history to /api/chat/stream and appends
 * streamed tokens to the last assistant message in real time.
 */
export function useChat(sessionId?: string): UseChatReturn {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [metadata, setMetadata] = useState<StreamMetadata | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const messagesRef = useRef<Message[]>([]);
  const lastSeqRef = useRef(-1);

  // Keep ref in sync with state so send() can read current messages
  // without including them in the useCallback dependency array.
  useEffect(() => {
    messagesRef.current = messages;
  }, [messages]);

  const send = useCallback(
    async (text: string) => {
      if (isStreaming) return;

      const userMessage: Message = {
        role: "user",
        content: text,
        id: crypto.randomUUID(),
      };
      const assistantStub: Message = {
        role: "assistant",
        content: "",
        id: crypto.randomUUID(),
      };
      const nextMessages: Message[] = [
        ...messagesRef.current,
        userMessage,
        assistantStub,
      ];
      setMessages(nextMessages);
      setIsStreaming(true);
      lastSeqRef.current = -1;

      const ctrl = new AbortController();
      abortRef.current = ctrl;

      try {
        await fetchEventSource("/api/chat/stream", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            messages: nextMessages.slice(0, -1).map((m) => ({
              role: m.role,
              content: m.content,
            })),
            session_id: sessionId ?? null,
          }),
          signal: ctrl.signal,
          openWhenHidden: true,

          onmessage(event) {
            if (event.event === "metadata") {
              const meta = JSON.parse(event.data) as StreamMetadata;
              setMetadata(meta);
              return;
            }
            if (event.event === "done") {
              setIsStreaming(false);
              lastSeqRef.current = -1;
              return;
            }
            const parsed = JSON.parse(event.data) as {
              content: string;
              seq: number;
            };
            if (parsed.seq <= lastSeqRef.current) return;
            lastSeqRef.current = parsed.seq;

            setMessages((prev) => {
              const updated = [...prev];
              const last = updated[updated.length - 1];
              if (last && last.role === "assistant") {
                updated[updated.length - 1] = {
                  ...last,
                  content: last.content + parsed.content,
                };
              }
              return updated;
            });
          },

          onclose() {
            setIsStreaming(false);
          },

          onerror(err) {
            console.error("SSE error", err);
            setIsStreaming(false);
          },
        });
      } finally {
        setIsStreaming(false);
      }
    },
    [isStreaming, sessionId],
  );

  const reset = useCallback(() => {
    abortRef.current?.abort();
    setMessages([]);
    setMetadata(null);
    setIsStreaming(false);
  }, []);

  return { messages, isStreaming, metadata, send, reset };
}
