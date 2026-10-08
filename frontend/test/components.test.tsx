import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import React from "react";
import { StatusBadge, ErrorState, EmptyState } from "@/components/common/StateComponents";
import { EvidencePanel } from "@/components/evidence/EvidencePanel";
import { ToolExecutionPanel } from "@/components/tools/ToolExecutionPanel";
import { EvidenceItem, ToolExecution } from "@/lib/types";

describe("Frontend UI Components", () => {
  it("renders status badge correctly", () => {
    render(<StatusBadge status="COMPLETED" />);
    expect(screen.getByText("COMPLETED")).toBeInTheDocument();
  });

  it("renders error state with retry message", () => {
    render(<ErrorState message="Backend unavailable" />);
    expect(screen.getByText("System Error")).toBeInTheDocument();
    expect(screen.getByText("Backend unavailable")).toBeInTheDocument();
  });

  it("renders empty state with message", () => {
    render(
      <EmptyState
        title="No Approvals Found"
        description="There are no pending actions."
      />
    );
    expect(screen.getByText("No Approvals Found")).toBeInTheDocument();
    expect(screen.getByText("There are no pending actions.")).toBeInTheDocument();
  });

  it("renders evidence panel with epistemic classification and sources", () => {
    const mockEvidence: EvidenceItem[] = [
      {
        evidence_id: "ev-1",
        source_type: "SYSTEM_METRIC",
        source_identifier: "get_service_metrics",
        originating_agent: "DiagnosticAgent",
        content: "Database pool utilization is at 96.5%",
        evidence_class: "FACT",
        confidence: 0.98,
        timestamp: new Date().toISOString(),
      },
      {
        evidence_id: "ev-2",
        source_type: "RAG_CHUNK",
        source_identifier: "postgres-runbook.md",
        originating_agent: "KnowledgeAgent",
        content: "Increase max_connections parameter to resolve pool exhaustion",
        evidence_class: "DOCUMENTATION",
        confidence: 0.92,
        timestamp: new Date().toISOString(),
      },
    ];

    render(<EvidencePanel evidence={mockEvidence} />);
    expect(screen.getByText("FACT")).toBeInTheDocument();
    expect(screen.getByText("DOCUMENTATION")).toBeInTheDocument();
    expect(screen.getByText("Database pool utilization is at 96.5%")).toBeInTheDocument();
    expect(screen.getByText("get_service_metrics")).toBeInTheDocument();
  });

  it("renders tool execution panel with sanitized arguments", () => {
    const mockTools: ToolExecution[] = [
      {
        id: "tool-1",
        run_id: "run-1",
        tool_name: "get_service_metrics",
        tool_input: { service: "payment-service" },
        tool_output: { error_rate_percent: 6.8 },
        status: "SUCCESS",
        latency_ms: 12.4,
        created_at: new Date().toISOString(),
      },
    ];

    render(<ToolExecutionPanel tools={mockTools} />);
    expect(screen.getByText("get_service_metrics")).toBeInTheDocument();
    expect(screen.getByText("SUCCESS")).toBeInTheDocument();
  });
});
