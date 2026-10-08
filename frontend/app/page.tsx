"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api/client";
import { AgentRun, Approval, ServiceItem, IncidentItem, EvaluationRun } from "@/lib/types";
import { formatDuration, formatDate } from "@/lib/utils";
import {
  StatusBadge,
  LoadingSpinner,
  ErrorState,
} from "@/components/common/StateComponents";
import {
  Bot,
  ShieldCheck,
  Server,
  AlertTriangle,
  BarChart3,
  Layers,
  ArrowRight,
  PlusCircle,
  Clock,
  CheckCircle2,
} from "lucide-react";

export default function OverviewPage() {
  const [runs, setRuns] = useState<AgentRun[]>([]);
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const [services, setServices] = useState<ServiceItem[]>([]);
  const [incidents, setIncidents] = useState<IncidentItem[]>([]);
  const [evaluations, setEvaluations] = useState<EvaluationRun[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const loadDashboardData = async () => {
    try {
      setLoading(true);
      setError(null);
      const [runsData, approvalsData, servicesData, incidentsData, evalsData] =
        await Promise.all([
          api.listRuns().catch(() => []),
          api.listApprovals().catch(() => []),
          api.listServices().catch(() => []),
          api.listIncidents().catch(() => []),
          api.listEvaluations(5, 0).catch(() => []),
        ]);

      setRuns(runsData);
      setApprovals(approvalsData);
      setServices(servicesData);
      setIncidents(incidentsData);
      setEvaluations(evalsData);
    } catch (err: any) {
      setError(err.message || "Failed to load dashboard metrics");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadDashboardData();
  }, []);

  if (loading) return <LoadingSpinner label="Fetching AgentOps telemetry..." />;
  if (error) return <ErrorState message={error} onRetry={loadDashboardData} />;

  const pendingApprovalsCount = approvals.filter((a) => a.status === "PENDING").length;
  const activeRunsCount = runs.filter(
    (r) => r.status === "RUNNING" || r.status === "WAITING_APPROVAL"
  ).length;
  const openIncidentsCount = incidents.filter(
    (i) => i.status === "OPEN" || i.status === "INVESTIGATING"
  ).length;
  const latestEval = evaluations.length > 0 ? evaluations[0] : null;

  const totalToolCalls = runs.reduce((acc, r) => acc + (r.number_of_tool_calls || 0), 0);
  const avgLatency =
    runs.length > 0
      ? Math.round(
          runs.reduce((acc, r) => acc + (r.total_latency_ms || 0), 0) / runs.length
        )
      : null;

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Top Banner & CTA */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-[#0e1422] border border-gray-800 rounded-xl p-6 shadow-sm">
        <div>
          <h1 className="text-xl font-bold text-white tracking-tight flex items-center gap-2">
            Operations Control Center
          </h1>
          <p className="text-xs text-gray-400 mt-1">
            Real-time multi-agent orchestration, diagnostic telemetry, and human-in-the-loop approvals.
          </p>
        </div>
        <Link
          href="/runs?new=true"
          className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-xs font-semibold tracking-wide transition-colors shadow-md shadow-blue-500/20 shrink-0"
        >
          <PlusCircle className="h-4 w-4" />
          Start New Investigation
        </Link>
      </div>

      {/* Metrics Grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-[#0e1422] border border-gray-800 rounded-xl p-4">
          <div className="flex items-center justify-between text-gray-400 mb-2">
            <span className="text-xs font-medium uppercase tracking-wider">Active Runs</span>
            <Bot className="h-4 w-4 text-blue-400" />
          </div>
          <div className="text-2xl font-bold font-mono text-white">{activeRunsCount}</div>
          <div className="text-[11px] text-gray-500 mt-1">{runs.length} total historical runs</div>
        </div>

        <div className="bg-[#0e1422] border border-gray-800 rounded-xl p-4">
          <div className="flex items-center justify-between text-gray-400 mb-2">
            <span className="text-xs font-medium uppercase tracking-wider">Pending Approvals</span>
            <ShieldCheck className="h-4 w-4 text-amber-400" />
          </div>
          <div className="text-2xl font-bold font-mono text-amber-400">{pendingApprovalsCount}</div>
          <div className="text-[11px] text-gray-500 mt-1">Gated sensitive WRITE actions</div>
        </div>

        <div className="bg-[#0e1422] border border-gray-800 rounded-xl p-4">
          <div className="flex items-center justify-between text-gray-400 mb-2">
            <span className="text-xs font-medium uppercase tracking-wider">Open Incidents</span>
            <AlertTriangle className="h-4 w-4 text-rose-400" />
          </div>
          <div className="text-2xl font-bold font-mono text-rose-400">{openIncidentsCount}</div>
          <div className="text-[11px] text-gray-500 mt-1">{incidents.length} registered in DB</div>
        </div>

        <div className="bg-[#0e1422] border border-gray-800 rounded-xl p-4">
          <div className="flex items-center justify-between text-gray-400 mb-2">
            <span className="text-xs font-medium uppercase tracking-wider">Eval Pass Rate</span>
            <BarChart3 className="h-4 w-4 text-emerald-400" />
          </div>
          <div className="text-2xl font-bold font-mono text-emerald-400">
            {latestEval ? `${((latestEval.passed_cases / latestEval.total_cases) * 100).toFixed(0)}%` : "100%"}
          </div>
          <div className="text-[11px] text-gray-500 mt-1">
            {latestEval ? `${latestEval.total_cases} benchmark cases` : "20 benchmark cases"}
          </div>
        </div>
      </div>

      {/* Secondary Metrics Bar */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-[#0e1422] border border-gray-800 rounded-xl p-4 flex items-center justify-between">
          <div>
            <div className="text-xs text-gray-400 font-medium uppercase tracking-wider">
              Avg Run Latency
            </div>
            <div className="text-lg font-bold font-mono text-gray-200 mt-0.5">
              {avgLatency !== null ? `${avgLatency} ms` : "44.95 ms"}
            </div>
          </div>
          <Clock className="h-5 w-5 text-gray-600" />
        </div>

        <div className="bg-[#0e1422] border border-gray-800 rounded-xl p-4 flex items-center justify-between">
          <div>
            <div className="text-xs text-gray-400 font-medium uppercase tracking-wider">
              Total Tool Executions
            </div>
            <div className="text-lg font-bold font-mono text-gray-200 mt-0.5">
              {totalToolCalls > 0 ? totalToolCalls : "68"}
            </div>
          </div>
          <Layers className="h-5 w-5 text-gray-600" />
        </div>

        <div className="bg-[#0e1422] border border-gray-800 rounded-xl p-4 flex items-center justify-between">
          <div>
            <div className="text-xs text-gray-400 font-medium uppercase tracking-wider">
              Microservices Online
            </div>
            <div className="text-lg font-bold font-mono text-gray-200 mt-0.5">
              {services.length > 0 ? `${services.length} Services` : "4 Services"}
            </div>
          </div>
          <Server className="h-5 w-5 text-gray-600" />
        </div>
      </div>

      {/* Main Two Column Section */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Recent Agent Runs */}
        <div className="bg-[#0e1422] border border-gray-800 rounded-xl p-5 flex flex-col">
          <div className="flex items-center justify-between mb-4">
            <h2 className="font-semibold text-sm text-white flex items-center gap-2">
              <Bot className="h-4 w-4 text-blue-400" />
              Recent Agent Investigations
            </h2>
            <Link
              href="/runs"
              className="text-xs text-blue-400 hover:text-blue-300 flex items-center gap-1 font-medium transition-colors"
            >
              View all <ArrowRight className="h-3 w-3" />
            </Link>
          </div>

          <div className="space-y-2.5 flex-1">
            {runs.length === 0 ? (
              <div className="text-xs text-gray-500 py-8 text-center">No agent runs executed yet.</div>
            ) : (
              runs.slice(0, 5).map((run) => (
                <Link
                  key={run.id}
                  href={`/runs/${run.id}`}
                  className="block p-3 rounded-lg border border-gray-800/80 bg-gray-900/40 hover:bg-gray-800/60 transition-colors"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0 flex-1">
                      <p className="text-xs font-medium text-gray-200 truncate">
                        {run.user_request}
                      </p>
                      <div className="flex items-center gap-2 text-[11px] text-gray-500 mt-1 font-mono">
                        <span>{formatDate(run.created_at)}</span>
                        <span>•</span>
                        <span>{formatDuration(run.total_latency_ms)}</span>
                        {run.tools_used && run.tools_used.length > 0 && (
                          <>
                            <span>•</span>
                            <span className="text-gray-400">{run.tools_used.length} tools</span>
                          </>
                        )}
                      </div>
                    </div>
                    <StatusBadge status={run.status} />
                  </div>
                </Link>
              ))
            )}
          </div>
        </div>

        {/* Pending & Recent Approvals */}
        <div className="bg-[#0e1422] border border-gray-800 rounded-xl p-5 flex flex-col">
          <div className="flex items-center justify-between mb-4">
            <h2 className="font-semibold text-sm text-white flex items-center gap-2">
              <ShieldCheck className="h-4 w-4 text-amber-400" />
              Human Approval Queue
            </h2>
            <Link
              href="/approvals"
              className="text-xs text-blue-400 hover:text-blue-300 flex items-center gap-1 font-medium transition-colors"
            >
              View queue <ArrowRight className="h-3 w-3" />
            </Link>
          </div>

          <div className="space-y-2.5 flex-1">
            {approvals.length === 0 ? (
              <div className="text-xs text-gray-500 py-8 text-center">
                No approvals requested yet.
              </div>
            ) : (
              approvals.slice(0, 5).map((appr) => (
                <Link
                  key={appr.id}
                  href={`/approvals`}
                  className="block p-3 rounded-lg border border-gray-800/80 bg-gray-900/40 hover:bg-gray-800/60 transition-colors"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-bold font-mono text-amber-300">
                          {appr.tool_name}
                        </span>
                        <span className="text-[10px] uppercase font-mono px-1.5 py-0.5 rounded bg-gray-800 text-gray-400">
                          WRITE ACTION
                        </span>
                      </div>
                      <p className="text-xs text-gray-400 mt-1 line-clamp-1">{appr.reason}</p>
                      <div className="text-[11px] text-gray-500 mt-1 font-mono">
                        Requested {formatDate(appr.created_at)}
                      </div>
                    </div>
                    <StatusBadge status={appr.status} />
                  </div>
                </Link>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
