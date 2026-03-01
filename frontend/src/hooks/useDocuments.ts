import { useCallback, useEffect, useRef, useState } from "react";

export interface DocumentRecord {
  doc_id: string;
  filename: string;
  status: "queued" | "processing" | "done" | "error";
  chunk_count: number;
  error: string;
}

interface UseDocumentsReturn {
  documents: DocumentRecord[];
  isUploading: boolean;
  upload: (file: File) => Promise<string | null>;
  refresh: () => Promise<void>;
  deleteDocument: (doc_id: string) => Promise<void>;
}

/**
 * Manages the list of uploaded textbook documents.
 *
 * - Fetches the current list from GET /api/documents/ on mount.
 * - upload() posts a file, then polls status every 2 s until the
 *   document reaches a terminal state (done | error), then refreshes the list.
 */
export function useDocuments(): UseDocumentsReturn {
  const [documents, setDocuments] = useState<DocumentRecord[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const pollTimers = useRef<Map<string, ReturnType<typeof setInterval>>>(new Map());

  const refresh = useCallback(async () => {
    try {
      const res = await fetch("/api/documents/");
      if (!res.ok) return;
      const data = (await res.json()) as Array<{
        doc_id: string;
        filename: string;
        status: string;
        chunk_count?: number;
        error?: string;
      }>;
      setDocuments(
        data.map((d) => ({
          doc_id: d.doc_id,
          filename: d.filename,
          status: d.status as DocumentRecord["status"],
          chunk_count: d.chunk_count ?? 0,
          error: d.error ?? "",
        })),
      );
    } catch {
      // Network errors during refresh are silent — user sees stale data
    }
  }, []);

  // Load list on mount
  useEffect(() => {
    void refresh();
    return () => {
      // Clear any active polling timers on unmount
      for (const timer of pollTimers.current.values()) {
        clearInterval(timer);
      }
    };
  }, [refresh]);

  const startPolling = useCallback(
    (doc_id: string) => {
      const timer = setInterval(async () => {
        try {
          const res = await fetch(`/api/documents/${doc_id}/status`);
          if (!res.ok) return;
          const data = (await res.json()) as {
            status: string;
            chunk_count: string;
            error?: string;
          };
          const status = data.status as DocumentRecord["status"];

          // Update just this document in state
          setDocuments((prev) =>
            prev.map((d) =>
              d.doc_id === doc_id
                ? {
                    ...d,
                    status,
                    chunk_count: parseInt(data.chunk_count, 10) || 0,
                    error: data.error ?? "",
                  }
                : d,
            ),
          );

          // Stop polling once terminal
          if (status === "done" || status === "error") {
            clearInterval(timer);
            pollTimers.current.delete(doc_id);
            setIsUploading(false);
            await refresh();
          }
        } catch {
          // Transient network errors — keep polling
        }
      }, 2000);

      pollTimers.current.set(doc_id, timer);
    },
    [refresh],
  );

  const upload = useCallback(
    async (file: File): Promise<string | null> => {
      setIsUploading(true);

      const form = new FormData();
      form.append("file", file);

      try {
        const res = await fetch("/api/documents/upload", {
          method: "POST",
          body: form,
        });

        if (!res.ok) {
          setIsUploading(false);
          return null;
        }

        const data = (await res.json()) as { doc_id: string; status: string };

        // Optimistically add the doc to the list before polling confirms
        setDocuments((prev) => [
          ...prev,
          {
            doc_id: data.doc_id,
            filename: file.name,
            status: "queued",
            chunk_count: 0,
            error: "",
          },
        ]);

        startPolling(data.doc_id);
        return data.doc_id;
      } catch {
        setIsUploading(false);
        return null;
      }
    },
    [startPolling],
  );

  const deleteDocument = useCallback(async (doc_id: string) => {
    // Stop any active polling for this doc before deleting
    const timer = pollTimers.current.get(doc_id);
    if (timer !== undefined) {
      clearInterval(timer);
      pollTimers.current.delete(doc_id);
    }
    const res = await fetch(`/api/documents/${doc_id}`, { method: "DELETE" });
    if (res.ok || res.status === 404) {
      setDocuments((prev) => prev.filter((d) => d.doc_id !== doc_id));
    }
  }, []);

  return { documents, isUploading, upload, refresh, deleteDocument };
}
