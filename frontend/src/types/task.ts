export type TaskStatus = "todo" | "in_progress" | "done";

export type TaskPriority = "low" | "medium" | "high";

export interface Task {
  id: string;
  title: string;
  description: string;
  status: TaskStatus;
  priority: TaskPriority;
  due_date: string | null;
  created_at: string;
  updated_at: string;
}

export interface TaskListResponse {
  ok: boolean;
  tasks: Task[];
  count: number;
}

export interface ApiError {
  ok: false;
  status: string;
  message: string;
  detail?: string;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  created_at?: string;
  meta?: Record<string, unknown>;
}

export interface ChatResponse {
  ok: boolean;
  status?: string;
  message: string;
  tasks?: Task[];
  [key: string]: unknown;
}

export interface ChatHistoryResponse {
  ok: boolean;
  session_id: string;
  messages: Array<{
    id?: string | number;
    session_id?: string;
    role: string;
    content: string;
    created_at?: string;
    meta?: Record<string, unknown> | string | null;
  }>;
  count: number;
}

export interface HealthResponse {
  status: string;
  sqlite_count: number;
  chroma_count: number | null;
  in_sync: boolean | null;
  model: string;
}