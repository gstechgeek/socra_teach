import React, { type FormEvent, type ReactNode, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import { type Message } from "../hooks/useChat";

// Phase 6: replace react-markdown with Streamdown (by Vercel) for
// native streaming markdown + KaTeX + Shiki code highlighting.

const CITATION_RE = /\[p\.\s*(\d+)\]/g;

/** Split text into segments of plain text and citation badges. */
function parseCitations(
  text: string,
  onCitationClick?: (page: number) => void,
): ReactNode[] {
  const parts: ReactNode[] = [];
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  CITATION_RE.lastIndex = 0;
  while ((match = CITATION_RE.exec(text)) !== null) {
    if (match.index > lastIndex) {
      parts.push(text.slice(lastIndex, match.index));
    }
    const page = parseInt(match[1] ?? "0", 10);
    parts.push(
      <button
        key={`cite-${match.index}`}
        onClick={() => onCitationClick?.(page)}
        style={{
          display: "inline",
          padding: "0.05rem 0.35rem",
          borderRadius: 3,
          border: "none",
          background: "#2563eb33",
          color: "#93bbfd",
          fontSize: "0.78em",
          cursor: onCitationClick ? "pointer" : "default",
          fontFamily: "inherit",
          verticalAlign: "baseline",
        }}
      >
        p.{page}
      </button>,
    );
    lastIndex = match.index + match[0].length;
  }

  if (lastIndex < text.length) {
    parts.push(text.slice(lastIndex));
  }
  return parts;
}

interface MessageBubbleProps {
  message: Message;
  onCitationClick?: (page: number) => void;
}

const MessageBubble = React.memo(function MessageBubble({
  message,
  onCitationClick,
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
          components={{
            p: ({ children }) => {
              const processed = React.Children.map(children, (child) => {
                if (typeof child === "string" && CITATION_RE.test(child)) {
                  return <>{parseCitations(child, onCitationClick)}</>;
                }
                return child;
              });
              return <p>{processed}</p>;
            },
          }}
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
  onCitationClick?: (page: number) => void;
}

export function Chat({ messages, isStreaming, onSend, onCitationClick }: ChatProps) {
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
          <MessageBubble key={msg.id} message={msg} onCitationClick={onCitationClick} />
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
