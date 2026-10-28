import type { TaskStatus } from "../../types/task";
import { TASK_FILTERS } from "./TaskSummary";

interface TaskFiltersProps {
  value: TaskStatus | "all";
  onChange: (value: TaskStatus | "all") => void;
  counts?: Partial<Record<TaskStatus | "all", number>>;
}

export function TaskFilters({
  value,
  onChange,
  counts,
}: TaskFiltersProps) {
  return (
    <div
      className="flex flex-wrap gap-2"
      role="group"
      aria-label="Filter tasks by status"
    >
      {TASK_FILTERS.map((filter) => {
        const active = value === filter.value;
        const count = counts?.[filter.value];

        return (
          <button
            key={filter.value}
            type="button"
            onClick={() => onChange(filter.value)}
            aria-pressed={active}
            className={`inline-flex min-h-9 items-center gap-2 rounded-lg border px-3 py-2 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-zinc-500 focus-visible:ring-offset-2 ${
              active
                ? "border-zinc-900 bg-zinc-900 text-white"
                : "border-zinc-200 bg-white text-zinc-600 hover:border-zinc-300 hover:bg-zinc-50"
            }`}
          >
            {filter.label}

            {typeof count === "number" && (
              <span
                className={`rounded-md px-1.5 py-0.5 text-xs ${
                  active
                    ? "bg-white/15 text-white"
                    : "bg-zinc-100 text-zinc-600"
                }`}
              >
                {count}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}