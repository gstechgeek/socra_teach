import React, { type FormEvent, type KeyboardEvent, type ReactNode, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import { type Message, type SelectionAttachment } from "../hooks/useChat";

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
        display: "flex",
        justifyContent: "flex-start",
      }}
    >
      <div
        style={{
          maxWidth: "80%",
          padding: "0.6rem 0.9rem",
          borderRadius: 8,
          background: message.role === "user" ? "#2563eb" : "#1e2030",
          color: "#e8eaf0",
          fontSize: "0.9rem",
          lineHeight: 1.6,
          textAlign: "left",
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
  onSend: (text: string, attachment?: SelectionAttachment) => void;
  onCitationClick?: (page: number) => void;
  /** Pending selection from the PDF viewer. */
  pendingSelection?: SelectionAttachment | null;
  /** Clear the pending selection. */
  onClearSelection?: () => void;
}

export function Chat({
  messages,
  isStreaming,
  onSend,
  onCitationClick,
  pendingSelection,
  onClearSelection,
}: ChatProps) {
  const [input, setInput] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-resize textarea to fit content
  React.useEffect(() => {
    const ta = textareaRef.current;
    if (!ta) return;
    ta.style.height = "auto";
    ta.style.height = `${Math.min(ta.scrollHeight, 96)}px`;
    ta.style.overflow = ta.scrollHeight > 96 ? "auto" : "hidden";
  }, [input]);

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    // Enter submits, Shift+Enter inserts a newline
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  const handleSubmit = (e: FormEvent | KeyboardEvent) => {
    e.preventDefault();
    const trimmed = input.trim();
    if (!trimmed || isStreaming) return;
    setInput("");
    onSend(trimmed, pendingSelection ?? undefined);
    onClearSelection?.();
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

      {/* Selection preview */}
      {pendingSelection && (
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "0.5rem",
            padding: "0.4rem 0.6rem",
            marginBottom: "0.4rem",
            background: "#1a1d2e",
            borderRadius: 6,
            border: "1px solid #2563eb44",
          }}
        >
          <img
            src={`data:image/png;base64,${pendingSelection.imageBase64}`}
            alt="PDF selection"
            style={{
              maxWidth: 80,
              maxHeight: 48,
              borderRadius: 4,
              border: "1px solid #333",
            }}
          />
          <span style={{ fontSize: "0.75rem", color: "#93a3c0", flex: 1 }}>
            Selection{pendingSelection.page ? ` from p.${pendingSelection.page}` : ""}
          </span>
          <button
            type="button"
            onClick={onClearSelection}
            style={{
              background: "none",
              border: "none",
              color: "#7c84a0",
              cursor: "pointer",
              fontSize: "0.85rem",
              padding: "0.1rem 0.3rem",
            }}
          >
            ✕
          </button>
        </div>
      )}

      {/* Input bar */}
      <form onSubmit={handleSubmit} style={{ display: "flex", gap: "0.5rem", alignItems: "flex-end" }}>
        <textarea
          ref={textareaRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Type your answer or question…"
          disabled={isStreaming}
          rows={1}
          style={{
            flex: 1,
            padding: "0.6rem 0.8rem",
            borderRadius: 6,
            border: "1px solid #333",
            background: "#1a1d27",
            color: "#e8eaf0",
            fontSize: "0.9rem",
            resize: "none",
            overflow: "hidden",
            lineHeight: 1.5,
            maxHeight: "6rem",
            fontFamily: "inherit",
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
