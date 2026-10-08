"use client";

import { useEffect, useState, useTransition } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { api } from "@/lib/api/client";
import { AgentRun } from "@/lib/types";
import { formatDate, formatDuration } from "@/lib/utils";
import {
  StatusBadge,
  LoadingSpinner,
  ErrorState,
  EmptyState,
} from "@/components/common/StateComponents";
import { Bot, Plus, Search, Filter, Play, Sparkles, ShieldCheck } from "lucide-react";

const EXAMPLE_QUERIES = [
  "Why is payment-service experiencing database exhaustion?",
  "Check Kafka consumer lag and active cluster alerts.",
  "Create a high-severity incident for payment-service.",
  "Retrieve Redis cache memory optimization runbook.",
];

export default function RunsPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const shouldOpenNew = searchParams.get("new") === "true";

  const [runs, setRuns] = useState<AgentRun[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Form State for Starting Run
  const [showNewModal, setShowNewModal] = useState<boolean>(shouldOpenNew);
  const [message, setMessage] = useState<string>("");
  const [submitting, setSubmitting] = useState<boolean>(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  // Search & Filter
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [statusFilter, setStatusFilter] = useState<string>("ALL");

  const loadRuns = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await api.listRuns(statusFilter === "ALL" ? undefined : statusFilter);
      setRuns(data);
    } catch (err: any) {
      setError(err.message || "Failed to load agent runs");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadRuns();
  }, [statusFilter]);

  const handleCreateRun = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!message.trim() || submitting) return;

    try {
      setSubmitting(true);
      setSubmitError(null);
      const res = await api.createRun(message.trim());
      setShowNewModal(false);
      setMessage("");
      router.push(`/runs/${res.id}`);
    } catch (err: any) {
      setSubmitError(err.message || "Failed to start agent run");
      setSubmitting(false);
    }
  };

  const filteredRuns = runs.filter((r) => {
    if (!searchQuery) return true;
    const q = searchQuery.toLowerCase();
    return (
      r.user_request.toLowerCase().includes(q) ||
      r.id.toLowerCase().includes(q) ||
      (r.tools_used && r.tools_used.some((t) => t.toLowerCase().includes(q)))
    );
  });

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-white tracking-tight flex items-center gap-2">
            <Bot className="h-5 w-5 text-blue-400" />
            Agent Run History & Investigations
          </h1>
          <p className="text-xs text-gray-400 mt-1">
            Browse autonomous LangGraph agent runs, telemetry traces, tool invocations, and decisions.
          </p>
        </div>

        <button
          onClick={() => setShowNewModal(true)}
          className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-xs font-semibold tracking-wide transition-colors shadow-md shadow-blue-500/20 shrink-0"
        >
          <Plus className="h-4 w-4" />
          New Investigation
        </button>
      </div>

      {/* Filter / Search Bar */}
      <div className="flex flex-col sm:flex-row items-center gap-3 bg-[#0e1422] border border-gray-800 rounded-xl p-3">
        <div className="relative flex-1 w-full">
          <Search className="absolute left-3 top-2.5 h-4 w-4 text-gray-500" />
          <input
            type="text"
            placeholder="Search by query, tool, or run ID..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-9 pr-4 py-1.5 bg-gray-900/60 border border-gray-800 rounded-lg text-xs text-gray-200 placeholder-gray-500 focus:outline-none focus:border-blue-500 font-mono"
          />
        </div>

        <div className="flex items-center gap-2 w-full sm:w-auto">
          <Filter className="h-4 w-4 text-gray-500 shrink-0" />
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="px-3 py-1.5 bg-gray-900/60 border border-gray-800 rounded-lg text-xs text-gray-300 focus:outline-none focus:border-blue-500 font-mono"
          >
            <option value="ALL">All Statuses</option>
            <option value="COMPLETED">COMPLETED</option>
            <option value="WAITING_APPROVAL">WAITING_APPROVAL</option>
            <option value="RUNNING">RUNNING</option>
            <option value="FAILED">FAILED</option>
          </select>
        </div>
      </div>

      {/* Main List */}
      {loading ? (
        <LoadingSpinner label="Loading historical agent runs..." />
      ) : error ? (
        <ErrorState message={error} onRetry={loadRuns} />
      ) : filteredRuns.length === 0 ? (
        <EmptyState
          title="No Agent Runs Found"
          description={
            searchQuery || statusFilter !== "ALL"
              ? "No agent runs matched your search filters."
              : "No agent investigations have been started yet."
          }
          actionLabel="Start First Investigation"
          onAction={() => setShowNewModal(true)}
        />
      ) : (
        <div className="space-y-3">
          {filteredRuns.map((run) => (
            <Link
              key={run.id}
              href={`/runs/${run.id}`}
              className="block p-4 rounded-xl border border-gray-800 bg-[#0e1422] hover:bg-gray-800/40 hover:border-gray-700 transition-all"
            >
              <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1.5">
                    <span className="text-xs font-mono text-gray-400 bg-gray-900 px-2 py-0.5 rounded border border-gray-800">
                      ID: {run.id.slice(0, 8)}
                    </span>
                    <StatusBadge status={run.status} />
                    {run.status === "WAITING_APPROVAL" && (
                      <span className="text-[10px] font-mono font-semibold px-2 py-0.5 rounded bg-amber-950 text-amber-300 border border-amber-800 flex items-center gap-1">
                        <ShieldCheck className="h-3 w-3" /> ACTION REQUIRED
                      </span>
                    )}
                  </div>
                  <h3 className="text-sm font-semibold text-white group-hover:text-blue-400 transition-colors">
                    {run.user_request}
                  </h3>

                  <div className="flex flex-wrap items-center gap-3 text-xs text-gray-500 font-mono mt-2">
                    <span>Started: {formatDate(run.created_at)}</span>
                    <span>•</span>
                    <span>Duration: {formatDuration(run.total_latency_ms)}</span>
                    {run.tools_used && run.tools_used.length > 0 && (
                      <>
                        <span>•</span>
                        <span className="text-blue-400">
                          Tools: {run.tools_used.join(", ")}
                        </span>
                      </>
                    )}
                  </div>
                </div>

                <div className="flex items-center gap-2 text-xs font-mono text-blue-400 shrink-0">
                  <span>Inspect Trace →</span>
                </div>
              </div>
            </Link>
          ))}
        </div>
      )}

      {/* New Investigation Modal */}
      {showNewModal && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-[#0e1422] border border-gray-800 rounded-2xl w-full max-w-xl p-6 shadow-2xl relative">
            <div className="flex items-center justify-between pb-4 border-b border-gray-800">
              <div className="flex items-center gap-2">
                <Sparkles className="h-5 w-5 text-blue-400" />
                <h2 className="text-base font-bold text-white">Start New Agent Investigation</h2>
              </div>
              <button
                onClick={() => setShowNewModal(false)}
                className="text-gray-400 hover:text-gray-200 text-sm font-mono"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleCreateRun} className="space-y-4 mt-4">
              <div>
                <label className="block text-xs font-mono uppercase text-gray-400 mb-1.5">
                  Operational Inquiry or Directive
                </label>
                <textarea
                  rows={4}
                  value={message}
                  onChange={(e) => setMessage(e.target.value)}
                  placeholder="e.g. Why is payment-service experiencing database exhaustion?"
                  className="w-full px-3.5 py-2.5 bg-gray-900 border border-gray-800 rounded-xl text-xs text-gray-100 placeholder-gray-500 focus:outline-none focus:border-blue-500 font-mono leading-relaxed"
                  required
                />
              </div>

              {/* Sample Prompts */}
              <div>
                <span className="text-[11px] font-mono text-gray-400 block mb-1.5">
                  Sample Scenarios:
                </span>
                <div className="flex flex-wrap gap-1.5">
                  {EXAMPLE_QUERIES.map((q) => (
                    <button
                      key={q}
                      type="button"
                      onClick={() => setMessage(q)}
                      className="text-[11px] px-2.5 py-1 bg-gray-850 hover:bg-gray-800 text-gray-300 rounded-md border border-gray-800 transition-colors text-left font-mono"
                    >
                      {q}
                    </button>
                  ))}
                </div>
              </div>

              {submitError && (
                <div className="p-3 bg-rose-950/40 border border-rose-800/60 rounded-lg text-xs text-rose-300">
                  {submitError}
                </div>
              )}

              <div className="flex items-center justify-end gap-3 pt-4 border-t border-gray-800">
                <button
                  type="button"
                  onClick={() => setShowNewModal(false)}
                  className="px-4 py-2 bg-gray-800 hover:bg-gray-700 text-gray-300 rounded-lg text-xs font-semibold transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submitting || !message.trim()}
                  className="inline-flex items-center gap-2 px-5 py-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white rounded-lg text-xs font-semibold transition-colors shadow-md shadow-blue-500/20"
                >
                  <Play className={`h-3.5 w-3.5 ${submitting ? "animate-spin" : ""}`} />
                  {submitting ? "Executing LangGraph..." : "Execute Investigation"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
