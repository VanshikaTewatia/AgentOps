"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api/client";
import { IncidentItem } from "@/lib/types";
import { formatDate } from "@/lib/utils";
import {
  StatusBadge,
  LoadingSpinner,
  ErrorState,
  EmptyState,
} from "@/components/common/StateComponents";
import { AlertTriangle, Clock, RefreshCw, Server, MessageSquare } from "lucide-react";

export default function IncidentsPage() {
  const [incidents, setIncidents] = useState<IncidentItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const loadIncidents = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await api.listIncidents();
      setIncidents(data);
    } catch (err: any) {
      setError(err.message || "Failed to load operational incidents");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadIncidents();
  }, []);

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-white tracking-tight flex items-center gap-2">
            <AlertTriangle className="h-5 w-5 text-rose-400" />
            Operational Incident Registry
          </h1>
          <p className="text-xs text-gray-400 mt-1">
            Real-time incident records, triage notes, and automated post-mortem diagnoses.
          </p>
        </div>

        <button
          onClick={loadIncidents}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-gray-800 hover:bg-gray-750 text-gray-300 rounded-lg text-xs font-mono transition-colors self-start sm:self-auto border border-gray-700"
        >
          <RefreshCw className="h-3.5 w-3.5" />
          Refresh
        </button>
      </div>

      {/* Incidents Grid */}
      {loading ? (
        <LoadingSpinner label="Loading operational incidents..." />
      ) : error ? (
        <ErrorState message={error} onRetry={loadIncidents} />
      ) : incidents.length === 0 ? (
        <EmptyState
          title="No Incidents Found"
          description="There are currently no active or historical incidents recorded in PostgreSQL."
        />
      ) : (
        <div className="space-y-4">
          {incidents.map((inc) => (
            <div
              key={inc.id}
              className="p-5 rounded-xl border border-gray-800 bg-[#0e1422] space-y-3 hover:border-gray-700 transition-colors"
            >
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-mono font-bold text-gray-400 bg-gray-900 px-2 py-0.5 rounded border border-gray-800">
                    ID: {inc.id.slice(0, 8)}
                  </span>
                  <StatusBadge status={inc.severity} />
                  <StatusBadge status={inc.status} />
                </div>
                <div className="text-[11px] font-mono text-gray-500">
                  Created: {formatDate(inc.created_at)}
                </div>
              </div>

              <div>
                <h3 className="text-sm font-bold text-white">{inc.title}</h3>
                <p className="text-xs text-gray-300 mt-1 leading-relaxed">{inc.description}</p>
              </div>

              {/* Service & Meta */}
              <div className="flex flex-wrap items-center gap-4 text-xs font-mono text-gray-400 pt-1">
                <span className="flex items-center gap-1 text-blue-400">
                  <Server className="h-3.5 w-3.5" /> Service: {inc.service_name || "infrastructure"}
                </span>
                {inc.root_cause && (
                  <span className="text-amber-300">Root Cause: {inc.root_cause}</span>
                )}
              </div>

              {/* Comments / Triage Notes */}
              {inc.comments && inc.comments.length > 0 && (
                <div className="p-3 bg-gray-950 rounded-lg border border-gray-850 space-y-2">
                  <span className="text-[10px] font-mono uppercase text-gray-400 flex items-center gap-1">
                    <MessageSquare className="h-3 w-3" /> Triage Comments ({inc.comments.length}):
                  </span>
                  <div className="space-y-1.5">
                    {inc.comments.map((c: any, i: number) => {
                      const text = typeof c === "object" ? c.comment : c;
                      const author = typeof c === "object" ? c.author : "Agent";
                      return (
                        <div key={i} className="text-xs text-gray-300 font-sans">
                          <strong className="text-blue-400 font-mono text-[11px]">{author}:</strong>{" "}
                          {text}
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
