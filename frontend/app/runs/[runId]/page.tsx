"use client";

import { useEffect, useState, use } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api/client";
import { AgentEvent, AgentRun, Approval, EvidenceItem } from "@/lib/types";
import { formatDate, formatDuration } from "@/lib/utils";
import {
  StatusBadge,
  LoadingSpinner,
  ErrorState,
} from "@/components/common/StateComponents";
import { AgentGraphView } from "@/components/agent/AgentGraphView";
import { ToolExecutionPanel } from "@/components/tools/ToolExecutionPanel";
import { EvidencePanel } from "@/components/evidence/EvidencePanel";
import {
  Bot,
  CheckCircle2,
  Clock,
  Compass,
  FileSearch,
  Layers,
  RefreshCw,
  ShieldAlert,
  ShieldCheck,
  Terminal,
  ArrowLeft,
  Check,
  X,
} from "lucide-react";

export default function RunDetailPage({ params }: { params: Promise<{ runId: string }> }) {
  const router = useRouter();
  const { runId } = use(params);

  const [run, setRun] = useState<AgentRun | null>(null);
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [pendingApproval, setPendingApproval] = useState<Approval | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<"graph" | "tools" | "evidence" | "raw">("graph");

  // Approval decision state
  const [actionLoading, setActionLoading] = useState<boolean>(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [rejectionModal, setRejectionModal] = useState<boolean>(false);
  const [rejectionReason, setRejectionReason] = useState<string>("");

  const loadRunData = async () => {
    try {
      setError(null);
      const [runData, eventsData, approvalsData] = await Promise.all([
        api.getRun(runId),
        api.getRunEvents(runId).catch(() => []),
        api.listApprovals("PENDING").catch(() => []),
      ]);

      setRun(runData);
      setEvents(eventsData);

      const matchingAppr = approvalsData.find((a) => a.run_id === runId);
      setPendingApproval(matchingAppr || null);
    } catch (err: any) {
      setError(err.message || "Failed to load agent run details");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadRunData();

    // Auto poll if run is still in progress
    const timer = setInterval(() => {
      if (run?.status === "RUNNING" || run?.status === "WAITING_APPROVAL") {
        loadRunData();
      }
    }, 3000);

    return () => clearInterval(timer);
  }, [runId, run?.status]);

  const handleApprove = async () => {
    if (!pendingApproval || actionLoading) return;
    try {
      setActionLoading(true);
      setActionError(null);
      await api.approve(pendingApproval.id, "SRE-Lead", "Approved via Control Center");
      await loadRunData();
    } catch (err: any) {
      if (err.status === 409) {
        setActionError("This approval has already been resolved.");
      } else {
        setActionError(err.message || "Failed to approve action");
      }
    } finally {
      setActionLoading(false);
    }
  };

  const handleReject = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!pendingApproval || !rejectionReason.trim() || actionLoading) return;
    try {
      setActionLoading(true);
      setActionError(null);
      await api.reject(pendingApproval.id, rejectionReason.trim(), "SRE-Lead");
      setRejectionModal(false);
      setRejectionReason("");
      await loadRunData();
    } catch (err: any) {
      if (err.status === 409) {
        setActionError("This approval has already been resolved.");
      } else {
        setActionError(err.message || "Failed to reject action");
      }
    } finally {
      setActionLoading(false);
    }
  };

  if (loading) return <LoadingSpinner label="Loading execution telemetry..." />;
  if (error || !run) return <ErrorState message={error || "Run not found"} onRetry={loadRunData} />;

  // Extract evidence list from plan or synthesis payload if present
  let evidenceList: EvidenceItem[] = [];
  if (events) {
    for (const ev of events) {
      if (ev.payload && ev.payload.evidence && Array.isArray(ev.payload.evidence)) {
        evidenceList = ev.payload.evidence;
      }
    }
  }

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Top Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <Link
            href="/runs"
            className="inline-flex items-center gap-1.5 text-xs font-mono text-gray-400 hover:text-gray-200 mb-2 transition-colors"
          >
            <ArrowLeft className="h-3.5 w-3.5" /> Back to Runs
          </Link>
          <div className="flex items-center gap-3">
            <h1 className="text-lg font-bold text-white font-mono flex items-center gap-2">
              <Bot className="h-5 w-5 text-blue-400" />
              RUN #{run.id.slice(0, 8)}
            </h1>
            <StatusBadge status={run.status} size="md" />
          </div>
        </div>

        <button
          onClick={loadRunData}
          className="inline-flex items-center gap-2 px-3 py-1.5 bg-gray-800 hover:bg-gray-750 text-gray-300 rounded-lg text-xs font-mono transition-colors self-start md:self-auto border border-gray-700"
        >
          <RefreshCw className="h-3.5 w-3.5" />
          Refresh
        </button>
      </div>

      {/* Query Bar */}
      <div className="p-4 rounded-xl border border-gray-800 bg-[#0e1422] space-y-2">
        <span className="text-[11px] font-mono uppercase text-gray-400">User Query:</span>
        <div className="text-sm font-semibold text-white leading-relaxed">{run.user_request}</div>
        <div className="flex flex-wrap items-center gap-4 text-xs font-mono text-gray-400 pt-1">
          <span>Started: {formatDate(run.created_at)}</span>
          <span>•</span>
          <span>Latency: {formatDuration(run.total_latency_ms)}</span>
          <span>•</span>
          <span>Tokens: {run.total_tokens || 0}</span>
          <span>•</span>
          <span>Tools Executed: {run.number_of_tool_calls || 0}</span>
        </div>
      </div>

      {/* Sensitive WRITE Action Gate Banner */}
      {run.status === "WAITING_APPROVAL" && pendingApproval && (
        <div className="p-5 rounded-xl border border-amber-500 bg-amber-950/40 space-y-4 shadow-lg">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div className="flex items-start gap-3">
              <div className="p-2 rounded-lg bg-amber-900/60 text-amber-300">
                <ShieldAlert className="h-6 w-6" />
              </div>
              <div>
                <h3 className="font-bold text-sm text-amber-300">
                  Human Approval Required Before Resuming
                </h3>
                <p className="text-xs text-amber-200 mt-0.5">{pendingApproval.reason}</p>
                <div className="text-xs font-mono text-amber-400 mt-1">
                  Tool: <strong>{pendingApproval.tool_name}</strong> (HIGH RISK WRITE OPERATION)
                </div>
              </div>
            </div>

            <div className="flex items-center gap-2 self-end sm:self-auto">
              <button
                onClick={() => setRejectionModal(true)}
                disabled={actionLoading}
                className="inline-flex items-center gap-1.5 px-3.5 py-1.5 bg-rose-950 hover:bg-rose-900 border border-rose-700 text-rose-200 rounded-lg text-xs font-semibold transition-colors disabled:opacity-50"
              >
                <X className="h-3.5 w-3.5" />
                Reject
              </button>
              <button
                onClick={handleApprove}
                disabled={actionLoading}
                className="inline-flex items-center gap-1.5 px-4 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-xs font-semibold transition-colors shadow-md shadow-emerald-600/20 disabled:opacity-50"
              >
                <Check className="h-3.5 w-3.5" />
                {actionLoading ? "Resuming Workflow..." : "Approve & Execute"}
              </button>
            </div>
          </div>

          {actionError && (
            <div className="p-2.5 rounded bg-rose-950/60 border border-rose-800 text-xs text-rose-300 font-mono">
              {actionError}
            </div>
          )}

          <div className="p-3 bg-gray-950 rounded-lg border border-gray-800 text-xs font-mono">
            <span className="text-gray-400 block mb-1 uppercase text-[10px]">
              Server-Side Sanitized Arguments:
            </span>
            <pre className="text-amber-300 overflow-x-auto">
              {JSON.stringify(pendingApproval.tool_args, null, 2)}
            </pre>
          </div>
        </div>
      )}

      {/* Final Synthesized Answer (if completed) */}
      {run.final_answer && (
        <div className="p-5 rounded-xl border border-emerald-800/80 bg-emerald-950/20 space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="font-bold text-sm text-emerald-400 flex items-center gap-2">
              <CheckCircle2 className="h-4 w-4" />
              Final Synthesized Response & Root Cause Analysis
            </h2>
            <span className="text-[11px] font-mono text-emerald-500">Grounded & Verified</span>
          </div>
          <div className="text-xs text-gray-200 leading-relaxed font-sans whitespace-pre-wrap bg-[#0c101a] p-4 rounded-lg border border-emerald-900/40">
            {run.final_answer}
          </div>
        </div>
      )}

      {/* Tabs */}
      <div className="flex items-center gap-2 border-b border-gray-800 pb-2">
        <button
          onClick={() => setActiveTab("graph")}
          className={`px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-colors ${
            activeTab === "graph"
              ? "bg-blue-600/20 text-blue-400 border border-blue-500/30"
              : "text-gray-400 hover:text-gray-200"
          }`}
        >
          Agent Graph & Trace ({events.length})
        </button>
        <button
          onClick={() => setActiveTab("tools")}
          className={`px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-colors ${
            activeTab === "tools"
              ? "bg-blue-600/20 text-blue-400 border border-blue-500/30"
              : "text-gray-400 hover:text-gray-200"
          }`}
        >
          Tool Executions ({run.tool_executions?.length || 0})
        </button>
        <button
          onClick={() => setActiveTab("evidence")}
          className={`px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-colors ${
            activeTab === "evidence"
              ? "bg-blue-600/20 text-blue-400 border border-blue-500/30"
              : "text-gray-400 hover:text-gray-200"
          }`}
        >
          Evidence & Provenance
        </button>
        <button
          onClick={() => setActiveTab("raw")}
          className={`px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-colors ${
            activeTab === "raw"
              ? "bg-blue-600/20 text-blue-400 border border-blue-500/30"
              : "text-gray-400 hover:text-gray-200"
          }`}
        >
          Raw Plan JSON
        </button>
      </div>

      {/* Tab Content */}
      <div className="pt-2">
        {activeTab === "graph" && <AgentGraphView run={run} events={events} />}
        {activeTab === "tools" && <ToolExecutionPanel tools={run.tool_executions} />}
        {activeTab === "evidence" && (
          <EvidencePanel
            evidence={evidenceList}
            warnings={run.final_answer?.includes("conflict") ? ["Discrepancy detected"] : []}
          />
        )}
        {activeTab === "raw" && (
          <pre className="p-4 rounded-xl bg-gray-950 border border-gray-800 text-xs font-mono text-gray-300 overflow-x-auto">
            {JSON.stringify(run.plan, null, 2)}
          </pre>
        )}
      </div>

      {/* Reject Modal */}
      {rejectionModal && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-[#0e1422] border border-gray-800 rounded-2xl w-full max-w-md p-6 shadow-2xl">
            <h3 className="font-bold text-base text-white mb-2">Reject Sensitive Action</h3>
            <p className="text-xs text-gray-400 mb-4">
              Please state the reason for rejecting the action. The agent will safely observe this
              rejection and resume final synthesis.
            </p>

            <form onSubmit={handleReject} className="space-y-4">
              <div>
                <label className="block text-[11px] font-mono uppercase text-gray-400 mb-1">
                  Rejection Reason:
                </label>
                <textarea
                  rows={3}
                  value={rejectionReason}
                  onChange={(e) => setRejectionReason(e.target.value)}
                  placeholder="e.g. Action not permitted during freeze period."
                  required
                  className="w-full px-3 py-2 bg-gray-900 border border-gray-800 rounded-lg text-xs text-gray-200 placeholder-gray-500 focus:outline-none focus:border-rose-500 font-mono"
                />
              </div>

              <div className="flex items-center justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setRejectionModal(false)}
                  className="px-3.5 py-1.5 bg-gray-800 hover:bg-gray-700 text-gray-300 rounded-lg text-xs font-semibold"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={actionLoading || !rejectionReason.trim()}
                  className="px-4 py-1.5 bg-rose-600 hover:bg-rose-500 text-white rounded-lg text-xs font-semibold disabled:opacity-50"
                >
                  {actionLoading ? "Rejecting..." : "Confirm Rejection"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
