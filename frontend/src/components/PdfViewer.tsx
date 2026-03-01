// Phase 4: implement with @react-pdf-viewer/core + highlightPlugin()
// When a user selects text, pass the selection to the RAG pipeline
// via the onTextSelect callback, which routes to retrieve() → socratic engine.

interface PdfViewerProps {
  fileUrl: string;
  onTextSelect?: (selectedText: string) => void;
}

export function PdfViewer({ fileUrl: _fileUrl, onTextSelect: _onTextSelect }: PdfViewerProps) {
  return (
    <div
      style={{
        height: "100%",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: "#13151f",
        color: "#444",
        fontSize: "0.85rem",
      }}
    >
      PDF viewer — Phase 4
      <br />
      <code style={{ fontSize: "0.75rem" }}>@react-pdf-viewer/core + highlightPlugin()</code>
    </div>
  );
}
