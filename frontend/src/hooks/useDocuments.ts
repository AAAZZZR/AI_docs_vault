"use client";

import { useCallback, useEffect, useState } from "react";
import { api, type Document, type Tag } from "@/lib/api";

export function useDocuments() {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [tags, setTags] = useState<Tag[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [selectedTagIds, setSelectedTagIds] = useState<string[]>([]);

  const fetchDocuments = useCallback(async () => {
    setLoading(true);
    try {
      const result = await api.listDocuments({
        page,
        page_size: 20,
        search: search || undefined,
        tag_ids: selectedTagIds.length > 0 ? selectedTagIds : undefined,
      });
      setDocuments(result.documents);
      setTotal(result.total);
    } catch (err) {
      console.error("Failed to fetch documents:", err);
    } finally {
      setLoading(false);
    }
  }, [page, search, selectedTagIds]);

  const fetchTags = useCallback(async () => {
    try {
      const result = await api.listTags();
      setTags(result);
    } catch (err) {
      console.error("Failed to fetch tags:", err);
    }
  }, []);

  useEffect(() => {
    fetchDocuments();
  }, [fetchDocuments]);

  useEffect(() => {
    fetchTags();
  }, [fetchTags]);

  const toggleTag = (tagId: string) => {
    setSelectedTagIds((prev) =>
      prev.includes(tagId)
        ? prev.filter((id) => id !== tagId)
        : [...prev, tagId],
    );
    setPage(1);
  };

  const clearFilters = () => {
    setSelectedTagIds([]);
    setSearch("");
    setPage(1);
  };

  return {
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
    refetch: () => {
      fetchDocuments();
      fetchTags();
    },
  };
}
