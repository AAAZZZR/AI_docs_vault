"use client";

import { Grid3X3, List, Loader2 } from "lucide-react";
import { useState } from "react";
import type { Document } from "@/lib/api";
import DocumentCard from "./DocumentCard";
import { cn, formatDate, formatFileSize } from "@/lib/utils";
import StatusBadge from "./StatusBadge";
import TagChip from "@/components/tags/TagChip";

interface DocumentListProps {
  documents: Document[];
  loading: boolean;
  onDocumentClick: (id: string) => void;
  onDocumentDelete: (id: string) => void;
}

export default function DocumentList({
  documents,
  loading,
  onDocumentClick,
  onDocumentDelete,
}: DocumentListProps) {
  const [viewMode, setViewMode] = useState<"card" | "table">("card");

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-indigo-600" />
      </div>
    );
  }

  if (documents.length === 0) {
    return (
      <div className="flex h-64 flex-col items-center justify-center text-gray-500">
        <p className="text-lg font-medium">No documents yet</p>
        <p className="mt-1 text-sm">Upload a PDF to get started</p>
      </div>
    );
  }

  return (
    <div>
      {/* View toggle */}
      <div className="mb-4 flex justify-end">
        <div className="flex rounded-md border border-gray-200">
          <button
            onClick={() => setViewMode("card")}
            className={cn(
              "rounded-l-md px-2.5 py-1.5 text-sm",
              viewMode === "card"
                ? "bg-indigo-50 text-indigo-700"
                : "text-gray-500 hover:bg-gray-50",
            )}
          >
            <Grid3X3 className="h-4 w-4" />
          </button>
          <button
            onClick={() => setViewMode("table")}
            className={cn(
              "rounded-r-md px-2.5 py-1.5 text-sm",
              viewMode === "table"
                ? "bg-indigo-50 text-indigo-700"
                : "text-gray-500 hover:bg-gray-50",
            )}
          >
            <List className="h-4 w-4" />
          </button>
        </div>
      </div>

      {viewMode === "card" ? (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {documents.map((doc) => (
            <DocumentCard
              key={doc.id}
              document={doc}
              onClick={() => onDocumentClick(doc.id)}
              onDelete={() => onDocumentDelete(doc.id)}
            />
          ))}
        </div>
      ) : (
        <div className="overflow-hidden rounded-lg border border-gray-200 bg-white">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase text-gray-500">
                  Title
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase text-gray-500">
                  Tags
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase text-gray-500">
                  Status
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase text-gray-500">
                  Pages
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase text-gray-500">
                  Size
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase text-gray-500">
                  Date
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {documents.map((doc) => (
                <tr
                  key={doc.id}
                  onClick={() => onDocumentClick(doc.id)}
                  className="cursor-pointer hover:bg-gray-50"
                >
                  <td className="max-w-xs truncate px-4 py-3 text-sm font-medium text-gray-900">
                    {doc.title}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex flex-wrap gap-1">
                      {doc.tags.slice(0, 2).map((tag) => (
                        <TagChip
                          key={tag.id}
                          name={tag.name}
                          color={tag.color}
                        />
                      ))}
                      {doc.tags.length > 2 && (
                        <span className="text-[10px] text-gray-400">
                          +{doc.tags.length - 2}
                        </span>
                      )}
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <StatusBadge status={doc.status} />
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-500">
                    {doc.page_count ?? "-"}
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-500">
                    {formatFileSize(doc.file_size)}
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-500">
                    {formatDate(doc.created_at)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
