const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

export async function apiFetch<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const headers: HeadersInit = { "Content-Type": "application/json" };
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      ...headers,
      ...options.headers,
    },
  });

  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new ApiError(
      response.status,
      body.detail || `Request failed: ${response.status}`,
    );
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json();
}

// Typed API methods
export const api = {
  // Documents
  listDocuments: (params?: {
    page?: number;
    page_size?: number;
    status?: string;
    tag_ids?: string[];
    search?: string;
  }) => {
    const searchParams = new URLSearchParams();
    if (params?.page) searchParams.set("page", String(params.page));
    if (params?.page_size) searchParams.set("page_size", String(params.page_size));
    if (params?.status) searchParams.set("status", params.status);
    if (params?.search) searchParams.set("search", params.search);
    params?.tag_ids?.forEach((id) => searchParams.append("tag_ids", id));
    const qs = searchParams.toString();
    return apiFetch<{
      documents: Document[];
      total: number;
      page: number;
      page_size: number;
    }>(`/documents${qs ? `?${qs}` : ""}`);
  },

  getDocument: (id: string) =>
    apiFetch<Document & { has_pdf?: boolean }>(
      `/documents/${id}`,
    ),

  downloadDocumentUrl: (id: string) =>
    `${API_BASE}/documents/${id}/download`,

  deleteDocument: (id: string) =>
    apiFetch<void>(`/documents/${id}`, { method: "DELETE" }),

  // Tags
  listTags: () => apiFetch<Tag[]>("/tags"),

  createTag: (data: { name: string; color?: string; description?: string; parent_id?: string }) =>
    apiFetch<Tag>("/tags", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  updateTag: (id: string, data: { name?: string; color?: string; description?: string; parent_id?: string }) =>
    apiFetch<Tag>(`/tags/${id}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),

  deleteTag: (id: string) =>
    apiFetch<void>(`/tags/${id}`, { method: "DELETE" }),

  addTagToDocument: (documentId: string, tagId: string) =>
    apiFetch<void>(`/tags/documents/${documentId}/tags/${tagId}`, {
      method: "POST",
    }),

  removeTagFromDocument: (documentId: string, tagId: string) =>
    apiFetch<void>(`/tags/documents/${documentId}/tags/${tagId}`, {
      method: "DELETE",
    }),

  mergeTag: (sourceId: string, targetId: string) =>
    apiFetch<{ merged_into: string; deleted: string }>(
      `/tags/${sourceId}/merge?target_id=${targetId}`,
      { method: "POST" },
    ),

  // Evolution
  listPendingEvolutions: () =>
    apiFetch<EvolutionEntry[]>("/evolution/pending"),

  approveEvolution: (id: string) =>
    apiFetch<{ status: string }>(`/evolution/${id}/approve`, { method: "POST" }),

  rejectEvolution: (id: string) =>
    apiFetch<{ status: string }>(`/evolution/${id}/reject`, { method: "POST" }),

  triggerEvolution: () =>
    apiFetch<{ status: string }>("/evolution/run", { method: "POST" }),

  // Chat
  getMessages: (limit?: number) =>
    apiFetch<ChatMessage[]>(
      `/chat/messages${limit ? `?limit=${limit}` : ""}`,
    ),

  clearMessages: () =>
    apiFetch<void>("/chat/messages", { method: "DELETE" }),
};

// Type definitions
export interface Document {
  id: string;
  title: string;
  original_filename: string;
  file_size: number;
  page_count: number | null;
  status: "processing" | "ready" | "error";
  global_index_entry: string | null;
  condensed_note: CondensedNote | null;
  tags: DocumentTag[];
  created_at: string;
  updated_at: string;
}

export interface DocumentTag {
  id: string;
  name: string;
  color: string | null;
  source: string;
  confidence: number | null;
}

export interface Tag {
  id: string;
  name: string;
  color: string | null;
  source: string;
  description: string | null;
  parent_id: string | null;
  document_count: number;
  created_at: string;
}

export interface CondensedNote {
  version: number;
  title: string;
  summary: string;
  document_type: string;
  language: string;
  detected_date: string | null;
  sections: { heading: string; content: string; pages: number[] }[];
  key_findings: string[];
  tables: { description: string; markdown: string; page?: number }[];
  entities: Record<string, string[]>;
  auto_tags: string[];
}

export interface EvolutionEntry {
  id: string;
  action: string;
  details: Record<string, unknown>;
  status: string;
  created_at: string;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  referenced_documents: string[] | null;
  created_at: string;
}
