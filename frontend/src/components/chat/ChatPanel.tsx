import {
  Bot,
  MessageSquare,
  RotateCcw,
  Trash2,
} from "lucide-react";
import { useEffect, useRef } from "react";
import type { ChatMessage } from "../../types/task";
import { ChatComposer } from "./ChatComposer";
import { ChatMessageBubble } from "./ChatMessageBubble";

interface ChatPanelProps {
  messages: ChatMessage[];
  sending: boolean;
  loadingHistory: boolean;
  error: string | null;
  onSend: (message: string) => Promise<void>;
  onClearHistory: () => Promise<void>;
}

export function ChatPanel({
  messages,
  sending,
  loadingHistory,
  error,
  onSend,
  onClearHistory,
}: ChatPanelProps) {
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({
      behavior: "smooth",
      block: "end",
    });
  }, [messages, sending]);

  return (
    <section className="flex min-h-[520px] flex-col overflow-hidden rounded-2xl border border-zinc-200 bg-zinc-50/70 lg:min-h-[680px]">
      <header className="flex items-center justify-between gap-3 border-b border-zinc-200 bg-white px-4 py-4 sm:px-5">
        <div className="flex min-w-0 items-center gap-3">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-zinc-900 text-white">
            <Bot size={21} aria-hidden="true" />
          </div>

          <div className="min-w-0">
            <h2 className="truncate text-sm font-semibold text-zinc-900">
              TaskFlow Assistant
            </h2>
            <p className="mt-0.5 text-xs text-zinc-500">
              Manage tasks using natural language
            </p>
          </div>
        </div>

        <button
          type="button"
          onClick={() => {
            void onClearHistory();
          }}
          disabled={loadingHistory || sending || messages.length === 0}
          className="inline-flex h-9 shrink-0 items-center gap-2 rounded-lg border border-zinc-200 bg-white px-3 text-xs font-medium text-zinc-600 transition-colors hover:bg-zinc-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-zinc-400 disabled:cursor-not-allowed disabled:opacity-40"
          aria-label="Clear conversation history"
          title="Clear conversation history"
        >
          <Trash2 size={14} aria-hidden="true" />
          <span className="hidden sm:inline">Clear</span>
        </button>
      </header>

      <div className="flex-1 space-y-5 overflow-y-auto px-4 py-5 sm:px-5">
        {loadingHistory ? (
          <div
            className="flex min-h-64 flex-col items-center justify-center gap-3 text-zinc-500"
            role="status"
          >
            <RotateCcw size={21} className="animate-spin" aria-hidden="true" />
            <p className="text-sm">Loading conversation...</p>
          </div>
        ) : messages.length === 0 ? (
          <div className="flex min-h-64 flex-col items-center justify-center px-4 text-center">
            <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-2xl border border-zinc-200 bg-white text-zinc-600">
              <MessageSquare size={25} aria-hidden="true" />
            </div>

            <h3 className="text-base font-semibold text-zinc-900">
              What needs to get done?
            </h3>

            <p className="mt-2 max-w-xs text-sm leading-6 text-zinc-500">
              Tell the assistant what you need to do. You can create tasks,
              update their status, search your list, or find upcoming deadlines.
            </p>

            <div className="mt-5 flex max-w-sm flex-wrap justify-center gap-2">
              {[
                "Show my tasks",
                "Create a high-priority task",
                "What is overdue?",
              ].map((suggestion) => (
                <button
                  key={suggestion}
                  type="button"
                  onClick={() => {
                    void onSend(suggestion);
                  }}
                  disabled={sending}
                  className="rounded-full border border-zinc-200 bg-white px-3 py-2 text-xs text-zinc-600 transition-colors hover:border-zinc-400 hover:text-zinc-900 disabled:opacity-50"
                >
                  {suggestion}
                </button>
              ))}
            </div>
          </div>
        ) : (
          messages.map((message) => (
            <ChatMessageBubble key={message.id} message={message} />
          ))
        )}

        {sending && (
          <div className="flex items-center gap-3" role="status">
            <div className="flex h-8 w-8 items-center justify-center rounded-full border border-zinc-200 bg-white text-zinc-600">
              <Bot size={16} aria-hidden="true" />
            </div>

            <div className="flex items-center gap-2 rounded-2xl rounded-tl-sm border border-zinc-200 bg-white px-4 py-3">
              <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-zinc-400" />
              <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-zinc-400 [animation-delay:150ms]" />
              <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-zinc-400 [animation-delay:300ms]" />
              <span className="ml-1 text-xs text-zinc-500">
                Thinking...
              </span>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {error && (
        <div
          className="mx-4 mb-3 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700 sm:mx-5"
          role="alert"
        >
          {error}
        </div>
      )}

      <footer className="border-t border-zinc-200 bg-white p-4 sm:p-5">
        <ChatComposer
          onSend={onSend}
          sending={sending}
          disabled={loadingHistory}
        />
      </footer>
    </section>
  );
}