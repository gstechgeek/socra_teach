import { useCallback, useRef, useState } from "react";
import { fetchEventSource } from "@microsoft/fetch-event-source";

export interface Message {
  role: "user" | "assistant";
  content: string;
}

interface UseChatReturn {
  messages: Message[];
  isStreaming: boolean;
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
  const abortRef = useRef<AbortController | null>(null);

  const send = useCallback(
    async (text: string) => {
      if (isStreaming) return;

      const userMessage: Message = { role: "user", content: text };
      const nextMessages: Message[] = [
        ...messages,
        userMessage,
        { role: "assistant", content: "" },
      ];
      setMessages(nextMessages);
      setIsStreaming(true);

      const ctrl = new AbortController();
      abortRef.current = ctrl;

      try {
        await fetchEventSource("/api/chat/stream", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            messages: nextMessages.slice(0, -1), // exclude empty assistant stub
            session_id: sessionId ?? null,
          }),
          signal: ctrl.signal,

          onmessage(event) {
            if (event.event === "done") {
              setIsStreaming(false);
              return;
            }
            const { content } = JSON.parse(event.data) as { content: string };
            setMessages((prev) => {
              const updated = [...prev];
              const last = updated[updated.length - 1];
              if (last && last.role === "assistant") {
                updated[updated.length - 1] = {
                  ...last,
                  content: last.content + content,
                };
              }
              return updated;
            });
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
    [isStreaming, messages, sessionId],
  );

  const reset = useCallback(() => {
    abortRef.current?.abort();
    setMessages([]);
    setIsStreaming(false);
  }, []);

  return { messages, isStreaming, send, reset };
}
