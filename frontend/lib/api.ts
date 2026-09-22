import type {
  AgentEvent,
  AuthUser,
  ChatMessageOut,
  DecisionOut,
  ExpertiseLevel,
  KernelStatusOut,
  NotebookCell,
  PreviewResponse,
  RequestLinkResponse,
  SampleDataset,
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
  // Auth (Phase 8, MASTER_PROMPT.md §9): the session cookie is set by POST /auth/verify on the
  // backend's own origin (a different port in dev) — `credentials: "include"` is what makes
  // the browser send it back on every request here instead of treating this as a cookie-less
  // cross-origin call.
  const res = await fetch(`${API_BASE_URL}${path}`, {
    cache: "no-store",
    credentials: "include",
    ...init,
  });
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

/** Uploads a dataset. Uses XMLHttpRequest rather than fetch because only XHR reports upload
 * progress, which matters for files in the hundreds of megabytes. `onProgress` gets 0 to 1. */
export function uploadSession(
  file: File,
  onProgress?: (fraction: number) => void,
): Promise<SessionDetail> {
  const formData = new FormData();
  formData.append("file", file);
  if (!onProgress || typeof XMLHttpRequest === "undefined") {
    return request<SessionDetail>("/sessions", { method: "POST", body: formData });
  }
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${API_BASE_URL}/sessions`);
    xhr.withCredentials = true;
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) onProgress(e.loaded / e.total);
    };
    xhr.onload = () => {
      let body: unknown = null;
      try {
        body = JSON.parse(xhr.responseText);
      } catch {
        // non-JSON body; handled below
      }
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(body as SessionDetail);
      } else {
        const detail = (body as { detail?: unknown } | null)?.detail;
        reject(new ApiError(typeof detail === "string" ? detail : xhr.statusText, xhr.status));
      }
    };
    xhr.onerror = () => reject(new ApiError("Network error during upload.", 0));
    xhr.send(formData);
  });
}

export function listSamples(): Promise<SampleDataset[]> {
  return request<SampleDataset[]>("/sessions/samples");
}

export function createSampleSession(key: string): Promise<SessionDetail> {
  return request<SessionDetail>(`/sessions/samples/${key}`, { method: "POST" });
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
  // `withCredentials: true` so the session cookie (a different port in dev, so cross-origin
  // from the browser's point of view) is sent — same reasoning as `request()`'s
  // `credentials: "include"` above.
  const source = new EventSource(`${API_BASE_URL}/sessions/${sessionId}/stream`, {
    withCredentials: true,
  });
  source.onmessage = (message) => {
    try {
      onEvent(JSON.parse(message.data) as AgentEvent);
    } catch {
      // ignore malformed/keep-alive frames
    }
  };
  return () => source.close();
}

export interface ExportOptions {
  format: "zip" | "html";
  includeData?: boolean;
  includePipeline?: boolean;
  includeExploratory?: boolean;
}

export async function exportNotebook(sessionId: string, options: ExportOptions): Promise<void> {
  const params = new URLSearchParams({
    format: options.format,
    include_data: String(options.includeData ?? false),
    include_pipeline: String(options.includePipeline ?? false),
    include_exploratory: String(options.includeExploratory ?? false),
  });
  const res = await fetch(`${API_BASE_URL}/sessions/${sessionId}/notebook/export?${params}`, {
    method: "POST",
    cache: "no-store",
    credentials: "include",
  });
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
  const filename =
    match?.[1] ?? (options.format === "html" ? "datapilot_report.html" : "datapilot_export.zip");

  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

// Auth (Phase 8, MASTER_PROMPT.md §9, §12): email magic-link login.

export function requestLoginLink(email: string): Promise<RequestLinkResponse> {
  return request<RequestLinkResponse>("/auth/request-link", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email }),
  });
}

export function verifyLoginToken(token: string): Promise<AuthUser> {
  return request<AuthUser>(`/auth/verify?token=${encodeURIComponent(token)}`);
}

export async function logout(): Promise<void> {
  await request("/auth/logout", { method: "POST" });
}

export function getCurrentUser(): Promise<AuthUser> {
  return request<AuthUser>("/auth/me");
}
