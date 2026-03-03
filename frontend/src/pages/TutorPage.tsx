import { Chat } from "../components/Chat";
import { useChat } from "../hooks/useChat";

/**
 * TutorPage composes the chat interface with session state management.
 * Phase 4: will also wire the PdfViewer text-selection callback to
 * prepend selected text as context into the next chat message.
 */
export function TutorPage() {
  const { messages, isStreaming, streamError, metadata, send } = useChat();

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

      <div style={{ flex: 1, overflow: "hidden" }}>
        <Chat messages={messages} isStreaming={isStreaming} onSend={send} />
      </div>
    </div>
  );
}
