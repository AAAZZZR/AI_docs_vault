"use client";

import { useCallback, useState } from "react";
import { Search, X } from "lucide-react";
import { useDocuments } from "@/hooks/useDocuments";
import { api } from "@/lib/api";
import DocumentList from "@/components/documents/DocumentList";
import DocumentDetailModal from "@/components/documents/DocumentDetailModal";
import TagFilterSidebar from "@/components/tags/TagFilterSidebar";
import UploadButton from "@/components/documents/UploadButton";
import TagChip from "@/components/tags/TagChip";

export default function DashboardPage() {
  const {
    documents,
    tags,
    total,
    loading,
    page,
    search,
    selectedTagIds,
    setPage,
    setSearch,
    toggleTag,
    clearFilters,
    refetch,
  } = useDocuments();

  const [selectedDocId, setSelectedDocId] = useState<string | null>(null);
  const [searchInput, setSearchInput] = useState("");

  const handleSearch = useCallback(
    (value: string) => {
      setSearchInput(value);
      // Debounce search
      const timer = setTimeout(() => setSearch(value), 300);
      return () => clearTimeout(timer);
    },
    [setSearch],
  );

  const handleDelete = useCallback(
    async (id: string) => {
      if (!confirm("Are you sure you want to delete this document?")) return;
      try {
        await api.deleteDocument(id);
        refetch();
      } catch (err) {
        console.error("Failed to delete document:", err);
      }
    },
    [refetch],
  );

  const totalPages = Math.ceil(total / 20);

  return (
    <div className="flex h-full">
      {/* Tag Filter Sidebar */}
      <TagFilterSidebar
        tags={tags}
        selectedTagIds={selectedTagIds}
        onToggleTag={toggleTag}
        onClearAll={clearFilters}
      />

      {/* Main Content */}
      <div className="flex-1 p-6">
        {/* Header */}
        <div className="mb-6 flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Knowledge Base</h1>
            <p className="mt-1 text-sm text-gray-500">
              {total} document{total !== 1 ? "s" : ""}
            </p>
          </div>
          <div className="w-72">
            <UploadButton onUploadComplete={refetch} />
          </div>
        </div>

        {/* Search bar */}
        <div className="mb-4 flex items-center gap-3">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
            <input
              type="text"
              placeholder="Search documents..."
              value={searchInput}
              onChange={(e) => handleSearch(e.target.value)}
              className="w-full rounded-lg border border-gray-300 bg-white py-2 pl-10 pr-4 text-sm text-gray-900 placeholder-gray-400 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
            />
            {searchInput && (
              <button
                onClick={() => {
                  setSearchInput("");
                  setSearch("");
                }}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
              >
                <X className="h-4 w-4" />
              </button>
            )}
          </div>
        </div>

        {/* Active filters */}
        {selectedTagIds.length > 0 && (
          <div className="mb-4 flex flex-wrap items-center gap-2">
            <span className="text-xs text-gray-500">Filtering by:</span>
            {selectedTagIds.map((tagId) => {
              const tag = tags.find((t) => t.id === tagId);
              return tag ? (
                <TagChip
                  key={tagId}
                  name={tag.name}
                  color={tag.color}
                  selected
                  removable
                  onRemove={() => toggleTag(tagId)}
                />
              ) : null;
            })}
            <button
              onClick={clearFilters}
              className="text-xs text-indigo-600 hover:text-indigo-800"
            >
              Clear all
            </button>
          </div>
        )}

        {/* Document list */}
        <DocumentList
          documents={documents}
          loading={loading}
          onDocumentClick={setSelectedDocId}
          onDocumentDelete={handleDelete}
        />

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="mt-6 flex items-center justify-center gap-2">
            <button
              onClick={() => setPage(Math.max(1, page - 1))}
              disabled={page === 1}
              className="rounded-md border border-gray-300 px-3 py-1.5 text-sm text-gray-700 hover:bg-gray-50 disabled:opacity-50"
            >
              Previous
            </button>
            <span className="text-sm text-gray-600">
              Page {page} of {totalPages}
            </span>
            <button
              onClick={() => setPage(Math.min(totalPages, page + 1))}
              disabled={page === totalPages}
              className="rounded-md border border-gray-300 px-3 py-1.5 text-sm text-gray-700 hover:bg-gray-50 disabled:opacity-50"
            >
              Next
            </button>
          </div>
        )}
      </div>

      {/* Document Detail Modal */}
      {selectedDocId && (
        <DocumentDetailModal
          documentId={selectedDocId}
          onClose={() => setSelectedDocId(null)}
        />
      )}
    </div>
  );
}
