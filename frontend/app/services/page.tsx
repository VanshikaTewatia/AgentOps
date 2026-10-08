"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api/client";
import { ServiceItem } from "@/lib/types";
import { formatDate } from "@/lib/utils";
import {
  StatusBadge,
  LoadingSpinner,
  ErrorState,
  EmptyState,
} from "@/components/common/StateComponents";
import { Server, ExternalLink, RefreshCw, Cpu, Database, Activity } from "lucide-react";

export default function ServicesPage() {
  const [services, setServices] = useState<ServiceItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const loadServices = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await api.listServices();
      setServices(data);
    } catch (err: any) {
      setError(err.message || "Failed to load services");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadServices();
  }, []);

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-white tracking-tight flex items-center gap-2">
            <Server className="h-5 w-5 text-blue-400" />
            Infrastructure & Microservices Telemetry
          </h1>
          <p className="text-xs text-gray-400 mt-1">
            Core production microservices, health indicators, ownership metadata, and active runbooks.
          </p>
        </div>

        <button
          onClick={loadServices}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-gray-800 hover:bg-gray-750 text-gray-300 rounded-lg text-xs font-mono transition-colors self-start sm:self-auto border border-gray-700"
        >
          <RefreshCw className="h-3.5 w-3.5" />
          Refresh
        </button>
      </div>

      {/* Services Grid */}
      {loading ? (
        <LoadingSpinner label="Querying service registry..." />
      ) : error ? (
        <ErrorState message={error} onRetry={loadServices} />
      ) : services.length === 0 ? (
        <EmptyState
          title="No Services Registered"
          description="There are currently no registered microservices in the database."
        />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {services.map((svc) => (
            <div
              key={svc.id}
              className="p-5 rounded-xl border border-gray-800 bg-[#0e1422] space-y-4 hover:border-gray-700 transition-colors"
            >
              <div className="flex items-start justify-between gap-3">
                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="font-bold text-sm text-white font-mono">{svc.name}</h3>
                    <StatusBadge status={svc.status} />
                  </div>
                  <p className="text-xs text-gray-400 mt-1">{svc.description}</p>
                </div>
              </div>

              {/* Ownership & Repo */}
              <div className="grid grid-cols-2 gap-2 text-xs font-mono bg-gray-950/60 p-3 rounded-lg border border-gray-850">
                <div>
                  <span className="text-gray-500 uppercase text-[10px] block">Owner Team:</span>
                  <span className="text-gray-200">{svc.owner_team}</span>
                </div>
                <div>
                  <span className="text-gray-500 uppercase text-[10px] block">Repository:</span>
                  {svc.repository_url ? (
                    <a
                      href={svc.repository_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-blue-400 hover:underline inline-flex items-center gap-1 truncate max-w-[150px]"
                    >
                      {svc.name} <ExternalLink className="h-2.5 w-2.5 shrink-0" />
                    </a>
                  ) : (
                    <span className="text-gray-500">None</span>
                  )}
                </div>
              </div>

              {/* Footer */}
              <div className="flex items-center justify-between text-[11px] font-mono text-gray-500 pt-1">
                <span>Registered: {formatDate(svc.created_at)}</span>
                <span className="text-emerald-400 flex items-center gap-1">
                  <Activity className="h-3 w-3" /> Monitored
                </span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
