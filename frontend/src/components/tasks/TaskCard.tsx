import {
  CalendarDays,
  CheckCircle2,
  Circle,
  Clock3,
  ListTodo,
} from "lucide-react";
import type { Task, TaskPriority, TaskStatus } from "../../types/task";

interface TaskCardProps {
  task: Task;
}

const statusConfig: Record<
  TaskStatus,
  { label: string; className: string; icon: typeof Circle }
> = {
  todo: {
    label: "To do",
    className: "bg-zinc-100 text-zinc-700",
    icon: Circle,
  },
  in_progress: {
    label: "In progress",
    className: "bg-blue-50 text-blue-700",
    icon: Clock3,
  },
  done: {
    label: "Completed",
    className: "bg-emerald-50 text-emerald-700",
    icon: CheckCircle2,
  },
};

const priorityConfig: Record<
  TaskPriority,
  { label: string; className: string }
> = {
  low: {
    label: "Low",
    className: "bg-zinc-100 text-zinc-600",
  },
  medium: {
    label: "Medium",
    className: "bg-amber-50 text-amber-700",
  },
  high: {
    label: "High",
    className: "bg-rose-50 text-rose-700",
  },
};

function formatDueDate(value: string | null): string | null {
  if (!value) {
    return null;
  }

  const datePart = value.slice(0, 10);
  const date = new Date(`${datePart}T00:00:00`);

  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
  }).format(date);
}

function isOverdue(task: Task): boolean {
  if (!task.due_date || task.status === "done") {
    return false;
  }

  const dueDate = task.due_date.slice(0, 10);
  const today = new Date();
  const todayDate = [
    today.getFullYear(),
    String(today.getMonth() + 1).padStart(2, "0"),
    String(today.getDate()).padStart(2, "0"),
  ].join("-");

  return dueDate < todayDate;
}

export function TaskCard({ task }: TaskCardProps) {
  const status = statusConfig[task.status];
  const priority = priorityConfig[task.priority];
  const StatusIcon = status.icon;
  const dueDate = formatDueDate(task.due_date);
  const overdue = isOverdue(task);

  return (
    <article className="rounded-xl border border-zinc-200 bg-white p-4 transition-colors hover:border-zinc-300 sm:p-5">
      <div className="flex items-start gap-3">
        <div className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-zinc-100 text-zinc-600">
          <ListTodo size={18} aria-hidden="true" />
        </div>

        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-start justify-between gap-2">
            <div className="min-w-0">
              <p className="mb-1 font-mono text-xs text-zinc-500">
                {task.id}
              </p>

              <h3
                className={`break-words text-sm font-semibold leading-5 ${
                  task.status === "done"
                    ? "text-zinc-500 line-through"
                    : "text-zinc-900"
                }`}
              >
                {task.title}
              </h3>
            </div>

            <span
              className={`inline-flex shrink-0 items-center rounded-full px-2.5 py-1 text-xs font-medium ${priority.className}`}
            >
              {priority.label} priority
            </span>
          </div>

          {task.description.trim() && (
            <p className="mt-2 whitespace-pre-wrap break-words text-sm leading-6 text-zinc-600">
              {task.description}
            </p>
          )}

          <div className="mt-4 flex flex-wrap items-center gap-x-4 gap-y-2 border-t border-zinc-100 pt-3">
            <span
              className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ${status.className}`}
            >
              <StatusIcon size={13} aria-hidden="true" />
              {status.label}
            </span>

            {dueDate && (
              <span
                className={`inline-flex items-center gap-1.5 text-xs ${
                  overdue ? "font-medium text-rose-600" : "text-zinc-500"
                }`}
              >
                <CalendarDays size={14} aria-hidden="true" />
                {overdue ? `Overdue · ${dueDate}` : dueDate}
              </span>
            )}
          </div>
        </div>
      </div>
    </article>
  );
}