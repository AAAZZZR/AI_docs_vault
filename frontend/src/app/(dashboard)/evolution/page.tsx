"use client";

import { useCallback, useEffect, useState } from "react";
import {
  CheckCircle,
  XCircle,
  Loader2,
  RefreshCw,
  GitMerge,
  GitBranch,
  ArrowRight,
  Zap,
} from "lucide-react";
import { api, type EvolutionEntry } from "@/lib/api";
import { cn } from "@/lib/utils";

const actionIcons: Record<string, typeof GitMerge> = {
  merge: GitMerge,
  split: GitBranch,
  reparent: ArrowRight,
  rename: RefreshCw,
};

const actionColors: Record<string, string> = {
  merge: "text-purple-600 bg-purple-50",
  split: "text-blue-600 bg-blue-50",
  reparent: "text-amber-600 bg-amber-50",
  rename: "text-gray-600 bg-gray-50",
};

function EvolutionCard({
  entry,
  onApprove,
  onReject,
  loading,
}: {
  entry: EvolutionEntry;
  onApprove: () => void;
  onReject: () => void;
  loading: boolean;
}) {
  const Icon = actionIcons[entry.action] || Zap;
  const colorClass = actionColors[entry.action] || "text-gray-600 bg-gray-50";
  const details = entry.details as Record<string, unknown>;

  const renderDetails = () => {
    switch (entry.action) {
      case "merge":
        return (
          <div className="text-sm text-gray-600">
            <span className="font-medium">{String(details.remove || details.tag_a_name)}</span>
            <ArrowRight className="mx-1.5 inline h-3.5 w-3.5 text-gray-400" />
            <span className="font-medium">{String(details.keep || details.tag_b_name)}</span>
            {details.similarity && (
              <span className="ml-2 text-xs text-gray-400">
                {(Number(details.similarity) * 100).toFixed(0)}% similar
              </span>
            )}
          </div>
        );
      case "split":
        return (
          <div className="text-sm text-gray-600">
            <span className="font-medium">{String(details.tag_name)}</span>
            <span className="ml-2 text-xs text-gray-400">
              {String(details.document_count)} documents
            </span>
            {details.suggestion && (
              <p className="mt-1 text-xs text-gray-500">{String(details.suggestion)}</p>
            )}
          </div>
        );
      case "reparent":
        return (
          <div className="text-sm text-gray-600">
            <span className="font-medium">{String(details.child_name)}</span>
            <span className="mx-1.5 text-gray-400">→ child of</span>
            <span className="font-medium">{String(details.parent_name)}</span>
          </div>
        );
      default:
        return (
          <pre className="mt-1 text-xs text-gray-500">
            {JSON.stringify(details, null, 2)}
          </pre>
        );
    }
  };

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
      <div className="flex items-start justify-between">
        <div className="flex items-start gap-3">
          <div className={cn("flex h-9 w-9 items-center justify-center rounded-lg", colorClass)}>
            <Icon className="h-4.5 w-4.5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-sm font-semibold capitalize text-gray-900">
                {entry.action}
              </span>
              <span className="text-[10px] text-gray-400">
                {new Date(entry.created_at).toLocaleString()}
              </span>
            </div>
            <div className="mt-1">{renderDetails()}</div>
          </div>
        </div>

        <div className="flex gap-1.5">
          <button
            onClick={onApprove}
            disabled={loading}
            className="flex items-center gap-1 rounded-md bg-green-50 px-3 py-1.5 text-sm font-medium text-green-700 hover:bg-green-100 disabled:opacity-50"
          >
            {loading ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <CheckCircle className="h-3.5 w-3.5" />
            )}
            Approve
          </button>
          <button
            onClick={onReject}
            disabled={loading}
            className="flex items-center gap-1 rounded-md bg-red-50 px-3 py-1.5 text-sm font-medium text-red-700 hover:bg-red-100 disabled:opacity-50"
          >
            <XCircle className="h-3.5 w-3.5" />
            Reject
          </button>
        </div>
      </div>
    </div>
  );
}

export default function EvolutionPage() {
  const [entries, setEntries] = useState<EvolutionEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [triggerLoading, setTriggerLoading] = useState(false);

  const fetchEntries = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.listPendingEvolutions();
      setEntries(data);
    } catch (err) {
      console.error("Failed to fetch evolutions:", err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchEntries();
  }, [fetchEntries]);

  const handleApprove = async (id: string) => {
    setActionLoading(id);
    try {
      await api.approveEvolution(id);
      setEntries((prev) => prev.filter((e) => e.id !== id));
    } catch (err) {
      console.error("Failed to approve:", err);
    } finally {
      setActionLoading(null);
    }
  };

  const handleReject = async (id: string) => {
    setActionLoading(id);
    try {
      await api.rejectEvolution(id);
      setEntries((prev) => prev.filter((e) => e.id !== id));
    } catch (err) {
      console.error("Failed to reject:", err);
    } finally {
      setActionLoading(null);
    }
  };

  const handleTrigger = async () => {
    setTriggerLoading(true);
    try {
      await api.triggerEvolution();
      // Wait a bit then refresh
      setTimeout(fetchEntries, 3000);
    } catch (err) {
      console.error("Failed to trigger evolution:", err);
    } finally {
      setTriggerLoading(false);
    }
  };

  return (
    <div className="p-6">
      {/* Header */}
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Tag Evolution</h1>
          <p className="mt-1 text-sm text-gray-500">
            Review and approve AI-suggested tag improvements
          </p>
        </div>
        <button
          onClick={handleTrigger}
          disabled={triggerLoading}
          className="flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
        >
          {triggerLoading ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Zap className="h-4 w-4" />
          )}
          Run Analysis
        </button>
      </div>

      {/* Content */}
      {loading ? (
        <div className="flex h-64 items-center justify-center">
          <Loader2 className="h-8 w-8 animate-spin text-indigo-600" />
        </div>
      ) : entries.length === 0 ? (
        <div className="flex h-64 flex-col items-center justify-center text-gray-400">
          <CheckCircle className="mb-3 h-12 w-12" />
          <p className="text-lg font-medium">All caught up!</p>
          <p className="mt-1 text-sm">
            No pending tag evolution suggestions. Run analysis to check for new ones.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {entries.map((entry) => (
            <EvolutionCard
              key={entry.id}
              entry={entry}
              onApprove={() => handleApprove(entry.id)}
              onReject={() => handleReject(entry.id)}
              loading={actionLoading === entry.id}
            />
          ))}
        </div>
      )}
    </div>
  );
}
