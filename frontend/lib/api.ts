import type { PreviewResponse, SessionDetail, SessionSummary } from "@/types";

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
