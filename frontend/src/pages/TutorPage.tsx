import { Chat } from "../components/Chat";
import type { SelectionAttachment, UseChatReturn } from "../hooks/useChat";

interface TutorPageProps {
  chat: UseChatReturn;
  onCitationClick?: (page: number) => void;
  pendingSelection?: SelectionAttachment | null;
  onClearSelection?: () => void;
}

/**
 * TutorPage composes the chat interface with session state management.
 * Receives chat state from App (lifted for citation bridging to PdfViewer).
 */
export function TutorPage({ chat, onCitationClick, pendingSelection, onClearSelection }: TutorPageProps) {
  const { messages, isStreaming, streamError, metadata, sources, send } = chat;

  return (
    <div style={{ height: "100%", display: "flex", flexDirection: "column" }}>
      <header
        style={{
          padding: "0.75rem 1rem",
          borderBottom: "1px solid #1e2030",
          fontSize: "0.85rem",
          color: "#7c84a0",
          display: "flex",
          alignItems: "center",
          gap: "0.5rem",
        }}
      >
        <span>Socratic AI Tutor</span>
        {metadata && (
          <span
            style={{
              padding: "0.15rem 0.5rem",
              borderRadius: 4,
              fontSize: "0.7rem",
              fontWeight: 500,
              background: "#2e1a4d",
              color: "#c4b5fd",
            }}
          >
            {metadata.model}
          </span>
        )}
      </header>

      {streamError && (
        <div
          style={{
            padding: "0.4rem 1rem",
            fontSize: "0.78rem",
            color: "#f59e0b",
            background: "#3b2f11",
            borderBottom: "1px solid #1e2030",
          }}
        >
          {streamError}
        </div>
      )}

      {sources.length > 0 && (
        <div
          style={{
            padding: "0.35rem 1rem",
            display: "flex",
            gap: "0.4rem",
            flexWrap: "wrap",
            borderBottom: "1px solid #1e2030",
            background: "#0f1119",
          }}
        >
          {sources.map((s) => (
            <button
              key={`${s.doc_id}-${s.page}`}
              onClick={() => onCitationClick?.(s.page)}
              style={{
                padding: "0.15rem 0.5rem",
                borderRadius: 4,
                border: "1px solid #2563eb44",
                background: "#1a1d2e",
                color: "#93a3c0",
                fontSize: "0.7rem",
                cursor: "pointer",
                transition: "background 0.15s",
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = "#252a3e";
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = "#1a1d2e";
              }}
            >
              p.{s.page} — {s.section}
            </button>
          ))}
        </div>
      )}

      <div style={{ flex: 1, overflow: "hidden" }}>
        <Chat
          messages={messages}
          isStreaming={isStreaming}
          onSend={send}
          onCitationClick={onCitationClick}
          pendingSelection={pendingSelection}
          onClearSelection={onClearSelection}
        />
      </div>
    </div>
  );
}
