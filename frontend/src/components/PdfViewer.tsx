import { useCallback, useEffect, useRef } from "react";
import { SpecialZoomLevel, Viewer, Worker } from "@react-pdf-viewer/core";
import { defaultLayoutPlugin } from "@react-pdf-viewer/default-layout";
import { useRectSelect } from "../hooks/useRectSelect";

import "@react-pdf-viewer/core/lib/styles/index.css";
import "@react-pdf-viewer/default-layout/lib/styles/index.css";

// pdfjs worker — must match the installed pdfjs-dist version
const WORKER_URL =
  "https://unpkg.com/pdfjs-dist@3.11.174/build/pdf.worker.min.js";

/** Minimum rectangle size (px) to be considered a valid selection. */
const MIN_RECT_SIZE = 20;

export interface PdfSelection {
  /** Base64 PNG of the captured rectangle. */
  imageBase64: string;
  /** 1-indexed page number where the selection was made (best-effort). */
  page: number | null;
}

interface PdfViewerProps {
  fileUrl: string | null;
  targetPage?: number; // 0-indexed page to jump to
  onSelectionCapture?: (selection: PdfSelection) => void;
}

/**
 * PDF viewer powered by @react-pdf-viewer/core.
 *
 * Renders the uploaded PDF immediately (before ingestion completes) so the
 * user can read while background processing runs. Uses the default-layout
 * plugin for sidebar navigation (thumbnails, bookmarks, search).
 *
 * When `targetPage` changes, the viewer jumps to that page.
 *
 * In selection mode, the user can draw a rectangle over any area (text or
 * diagram) which is captured as a PNG and forwarded to the chat.
 */
export function PdfViewer({ fileUrl, targetPage, onSelectionCapture }: PdfViewerProps) {
  // Called at top level — defaultLayoutPlugin() uses hooks internally
  const pluginInstance = defaultLayoutPlugin();
  const viewerContainerRef = useRef<HTMLDivElement>(null);
  const { isSelecting, toggleSelecting, rect, clearRect, onMouseDown, onMouseMove, onMouseUp } =
    useRectSelect();

  // Jump to page when targetPage changes
  useEffect(() => {
    if (targetPage === undefined || targetPage < 0 || !pluginInstance) return;
    const nav = pluginInstance.toolbarPluginInstance.pageNavigationPluginInstance;
    nav.jumpToPage(targetPage);
  }, [targetPage, pluginInstance]);

  /**
   * Capture the pixels within the current rectangle selection.
   *
   * Finds all visible PDF page canvases, determines which ones overlap the
   * selection rectangle, composites the overlapping regions onto an offscreen
   * canvas, and returns a base64 PNG.
   */
  const captureSelection = useCallback(() => {
    if (!rect || rect.width < MIN_RECT_SIZE || rect.height < MIN_RECT_SIZE) return;
    const container = viewerContainerRef.current;
    if (!container) return;

    const overlay = container.querySelector("[data-rect-overlay]") as HTMLElement | null;
    if (!overlay) return;
    const overlayBounds = overlay.getBoundingClientRect();

    // Absolute rect position in viewport coordinates
    const selLeft = overlayBounds.left + rect.x;
    const selTop = overlayBounds.top + rect.y;
    const selRight = selLeft + rect.width;
    const selBottom = selTop + rect.height;

    // Find all page canvases rendered by react-pdf-viewer.
    // Try the specific class first, then fall back to any canvas in the viewer.
    let canvases = container.querySelectorAll<HTMLCanvasElement>(
      ".rpv-core__canvas-layer canvas",
    );
    if (canvases.length === 0) {
      canvases = container.querySelectorAll<HTMLCanvasElement>("canvas");
    }
    if (canvases.length === 0) return;

    // Create offscreen canvas for compositing
    const dpr = window.devicePixelRatio || 1;
    const outW = Math.round(rect.width * dpr);
    const outH = Math.round(rect.height * dpr);
    const offscreen = document.createElement("canvas");
    offscreen.width = outW;
    offscreen.height = outH;
    const ctx = offscreen.getContext("2d");
    if (!ctx) return;

    let capturedPage: number | null = null;

    canvases.forEach((canvas) => {
      const cb = canvas.getBoundingClientRect();
      // Check overlap
      if (cb.right < selLeft || cb.left > selRight || cb.bottom < selTop || cb.top > selBottom) {
        return;
      }

      // Determine the page number from the DOM hierarchy
      if (capturedPage === null) {
        const pageContainer = canvas.closest("[data-testid]");
        if (pageContainer) {
          const testId = pageContainer.getAttribute("data-testid") ?? "";
          const match = /core__page-layer-(\d+)/.exec(testId);
          if (match?.[1]) {
            capturedPage = parseInt(match[1], 10) + 1; // convert 0-indexed to 1-indexed
          }
        }
      }

      // Source coordinates on the canvas (accounting for canvas internal resolution)
      const scaleX = canvas.width / cb.width;
      const scaleY = canvas.height / cb.height;

      const srcX = Math.max(0, (selLeft - cb.left) * scaleX);
      const srcY = Math.max(0, (selTop - cb.top) * scaleY);
      const srcRight = Math.min(canvas.width, (selRight - cb.left) * scaleX);
      const srcBottom = Math.min(canvas.height, (selBottom - cb.top) * scaleY);
      const srcW = srcRight - srcX;
      const srcH = srcBottom - srcY;

      // Destination coordinates on the output canvas
      const dstX = Math.max(0, (cb.left - selLeft) * dpr);
      const dstY = Math.max(0, (cb.top - selTop) * dpr);
      const dstW = srcW * (cb.width / canvas.width) * dpr;
      const dstH = srcH * (cb.height / canvas.height) * dpr;

      ctx.drawImage(canvas, srcX, srcY, srcW, srcH, dstX, dstY, dstW, dstH);
    });

    const dataUrl = offscreen.toDataURL("image/png");
    // Strip the data:image/png;base64, prefix
    const base64 = dataUrl.replace(/^data:image\/png;base64,/, "");

    onSelectionCapture?.({ imageBase64: base64, page: capturedPage });
    clearRect();
    toggleSelecting();
  }, [rect, clearRect, toggleSelecting, onSelectionCapture]);

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

  const hasValidRect = rect !== null && rect.width >= MIN_RECT_SIZE && rect.height >= MIN_RECT_SIZE;

  return (
    <div
      ref={viewerContainerRef}
      style={{ height: "100%", position: "relative" }}
    >
      {/* Selection mode toggle */}
      <button
        onClick={toggleSelecting}
        title={isSelecting ? "Cancel selection" : "Select area from PDF"}
        style={{
          position: "absolute",
          top: 8,
          right: 8,
          zIndex: 20,
          padding: "0.35rem 0.6rem",
          borderRadius: 6,
          border: isSelecting ? "1px solid #2563eb" : "1px solid #333",
          background: isSelecting ? "#2563eb33" : "#1a1d27",
          color: isSelecting ? "#93bbfd" : "#7c84a0",
          fontSize: "0.75rem",
          cursor: "pointer",
          display: "flex",
          alignItems: "center",
          gap: "0.3rem",
          transition: "background 0.15s, border-color 0.15s",
        }}
      >
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <rect x="3" y="3" width="18" height="18" rx="2" strokeDasharray="4 2" />
          <line x1="9" y1="3" x2="9" y2="21" opacity="0.3" />
          <line x1="15" y1="3" x2="15" y2="21" opacity="0.3" />
        </svg>
        {isSelecting ? "Cancel" : "Select"}
      </button>

      {/* Selection overlay — captures mouse events when in selection mode */}
      {isSelecting && (
        <div
          data-rect-overlay
          onMouseDown={onMouseDown}
          onMouseMove={onMouseMove}
          onMouseUp={onMouseUp}
          style={{
            position: "absolute",
            inset: 0,
            zIndex: 10,
            cursor: "crosshair",
            background: "transparent",
          }}
        >
          {/* The drawn rectangle */}
          {rect && rect.width > 0 && rect.height > 0 && (
            <div
              style={{
                position: "absolute",
                left: rect.x,
                top: rect.y,
                width: rect.width,
                height: rect.height,
                border: "2px solid #2563eb",
                background: "rgba(37, 99, 235, 0.12)",
                borderRadius: 2,
                pointerEvents: "none",
              }}
            />
          )}

          {/* Capture button appears after drawing a valid rectangle */}
          {hasValidRect && (
            <button
              onMouseDown={(e) => e.stopPropagation()}
              onClick={(e) => {
                e.stopPropagation();
                captureSelection();
              }}
              style={{
                position: "absolute",
                left: rect.x + rect.width / 2,
                top: rect.y + rect.height + 8,
                transform: "translateX(-50%)",
                zIndex: 15,
                padding: "0.3rem 0.7rem",
                borderRadius: 5,
                border: "none",
                background: "#2563eb",
                color: "#fff",
                fontSize: "0.75rem",
                fontWeight: 500,
                cursor: "pointer",
                pointerEvents: "auto",
                whiteSpace: "nowrap",
              }}
            >
              Use as context
            </button>
          )}
        </div>
      )}

      {/* PDF viewer */}
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
          <Viewer fileUrl={fileUrl} defaultScale={SpecialZoomLevel.PageFit} plugins={[pluginInstance]} />
        </Worker>
      </div>
    </div>
  );
}
