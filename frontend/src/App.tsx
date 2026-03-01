import { Panel, PanelGroup, PanelResizeHandle } from "react-resizable-panels";
import { TutorPage } from "./pages/TutorPage";

// App sets up the split-pane shell.
// Phase 4: PdfViewer will occupy the left panel.
// The chat interface lives in the right panel from Phase 1 onward.
export default function App() {
  return (
    <PanelGroup direction="horizontal" style={{ height: "100vh" }}>
      {/* Left pane — PDF viewer (Phase 4) */}
      <Panel defaultSize={45} minSize={20} style={{ overflow: "hidden" }}>
        <div
          style={{
            height: "100%",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            color: "#555",
            fontSize: "0.875rem",
          }}
        >
          PDF viewer — Phase 4
        </div>
      </Panel>

      <PanelResizeHandle
        style={{ width: 4, background: "#2a2d3a", cursor: "col-resize" }}
      />

      {/* Right pane — Socratic chat */}
      <Panel defaultSize={55} minSize={30} style={{ overflow: "hidden" }}>
        <TutorPage />
      </Panel>
    </PanelGroup>
  );
}
