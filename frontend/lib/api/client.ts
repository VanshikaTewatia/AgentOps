import {
  AgentRun,
  AgentEvent,
  Approval,
  ApprovalActionResponse,
  ServiceItem,
  IncidentItem,
  EvaluationRun,
  EvaluationCaseResult,
  HealthStatus,
} from "../types";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000/api/v1";

class ApiError extends Error {
  status: number;
  data: any;

  constructor(message: string, status: number, data?: any) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.data = data;
  }
}

async function request<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`;
  const headers = {
    "Content-Type": "application/json",
    ...(options?.headers || {}),
  };

  try {
    const res = await fetch(url, {
      ...options,
      headers,
    });

    if (!res.ok) {
      let errorBody: any;
      try {
        errorBody = await res.json();
      } catch {
        errorBody = await res.text();
      }

      const detail =
        typeof errorBody === "object" && errorBody?.detail
          ? errorBody.detail
          : typeof errorBody === "string"
          ? errorBody
          : "Request failed";

      throw new ApiError(detail, res.status, errorBody);
    }

    return (await res.json()) as T;
  } catch (err: any) {
    if (err instanceof ApiError) {
      throw err;
    }
    throw new ApiError(
      `AgentOps backend is unavailable. Check that the FastAPI server is running on ${API_BASE_URL}. (${err.message})`,
      0
    );
  }
}

export const api = {
  // Health
  async getHealth(): Promise<HealthStatus> {
    return request<HealthStatus>("/health");
  },

  // Agent Runs
  async listRuns(statusFilter?: string): Promise<AgentRun[]> {
    const query = statusFilter ? `?status_filter=${encodeURIComponent(statusFilter)}` : "";
    return request<AgentRun[]>(`/agent/runs${query}`);
  },

  async getRun(runId: string): Promise<AgentRun> {
    return request<AgentRun>(`/agent/runs/${runId}`);
  },

  async getRunEvents(runId: string): Promise<AgentEvent[]> {
    return request<AgentEvent[]>(`/agent/runs/${runId}/events`);
  },

  async createRun(message: string, conversationId?: string): Promise<AgentRun> {
    return request<AgentRun>("/agent/run", {
      method: "POST",
      body: JSON.stringify({
        message,
        conversation_id: conversationId || undefined,
      }),
    });
  },

  // Approvals
  async listApprovals(statusFilter?: string): Promise<Approval[]> {
    const query = statusFilter ? `?status_filter=${encodeURIComponent(statusFilter)}` : "";
    return request<Approval[]>(`/approvals${query}`);
  },

  async getApproval(approvalId: string): Promise<Approval> {
    return request<Approval>(`/approvals/${approvalId}`);
  },

  async approve(
    approvalId: string,
    decidedBy: string = "SRE-Lead",
    reason?: string
  ): Promise<ApprovalActionResponse> {
    return request<ApprovalActionResponse>(`/approvals/${approvalId}/approve`, {
      method: "POST",
      body: JSON.stringify({
        decided_by: decidedBy,
        reason: reason || undefined,
      }),
    });
  },

  async reject(
    approvalId: string,
    rejectionReason: string,
    decidedBy: string = "SRE-Lead"
  ): Promise<ApprovalActionResponse> {
    return request<ApprovalActionResponse>(`/approvals/${approvalId}/reject`, {
      method: "POST",
      body: JSON.stringify({
        rejection_reason: rejectionReason,
        decided_by: decidedBy,
      }),
    });
  },

  // Services
  async listServices(): Promise<ServiceItem[]> {
    return request<ServiceItem[]>("/services");
  },

  async getService(serviceId: string): Promise<ServiceItem> {
    return request<ServiceItem>(`/services/${serviceId}`);
  },

  // Incidents
  async listIncidents(serviceId?: string, statusFilter?: string): Promise<IncidentItem[]> {
    const params = new URLSearchParams();
    if (serviceId) params.append("service_id", serviceId);
    if (statusFilter) params.append("status_filter", statusFilter);
    const query = params.toString() ? `?${params.toString()}` : "";
    return request<IncidentItem[]>(`/incidents${query}`);
  },

  async getIncident(incidentId: string): Promise<IncidentItem> {
    return request<IncidentItem>(`/incidents/${incidentId}`);
  },

  // Evaluations
  async triggerEvaluation(datasetName: string = "agentops-eval-v1", maxCases?: number): Promise<EvaluationRun> {
    return request<EvaluationRun>("/evaluations/run", {
      method: "POST",
      body: JSON.stringify({
        dataset_name: datasetName,
        max_cases: maxCases || undefined,
      }),
    });
  },

  async listEvaluations(limit: number = 20, offset: number = 0): Promise<EvaluationRun[]> {
    return request<EvaluationRun[]>(`/evaluations?limit=${limit}&offset=${offset}`);
  },

  async getEvaluation(evaluationId: string): Promise<EvaluationRun> {
    return request<EvaluationRun>(`/evaluations/${evaluationId}`);
  },

  async getEvaluationResults(evaluationId: string): Promise<EvaluationCaseResult[]> {
    return request<EvaluationCaseResult[]>(`/evaluations/${evaluationId}/results`);
  },
};
