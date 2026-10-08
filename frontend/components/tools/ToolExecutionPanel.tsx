"use client";

import { ToolExecution } from "@/lib/types";
import { formatDuration } from "@/lib/utils";
import { StatusBadge } from "@/components/common/StateComponents";
import { ChevronDown, ChevronRight, Terminal, Wrench } from "lucide-react";
import { useState } from "react";

export function ToolExecutionPanel({ tools }: { tools?: ToolExecution[] | null }) {
  const [expandedId, setExpandedId] = useState<string | null>(null);

  if (!tools || tools.length === 0) {
    return (
      <div className="p-6 text-center text-xs text-gray-500 font-mono border border-gray-800 rounded-xl bg-gray-900/20">
        No tool calls executed for this run.
      </div>
    );
  }

  const toggleExpand = (id: string) => {
    setExpandedId(expandedId === id ? null : id);
  };

  return (
    <div className="space-y-3">
      {tools.map((tool) => {
        const isExpanded = expandedId === tool.id;
        const isWrite = ["create_incident", "add_incident_comment"].includes(tool.tool_name);
        const riskLevel = tool.tool_name === "create_incident" ? "HIGH" : isWrite ? "MEDIUM" : "LOW";

        return (
          <div
            key={tool.id}
            className="rounded-xl border border-gray-800 bg-gray-900/40 overflow-hidden transition-all"
          >
            {/* Clickable Header */}
            <div
              onClick={() => toggleExpand(tool.id)}
              className="p-4 flex items-center justify-between cursor-pointer hover:bg-gray-800/40 transition-colors"
            >
              <div className="flex items-center gap-3 min-w-0">
                <div className="p-2 rounded-lg bg-gray-800 text-gray-300">
                  <Terminal className="h-4 w-4 text-blue-400" />
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-bold font-mono text-white">
                      {tool.tool_name}
                    </span>
                    <span
                      className={`text-[10px] font-mono px-1.5 py-0.5 rounded border ${
                        isWrite
                          ? "bg-amber-950/60 text-amber-300 border-amber-800"
                          : "bg-blue-950/60 text-blue-300 border-blue-800"
                      }`}
                    >
                      {isWrite ? "WRITE" : "READ"} / {riskLevel}
                    </span>
                  </div>
                  <div className="text-[11px] font-mono text-gray-500 mt-0.5">
                    Latency: {formatDuration(tool.latency_ms)}
                  </div>
                </div>
              </div>

              <div className="flex items-center gap-3">
                <StatusBadge status={tool.status} />
                {isExpanded ? (
                  <ChevronDown className="h-4 w-4 text-gray-400" />
                ) : (
                  <ChevronRight className="h-4 w-4 text-gray-400" />
                )}
              </div>
            </div>

            {/* Expanded Content */}
            {isExpanded && (
              <div className="px-4 pb-4 pt-2 border-t border-gray-800/80 space-y-3 bg-[#0c101a]">
                {/* Arguments */}
                <div>
                  <span className="text-[11px] font-mono uppercase text-gray-400 block mb-1">
                    Sanitized Tool Arguments:
                  </span>
                  <pre className="p-2.5 rounded-lg bg-gray-950 border border-gray-800 text-xs font-mono text-emerald-400 overflow-x-auto">
                    {JSON.stringify(tool.tool_input, null, 2)}
                  </pre>
                </div>

                {/* Output or Error */}
                {tool.error ? (
                  <div>
                    <span className="text-[11px] font-mono uppercase text-rose-400 block mb-1">
                      Execution Error:
                    </span>
                    <div className="p-2.5 rounded-lg bg-rose-950/30 border border-rose-800/60 text-xs font-mono text-rose-300">
                      {tool.error}
                    </div>
                  </div>
                ) : (
                  <div>
                    <span className="text-[11px] font-mono uppercase text-gray-400 block mb-1">
                      Execution Result Output:
                    </span>
                    <pre className="p-2.5 rounded-lg bg-gray-950 border border-gray-800 text-xs font-mono text-gray-300 overflow-x-auto max-h-60">
                      {JSON.stringify(tool.tool_output, null, 2)}
                    </pre>
                  </div>
                )}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
