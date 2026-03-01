import { useRef, useState } from "react";
import { type DocumentRecord, useDocuments } from "../hooks/useDocuments";

function statusColor(status: DocumentRecord["status"]): string {
  if (status === "done") return "#22c55e";
  if (status === "error") return "#ef4444";
  return "#2563eb"; // queued | processing
}

function statusLabel(status: DocumentRecord["status"]): string {
  if (status === "done") return "✓ done";
  if (status === "error") return "✗ error";
  if (status === "processing") return "● processing";
  return "● queued";
}

interface DocumentsPageProps {
  onSelectDocument?: (docId: string) => void;
}

/**
 * DocumentsPage — upload textbook PDFs and view ingestion status.
 *
 * Supports drag-and-drop and click-to-browse. Shows a live status table
 * that polls the backend every 2 s until each upload is fully ingested.
 * Clicking a document row calls onSelectDocument to open it in the PDF viewer.
 */
export function DocumentsPage({ onSelectDocument }: DocumentsPageProps) {
  const { documents, isUploading, upload, deleteDocument } = useDocuments();
  const [isDragging, setIsDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  async function handleFiles(files: FileList | null) {
    if (!files || files.length === 0) return;
    const file = files[0];
    if (!file) return;
    const docId = await upload(file);
    if (docId && onSelectDocument) {
      onSelectDocument(docId);
    }
  }

  return (
    <div
      style={{
        height: "100%",
        display: "flex",
        flexDirection: "column",
        background: "#0f1117",
        color: "#e8eaf0",
      }}
    >
      {/* Header */}
      <header
        style={{
          padding: "0.75rem 1.25rem",
          borderBottom: "1px solid #1e2030",
          fontSize: "0.85rem",
          color: "#7c84a0",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
        }}
      >
        <span>Textbooks — upload PDFs to ground Socratic responses</span>
      </header>

      {/* Content */}
      <div style={{ flex: 1, overflowY: "auto", padding: "1.25rem" }}>
        {/* Drop zone */}
        <div
          onClick={() => inputRef.current?.click()}
          onDragOver={(e) => {
            e.preventDefault();
            setIsDragging(true);
          }}
          onDragLeave={() => setIsDragging(false)}
          onDrop={(e) => {
            e.preventDefault();
            setIsDragging(false);
            handleFiles(e.dataTransfer.files);
          }}
          style={{
            height: 160,
            border: isDragging ? "2px dashed #2563eb" : "2px dashed #2a2d3a",
            borderRadius: 8,
            background: isDragging ? "#0d1626" : "transparent",
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            gap: "0.5rem",
            cursor: isUploading ? "not-allowed" : "pointer",
            opacity: isUploading ? 0.5 : 1,
            pointerEvents: isUploading ? "none" : "auto",
            transition: "border-color 0.15s, background 0.15s",
            marginBottom: "1.5rem",
            userSelect: "none",
          }}
        >
          <span style={{ fontSize: "1.75rem", color: "#2a2d3a" }}>↑</span>
          <span style={{ fontSize: "0.875rem", color: "#7c84a0" }}>
            {isUploading ? "Uploading…" : "Drop a PDF here, or click to browse"}
          </span>
          <span style={{ fontSize: "0.75rem", color: "#555" }}>PDF, DOCX</span>
        </div>

        {/* Hidden file input */}
        <input
          ref={inputRef}
          type="file"
          accept=".pdf,.docx"
          style={{ display: "none" }}
          onChange={(e) => handleFiles(e.target.files)}
        />

        {/* Document table */}
        {documents.length === 0 ? (
          <div
            style={{
              textAlign: "center",
              color: "#555",
              fontSize: "0.875rem",
              padding: "2rem 0",
            }}
          >
            No textbooks uploaded yet.
          </div>
        ) : (
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.875rem" }}>
            <thead>
              <tr
                style={{
                  borderBottom: "1px solid #1e2030",
                  color: "#7c84a0",
                  textAlign: "left",
                }}
              >
                <th style={{ padding: "0.5rem 0.75rem", fontWeight: 500 }}>Filename</th>
                <th style={{ padding: "0.5rem 0.75rem", fontWeight: 500 }}>Status</th>
                <th style={{ padding: "0.5rem 0.75rem", fontWeight: 500 }}>Chunks</th>
                <th style={{ padding: "0.5rem 0.75rem", fontWeight: 500, width: 40 }} />
              </tr>
            </thead>
            <tbody>
              {documents.map((doc) => (
                <tr
                  key={doc.doc_id}
                  onClick={() => {
                    if (doc.status !== "error" && onSelectDocument) {
                      onSelectDocument(doc.doc_id);
                    }
                  }}
                  style={{
                    borderBottom: "1px solid #1a1d27",
                    cursor: doc.status !== "error" ? "pointer" : "default",
                    transition: "background 0.12s",
                  }}
                  onMouseEnter={(e) => {
                    if (doc.status !== "error") {
                      (e.currentTarget as HTMLTableRowElement).style.background =
                        "#1a1d27";
                    }
                  }}
                  onMouseLeave={(e) => {
                    (e.currentTarget as HTMLTableRowElement).style.background = "";
                  }}
                >
                  <td
                    style={{
                      padding: "0.6rem 0.75rem",
                      color: "#e8eaf0",
                      maxWidth: 300,
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace: "nowrap",
                    }}
                    title={doc.filename}
                  >
                    {doc.filename}
                  </td>
                  <td style={{ padding: "0.6rem 0.75rem" }}>
                    <span style={{ color: statusColor(doc.status) }}>
                      {statusLabel(doc.status)}
                    </span>
                    {doc.status === "processing" && doc.error && (
                      <div
                        style={{
                          fontSize: "0.72rem",
                          color: "#7c84a0",
                          marginTop: "0.2rem",
                        }}
                      >
                        {doc.error}
                      </div>
                    )}
                    {doc.status === "error" && doc.error && (
                      <span
                        style={{
                          marginLeft: "0.5rem",
                          fontSize: "0.75rem",
                          color: "#7c84a0",
                        }}
                        title={doc.error}
                      >
                        (hover for detail)
                      </span>
                    )}
                  </td>
                  <td style={{ padding: "0.6rem 0.75rem", color: "#7c84a0" }}>
                    {doc.status === "done" ? `${doc.chunk_count} chunks` : "—"}
                  </td>
                  <td style={{ padding: "0.6rem 0.5rem", textAlign: "right" }}>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        void deleteDocument(doc.doc_id);
                      }}
                      title="Remove"
                      style={{
                        background: "none",
                        border: "none",
                        cursor: "pointer",
                        color: "#555",
                        fontSize: "0.85rem",
                        padding: "0.1rem 0.3rem",
                        lineHeight: 1,
                      }}
                      onMouseEnter={(e) => {
                        (e.currentTarget as HTMLButtonElement).style.color = "#ef4444";
                      }}
                      onMouseLeave={(e) => {
                        (e.currentTarget as HTMLButtonElement).style.color = "#555";
                      }}
                    >
                      ✕
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
