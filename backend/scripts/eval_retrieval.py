"""Evaluate semantic task retrieval using an isolated temporary database."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from typing import Any

BACKEND_DIR = Path(__file__).resolve().parents[1]

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import chromadb
from chromadb.utils.embedding_functions import DefaultEmbeddingFunction

from app import db, task_service, vector_store
from scripts.seed import build_demo_tasks


QUERIES: list[tuple[str, set[str]]] = [
    ("docs", {"TASK-001", "TASK-009"}),
    (
        "things about the backend",
        {
            "TASK-001",
            "TASK-002",
            "TASK-007",
            "TASK-008",
            "TASK-011",
            "TASK-012",
            "TASK-018",
            "TASK-019",
        },
    ),
    ("weekly status update", {"TASK-004"}),
    ("fix a problem with signing in", {"TASK-003"}),
    ("make the dashboard look better", {"TASK-005"}),
    ("tests for adding new tasks", {"TASK-006"}),
    ("make database operations faster", {"TASK-007", "TASK-012"}),
    ("put the application on a test server", {"TASK-008"}),
    ("meeting to plan upcoming work", {"TASK-010"}),
    ("find tasks using natural language", {"TASK-011"}),
    ("prepare slides to explain the project", {"TASK-013"}),
    ("check whether task status changes work correctly", {"TASK-014"}),
    ("buy food and household supplies", {"TASK-015"}),
    ("pay the monthly utility bill", {"TASK-016"}),
    ("investigate incorrect search results", {"TASK-018"}),
]

TOP_K = 5


def _extract_task_ids(results: Any) -> list[str]:
    """Extract task IDs from the vector store's query results."""
    if isinstance(results, dict):
        ids = results.get("ids")

        if isinstance(ids, list):
            if ids and isinstance(ids[0], list):
                return [str(item) for item in ids[0]]
            return [str(item) for item in ids]

        for key in ("tasks", "results", "items"):
            if key in results:
                return _extract_task_ids(results[key])

        return []

    if not isinstance(results, (list, tuple)):
        return []

    task_ids: list[str] = []

    for item in results:
        if isinstance(item, str):
            task_ids.append(item)
        elif isinstance(item, dict):
            task_id = item.get("id", item.get("task_id"))
            if task_id is not None:
                task_ids.append(str(task_id))
        else:
            task_id = getattr(item, "id", None)
            if task_id is not None:
                task_ids.append(str(task_id))

    return task_ids


def evaluate() -> None:
    """Run retrieval evaluation in temporary storage and report hit rates."""
    original_database_path = db.DATABASE_PATH
    original_get_collection = vector_store._get_collection

    with tempfile.TemporaryDirectory(prefix="taskflow-eval-") as temporary_dir:
        temporary_path = Path(temporary_dir)
        database_path = temporary_path / "tasks.db"
        chroma_path = temporary_path / "chroma"

        client = chromadb.PersistentClient(path=str(chroma_path))
        collection = client.get_or_create_collection(
            name="tasks",
            metadata={"hnsw:space": "cosine"},
            embedding_function=DefaultEmbeddingFunction(),
        )

        try:
            db.DATABASE_PATH = database_path

            # Accept the optional path argument used by vector_store.py,
            # but always return this evaluation's isolated collection.
            vector_store._get_collection = (
                lambda _chroma_path=None: collection
            )

            db.initialize_default_database()

            for task_data in build_demo_tasks():
                result = task_service.create_task(**task_data)

                if not result.ok:
                    raise RuntimeError(
                        f"Could not seed evaluation task "
                        f"{task_data['title']!r}: {result.message}"
                    )

            top1_hits = 0
            top3_hits = 0
            total_queries = len(QUERIES)

            print(f"Evaluating {total_queries} queries against 20 demo tasks.")
            print("-" * 72)

            for query, expected_ids in QUERIES:
                results = vector_store.query_tasks(query, limit=TOP_K)
                retrieved_ids = _extract_task_ids(results)

                top1_hit = bool(
                    retrieved_ids and retrieved_ids[0] in expected_ids
                )
                top3_hit = bool(set(retrieved_ids[:3]) & expected_ids)

                top1_hits += int(top1_hit)
                top3_hits += int(top3_hit)

                print(f"[{'PASS' if top3_hit else 'MISS'}] {query}")
                print(f"  Expected IDs: {', '.join(sorted(expected_ids))}")
                print(
                    f"  Retrieved IDs: "
                    f"{', '.join(retrieved_ids[:3]) or '(none)'}"
                )

                if not top1_hit:
                    print("  Top-1 miss.")

                if not top3_hit:
                    print("  Top-3 miss.")

            top1_rate = top1_hits / total_queries * 100
            top3_rate = top3_hits / total_queries * 100

            print("-" * 72)
            print(
                f"Top-1 hit rate: "
                f"{top1_hits}/{total_queries} ({top1_rate:.1f}%)"
            )
            print(
                f"Top-3 hit rate: "
                f"{top3_hits}/{total_queries} ({top3_rate:.1f}%)"
            )
            print("Target top-3 hit rate: 85.0%")
            print(
                "Target reached."
                if top3_rate >= 85.0
                else "Target not reached; inspect misses before tuning retrieval."
            )

        finally:
            vector_store._get_collection = original_get_collection
            db.DATABASE_PATH = original_database_path
            del collection
            del client


if __name__ == "__main__":
    evaluate()  