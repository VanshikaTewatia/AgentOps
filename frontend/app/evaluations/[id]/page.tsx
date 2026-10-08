"use client";

import { useEffect, useState, use } from "react";
import Link from "next/link";
import { api } from "@/lib/api/client";
import { EvaluationCaseResult, EvaluationRun } from "@/lib/types";
import { formatDate, formatDuration } from "@/lib/utils";
import {
  StatusBadge,
  LoadingSpinner,
  ErrorState,
} from "@/components/common/StateComponents";
import {
  BarChart3,
  CheckCircle2,
  XCircle,
  ArrowLeft,
  Filter,
  Search,
  Check,
  X,
} from "lucide-react";

export default function EvaluationDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);

  const [evaluation, setEvaluation] = useState<EvaluationRun | null>(null);
  const [results, setResults] = useState<EvaluationCaseResult[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [categoryFilter, setCategoryFilter] = useState<string>("ALL");
  const [statusFilter, setStatusFilter] = useState<string>("ALL");

  const loadData = async () => {
    try {
      setLoading(true);
      setError(null);
      const [evalData, resultsData] = await Promise.all([
        api.getEvaluation(id),
        api.getEvaluationResults(id),
      ]);
      setEvaluation(evalData);
      setResults(resultsData);
    } catch (err: any) {
      setError(err.message || "Failed to load evaluation details");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [id]);

  if (loading) return <LoadingSpinner label="Loading evaluation details & cases..." />;
  if (error || !evaluation) return <ErrorState message={error || "Evaluation not found"} onRetry={loadData} />;

  const categories = Array.from(new Set(results.map((r) => r.category)));

  const filteredCases = results.filter((c) => {
    if (categoryFilter !== "ALL" && c.category !== categoryFilter) return false;
    if (statusFilter !== "ALL" && c.status !== statusFilter) return false;
    return true;
  });

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div>
        <Link
          href="/evaluations"
          className="inline-flex items-center gap-1.5 text-xs font-mono text-gray-400 hover:text-gray-200 mb-2 transition-colors"
        >
          <ArrowLeft className="h-3.5 w-3.5" /> Back to Evaluations
        </Link>
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <h1 className="text-lg font-bold text-white font-mono flex items-center gap-2">
              <BarChart3 className="h-5 w-5 text-emerald-400" />
              BENCHMARK RUN: {evaluation.dataset_name}
            </h1>
            <p className="text-xs text-gray-400 mt-1 font-mono">
              Executed {formatDate(evaluation.created_at)} • Provider: {evaluation.model_provider}
            </p>
          </div>
          <StatusBadge
            status={evaluation.passed_cases === evaluation.total_cases ? "PASSED" : "FAILED"}
            size="md"
          />
        </div>
      </div>

      {/* Metrics Summary Grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="p-4 bg-[#0e1422] rounded-xl border border-gray-800">
          <span className="text-[10px] font-mono text-gray-500 uppercase block">
            Supervisor Routing
          </span>
          <span className="text-xl font-bold font-mono text-emerald-400">
            {(evaluation.routing_accuracy * 100).toFixed(1)}%
          </span>
        </div>
        <div className="p-4 bg-[#0e1422] rounded-xl border border-gray-800">
          <span className="text-[10px] font-mono text-gray-500 uppercase block">
            Tool Selection
          </span>
          <span className="text-xl font-bold font-mono text-emerald-400">
            {(evaluation.tool_selection_accuracy * 100).toFixed(1)}%
          </span>
        </div>
        <div className="p-4 bg-[#0e1422] rounded-xl border border-gray-800">
          <span className="text-[10px] font-mono text-gray-500 uppercase block">
            Evidence Grounding
          </span>
          <span className="text-xl font-bold font-mono text-emerald-400">
            {(evaluation.grounding_rate * 100).toFixed(1)}%
          </span>
        </div>
        <div className="p-4 bg-[#0e1422] rounded-xl border border-gray-800">
          <span className="text-[10px] font-mono text-gray-500 uppercase block">
            Approval Safety
          </span>
          <span className="text-xl font-bold font-mono text-emerald-400">
            {(evaluation.approval_safety_rate * 100).toFixed(1)}%
          </span>
        </div>
      </div>

      {/* Latency & Stats */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 p-4 bg-[#0e1422] border border-gray-800 rounded-xl text-xs font-mono text-gray-300">
        <div>
          Total Cases: <strong>{evaluation.total_cases}</strong>
        </div>
        <div>
          Passed: <strong className="text-emerald-400">{evaluation.passed_cases}</strong>
        </div>
        <div>
          Avg Latency: <strong>{evaluation.avg_latency_ms.toFixed(1)} ms</strong>
        </div>
        <div>
          P95 Latency: <strong>{evaluation.p95_latency_ms.toFixed(1)} ms</strong>
        </div>
      </div>

      {/* Filter Bar */}
      <div className="flex flex-wrap items-center gap-3 bg-[#0e1422] border border-gray-800 rounded-xl p-3">
        <div className="flex items-center gap-2 text-xs font-mono text-gray-400">
          <Filter className="h-4 w-4" />
          <span>Category:</span>
          <select
            value={categoryFilter}
            onChange={(e) => setCategoryFilter(e.target.value)}
            className="px-2.5 py-1 bg-gray-900 border border-gray-800 rounded-md text-gray-200 text-xs focus:outline-none"
          >
            <option value="ALL">All Categories ({results.length})</option>
            {categories.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </div>

        <div className="flex items-center gap-2 text-xs font-mono text-gray-400">
          <span>Status:</span>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="px-2.5 py-1 bg-gray-900 border border-gray-800 rounded-md text-gray-200 text-xs focus:outline-none"
          >
            <option value="ALL">All Statuses</option>
            <option value="PASSED">Passed Only</option>
            <option value="FAILED">Failed Only</option>
          </select>
        </div>
      </div>

      {/* Per-Case Detailed Cards */}
      <div className="space-y-3">
        {filteredCases.map((c) => {
          const isPassed = c.status === "PASSED";
          return (
            <div
              key={c.case_id}
              className="p-4 rounded-xl border border-gray-800 bg-[#0e1422] space-y-3"
            >
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-mono font-bold text-gray-400 bg-gray-900 px-2 py-0.5 rounded border border-gray-800">
                    {c.case_id}
                  </span>
                  <span className="text-xs font-mono text-blue-400 font-medium">
                    [{c.category}]
                  </span>
                </div>
                <div className="flex items-center gap-3">
                  <span className="text-xs font-mono text-gray-500">
                    Latency: {formatDuration(c.latency_ms)}
                  </span>
                  <StatusBadge status={c.status} />
                </div>
              </div>

              <div className="text-xs font-semibold text-white">{c.query}</div>

              {/* Sub-Metric Verification Checklist */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-[11px] font-mono bg-gray-950/60 p-2.5 rounded-lg border border-gray-850">
                <div className="flex items-center gap-1.5">
                  {c.routing_correct ? (
                    <Check className="h-3.5 w-3.5 text-emerald-400" />
                  ) : (
                    <X className="h-3.5 w-3.5 text-rose-400" />
                  )}
                  <span className={c.routing_correct ? "text-gray-300" : "text-rose-300"}>
                    Routing Precision
                  </span>
                </div>

                <div className="flex items-center gap-1.5">
                  {c.tool_selection_correct ? (
                    <Check className="h-3.5 w-3.5 text-emerald-400" />
                  ) : (
                    <X className="h-3.5 w-3.5 text-rose-400" />
                  )}
                  <span className={c.tool_selection_correct ? "text-gray-300" : "text-rose-300"}>
                    Tool Precision
                  </span>
                </div>

                <div className="flex items-center gap-1.5">
                  {c.grounded ? (
                    <Check className="h-3.5 w-3.5 text-emerald-400" />
                  ) : (
                    <X className="h-3.5 w-3.5 text-rose-400" />
                  )}
                  <span className={c.grounded ? "text-gray-300" : "text-rose-300"}>
                    Grounded Output
                  </span>
                </div>

                <div className="flex items-center gap-1.5">
                  {c.approval_safety_passed ? (
                    <Check className="h-3.5 w-3.5 text-emerald-400" />
                  ) : (
                    <X className="h-3.5 w-3.5 text-rose-400" />
                  )}
                  <span className={c.approval_safety_passed ? "text-gray-300" : "text-rose-300"}>
                    Safety Enforced
                  </span>
                </div>
              </div>

              {/* Agents & Tools Comparison */}
              <div className="flex flex-wrap items-center gap-4 text-[11px] font-mono text-gray-400 pt-1">
                <div>
                  Agents: <span className="text-gray-200">{c.actual_agents?.join(", ") || "None"}</span>
                </div>
                <div>
                  Tools: <span className="text-gray-200">{c.actual_tools?.join(", ") || "None"}</span>
                </div>
                <div>
                  Evidence: <span className="text-gray-200">{c.evidence_count} items</span>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
