"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api/client";
import { HealthStatus } from "@/lib/types";
import { Activity, ShieldCheck, RefreshCw } from "lucide-react";

export function Header() {
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);

  const fetchHealth = async () => {
    try {
      setIsRefreshing(true);
      const data = await api.getHealth();
      setHealth(data);
    } catch {
      setHealth(null);
    } finally {
      setLoading(false);
      setIsRefreshing(false);
    }
  };

  useEffect(() => {
    fetchHealth();
    const timer = setInterval(fetchHealth, 15000);
    return () => clearInterval(timer);
  }, []);

  return (
    <header className="h-16 border-b border-gray-800 bg-[#0c121e]/80 backdrop-blur-md px-6 flex items-center justify-between shrink-0">
      <div className="flex items-center gap-3">
        <span className="text-xs font-mono uppercase tracking-wider text-gray-400">
          Agent Control Center
        </span>
        <span className="text-gray-600">/</span>
        <span className="text-xs font-mono text-gray-300">FastAPI LangGraph PGVector</span>
      </div>

      <div className="flex items-center gap-4 text-xs font-mono">
        {/* Environment Badge */}
        <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-gray-800/80 border border-gray-700 text-gray-300">
          <span className="text-gray-400">ENV:</span>
          <span className="font-semibold text-blue-400">
            {health?.environment ? health.environment.toUpperCase() : "DEVELOPMENT"}
          </span>
        </div>

        {/* Execution Policy Badge */}
        <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-amber-950/40 border border-amber-800/60 text-amber-300">
          <ShieldCheck className="h-3.5 w-3.5 text-amber-400" />
          <span>POLICY:</span>
          <span className="font-bold">ASSISTED</span>
        </div>

        {/* Backend Connection Indicator */}
        <div className="flex items-center gap-2 px-2.5 py-1 rounded-md bg-gray-800/80 border border-gray-700">
          <Activity
            className={`h-3.5 w-3.5 ${
              health?.status === "healthy" ? "text-emerald-400 animate-pulse" : "text-rose-400"
            }`}
          />
          <span className={health?.status === "healthy" ? "text-emerald-400" : "text-rose-400"}>
            {loading
              ? "CONNECTING..."
              : health?.status === "healthy"
              ? "BACKEND ONLINE"
              : "OFFLINE"}
          </span>
        </div>

        {/* Manual Refresh */}
        <button
          onClick={fetchHealth}
          disabled={isRefreshing}
          className="p-1.5 rounded-md hover:bg-gray-800 text-gray-400 hover:text-gray-200 transition-colors"
          title="Refresh Health"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${isRefreshing ? "animate-spin text-blue-400" : ""}`} />
        </button>
      </div>
    </header>
  );
}
