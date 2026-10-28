import { useCallback, useEffect, useState } from "react";
import { api } from "../lib/api";
import { getSessionId } from "../lib/session";
import type { ChatMessage, Task } from "../types/task";

interface UseChatOptions {
  onTasksChanged?: (tasks?: Task[]) => Promise<void>;
}

interface UseChatReturn {
  messages: ChatMessage[];
  sending: boolean;
  loadingHistory: boolean;
  error: string | null;
  sessionId: string;
  sendMessage: (content: string) => Promise<void>;
  clearHistory: () => Promise<void>;
}

function createMessage(
  role: ChatMessage["role"],
  content: string,
): ChatMessage {
  return {
    id: crypto.randomUUID(),
    role,
    content,
    created_at: new Date().toISOString(),
  };
}

export function useChat(
  options: UseChatOptions = {},
): UseChatReturn {
  const [sessionId] = useState(() => getSessionId());
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [sending, setSending] = useState(false);
  const [loadingHistory, setLoadingHistory] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadHistory = useCallback(async () => {
    setLoadingHistory(true);
    setError(null);

    try {
      const response = await api.getChatHistory(sessionId);

      const history: ChatMessage[] = response.messages
        .filter(
          (message) =>
            message.role === "user" || message.role === "assistant",
        )
        .map((message, index) => {
          let meta: Record<string, unknown> | undefined;

          if (typeof message.meta === "string") {
            try {
              const parsed: unknown = JSON.parse(message.meta);

              if (
                parsed !== null &&
                typeof parsed === "object" &&
                !Array.isArray(parsed)
              ) {
                meta = parsed as Record<string, unknown>;
              }
            } catch {
              meta = undefined;
            }
          } else if (
            message.meta !== null &&
            typeof message.meta === "object"
          ) {
            meta = message.meta;
          }

          return {
            id: String(message.id ?? `${sessionId}-${index}`),
            role: message.role as ChatMessage["role"],
            content: message.content,
            created_at: message.created_at,
            meta,
          };
        });

      setMessages(history);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Failed to load conversation history.",
      );
    } finally {
      setLoadingHistory(false);
    }
  }, [sessionId]);

  useEffect(() => {
    void loadHistory();
  }, [loadHistory]);

  const sendMessage = useCallback(
    async (content: string) => {
      const trimmed = content.trim();

      if (!trimmed || sending) {
        return;
      }

      setError(null);
      setSending(true);

      setMessages((current) => [
        ...current,
        createMessage("user", trimmed),
      ]);

      try {
        const response = await api.sendMessage(sessionId, trimmed);

        // The backend agent returns "reply"; "message" remains supported
        // for compatibility with other API response shapes.
        const reply =
          typeof response.reply === "string"
            ? response.reply
            : typeof response.message === "string"
              ? response.message
              : "The assistant returned no message.";

        setMessages((current) => [
          ...current,
          createMessage("assistant", reply),
        ]);

        if (response.ok && options.onTasksChanged) {
          await options.onTasksChanged(response.tasks);
        }
      } catch (err) {
        const message =
          err instanceof Error
            ? err.message
            : "Failed to send your message.";

        setError(message);

        setMessages((current) => [
          ...current,
          createMessage(
            "assistant",
            `I couldn't complete that request: ${message}`,
          ),
        ]);
      } finally {
        setSending(false);
      }
    },
    [sending, sessionId, options.onTasksChanged],
  );

  const clearHistory = useCallback(async () => {
    setError(null);

    try {
      await api.clearChatHistory(sessionId);
      setMessages([]);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Failed to clear conversation history.",
      );
      throw err;
    }
  }, [sessionId]);

  return {
    messages,
    sending,
    loadingHistory,
    error,
    sessionId,
    sendMessage,
    clearHistory,
  };
}