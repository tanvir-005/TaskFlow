"""Tests for safe task-reference resolution."""

from __future__ import annotations

from pathlib import Path

import pytest

from app import db, task_service, vector_store
from app.models import ResultStatus


@pytest.fixture
def resolver_environment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> list[dict[str, object]]:
    """Create isolated SQLite tasks and a controllable semantic search."""
    database_path = tmp_path / "tasks.db"
    monkeypatch.setattr(db, "DATABASE_PATH", database_path)
    db.initialize_database(database_path)

    first = db.create_task(
        title="Write API documentation",
        description="Document the backend API endpoints.",
        priority="high",
    )
    second = db.create_task(
        title="Review API pull request",
        description="Review the new API implementation.",
        priority="medium",
    )
    third = db.create_task(
        title="Buy groceries",
        description="Purchase vegetables and rice.",
        priority="low",
    )

    def fake_query_tasks(
        query_text: str,
        limit: int = 5,
        status: str | None = None,
        priority: str | None = None,
        exclude_done: bool = False,
        chroma_path: str | Path | None = None,
    ) -> list[dict[str, object]]:
        """Return deterministic search matches for resolver tests."""
        del limit, status, priority, exclude_done, chroma_path

        if query_text == "backend API docs":
            return [
                {
                    "id": first["id"],
                    "similarity": 0.99,
                    "distance": 0.01,
                    "document": "Write API documentation.",
                    "metadata": {},
                },
                {
                    "id": second["id"],
                    "similarity": 0.20,
                    "distance": 0.80,
                    "document": "Review API pull request.",
                    "metadata": {},
                },
            ]

        if query_text == "API work":
            return [
                {
                    "id": first["id"],
                    "similarity": 0.75,
                    "distance": 0.25,
                    "document": "Write API documentation.",
                    "metadata": {},
                },
                {
                    "id": second["id"],
                    "similarity": 0.75,
                    "distance": 0.25,
                    "document": "Review API pull request.",
                    "metadata": {},
                },
            ]

        if query_text == "something completely unrelated":
            return [
                {
                    "id": third["id"],
                    "similarity": 0.05,
                    "distance": 0.95,
                    "document": "Buy groceries.",
                    "metadata": {},
                }
            ]

        return []

    monkeypatch.setattr(vector_store, "query_tasks", fake_query_tasks)

    return [first, second, third]


def test_resolve_exact_id(
    resolver_environment: list[dict[str, object]],
) -> None:
    """Resolve an existing task ID without semantic search."""
    tasks = resolver_environment

    result = task_service.resolve_task_ref(str(tasks[0]["id"]).lower())

    assert result.ok is True
    assert result.status == ResultStatus.SUCCESS
    assert result.task is not None
    assert result.task.id == tasks[0]["id"]


def test_missing_exact_id_returns_not_found(
    resolver_environment: list[dict[str, object]],
) -> None:
    """Never substitute another task when an exact ID is missing."""
    del resolver_environment

    result = task_service.resolve_task_ref("TASK-999")

    assert result.ok is False
    assert result.status == ResultStatus.NOT_FOUND
    assert result.task is None


def test_resolve_exact_title(
    resolver_environment: list[dict[str, object]],
) -> None:
    """Resolve a unique exact title case-insensitively."""
    tasks = resolver_environment

    result = task_service.resolve_task_ref("WRITE API DOCUMENTATION")

    assert result.ok is True
    assert result.status == ResultStatus.SUCCESS
    assert result.task is not None
    assert result.task.id == tasks[0]["id"]


def test_resolve_unambiguous_description(
    resolver_environment: list[dict[str, object]],
) -> None:
    """Resolve a semantic description when its score is clearly higher."""
    tasks = resolver_environment

    result = task_service.resolve_task_ref("backend API docs")

    assert result.ok is True
    assert result.status == ResultStatus.SUCCESS
    assert result.task is not None
    assert result.task.id == tasks[0]["id"]


def test_ambiguous_description_requires_clarification(
    resolver_environment: list[dict[str, object]],
) -> None:
    """Return candidate tasks instead of choosing between close matches."""
    del resolver_environment

    result = task_service.resolve_task_ref("API work")

    assert result.ok is False
    assert result.status == ResultStatus.NEEDS_CLARIFICATION
    assert result.task is None
    assert result.candidates is not None
    assert len(result.candidates) == 2
    assert {
        candidate.id for candidate in result.candidates
    } == {"TASK-001", "TASK-002"}


def test_nonsense_reference_returns_not_found(
    resolver_environment: list[dict[str, object]],
) -> None:
    """Reject semantic matches that do not meet the candidate threshold."""
    del resolver_environment

    result = task_service.resolve_task_ref(
        "something completely unrelated"
    )

    assert result.ok is False
    assert result.status == ResultStatus.NOT_FOUND
    assert result.candidates is None