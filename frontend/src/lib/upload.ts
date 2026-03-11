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

  const { document_id, status } = await response.json();

  onProgress({
    phase: "processing",
    progress: 60,
    detail: "Analyzing document...",
    documentId: document_id,
  });

  return document_id;
}
