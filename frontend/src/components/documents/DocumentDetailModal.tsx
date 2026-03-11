"use client";

import { useCallback, useEffect, useState } from "react";
import {
  ChevronDown,
  ChevronRight,
  Download,
  RefreshCw,
  X,
  Loader2,
} from "lucide-react";
import { api, type Document, type DocumentChunk, type CondensedNote } from "@/lib/api";
import StatusBadge from "./StatusBadge";
import TagChip from "@/components/tags/TagChip";

interface DocumentDetailModalProps {
  documentId: string;
  onClose: () => void;
}

export default function DocumentDetailModal({
  documentId,
  onClose,
}: DocumentDetailModalProps) {
  const [document, setDocument] = useState<
    (Document & { has_pdf?: boolean }) | null
  >(null);
  const [loading, setLoading] = useState(true);
  const [expandedSections, setExpandedSections] = useState<Set<number>>(
    new Set(),
  );
  const [chunks, setChunks] = useState<DocumentChunk[]>([]);
  const [showChunks, setShowChunks] = useState(false);
  const [reprocessing, setReprocessing] = useState(false);

  const fetchDocument = useCallback(async () => {
    try {
      const doc = await api.getDocument(documentId);
      setDocument(doc);
      // Expand first 3 sections by default
      setExpandedSections(new Set([0, 1, 2]));
    } catch (err) {
      console.error("Failed to fetch document:", err);
    } finally {
      setLoading(false);
    }
  }, [documentId]);

  const fetchChunks = useCallback(async () => {
    try {
      const data = await api.getDocumentChunks(documentId);
      setChunks(data);
    } catch (err) {
      console.error("Failed to fetch chunks:", err);
    }
  }, [documentId]);

  const handleReprocess = async () => {
    setReprocessing(true);
    try {
      await api.reprocessDocument(documentId);
      // Refresh after a delay
      setTimeout(() => {
        fetchDocument();
        setReprocessing(false);
      }, 2000);
    } catch (err) {
      console.error("Failed to reprocess:", err);
      setReprocessing(false);
    }
  };

  useEffect(() => {
    fetchDocument();
  }, [fetchDocument]);

  const toggleSection = (index: number) => {
    setExpandedSections((prev) => {
      const next = new Set(prev);
      if (next.has(index)) {
        next.delete(index);
      } else {
        next.add(index);
      }
      return next;
    });
  };

  const note = document?.condensed_note as CondensedNote | null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="relative max-h-[90vh] w-full max-w-3xl overflow-auto rounded-xl bg-white shadow-2xl">
        {/* Header */}
        <div className="sticky top-0 z-10 flex items-center justify-between border-b border-gray-200 bg-white px-6 py-4">
          <div className="flex-1">
            <h2 className="text-lg font-semibold text-gray-900">
              {document?.title || "Loading..."}
            </h2>
            {document && (
              <div className="mt-1 flex items-center gap-3">
                <StatusBadge status={document.status} />
                <span className="text-xs text-gray-500">
                  {document.original_filename}
                </span>
              </div>
            )}
          </div>
          <div className="flex items-center gap-2">
            {document?.status === "error" && (
              <button
                onClick={handleReprocess}
                disabled={reprocessing}
                className="flex items-center gap-1 rounded-md border border-amber-300 bg-amber-50 px-3 py-1.5 text-sm text-amber-700 hover:bg-amber-100 disabled:opacity-50"
              >
                {reprocessing ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <RefreshCw className="h-4 w-4" />
                )}
                Reprocess
              </button>
            )}
            {document?.has_pdf && (
              <a
                href={api.downloadDocumentUrl(documentId)}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-1 rounded-md border border-gray-300 px-3 py-1.5 text-sm text-gray-700 hover:bg-gray-50"
              >
                <Download className="h-4 w-4" />
                PDF
              </a>
            )}
            <button
              onClick={onClose}
              className="rounded-md p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
            >
              <X className="h-5 w-5" />
            </button>
          </div>
        </div>

        {loading ? (
          <div className="flex h-64 items-center justify-center">
            <div className="h-8 w-8 animate-spin rounded-full border-2 border-indigo-600 border-t-transparent" />
          </div>
        ) : note ? (
          <div className="px-6 py-4">
            {/* Summary */}
            <div className="mb-6">
              <h3 className="mb-2 text-sm font-semibold text-gray-700">
                Summary
              </h3>
              <p className="text-sm leading-relaxed text-gray-600">
                {note.summary}
              </p>
            </div>

            {/* Tags */}
            {document && document.tags.length > 0 && (
              <div className="mb-6">
                <h3 className="mb-2 text-sm font-semibold text-gray-700">
                  Tags
                </h3>
                <div className="flex flex-wrap gap-1.5">
                  {document.tags.map((tag) => (
                    <TagChip key={tag.id} name={tag.name} color={tag.color} />
                  ))}
                </div>
              </div>
            )}

            {/* Key Findings */}
            {note.key_findings.length > 0 && (
              <div className="mb-6">
                <h3 className="mb-2 text-sm font-semibold text-gray-700">
                  Key Findings
                </h3>
                <ul className="space-y-1.5">
                  {note.key_findings.map((finding, i) => (
                    <li
                      key={i}
                      className="flex items-start gap-2 text-sm text-gray-600"
                    >
                      <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-indigo-500" />
                      {finding}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* Sections */}
            {note.sections.length > 0 && (
              <div className="mb-6">
                <h3 className="mb-2 text-sm font-semibold text-gray-700">
                  Sections
                </h3>
                <div className="space-y-1">
                  {note.sections.map((section, i) => (
                    <div
                      key={i}
                      className="rounded-md border border-gray-100"
                    >
                      <button
                        onClick={() => toggleSection(i)}
                        className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm font-medium text-gray-700 hover:bg-gray-50"
                      >
                        {expandedSections.has(i) ? (
                          <ChevronDown className="h-4 w-4 text-gray-400" />
                        ) : (
                          <ChevronRight className="h-4 w-4 text-gray-400" />
                        )}
                        {section.heading}
                        {section.pages.length > 0 && (
                          <span className="text-[10px] text-gray-400">
                            p.{section.pages.join(", ")}
                          </span>
                        )}
                      </button>
                      {expandedSections.has(i) && (
                        <div className="border-t border-gray-100 px-3 py-2 text-sm leading-relaxed text-gray-600">
                          {section.content}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Entities */}
            {note.entities &&
              Object.keys(note.entities).some(
                (k) => (note.entities[k] as string[])?.length > 0,
              ) && (
                <div className="mb-6">
                  <h3 className="mb-2 text-sm font-semibold text-gray-700">
                    Entities
                  </h3>
                  <div className="grid grid-cols-2 gap-3">
                    {Object.entries(note.entities).map(
                      ([category, values]) =>
                        (values as string[])?.length > 0 && (
                          <div key={category}>
                            <span className="text-xs font-medium capitalize text-gray-500">
                              {category}
                            </span>
                            <div className="mt-1 flex flex-wrap gap-1">
                              {(values as string[]).map((v, i) => (
                                <span
                                  key={i}
                                  className="rounded bg-gray-100 px-1.5 py-0.5 text-xs text-gray-600"
                                >
                                  {v}
                                </span>
                              ))}
                            </div>
                          </div>
                        ),
                    )}
                  </div>
                </div>
              )}

            {/* Chunks */}
            <div className="mb-6">
              <button
                onClick={() => {
                  setShowChunks(!showChunks);
                  if (!showChunks && chunks.length === 0) fetchChunks();
                }}
                className="flex items-center gap-1 text-sm font-semibold text-gray-700 hover:text-indigo-600"
              >
                {showChunks ? (
                  <ChevronDown className="h-4 w-4" />
                ) : (
                  <ChevronRight className="h-4 w-4" />
                )}
                RAG Chunks ({chunks.length || "..."})
              </button>
              {showChunks && chunks.length > 0 && (
                <div className="mt-2 space-y-2">
                  {chunks.map((chunk) => (
                    <div
                      key={chunk.id}
                      className="rounded-md border border-gray-100 px-3 py-2"
                    >
                      <div className="flex items-center gap-2 text-xs text-gray-400">
                        <span>#{chunk.chunk_index}</span>
                        {chunk.heading && (
                          <span className="font-medium text-gray-600">
                            {chunk.heading}
                          </span>
                        )}
                        {chunk.page_start && (
                          <span>
                            p.{chunk.page_start}
                            {chunk.page_end && chunk.page_end !== chunk.page_start
                              ? `-${chunk.page_end}`
                              : ""}
                          </span>
                        )}
                        {chunk.token_count && (
                          <span>~{chunk.token_count} tokens</span>
                        )}
                        <span
                          className={
                            chunk.has_embedding
                              ? "text-green-500"
                              : "text-red-400"
                          }
                        >
                          {chunk.has_embedding ? "✓ embedded" : "✗ no embedding"}
                        </span>
                      </div>
                      <p className="mt-1 text-xs leading-relaxed text-gray-600">
                        {chunk.content}
                      </p>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Document metadata */}
            <div className="border-t border-gray-100 pt-4 text-xs text-gray-400">
              <div className="flex gap-4">
                <span>Type: {note.document_type}</span>
                <span>Language: {note.language}</span>
                {note.detected_date && (
                  <span>Date: {note.detected_date}</span>
                )}
              </div>
            </div>
          </div>
        ) : (
          <div className="flex h-64 items-center justify-center text-sm text-gray-500">
            No condensed note available yet.
          </div>
        )}
      </div>
    </div>
  );
}
