"""Integration tests for task business logic and ChromaDB synchronization."""

from __future__ import annotations

from pathlib import Path

import chromadb
import pytest
from chromadb.api.models.Collection import Collection
from chromadb.utils.embedding_functions import DefaultEmbeddingFunction

from app import db, task_service, vector_store
from app.models import ResultStatus


@pytest.fixture
def service_environment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Collection:
    """Set up isolated SQLite and ChromaDB storage for each test."""
    database_path = tmp_path / "tasks.db"
    chroma_path = tmp_path / "chroma"

    monkeypatch.setattr(db, "DATABASE_PATH", database_path)
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    db.initialize_database(database_path)

    chroma_path.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(chroma_path))
    collection = client.get_or_create_collection(
        name="tasks",
        embedding_function=DefaultEmbeddingFunction(),
        metadata={"hnsw:space": "cosine"},
    )

    monkeypatch.setattr(
        vector_store,
        "_get_collection",
        lambda chroma_path=None: collection,
    )

    return collection


def test_create_update_status_complete_and_delete_sync_index(
    service_environment: Collection,
) -> None:
    """Verify task mutations update SQLite and ChromaDB consistently."""
    collection = service_environment

    created = task_service.create_task(
        title="Write API documentation",
        description="Document the backend endpoints.",
        priority="high",
    )

    assert created.ok is True
    assert created.status == ResultStatus.SUCCESS
    assert created.task is not None
    task_id = created.task.id

    persisted = db.get_task(task_id)
    assert persisted is not None
    assert persisted["title"] == "Write API documentation"

    indexed = collection.get(ids=[task_id], include=["metadatas"])
    assert indexed["ids"] == [task_id]
    assert indexed["metadatas"][0]["content_hash"] == (
        vector_store.task_content_hash(persisted)
    )

    updated = task_service.update_task(
        task_ref=task_id,
        title="Document the API",
        priority="low",
    )

    assert updated.ok is True
    assert updated.task is not None
    assert updated.task.title == "Document the API"
    assert updated.task.priority == "low"

    persisted = db.get_task(task_id)
    assert persisted is not None
    indexed = collection.get(ids=[task_id], include=["metadatas"])
    assert indexed["metadatas"][0]["content_hash"] == (
        vector_store.task_content_hash(persisted)
    )

    moved = task_service.set_status(task_id, "in_progress")

    assert moved.ok is True
    assert moved.task is not None
    assert moved.task.status == "in_progress"

    indexed = collection.get(ids=[task_id], include=["metadatas"])
    assert indexed["metadatas"][0]["status"] == "in_progress"

    completed = task_service.complete_task(task_id)

    assert completed.ok is True
    assert completed.task is not None
    assert completed.task.status == "done"

    indexed = collection.get(ids=[task_id], include=["metadatas"])
    assert indexed["metadatas"][0]["status"] == "done"

    deleted = task_service.delete_task(task_id)

    assert deleted.ok is True
    assert db.get_task(task_id) is None
    assert collection.get(ids=[task_id])["ids"] == []


def test_ambiguous_update_does_not_mutate_any_task(
    service_environment: Collection,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ensure an ambiguous reference cannot change either candidate."""
    first = db.create_task(
        title="Write API documentation",
        description="Document API endpoints.",
    )
    second = db.create_task(
        title="Review API pull request",
        description="Review the API change.",
    )

    monkeypatch.setattr(
        vector_store,
        "query_tasks",
        lambda **kwargs: [
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
        ],
    )

    result = task_service.update_task(
        task_ref="API work",
        priority="high",
    )

    assert result.ok is False
    assert result.status == ResultStatus.NEEDS_CLARIFICATION
    assert db.get_task(str(first["id"]))["priority"] == "medium"
    assert db.get_task(str(second["id"]))["priority"] == "medium"


def test_reconcile_repairs_changed_and_orphaned_index_entries(
    service_environment: Collection,
) -> None:
    """Repair changed metadata and remove IDs absent from SQLite."""
    collection = service_environment

    created = task_service.create_task(
        title="Prepare weekly report",
        description="Summarize this week's work.",
    )

    assert created.ok is True
    assert created.task is not None
    task_id = created.task.id

    collection.upsert(
        ids=[task_id],
        documents=["Outdated document"],
        metadatas=[
            {
                "status": "done",
                "priority": "low",
                "due_date": "",
                "content_hash": "deliberately-corrupted",
            }
        ],
    )
    collection.upsert(
        ids=["TASK-999"],
        documents=["Orphaned task"],
        metadatas=[
            {
                "status": "todo",
                "priority": "medium",
                "due_date": "",
                "content_hash": "orphaned",
            }
        ],
    )

    result = task_service.reconcile()

    assert result["upserted"] == 1
    assert result["deleted"] == 1
    assert result["in_sync"] is True
    assert result["sqlite_count"] == 1
    assert result["chroma_count"] == 1

    persisted = db.get_task(task_id)
    assert persisted is not None

    indexed = collection.get(ids=[task_id], include=["metadatas"])
    assert indexed["metadatas"][0]["content_hash"] == (
        vector_store.task_content_hash(persisted)
    )
    assert collection.get(ids=["TASK-999"])["ids"] == []