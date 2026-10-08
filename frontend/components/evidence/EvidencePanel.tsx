"use client";

import { EvidenceItem } from "@/lib/types";
import { formatDate } from "@/lib/utils";
import { BookOpen, CheckCircle, Database, HelpCircle, Layers, ShieldAlert, Sparkles } from "lucide-react";

interface EvidencePanelProps {
  evidence: EvidenceItem[];
  warnings?: string[];
}

export function EvidencePanel({ evidence, warnings }: EvidencePanelProps) {
  if (!evidence || evidence.length === 0) {
    return (
      <div className="p-6 text-center text-xs text-gray-500 font-mono border border-gray-800 rounded-xl bg-gray-900/20">
        No formal evidence items collected for this run.
      </div>
    );
  }

  // Check for contradiction / conflict warning
  const hasConflict =
    warnings && warnings.some((w) => w.toLowerCase().includes("conflict") || w.toLowerCase().includes("discrepancy"));

  return (
    <div className="space-y-4">
      {/* Contradiction Warning Banner */}
      {hasConflict && (
        <div className="p-4 rounded-xl border border-amber-800/80 bg-amber-950/30 text-amber-200 space-y-2">
          <div className="flex items-center gap-2 font-bold text-xs uppercase tracking-wider text-amber-400">
            <ShieldAlert className="h-4 w-4" />
            Contradictory / Discrepant Evidence Detected
          </div>
          <p className="text-xs text-amber-300">
            The multi-agent supervisor detected conflicting telemetry across specialist agents.
            Calibrated uncertainty was exercised in the final synthesis.
          </p>
        </div>
      )}

      {/* Evidence Cards */}
      <div className="grid grid-cols-1 gap-3">
        {evidence.map((item, idx) => {
          let badgeColor = "bg-blue-950 text-blue-400 border-blue-800";
          let icon = <Database className="h-3.5 w-3.5" />;

          if (item.evidence_class === "DOCUMENTATION") {
            badgeColor = "bg-purple-950 text-purple-400 border-purple-800";
            icon = <BookOpen className="h-3.5 w-3.5" />;
          } else if (item.evidence_class === "INFERENCE") {
            badgeColor = "bg-amber-950 text-amber-400 border-amber-800";
            icon = <Sparkles className="h-3.5 w-3.5" />;
          } else if (item.evidence_class === "OBSERVATION") {
            badgeColor = "bg-emerald-950 text-emerald-400 border-emerald-800";
            icon = <CheckCircle className="h-3.5 w-3.5" />;
          }

          return (
            <div
              key={item.evidence_id || idx}
              className="p-4 rounded-xl border border-gray-800 bg-gray-900/40 space-y-2 hover:border-gray-700 transition-colors"
            >
              {/* Header */}
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <span
                    className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-md text-[11px] font-mono font-bold border ${badgeColor}`}
                  >
                    {icon}
                    {item.evidence_class}
                  </span>
                  {item.originating_agent && (
                    <span className="text-xs font-mono text-gray-400">
                      Agent: <strong className="text-gray-200">{item.originating_agent}</strong>
                    </span>
                  )}
                </div>

                <div className="text-[11px] font-mono text-gray-500">
                  Confidence: {Math.round(item.confidence * 100)}%
                </div>
              </div>

              {/* Content */}
              <div className="text-xs text-gray-200 leading-relaxed font-sans bg-[#0c101a] p-3 rounded-lg border border-gray-800/80">
                {item.content}
              </div>

              {/* Source Provenance */}
              <div className="flex flex-wrap items-center justify-between gap-2 text-[11px] font-mono text-gray-400 pt-1">
                <div>
                  Source: <span className="text-gray-300 font-semibold">{item.source_identifier}</span> ({item.source_type})
                </div>
                <div>{formatDate(item.timestamp)}</div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
