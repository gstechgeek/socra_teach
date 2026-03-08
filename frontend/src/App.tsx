import { useState, useCallback } from "react";
import { Panel, PanelGroup, PanelResizeHandle } from "react-resizable-panels";
import { DocumentsPage } from "./pages/DocumentsPage";
import { PdfViewer } from "./components/PdfViewer";
import { ProgressPage } from "./pages/ProgressPage";
import { TutorPage } from "./pages/TutorPage";
import { useChat } from "./hooks/useChat";
import type { SelectionAttachment } from "./hooks/useChat";

type View = "tutor" | "documents" | "progress";

const NAV_HEIGHT = 40;

// App sets up the top nav and switches between the Tutor split-pane and
// the Documents management page. The left panel renders the PDF viewer.
// useChat is lifted here so citation clicks can bridge Chat → PdfViewer.
export default function App() {
  const [view, setView] = useState<View>("tutor");
  const [activeDocId, setActiveDocId] = useState<string | null>(null);
  const [targetPage, setTargetPage] = useState<number | undefined>(undefined);
  const [pendingSelection, setPendingSelection] = useState<SelectionAttachment | null>(null);

  const chat = useChat();

  const pdfUrl = activeDocId ? `/api/documents/${activeDocId}/file` : null;

  const handleSelectDocument = useCallback((docId: string) => {
    setActiveDocId(docId);
    setView("tutor");
  }, []);

  const handleCitationClick = useCallback((page: number) => {
    // Citations are 1-indexed; PDF viewer is 0-indexed
    setTargetPage(page - 1);
    setView("tutor");
  }, []);

  const handleSelectionCapture = useCallback(
    (sel: { imageBase64: string; page: number | null }) => {
      setPendingSelection({ imageBase64: sel.imageBase64, page: sel.page });
    },
    [],
  );

  const handleClearSelection = useCallback(() => {
    setPendingSelection(null);
  }, []);

  return (
    <div style={{ height: "100vh", display: "flex", flexDirection: "column" }}>
      {/* ── Navigation bar ───────────────────────────────────────────────── */}
      <nav
        style={{
          height: NAV_HEIGHT,
          minHeight: NAV_HEIGHT,
          display: "flex",
          alignItems: "center",
          padding: "0 1rem",
          background: "#0a0c14",
          borderBottom: "1px solid #1e2030",
          gap: "1.5rem",
        }}
      >
        <span
          style={{
            fontSize: "0.8rem",
            fontWeight: 600,
            color: "#7c84a0",
            letterSpacing: "0.04em",
            marginRight: "auto",
          }}
        >
          SOCRATIC AI TUTOR
        </span>

        {(["tutor", "documents", "progress"] as View[]).map((v) => (
          <button
            key={v}
            onClick={() => setView(v)}
            style={{
              background: "none",
              border: "none",
              cursor: "pointer",
              fontSize: "0.8rem",
              fontWeight: view === v ? 600 : 400,
              color: view === v ? "#e8eaf0" : "#7c84a0",
              padding: "0.25rem 0",
              borderBottom: view === v ? "2px solid #2563eb" : "2px solid transparent",
              transition: "color 0.15s, border-color 0.15s",
            }}
          >
            {v === "tutor" ? "Tutor" : v === "documents" ? "Textbooks" : "Progress"}
          </button>
        ))}
      </nav>

      {/* ── Content area — both views stay mounted; CSS hides the inactive one ── */}

      {/* Tutor — split-pane layout (wrapped in div to avoid display conflicts with PanelGroup) */}
      <div
        style={{
          flex: 1,
          display: view === "tutor" ? "flex" : "none",
          height: `calc(100vh - ${NAV_HEIGHT}px)`,
        }}
      >
        <PanelGroup direction="horizontal" style={{ flex: 1 }}>
          {/* Left pane — PDF viewer */}
          <Panel defaultSize={45} minSize={20} style={{ overflow: "hidden" }}>
            <PdfViewer fileUrl={pdfUrl} targetPage={targetPage} onSelectionCapture={handleSelectionCapture} />
          </Panel>

          <PanelResizeHandle
            style={{ width: 4, background: "#2a2d3a", cursor: "col-resize" }}
          />

          {/* Right pane — Socratic chat */}
          <Panel defaultSize={55} minSize={30} style={{ overflow: "hidden" }}>
            <TutorPage
              chat={chat}
              onCitationClick={handleCitationClick}
              pendingSelection={pendingSelection}
              onClearSelection={handleClearSelection}
            />
          </Panel>
        </PanelGroup>
      </div>

      {/* Textbooks — document management */}
      <div
        style={{
          flex: 1,
          overflow: "hidden",
          display: view === "documents" ? "flex" : "none",
        }}
      >
        <DocumentsPage onSelectDocument={handleSelectDocument} />
      </div>

      {/* Progress — review + dashboard */}
      <div
        style={{
          flex: 1,
          overflow: "hidden",
          display: view === "progress" ? "flex" : "none",
        }}
      >
        <ProgressPage />
      </div>
    </div>
  );
}
