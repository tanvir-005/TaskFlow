"""Tests for TaskFlow's SQLite persistence layer."""

from datetime import date

import pytest

from app import db


@pytest.fixture
def database_path(tmp_path):
    """Provide an initialized temporary database for each test."""
    path = tmp_path / "tasks.db"
    db.initialize_database(path)
    return path


def test_task_ids_are_sequential_and_never_reused(database_path):
    """Deleting a task must not cause its ID to be reused."""
    first = db.create_task(
        title="First task",
        database_path=database_path,
    )
    second = db.create_task(
        title="Second task",
        database_path=database_path,
    )
    third = db.create_task(
        title="Third task",
        database_path=database_path,
    )

    assert first["id"] == "TASK-001"
    assert second["id"] == "TASK-002"
    assert third["id"] == "TASK-003"

    assert db.delete_task("TASK-003", database_path=database_path) is True
    assert db.get_task("TASK-003", database_path=database_path) is None

    fourth = db.create_task(
        title="Fourth task",
        database_path=database_path,
    )

    assert fourth["id"] == "TASK-004"
    assert db.get_task("TASK-002", database_path=database_path) is not None


def test_task_persists_across_database_connections(database_path):
    """A task must remain available when retrieved through a new connection."""
    created = db.create_task(
        title="Prepare project report",
        description="Summarize the completed work.",
        status="in_progress",
        priority="high",
        due_date=date(2026, 11, 5),
        database_path=database_path,
    )

    retrieved = db.get_task(
        created["id"],
        database_path=database_path,
    )

    assert retrieved is not None
    assert retrieved["id"] == created["id"]
    assert retrieved["title"] == "Prepare project report"
    assert retrieved["description"] == "Summarize the completed work."
    assert retrieved["status"] == "in_progress"
    assert retrieved["priority"] == "high"
    assert retrieved["due_date"] == date(2026, 11, 5)


def test_task_updates_persist(database_path):
    """Updates must be visible to subsequent database reads."""
    created = db.create_task(
        title="Review documentation",
        database_path=database_path,
    )

    updated = db.update_task(
        created["id"],
        {"status": "done", "priority": "low"},
        database_path=database_path,
    )

    assert updated is not None
    assert updated["status"] == "done"
    assert updated["priority"] == "low"

    retrieved = db.get_task(
        created["id"],
        database_path=database_path,
    )

    assert retrieved is not None
    assert retrieved["status"] == "done"
    assert retrieved["priority"] == "low"


def test_listing_can_filter_by_status(database_path):
    """Status filtering must return only matching tasks."""
    db.create_task(
        title="Open task",
        status="todo",
        database_path=database_path,
    )
    db.create_task(
        title="Finished task",
        status="done",
        database_path=database_path,
    )

    tasks = db.list_tasks(
        database_path=database_path,
        status="todo",
    )

    assert len(tasks) == 1
    assert tasks[0]["title"] == "Open task"
    assert tasks[0]["status"] == "todo"


def test_invalid_database_values_are_rejected(database_path):
    """SQLite constraints must reject invalid task values."""
    with pytest.raises(Exception):
        db.create_task(
            title="Invalid status task",
            status="invalid",
            database_path=database_path,
        )

    assert db.list_tasks(database_path=database_path) == []