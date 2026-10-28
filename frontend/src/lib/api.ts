import type {
  ChatHistoryResponse,
  ChatResponse,
  HealthResponse,
  TaskListResponse,
  TaskStatus,
} from "../types/task";

const API_BASE_URL = "/api";

async function request<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
  });

  const payload: unknown = await response.json().catch(() => null);

  if (!response.ok) {
    const body =
      payload && typeof payload === "object"
        ? (payload as Record<string, unknown>)
        : {};

    const detail =
      typeof body.detail === "string"
        ? body.detail
        : typeof body.message === "string"
          ? body.message
          : `Request failed with status ${response.status}`;

    throw new Error(detail);
  }

  return payload as T;
}

export const api = {
  health(): Promise<HealthResponse> {
    return request<HealthResponse>("/health");
  },

  getTasks(status?: TaskStatus): Promise<TaskListResponse> {
    const query = status
      ? `?status=${encodeURIComponent(status)}`
      : "";

    return request<TaskListResponse>(`/tasks${query}`);
  },

  sendMessage(
    sessionId: string,
    message: string,
  ): Promise<ChatResponse> {
    return request<ChatResponse>("/chat", {
      method: "POST",
      body: JSON.stringify({
        session_id: sessionId,
        message,
      }),
    });
  },

  getChatHistory(
    sessionId: string,
  ): Promise<ChatHistoryResponse> {
    const query = new URLSearchParams({
      session_id: sessionId,
    });

    return request<ChatHistoryResponse>(
      `/chat/history?${query.toString()}`,
    );
  },

  clearChatHistory(sessionId: string): Promise<void> {
    const query = new URLSearchParams({
      session_id: sessionId,
    });

    return request<void>(`/chat/history?${query.toString()}`, {
      method: "DELETE",
    });
  },
};