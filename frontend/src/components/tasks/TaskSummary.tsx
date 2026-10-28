import { CheckCircle2, Circle, Clock3, ListTodo } from "lucide-react";
import type { Task, TaskStatus } from "../../types/task";

interface TaskSummaryProps {
  tasks: Task[];
}

interface SummaryItem {
  label: string;
  count: number;
  icon: typeof ListTodo;
  iconClass: string;
}

export function TaskSummary({ tasks }: TaskSummaryProps) {
  const summary: SummaryItem[] = [
    {
      label: "Total tasks",
      count: tasks.length,
      icon: ListTodo,
      iconClass: "bg-zinc-100 text-zinc-700",
    },
    {
      label: "To do",
      count: tasks.filter((task) => task.status === "todo").length,
      icon: Circle,
      iconClass: "bg-zinc-100 text-zinc-600",
    },
    {
      label: "In progress",
      count: tasks.filter((task) => task.status === "in_progress").length,
      icon: Clock3,
      iconClass: "bg-blue-50 text-blue-700",
    },
    {
      label: "Completed",
      count: tasks.filter((task) => task.status === "done").length,
      icon: CheckCircle2,
      iconClass: "bg-emerald-50 text-emerald-700",
    },
  ];

  return (
    <section
      className="grid grid-cols-2 gap-3 lg:grid-cols-4"
      aria-label="Task summary"
    >
      {summary.map((item) => {
        const Icon = item.icon;

        return (
          <article
            key={item.label}
            className="rounded-xl border border-zinc-200 bg-white p-4"
          >
            <div className="flex items-center gap-3">
              <div
                className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-lg ${item.iconClass}`}
              >
                <Icon size={19} aria-hidden="true" />
              </div>

              <div className="min-w-0">
                <p className="text-xs text-zinc-500">{item.label}</p>
                <p className="mt-1 text-xl font-semibold tracking-tight text-zinc-900">
                  {item.count}
                </p>
              </div>
            </div>
          </article>
        );
      })}
    </section>
  );
}

export const TASK_FILTERS: {
  label: string;
  value: TaskStatus | "all";
}[] = [
  { label: "All tasks", value: "all" },
  { label: "To do", value: "todo" },
  { label: "In progress", value: "in_progress" },
  { label: "Completed", value: "done" },
];