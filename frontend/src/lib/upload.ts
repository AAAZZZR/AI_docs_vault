const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

export interface UploadProgress {
  phase: "uploading" | "processing" | "ready" | "error";
  progress: number; // 0-100
  detail: string;
  documentId?: string;
}

export async function uploadPDF(
  file: File,
  onProgress: (progress: UploadProgress) => void,
): Promise<string> {
  onProgress({
    phase: "uploading",
    progress: 10,
    detail: "Uploading PDF...",
  });

  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch(`${API_BASE}/documents/upload`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || `Upload failed: ${response.status}`);
  }

  const { document_id } = await response.json();

  onProgress({
    phase: "processing",
    progress: 30,
    detail: "Analyzing document...",
    documentId: document_id,
  });

  // Listen for status updates via SSE
  return new Promise<string>((resolve, reject) => {
    const timeout = setTimeout(() => {
      eventSource.close();
      // Resolve anyway — processing continues in background
      resolve(document_id);
    }, 120_000); // 2 min timeout

    const eventSource = new EventSource(
      `${API_BASE}/documents/status-stream`,
    );

    eventSource.addEventListener("status_update", (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.document_id !== document_id) return;

        if (data.status === "processing") {
          onProgress({
            phase: "processing",
            progress: Math.min(90, 30 + Math.random() * 50),
            detail: data.detail || "Processing...",
            documentId: document_id,
          });
        } else if (data.status === "ready") {
          clearTimeout(timeout);
          eventSource.close();
          onProgress({
            phase: "ready",
            progress: 100,
            detail: "Document ready!",
            documentId: document_id,
          });
          resolve(document_id);
        } else if (data.status === "error") {
          clearTimeout(timeout);
          eventSource.close();
          onProgress({
            phase: "error",
            progress: 0,
            detail: data.detail || "Processing failed",
            documentId: document_id,
          });
          reject(new Error(data.detail || "Processing failed"));
        }
      } catch {
        // Ignore parse errors
      }
    });

    eventSource.onerror = () => {
      // SSE disconnected — resolve anyway, user can refresh
      clearTimeout(timeout);
      eventSource.close();
      resolve(document_id);
    };
  });
}
