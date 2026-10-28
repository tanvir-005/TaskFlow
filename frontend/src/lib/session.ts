const SESSION_STORAGE_KEY = "taskflow_session_id";

function createSessionId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }

  return `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

export function getSessionId(): string {
  const existing = localStorage.getItem(SESSION_STORAGE_KEY);

  if (existing) {
    return existing;
  }

  const sessionId = createSessionId();

  localStorage.setItem(SESSION_STORAGE_KEY, sessionId);

  return sessionId;
}

export function resetSessionId(): string {
  const sessionId = createSessionId();

  localStorage.setItem(SESSION_STORAGE_KEY, sessionId);

  return sessionId;
}