import { AlertCircle, ClipboardList, LoaderCircle } from "lucide-react";
import type { Task } from "../../types/task";
import { TaskCard } from "./TaskCard";

interface TaskListProps {
  tasks: Task[];
  loading: boolean;
  error: string | null;
}

export function TaskList({ tasks, loading, error }: TaskListProps) {
  if (loading) {
    return (
      <div
        className="flex min-h-48 flex-col items-center justify-center gap-3 text-zinc-500"
        role="status"
      >
        <LoaderCircle
          size={24}
          className="animate-spin"
          aria-hidden="true"
        />
        <p className="text-sm">Loading tasks...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div
        className="flex min-h-48 flex-col items-center justify-center gap-3 rounded-xl border border-rose-200 bg-rose-50 p-6 text-center"
        role="alert"
      >
        <AlertCircle
          size={24}
          className="text-rose-600"
          aria-hidden="true"
        />
        <div>
          <p className="text-sm font-semibold text-rose-800">
            Could not load tasks
          </p>
          <p className="mt-1 break-words text-sm text-rose-700">{error}</p>
        </div>
      </div>
    );
  }

  if (tasks.length === 0) {
    return (
      <div className="flex min-h-56 flex-col items-center justify-center rounded-xl border border-dashed border-zinc-300 bg-white px-6 py-10 text-center">
        <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-zinc-100 text-zinc-500">
          <ClipboardList size={22} aria-hidden="true" />
        </div>

        <h3 className="text-sm font-semibold text-zinc-900">
          No tasks found
        </h3>

        <p className="mt-2 max-w-xs text-sm leading-6 text-zinc-500">
          Tasks you create will appear here. Use the assistant to create a task
          or change the current task filter.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {tasks.map((task) => (
        <TaskCard key={task.id} task={task} />
      ))}
    </div>
  );
}