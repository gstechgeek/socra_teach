import React, { type FormEvent, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import { type Message } from "../hooks/useChat";

// Phase 6: replace react-markdown with Streamdown (by Vercel) for
// native streaming markdown + KaTeX + Shiki code highlighting.

interface MessageBubbleProps {
  message: Message;
}

const MessageBubble = React.memo(function MessageBubble({
  message,
}: MessageBubbleProps) {
  return (
    <div
      style={{
        marginBottom: "1rem",
        textAlign: message.role === "user" ? "right" : "left",
      }}
    >
      <div
        style={{
          display: "inline-block",
          maxWidth: "80%",
          padding: "0.6rem 0.9rem",
          borderRadius: 8,
          background: message.role === "user" ? "#2563eb" : "#1e2030",
          color: "#e8eaf0",
          fontSize: "0.9rem",
          lineHeight: 1.6,
        }}
      >
        <ReactMarkdown
          remarkPlugins={[remarkMath]}
          rehypePlugins={[rehypeKatex]}
        >
          {message.content}
        </ReactMarkdown>
      </div>
    </div>
  );
});

interface ChatProps {
  messages: Message[];
  isStreaming: boolean;
  onSend: (text: string) => void;
}

export function Chat({ messages, isStreaming, onSend }: ChatProps) {
  const [input, setInput] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    const trimmed = input.trim();
    if (!trimmed || isStreaming) return;
    setInput("");
    onSend(trimmed);
    setTimeout(
      () => bottomRef.current?.scrollIntoView({ behavior: "smooth" }),
      50,
    );
  };

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        height: "100%",
        padding: "1rem",
      }}
    >
      {/* Message list */}
      <div style={{ flex: 1, overflowY: "auto", marginBottom: "1rem" }}>
        {messages.length === 0 && (
          <p
            style={{
              color: "#666",
              textAlign: "center",
              marginTop: "2rem",
            }}
          >
            Ask a question to start the Socratic session.
          </p>
        )}
        {messages.map((msg) => (
          <MessageBubble key={msg.id} message={msg} />
        ))}
        {isStreaming && (
          <span style={{ color: "#555", fontSize: "0.8rem" }}>Thinking…</span>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input bar */}
      <form onSubmit={handleSubmit} style={{ display: "flex", gap: "0.5rem" }}>
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Type your answer or question…"
          disabled={isStreaming}
          style={{
            flex: 1,
            padding: "0.6rem 0.8rem",
            borderRadius: 6,
            border: "1px solid #333",
            background: "#1a1d27",
            color: "#e8eaf0",
            fontSize: "0.9rem",
          }}
        />
        <button
          type="submit"
          disabled={isStreaming || !input.trim()}
          style={{
            padding: "0.6rem 1.2rem",
            borderRadius: 6,
            border: "none",
            background: isStreaming ? "#333" : "#2563eb",
            color: "#fff",
            cursor: isStreaming ? "not-allowed" : "pointer",
          }}
        >
          Send
        </button>
      </form>
    </div>
  );
}
