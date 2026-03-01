import { Chat } from "../components/Chat";
import { useChat } from "../hooks/useChat";

/**
 * TutorPage composes the chat interface with session state management.
 * Phase 4: will also wire the PdfViewer text-selection callback to
 * prepend selected text as context into the next chat message.
 */
export function TutorPage() {
  const { messages, isStreaming, send } = useChat();

  return (
    <div style={{ height: "100%", display: "flex", flexDirection: "column" }}>
      <header
        style={{
          padding: "0.75rem 1rem",
          borderBottom: "1px solid #1e2030",
          fontSize: "0.85rem",
          color: "#7c84a0",
        }}
      >
        Socratic AI Tutor — local inference via llama.cpp (Vulkan)
      </header>

      <div style={{ flex: 1, overflow: "hidden" }}>
        <Chat messages={messages} isStreaming={isStreaming} onSend={send} />
      </div>
    </div>
  );
}
