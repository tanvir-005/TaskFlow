import { useCallback, useEffect, useState } from "react";
import { api } from "../lib/api";
import type { Task, TaskStatus } from "../types/task";

interface UseTasksReturn {
  tasks: Task[];
  loading: boolean;
  error: string | null;
  filter: TaskStatus | "all";
  setFilter: (filter: TaskStatus | "all") => void;
  refreshTasks: () => Promise<void>;
}

export function useTasks(): UseTasksReturn {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<TaskStatus | "all">("all");

  const refreshTasks = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const response = await api.getTasks(
        filter === "all" ? undefined : filter,
      );

      setTasks(response.tasks);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Failed to load tasks.",
      );
    } finally {
      setLoading(false);
    }
  }, [filter]);

  useEffect(() => {
    void refreshTasks();
  }, [refreshTasks]);

  return {
    tasks,
    loading,
    error,
    filter,
    setFilter,
    refreshTasks,
  };
}