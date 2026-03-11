"use client";

import { Filter, X } from "lucide-react";
import type { Tag } from "@/lib/api";
import TagChip from "./TagChip";

interface TagFilterSidebarProps {
  tags: Tag[];
  selectedTagIds: string[];
  onToggleTag: (tagId: string) => void;
  onClearAll: () => void;
}

export default function TagFilterSidebar({
  tags,
  selectedTagIds,
  onToggleTag,
  onClearAll,
}: TagFilterSidebarProps) {
  if (tags.length === 0) return null;

  return (
    <div className="w-56 shrink-0 border-r border-gray-200 bg-white p-4">
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-1.5 text-sm font-medium text-gray-700">
          <Filter className="h-4 w-4" />
          Tags
        </div>
        {selectedTagIds.length > 0 && (
          <button
            onClick={onClearAll}
            className="flex items-center gap-1 text-xs text-gray-500 hover:text-gray-700"
          >
            <X className="h-3 w-3" />
            Clear
          </button>
        )}
      </div>

      <div className="flex flex-col gap-1">
        {tags.map((tag) => (
          <button
            key={tag.id}
            onClick={() => onToggleTag(tag.id)}
            className={`flex items-center justify-between rounded-md px-2 py-1.5 text-left text-sm transition-colors ${
              selectedTagIds.includes(tag.id)
                ? "bg-indigo-50 text-indigo-700"
                : "text-gray-600 hover:bg-gray-50"
            }`}
          >
            <span className="truncate">{tag.name}</span>
            <span className="ml-2 text-xs text-gray-400">
              {tag.document_count}
            </span>
          </button>
        ))}
      </div>
    </div>
  );
}
