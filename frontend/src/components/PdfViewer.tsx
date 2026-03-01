import { Viewer, Worker } from "@react-pdf-viewer/core";
import { defaultLayoutPlugin } from "@react-pdf-viewer/default-layout";

import "@react-pdf-viewer/core/lib/styles/index.css";
import "@react-pdf-viewer/default-layout/lib/styles/index.css";

// pdfjs worker — must match the installed pdfjs-dist version
const WORKER_URL =
  "https://unpkg.com/pdfjs-dist@3.11.174/build/pdf.worker.min.js";

interface PdfViewerProps {
  fileUrl: string | null;
  onTextSelect?: (selectedText: string) => void;
}

/**
 * PDF viewer powered by @react-pdf-viewer/core.
 *
 * Renders the uploaded PDF immediately (before ingestion completes) so the
 * user can read while background processing runs. Uses the default-layout
 * plugin for sidebar navigation (thumbnails, bookmarks, search).
 */
export function PdfViewer({ fileUrl, onTextSelect: _onTextSelect }: PdfViewerProps) {
  const defaultLayoutPluginInstance = defaultLayoutPlugin();

  if (!fileUrl) {
    return (
      <div
        style={{
          height: "100%",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          background: "#13151f",
          color: "#555",
          fontSize: "0.85rem",
          gap: "0.75rem",
        }}
      >
        <span style={{ fontSize: "2rem", opacity: 0.3 }}>📄</span>
        <span>Select a textbook to start reading</span>
      </div>
    );
  }

  return (
    <div
      className="rpv-dark-theme"
      style={{
        height: "100%",
        background: "#13151f",
        /* Dark theme overrides for react-pdf-viewer */
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        ["--rpv-color-primary" as any]: "#2563eb",
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        ["--rpv-color-primary-dark" as any]: "#1d4ed8",
      }}
    >
      <Worker workerUrl={WORKER_URL}>
        <Viewer fileUrl={fileUrl} plugins={[defaultLayoutPluginInstance]} />
      </Worker>
    </div>
  );
}
