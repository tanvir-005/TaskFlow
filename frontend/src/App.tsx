import { useCallback } from "react";
import {
  Activity,
  Bot,
  CheckCircle2,
  CircleHelp,
  RefreshCw,
  Sparkles,
} from "lucide-react";

import { ChatPanel } from "./components/chat/ChatPanel";
import {
  TaskFilters,
} from "./components/tasks/TaskFilters";
import { TaskList } from "./components/tasks/TaskList";
import { TaskSummary } from "./components/tasks/TaskSummary";
import { useChat } from "./hooks/useChat";
import { useTasks } from "./hooks/useTasks";
import type { Task } from "./types/task";

function App() {
  const {
    tasks,
    loading,
    error,
    filter,
    setFilter,
    refreshTasks,
    setTasksFromChat,
  } = useTasks();

  const refreshTasksAfterChat = useCallback(
    async (updatedTasks?: Task[]) => {
      if (updatedTasks) {
        setTasksFromChat(updatedTasks);
        return;
      }

      await refreshTasks();
    },
    [refreshTasks, setTasksFromChat],
  );

  const {
    messages,
    sending,
    loadingHistory,
    error: chatError,
    sendMessage,
    clearHistory,
  } = useChat({
    onTasksChanged: refreshTasksAfterChat,
  });

  return (
    <div className="min-h-screen bg-zinc-50 text-zinc-900">
      <header className="sticky top-0 z-20 border-b border-zinc-200 bg-white/95 backdrop-blur">
        <div className="mx-auto flex h-16 max-w-[1600px] items-center justify-between gap-4 px-4 sm:px-6 lg:px-8">
          <a
            href="/"
            className="flex min-w-0 items-center gap-3"
            aria-label="TaskFlow home"
          >
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-zinc-900 text-white">
              <CheckCircle2 size={22} aria-hidden="true" />
            </div>

            <div className="min-w-0">
              <h1 className="text-base font-bold tracking-tight text-zinc-900">
                TaskFlow
              </h1>
              <p className="hidden text-xs text-zinc-500 sm:block">
                Your tasks, organized
              </p>
            </div>
          </a>

          <div className="flex items-center gap-2 rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1.5">
            <span
              className="h-2 w-2 rounded-full bg-emerald-500"
              aria-hidden="true"
            />
            <span className="text-xs font-medium text-emerald-700">
              Workspace
            </span>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-[1600px] px-4 py-6 sm:px-6 sm:py-8 lg:px-8">
        <section className="mb-8 flex flex-col justify-between gap-5 md:flex-row md:items-end">
          <div>
            <div className="mb-3 inline-flex items-center gap-2 rounded-full border border-zinc-200 bg-white px-3 py-1.5 text-xs font-medium text-zinc-600">
              <Sparkles size={14} aria-hidden="true" />
              AI-powered task management
            </div>

            <h2 className="text-2xl font-bold tracking-tight text-zinc-950 sm:text-3xl">
              Your workspace
            </h2>

            <p className="mt-2 max-w-2xl text-sm leading-6 text-zinc-500">
              Organize your work, track progress, and manage tasks through a
              natural conversation with your assistant.
            </p>
          </div>

          <button
            type="button"
            onClick={() => {
              void refreshTasks();
            }}
            disabled={loading}
            className="inline-flex min-h-10 shrink-0 items-center justify-center gap-2 rounded-lg border border-zinc-200 bg-white px-4 py-2 text-sm font-medium text-zinc-700 transition-colors hover:bg-zinc-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-zinc-400 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <RefreshCw
              size={15}
              className={loading ? "animate-spin" : ""}
              aria-hidden="true"
            />
            Refresh tasks
          </button>
        </section>

        <div className="mb-8">
          <TaskSummary tasks={tasks} />
        </div>

        <div className="grid grid-cols-1 items-start gap-6 xl:grid-cols-[minmax(0,1fr)_minmax(420px,0.95fr)] 2xl:gap-8">
          <section className="min-w-0">
            <div className="mb-5 flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
              <div>
                <h2 className="text-lg font-semibold tracking-tight text-zinc-900">
                  Tasks
                </h2>
                <p className="mt-1 text-sm text-zinc-500">
                  Review your current workload.
                </p>
              </div>

              <span className="inline-flex w-fit items-center gap-1.5 rounded-full bg-white px-3 py-1.5 text-xs font-medium text-zinc-600 ring-1 ring-inset ring-zinc-200">
                <Activity size={13} aria-hidden="true" />
                {tasks.length} {tasks.length === 1 ? "task" : "tasks"}
              </span>
            </div>

            <div className="mb-5 overflow-x-auto pb-1">
              <TaskFilters value={filter} onChange={setFilter} />
            </div>

            <TaskList
              tasks={tasks}
              loading={loading}
              error={error}
            />

            <div className="mt-5 flex items-start gap-2 rounded-xl border border-zinc-200 bg-white p-4">
              <CircleHelp
                size={17}
                className="mt-0.5 shrink-0 text-zinc-500"
                aria-hidden="true"
              />
              <p className="text-xs leading-5 text-zinc-500">
                Create, edit, complete, or search for tasks by describing what
                you want in the assistant panel. Your tasks are stored in the
                backend.
              </p>
            </div>
          </section>

          <section className="min-w-0 xl:sticky xl:top-24">
            <div className="mb-5">
              <h2 className="text-lg font-semibold tracking-tight text-zinc-900">
                Assistant
              </h2>
              <p className="mt-1 text-sm text-zinc-500">
                Describe what you want to accomplish.
              </p>
            </div>

            <ChatPanel
              messages={messages}
              sending={sending}
              loadingHistory={loadingHistory}
              error={chatError}
              onSend={sendMessage}
              onClearHistory={clearHistory}
            />

            <div className="mt-3 flex items-center justify-center gap-2 text-xs text-zinc-400">
              <Bot size={14} aria-hidden="true" />
              <span>AI responses can make mistakes. Verify important changes.</span>
            </div>
          </section>
        </div>
      </main>

      <footer className="mt-10 border-t border-zinc-200 bg-white">
        <div className="mx-auto flex max-w-[1600px] flex-col gap-2 px-4 py-5 text-xs text-zinc-500 sm:flex-row sm:items-center sm:justify-between sm:px-6 lg:px-8">
          <p>
            <span className="font-semibold text-zinc-700">TaskFlow</span>
            {" "}· AI-powered task management
          </p>
          <p>Built for focused, organized work.</p>
        </div>
      </footer>
    </div>
  );
}

export default App;
