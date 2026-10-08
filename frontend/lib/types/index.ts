export type AgentRunStatus =
  | "PENDING"
  | "RUNNING"
  | "WAITING_APPROVAL"
  | "COMPLETED"
  | "FAILED"
  | "CANCELLED";

export type ApprovalStatus = "PENDING" | "APPROVED" | "REJECTED" | "CANCELLED";

export type EvidenceClass = "FACT" | "INFERENCE" | "DOCUMENTATION" | "OBSERVATION";

export type ToolRisk = "READ" | "WRITE";
export type RiskLevel = "LOW" | "MEDIUM" | "HIGH";

export interface PlanStep {
  step_number: number;
  description: string;
  tool_required?: string | null;
  requires_rag: boolean;
  requires_human_approval: boolean;
  status: "PENDING" | "RUNNING" | "COMPLETED" | "FAILED" | "SKIPPED";
  output?: string | null;
}

export interface Plan {
  task_summary: string;
  steps: PlanStep[];
  estimated_impact: "LOW" | "MEDIUM" | "HIGH";
}

export interface EvidenceItem {
  evidence_id: string;
  source_type: "RAG_CHUNK" | "TOOL_OUTPUT" | "SYSTEM_METRIC" | "LOG" | "AGENT_OBSERVATION";
  source_identifier: string;
  source_id?: string | null;
  source_description?: string | null;
  originating_agent?: string | null;
  content: string;
  evidence_class: EvidenceClass;
  confidence: number;
  timestamp: string;
}

export interface AgentEvent {
  id: string;
  run_id: string;
  node_name: string;
  event_type: string;
  payload: Record<string, any>;
  duration_ms?: number | null;
  created_at: string;
}

export interface ToolExecution {
  id: string;
  run_id: string;
  tool_name: string;
  tool_input: Record<string, any>;
  tool_output?: Record<string, any> | null;
  status: "SUCCESS" | "FAILED" | "PENDING_APPROVAL" | "REJECTED" | string;
  error?: string | null;
  latency_ms?: number | null;
  created_at: string;
}

export interface AgentRun {
  id: string;
  conversation_id: string;
  user_request: string;
  status: AgentRunStatus;
  plan?: Plan | Record<string, any> | null;
  final_answer?: string | null;
  error?: string | null;
  total_latency_ms?: number | null;
  total_tokens?: number | null;
  tools_used: string[];
  number_of_tool_calls: number;
  agents_used?: string[];
  delegation_count?: number;
  evidence_count?: number;
  approval_required?: boolean;
  created_at: string;
  updated_at: string;
  events?: AgentEvent[] | null;
  tool_executions?: ToolExecution[] | null;
}

export interface Approval {
  id: string;
  run_id: string;
  tool_name: string;
  tool_args: Record<string, any>;
  reason: string;
  status: ApprovalStatus;
  decided_by?: string | null;
  decided_at?: string | null;
  rejection_reason?: string | null;
  created_at: string;
  updated_at: string;
}

export interface ApprovalActionResponse {
  approval_id: string;
  status: ApprovalStatus;
  message: string;
  agent_run_id: string;
  agent_status: string;
  final_answer?: string | null;
}

export interface ServiceItem {
  id: string;
  name: string;
  description: string;
  status: "HEALTHY" | "DEGRADED" | "DOWN" | string;
  owner_team: string;
  repository_url?: string | null;
  metadata_info?: Record<string, any> | null;
  created_at: string;
  updated_at: string;
}

export interface IncidentItem {
  id: string;
  service_id: string;
  service_name?: string | null;
  title: string;
  description: string;
  severity: "LOW" | "MEDIUM" | "HIGH" | "CRITICAL" | string;
  status: "OPEN" | "INVESTIGATING" | "MITIGATED" | "RESOLVED" | "CLOSED" | string;
  root_cause?: string | null;
  resolution_notes?: string | null;
  comments?: any[] | null;
  resolved_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface EvaluationCaseResult {
  case_id: string;
  category: string;
  query: string;
  status: "PASSED" | "FAILED" | string;
  actual_agents: string[];
  expected_agents: string[];
  actual_tools: string[];
  expected_tools: string[];
  routing_correct: boolean;
  tool_selection_correct: boolean;
  grounded: boolean;
  provenance_valid: boolean;
  approval_safety_passed: boolean;
  conflict_handled: boolean;
  evidence_count: number;
  latency_ms: number;
  tokens_used: number;
  details: Record<string, any>;
  error?: string | null;
}

export interface EvaluationRun {
  id: string;
  dataset_name: string;
  model_provider: string;
  total_cases: number;
  passed_cases: number;
  failed_cases: number;
  routing_accuracy: number;
  tool_selection_accuracy: number;
  grounding_rate: number;
  provenance_rate: number;
  conflict_detection_rate: number;
  approval_safety_rate: number;
  avg_latency_ms: number;
  p95_latency_ms: number;
  total_tokens: number;
  estimated_cost_usd: number;
  metrics: Record<string, any>;
  created_at: string;
  results?: EvaluationCaseResult[] | null;
}

export interface HealthStatus {
  status: "healthy" | "degraded" | string;
  app_name: string;
  environment: string;
  database_connected: boolean;
  version: string;
  timestamp: string;
  details: {
    debug_mode: boolean;
    llm_provider: string;
    embedding_model: string;
  };
}
