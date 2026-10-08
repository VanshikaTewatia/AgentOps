"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api/client";
import { Approval } from "@/lib/types";
import { formatDate } from "@/lib/utils";
import {
  StatusBadge,
  LoadingSpinner,
  ErrorState,
  EmptyState,
} from "@/components/common/StateComponents";
import {
  ShieldCheck,
  Check,
  X,
  AlertTriangle,
  RefreshCw,
  Terminal,
  ExternalLink,
  Filter,
} from "lucide-react";

export default function ApprovalsPage() {
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<string>("ALL");

  // Approval / Reject modal action state
  const [actionLoading, setActionLoading] = useState<boolean>(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [activeRejectAppr, setActiveRejectAppr] = useState<Approval | null>(null);
  const [rejectionReason, setRejectionReason] = useState<string>("");

  const loadApprovals = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await api.listApprovals(
        statusFilter === "ALL" ? undefined : statusFilter
      );
      setApprovals(data);
    } catch (err: any) {
      setError(err.message || "Failed to load approval requests");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadApprovals();
  }, [statusFilter]);

  const handleApprove = async (approval: Approval) => {
    if (actionLoading) return;
    try {
      setActionLoading(true);
      setActionError(null);
      await api.approve(approval.id, "SRE-Lead", "Approved via Control Center");
      await loadApprovals();
    } catch (err: any) {
      if (err.status === 409) {
        setActionError("This approval has already been resolved.");
      } else {
        setActionError(err.message || "Failed to approve request");
      }
    } finally {
      setActionLoading(false);
    }
  };

  const handleReject = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeRejectAppr || !rejectionReason.trim() || actionLoading) return;
    try {
      setActionLoading(true);
      setActionError(null);
      await api.reject(activeRejectAppr.id, rejectionReason.trim(), "SRE-Lead");
      setActiveRejectAppr(null);
      setRejectionReason("");
      await loadApprovals();
    } catch (err: any) {
      if (err.status === 409) {
        setActionError("This approval has already been resolved.");
      } else {
        setActionError(err.message || "Failed to reject request");
      }
    } finally {
      setActionLoading(false);
    }
  };

  const pendingApprovals = approvals.filter((a) => a.status === "PENDING");

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-white tracking-tight flex items-center gap-2">
            <ShieldCheck className="h-5 w-5 text-amber-400" />
            Human Approval Center
          </h1>
          <p className="text-xs text-gray-400 mt-1">
            Gated review and authorization for high-impact WRITE actions (e.g. incident creation, comment triage).
          </p>
        </div>

        <button
          onClick={loadApprovals}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-gray-800 hover:bg-gray-750 text-gray-300 rounded-lg text-xs font-mono transition-colors self-start sm:self-auto border border-gray-700"
        >
          <RefreshCw className="h-3.5 w-3.5" />
          Refresh
        </button>
      </div>

      {actionError && (
        <div className="p-3 bg-rose-950/50 border border-rose-800 rounded-xl text-xs text-rose-300 font-mono">
          {actionError}
        </div>
      )}

      {/* Filter Tabs */}
      <div className="flex items-center gap-2 border-b border-gray-800 pb-3">
        <button
          onClick={() => setStatusFilter("ALL")}
          className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors ${
            statusFilter === "ALL"
              ? "bg-blue-600/20 text-blue-400 border border-blue-500/30"
              : "text-gray-400 hover:text-gray-200"
          }`}
        >
          All Requests ({approvals.length})
        </button>
        <button
          onClick={() => setStatusFilter("PENDING")}
          className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors ${
            statusFilter === "PENDING"
              ? "bg-amber-600/20 text-amber-400 border border-amber-500/30"
              : "text-gray-400 hover:text-gray-200"
          }`}
        >
          Pending Review ({pendingApprovals.length})
        </button>
        <button
          onClick={() => setStatusFilter("APPROVED")}
          className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors ${
            statusFilter === "APPROVED"
              ? "bg-emerald-600/20 text-emerald-400 border border-emerald-500/30"
              : "text-gray-400 hover:text-gray-200"
          }`}
        >
          Approved
        </button>
        <button
          onClick={() => setStatusFilter("REJECTED")}
          className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors ${
            statusFilter === "REJECTED"
              ? "bg-rose-600/20 text-rose-400 border border-rose-500/30"
              : "text-gray-400 hover:text-gray-200"
          }`}
        >
          Rejected
        </button>
      </div>

      {/* Approvals List */}
      {loading ? (
        <LoadingSpinner label="Fetching approval queue..." />
      ) : error ? (
        <ErrorState message={error} onRetry={loadApprovals} />
      ) : approvals.length === 0 ? (
        <EmptyState
          title="No Approvals Found"
          description="There are currently no pending or historical human approval requests."
        />
      ) : (
        <div className="space-y-4">
          {approvals.map((appr) => {
            const isPending = appr.status === "PENDING";
            return (
              <div
                key={appr.id}
                className={`p-5 rounded-xl border transition-all ${
                  isPending
                    ? "border-amber-600/60 bg-amber-950/20 shadow-md shadow-amber-950/30"
                    : "border-gray-800 bg-[#0e1422]"
                }`}
              >
                <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                  <div className="flex-1 space-y-2">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-xs font-bold font-mono text-white flex items-center gap-1.5">
                        <Terminal className="h-4 w-4 text-blue-400" />
                        {appr.tool_name}
                      </span>
                      <span className="text-[10px] uppercase font-mono px-2 py-0.5 rounded bg-amber-950/80 text-amber-300 border border-amber-800">
                        SENSITIVE WRITE ACTION
                      </span>
                      <StatusBadge status={appr.status} />
                    </div>

                    <p className="text-xs text-gray-200">{appr.reason}</p>

                    <div className="flex flex-wrap items-center gap-3 text-[11px] font-mono text-gray-400">
                      <span>
                        Run:{" "}
                        <Link
                          href={`/runs/${appr.run_id}`}
                          className="text-blue-400 hover:underline inline-flex items-center gap-0.5"
                        >
                          #{appr.run_id.slice(0, 8)} <ExternalLink className="h-2.5 w-2.5" />
                        </Link>
                      </span>
                      <span>•</span>
                      <span>Requested: {formatDate(appr.created_at)}</span>
                      {appr.decided_by && (
                        <>
                          <span>•</span>
                          <span className="text-gray-300">
                            Decided by: <strong>{appr.decided_by}</strong> (
                            {formatDate(appr.decided_at)})
                          </span>
                        </>
                      )}
                    </div>

                    {appr.rejection_reason && (
                      <div className="text-xs text-rose-300 font-mono mt-1">
                        Reason: {appr.rejection_reason}
                      </div>
                    )}
                  </div>

                  {/* Actions */}
                  {isPending && (
                    <div className="flex items-center gap-2 shrink-0">
                      <button
                        onClick={() => setActiveRejectAppr(appr)}
                        disabled={actionLoading}
                        className="inline-flex items-center gap-1.5 px-3.5 py-2 bg-rose-950 hover:bg-rose-900 border border-rose-700 text-rose-200 rounded-lg text-xs font-semibold transition-colors disabled:opacity-50"
                      >
                        <X className="h-3.5 w-3.5" />
                        Reject
                      </button>
                      <button
                        onClick={() => handleApprove(appr)}
                        disabled={actionLoading}
                        className="inline-flex items-center gap-1.5 px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-xs font-semibold transition-colors shadow-md shadow-emerald-600/20 disabled:opacity-50"
                      >
                        <Check className="h-3.5 w-3.5" />
                        {actionLoading ? "Resuming..." : "Approve"}
                      </button>
                    </div>
                  )}
                </div>

                {/* Sanitized Args View */}
                <div className="mt-3 pt-3 border-t border-gray-800/80">
                  <span className="text-[10px] font-mono uppercase text-gray-500 block mb-1">
                    Sanitized Parameters:
                  </span>
                  <pre className="p-2 rounded bg-gray-950 border border-gray-850 text-[11px] font-mono text-emerald-400 overflow-x-auto max-h-32">
                    {JSON.stringify(appr.tool_args, null, 2)}
                  </pre>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Reject Reason Modal */}
      {activeRejectAppr && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-[#0e1422] border border-gray-800 rounded-2xl w-full max-w-md p-6 shadow-2xl">
            <h3 className="font-bold text-base text-white mb-2">Reject Sensitive Action</h3>
            <p className="text-xs text-gray-400 mb-4">
              State the reason for rejecting <strong>{activeRejectAppr.tool_name}</strong>. The
              agent workflow will safely handle this rejection.
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
                  placeholder="e.g. Action forbidden during active migration."
                  required
                  className="w-full px-3 py-2 bg-gray-900 border border-gray-800 rounded-lg text-xs text-gray-200 placeholder-gray-500 focus:outline-none focus:border-rose-500 font-mono"
                />
              </div>

              <div className="flex items-center justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setActiveRejectAppr(null)}
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
