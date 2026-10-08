"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api/client";
import { EvaluationRun } from "@/lib/types";
import { formatDate, formatDuration } from "@/lib/utils";
import {
  StatusBadge,
  LoadingSpinner,
  ErrorState,
  EmptyState,
} from "@/components/common/StateComponents";
import {
  BarChart3,
  Play,
  CheckCircle2,
  ShieldCheck,
  Compass,
  FileCheck,
  Wrench,
  Clock,
  ExternalLink,
  RefreshCw,
} from "lucide-react";

export default function EvaluationsPage() {
  const [evaluations, setEvaluations] = useState<EvaluationRun[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Triggering new evaluation run
  const [triggerLoading, setTriggerLoading] = useState<boolean>(false);
  const [triggerError, setTriggerError] = useState<string | null>(null);

  const loadEvaluations = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await api.listEvaluations(20, 0);
      setEvaluations(data);
    } catch (err: any) {
      setError(err.message || "Failed to load evaluation benchmarks");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadEvaluations();
  }, []);

  const handleRunEvaluation = async () => {
    if (triggerLoading) return;
    try {
      setTriggerLoading(true);
      setTriggerError(null);
      await api.triggerEvaluation("agentops-eval-v1");
      await loadEvaluations();
    } catch (err: any) {
      setTriggerError(err.message || "Failed to trigger evaluation run");
    } finally {
      setTriggerLoading(false);
    }
  };

  const latest = evaluations.length > 0 ? evaluations[0] : null;

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-white tracking-tight flex items-center gap-2">
            <BarChart3 className="h-5 w-5 text-emerald-400" />
            Evaluation, Grounding & Reliability Benchmark
          </h1>
          <p className="text-xs text-gray-400 mt-1">
            Systematic benchmark measurement of routing precision, tool selection, RAG grounding, conflict handling, and safety gates.
          </p>
        </div>

        <button
          onClick={handleRunEvaluation}
          disabled={triggerLoading}
          className="inline-flex items-center gap-2 px-4 py-2 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white rounded-lg text-xs font-semibold tracking-wide transition-colors shadow-md shadow-emerald-600/20 shrink-0"
        >
          <Play className={`h-4 w-4 ${triggerLoading ? "animate-spin" : ""}`} />
          {triggerLoading ? "Running Benchmark (20 Cases)..." : "Trigger Evaluation Run"}
        </button>
      </div>

      {triggerError && (
        <div className="p-3 bg-rose-950/50 border border-rose-800 rounded-xl text-xs text-rose-300 font-mono">
          {triggerError}
        </div>
      )}

      {/* Latest Benchmark Highlights Card */}
      {latest && (
        <div className="p-6 rounded-xl border border-gray-800 bg-[#0e1422] space-y-5">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-4 border-b border-gray-800">
            <div>
              <span className="text-[10px] font-mono uppercase text-emerald-400 font-semibold tracking-wider">
                LATEST BENCHMARK REPORT
              </span>
              <h2 className="text-base font-bold text-white mt-0.5">
                Dataset: {latest.dataset_name} ({latest.model_provider})
              </h2>
            </div>
            <div className="text-xs font-mono text-gray-400">
              Executed: {formatDate(latest.created_at)}
            </div>
          </div>

          {/* Key Metrics Grid */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            <div className="p-3 bg-gray-950 rounded-lg border border-gray-850">
              <span className="text-[10px] font-mono text-gray-500 uppercase block">
                Routing Accuracy
              </span>
              <span className="text-xl font-bold font-mono text-emerald-400">
                {(latest.routing_accuracy * 100).toFixed(1)}%
              </span>
            </div>

            <div className="p-3 bg-gray-950 rounded-lg border border-gray-850">
              <span className="text-[10px] font-mono text-gray-500 uppercase block">
                Tool Selection
              </span>
              <span className="text-xl font-bold font-mono text-emerald-400">
                {(latest.tool_selection_accuracy * 100).toFixed(1)}%
              </span>
            </div>

            <div className="p-3 bg-gray-950 rounded-lg border border-gray-850">
              <span className="text-[10px] font-mono text-gray-500 uppercase block">
                Grounding Rate
              </span>
              <span className="text-xl font-bold font-mono text-emerald-400">
                {(latest.grounding_rate * 100).toFixed(1)}%
              </span>
            </div>

            <div className="p-3 bg-gray-950 rounded-lg border border-gray-850">
              <span className="text-[10px] font-mono text-gray-500 uppercase block">
                Approval Safety
              </span>
              <span className="text-xl font-bold font-mono text-emerald-400">
                {(latest.approval_safety_rate * 100).toFixed(1)}%
              </span>
            </div>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-xs font-mono text-gray-400">
            <div>
              Total Cases: <strong className="text-white">{latest.total_cases}</strong>
            </div>
            <div>
              Passed: <strong className="text-emerald-400">{latest.passed_cases}</strong>
            </div>
            <div>
              Avg Latency: <strong className="text-white">{latest.avg_latency_ms.toFixed(1)} ms</strong>
            </div>
            <div>
              P95 Latency: <strong className="text-white">{latest.p95_latency_ms.toFixed(1)} ms</strong>
            </div>
          </div>
        </div>
      )}

      {/* Historical Benchmark Runs Table */}
      <div className="space-y-3">
        <h2 className="font-semibold text-sm text-white flex items-center gap-2">
          Historical Benchmark Executions
        </h2>

        {loading ? (
          <LoadingSpinner label="Loading historical benchmark reports..." />
        ) : error ? (
          <ErrorState message={error} onRetry={loadEvaluations} />
        ) : evaluations.length === 0 ? (
          <EmptyState
            title="No Evaluations Found"
            description="Trigger an evaluation run to generate benchmark quality metrics."
            actionLabel="Run 20-Case Benchmark"
            onAction={handleRunEvaluation}
          />
        ) : (
          <div className="space-y-3">
            {evaluations.map((ev) => (
              <Link
                key={ev.id}
                href={`/evaluations/${ev.id}`}
                className="block p-4 rounded-xl border border-gray-800 bg-[#0e1422] hover:bg-gray-800/40 hover:border-gray-700 transition-all"
              >
                <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
                  <div>
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-xs font-bold text-white font-mono">{ev.dataset_name}</span>
                      <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-950 text-emerald-300 border border-emerald-800">
                        {ev.passed_cases}/{ev.total_cases} PASSED
                      </span>
                    </div>
                    <div className="flex flex-wrap items-center gap-3 text-xs font-mono text-gray-400">
                      <span>Executed: {formatDate(ev.created_at)}</span>
                      <span>•</span>
                      <span>Avg: {ev.avg_latency_ms.toFixed(1)} ms</span>
                      <span>•</span>
                      <span>P95: {ev.p95_latency_ms.toFixed(1)} ms</span>
                    </div>
                  </div>

                  <div className="flex items-center gap-4 text-xs font-mono text-gray-300">
                    <div>
                      Routing: <strong className="text-emerald-400">{(ev.routing_accuracy * 100).toFixed(0)}%</strong>
                    </div>
                    <div>
                      Tools: <strong className="text-emerald-400">{(ev.tool_selection_accuracy * 100).toFixed(0)}%</strong>
                    </div>
                    <span className="text-blue-400">View Cases →</span>
                  </div>
                </div>
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
