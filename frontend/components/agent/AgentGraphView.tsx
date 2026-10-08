"use client";

import { AgentEvent, AgentRun } from "@/lib/types";
import { formatDuration, formatDate } from "@/lib/utils";
import {
  Bot,
  CheckCircle2,
  Clock,
  Compass,
  FileSearch,
  Layers,
  ShieldCheck,
  Terminal,
  User,
  Wrench,
  XCircle,
} from "lucide-react";

interface AgentGraphProps {
  run: AgentRun;
  events?: AgentEvent[] | null;
}

export function AgentGraphView({ run, events }: AgentGraphProps) {
  const eventsList = events || [];

  return (
    <div className="space-y-6">
      {/* Node Flow Diagram */}
      <div className="p-6 rounded-xl border border-gray-800 bg-[#0c101a] overflow-x-auto">
        <div className="flex items-center min-w-[700px] justify-between relative">
          {/* Connector Line */}
          <div className="absolute top-1/2 left-8 right-8 h-0.5 bg-gray-800 -translate-y-1/2 z-0" />

          {/* Node 1: User Request */}
          <div className="relative z-10 flex flex-col items-center text-center">
            <div className="h-12 w-12 rounded-xl bg-blue-950 border border-blue-700 flex items-center justify-center text-blue-400 shadow-md">
              <User className="h-5 w-5" />
            </div>
            <span className="text-xs font-mono font-bold text-gray-200 mt-2">USER</span>
            <span className="text-[10px] font-mono text-gray-500">Inquiry</span>
          </div>

          {/* Node 2: Supervisor / Planner */}
          <div className="relative z-10 flex flex-col items-center text-center">
            <div className="h-12 w-12 rounded-xl bg-indigo-950 border border-indigo-700 flex items-center justify-center text-indigo-400 shadow-md">
              <Compass className="h-5 w-5" />
            </div>
            <span className="text-xs font-mono font-bold text-indigo-300 mt-2">SUPERVISOR</span>
            <span className="text-[10px] font-mono text-gray-500">Planning & Route</span>
          </div>

          {/* Node 3: Multi-Agent Execution */}
          <div className="relative z-10 flex flex-col items-center text-center">
            <div className="h-12 w-12 rounded-xl bg-purple-950 border border-purple-700 flex items-center justify-center text-purple-400 shadow-md">
              <Bot className="h-5 w-5" />
            </div>
            <span className="text-xs font-mono font-bold text-purple-300 mt-2">SPECIALISTS</span>
            <span className="text-[10px] font-mono text-gray-500">Diagnostic / RAG</span>
          </div>

          {/* Node 4: Approval Gate */}
          <div className="relative z-10 flex flex-col items-center text-center">
            <div
              className={`h-12 w-12 rounded-xl border flex items-center justify-center shadow-md ${
                run.status === "WAITING_APPROVAL"
                  ? "bg-amber-950 border-amber-500 text-amber-400 animate-pulse"
                  : "bg-gray-900 border-gray-700 text-gray-400"
              }`}
            >
              <ShieldCheck className="h-5 w-5" />
            </div>
            <span className="text-xs font-mono font-bold text-amber-300 mt-2">APPROVAL</span>
            <span className="text-[10px] font-mono text-gray-500">
              {run.status === "WAITING_APPROVAL" ? "ACTION REQUIRED" : "Security Gate"}
            </span>
          </div>

          {/* Node 5: Synthesis & Response */}
          <div className="relative z-10 flex flex-col items-center text-center">
            <div
              className={`h-12 w-12 rounded-xl border flex items-center justify-center shadow-md ${
                run.status === "COMPLETED"
                  ? "bg-emerald-950 border-emerald-600 text-emerald-400"
                  : "bg-gray-900 border-gray-700 text-gray-400"
              }`}
            >
              <CheckCircle2 className="h-5 w-5" />
            </div>
            <span className="text-xs font-mono font-bold text-emerald-300 mt-2">SYNTHESIS</span>
            <span className="text-[10px] font-mono text-gray-500">Grounded Output</span>
          </div>
        </div>
      </div>

      {/* Execution Timeline */}
      <div className="space-y-3">
        <h3 className="text-xs font-mono uppercase tracking-wider text-gray-400">
          Execution Trace Timeline ({eventsList.length} Trace Events)
        </h3>

        {eventsList.length === 0 ? (
          <div className="p-4 text-xs font-mono text-gray-500 bg-gray-900/30 rounded-lg border border-gray-800">
            No trace events recorded yet.
          </div>
        ) : (
          <div className="relative pl-6 border-l-2 border-gray-800 space-y-4 my-2">
            {eventsList.map((ev, i) => (
              <div key={ev.id || i} className="relative">
                {/* Bullet */}
                <div className="absolute -left-[31px] top-1 h-3.5 w-3.5 rounded-full bg-blue-600 border-2 border-gray-950" />

                <div className="p-3 rounded-lg border border-gray-800 bg-[#0e1422]">
                  <div className="flex items-center justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-mono font-bold text-blue-400">
                        {ev.node_name}
                      </span>
                      <span className="text-[10px] font-mono text-gray-500 uppercase px-1.5 py-0.5 rounded bg-gray-900 border border-gray-800">
                        {ev.event_type}
                      </span>
                    </div>
                    <div className="text-[11px] font-mono text-gray-500">
                      {formatDuration(ev.duration_ms)} • {formatDate(ev.created_at)}
                    </div>
                  </div>

                  {ev.payload && Object.keys(ev.payload).length > 0 && (
                    <pre className="mt-2 p-2 rounded bg-gray-950 text-[11px] font-mono text-gray-300 overflow-x-auto max-h-36">
                      {JSON.stringify(ev.payload, null, 2)}
                    </pre>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
