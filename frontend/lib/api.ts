import type {
  AgentEvent,
  ChatMessageOut,
  DecisionOut,
  ExpertiseLevel,
  KernelStatusOut,
  NotebookCell,
  PreviewResponse,
  SessionDetail,
  SessionSummary,
  TemplateInfo,
  UsageOut,
} from "@/types";

export const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export interface HealthResponse {
  status: string;
  llm: {
    configured: boolean;
    model: string;
  };
}

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`, { cache: "no-store", ...init });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ?? detail;
    } catch {
      // response body wasn't JSON; fall back to statusText
    }
    throw new ApiError(detail, res.status);
  }
  if (res.status === 204) {
    return undefined as T;
  }
  return res.json();
}

export function fetchHealth(): Promise<HealthResponse> {
  return request<HealthResponse>("/health");
}

export function uploadSession(file: File): Promise<SessionDetail> {
  const formData = new FormData();
  formData.append("file", file);
  return request<SessionDetail>("/sessions", { method: "POST", body: formData });
}

export function listSessions(): Promise<SessionSummary[]> {
  return request<SessionSummary[]>("/sessions");
}

export function getSession(id: string): Promise<SessionDetail> {
  return request<SessionDetail>(`/sessions/${id}`);
}

export function selectSheet(id: string, sheetName: string): Promise<SessionDetail> {
  return request<SessionDetail>(`/sessions/${id}/sheet`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ sheet_name: sheetName }),
  });
}

export function getPreview(id: string, offset: number, limit: number): Promise<PreviewResponse> {
  return request<PreviewResponse>(`/sessions/${id}/preview?offset=${offset}&limit=${limit}`);
}

export function deleteSession(id: string): Promise<void> {
  return request<void>(`/sessions/${id}`, { method: "DELETE" });
}

export function listTemplates(): Promise<TemplateInfo[]> {
  return request<TemplateInfo[]>("/templates");
}

export function getNotebook(sessionId: string): Promise<NotebookCell[]> {
  return request<NotebookCell[]>(`/sessions/${sessionId}/notebook`);
}

export function getKernelStatus(sessionId: string): Promise<KernelStatusOut> {
  return request<KernelStatusOut>(`/sessions/${sessionId}/kernel/status`);
}

export function runTemplate(sessionId: string, templateKey: string): Promise<NotebookCell[]> {
  return request<NotebookCell[]>(`/sessions/${sessionId}/templates/${templateKey}/run`, {
    method: "POST",
  });
}

export async function startAgent(sessionId: string): Promise<void> {
  await request(`/sessions/${sessionId}/agent/start`, { method: "POST" });
}

export function getUsage(sessionId: string): Promise<UsageOut> {
  return request<UsageOut>(`/sessions/${sessionId}/usage`);
}

export function getDecisions(sessionId: string): Promise<DecisionOut[]> {
  return request<DecisionOut[]>(`/sessions/${sessionId}/decisions`);
}

export function answerDecision(
  sessionId: string,
  decisionId: string,
  selectedOption: string,
): Promise<DecisionOut> {
  return request<DecisionOut>(`/sessions/${sessionId}/decisions/${decisionId}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ selected_option: selectedOption }),
  });
}

export function editPlan(sessionId: string, steps: string[]): Promise<DecisionOut> {
  return request<DecisionOut>(`/sessions/${sessionId}/plan`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ steps }),
  });
}

export function setAutoDecide(sessionId: string, autoDecide: boolean): Promise<SessionDetail> {
  return request<SessionDetail>(`/sessions/${sessionId}/settings`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ auto_decide: autoDecide }),
  });
}

export function setExpertiseLevel(
  sessionId: string,
  expertiseLevel: ExpertiseLevel,
): Promise<SessionDetail> {
  return request<SessionDetail>(`/sessions/${sessionId}/settings`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ expertise_level: expertiseLevel }),
  });
}

export function getMessages(sessionId: string): Promise<ChatMessageOut[]> {
  return request<ChatMessageOut[]>(`/sessions/${sessionId}/messages`);
}

export function askQuestion(sessionId: string, content: string): Promise<ChatMessageOut> {
  return request<ChatMessageOut>(`/sessions/${sessionId}/messages`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ content }),
  });
}

export function revertToCell(sessionId: string, cellId: string): Promise<NotebookCell[]> {
  return request<NotebookCell[]>(`/sessions/${sessionId}/cells/${cellId}/revert`, {
    method: "POST",
  });
}

/** Opens the agent's SSE stream (MASTER_PROMPT.md §7, §8) and returns an unsubscribe function. */
export function subscribeToAgentStream(
  sessionId: string,
  onEvent: (event: AgentEvent) => void,
): () => void {
  const source = new EventSource(`${API_BASE_URL}/sessions/${sessionId}/stream`);
  source.onmessage = (message) => {
    try {
      onEvent(JSON.parse(message.data) as AgentEvent);
    } catch {
      // ignore malformed/keep-alive frames
    }
  };
  return () => source.close();
}

export async function exportNotebook(
  sessionId: string,
  includeData: boolean,
  includePipeline = false,
  includeExploratory = false,
): Promise<void> {
  const res = await fetch(
    `${API_BASE_URL}/sessions/${sessionId}/notebook/export?include_data=${includeData}&include_pipeline=${includePipeline}&include_exploratory=${includeExploratory}`,
    { method: "POST", cache: "no-store" },
  );
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = typeof body.detail === "string" ? body.detail : (body.detail?.message ?? detail);
    } catch {
      // response body wasn't JSON; fall back to statusText
    }
    throw new ApiError(detail, res.status);
  }
  const blob = await res.blob();
  const disposition = res.headers.get("Content-Disposition") ?? "";
  const match = /filename="?([^"]+)"?/.exec(disposition);
  const filename = match?.[1] ?? "datapilot_export.zip";

  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}
