"use client";

import { FileText, MoreVertical, Trash2, Download } from "lucide-react";
import type { Document } from "@/lib/api";
import { formatDate, formatFileSize } from "@/lib/utils";
import StatusBadge from "./StatusBadge";
import TagChip from "@/components/tags/TagChip";
import { useState } from "react";

interface DocumentCardProps {
  document: Document;
  onClick: () => void;
  onDelete: () => void;
}

export default function DocumentCard({
  document,
  onClick,
  onDelete,
}: DocumentCardProps) {
  const [showMenu, setShowMenu] = useState(false);
  const displayTags = document.tags.slice(0, 3);
  const extraTags = document.tags.length - 3;

  return (
    <div
      onClick={onClick}
      className="group relative cursor-pointer rounded-lg border border-gray-200 bg-white p-4 shadow-sm transition-all hover:border-indigo-200 hover:shadow-md"
    >
      {/* Header */}
      <div className="mb-2 flex items-start justify-between">
        <div className="flex items-center gap-2">
          <FileText className="h-5 w-5 shrink-0 text-indigo-500" />
          <h3 className="line-clamp-1 text-sm font-medium text-gray-900">
            {document.title}
          </h3>
        </div>
        <div className="flex items-center gap-2">
          <StatusBadge status={document.status} />
          <div className="relative">
            <button
              onClick={(e) => {
                e.stopPropagation();
                setShowMenu(!showMenu);
              }}
              className="rounded p-1 text-gray-400 opacity-0 transition-opacity hover:bg-gray-100 hover:text-gray-600 group-hover:opacity-100"
            >
              <MoreVertical className="h-4 w-4" />
            </button>
            {showMenu && (
              <div className="absolute right-0 top-8 z-10 w-36 rounded-md border border-gray-200 bg-white py-1 shadow-lg">
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    onDelete();
                    setShowMenu(false);
                  }}
                  className="flex w-full items-center gap-2 px-3 py-1.5 text-sm text-red-600 hover:bg-red-50"
                >
                  <Trash2 className="h-4 w-4" />
                  Delete
                </button>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Summary */}
      {document.global_index_entry && (
        <p className="mb-3 line-clamp-2 text-xs text-gray-500">
          {document.global_index_entry}
        </p>
      )}

      {/* Tags */}
      {document.tags.length > 0 && (
        <div className="mb-3 flex flex-wrap gap-1">
          {displayTags.map((tag) => (
            <TagChip key={tag.id} name={tag.name} color={tag.color} />
          ))}
          {extraTags > 0 && (
            <span className="inline-flex items-center rounded-full bg-gray-100 px-2 py-0.5 text-[10px] text-gray-500">
              +{extraTags} more
            </span>
          )}
        </div>
      )}

      {/* Footer */}
      <div className="flex items-center justify-between text-[11px] text-gray-400">
        <span>{formatDate(document.created_at)}</span>
        <div className="flex items-center gap-2">
          {document.page_count && <span>{document.page_count} pages</span>}
          <span>{formatFileSize(document.file_size)}</span>
        </div>
      </div>
    </div>
  );
}
