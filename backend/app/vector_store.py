"""Persistent ChromaDB vector store for TaskFlow tasks."""

from __future__ import annotations

import hashlib
import json
import threading
from pathlib import Path
from typing import Any

import chromadb
from chromadb.api.models.Collection import Collection
from chromadb.utils.embedding_functions import DefaultEmbeddingFunction

from app.config import CHROMA_PATH

COLLECTION_NAME = "tasks"

_CLIENT_LOCK = threading.Lock()
_CLIENT: chromadb.PersistentClient | None = None
_COLLECTION: Collection | None = None


def _get_collection(
    chroma_path: str | Path | None = None,
) -> Collection:
    """Return the persistent task collection, creating it when necessary."""
    global _CLIENT, _COLLECTION

    if chroma_path is not None:
        path = Path(chroma_path)
        path.mkdir(parents=True, exist_ok=True)

        client = chromadb.PersistentClient(path=str(path))
        return client.get_or_create_collection(
            name=COLLECTION_NAME,
            embedding_function=DefaultEmbeddingFunction(),
            metadata={"hnsw:space": "cosine"},
        )

    with _CLIENT_LOCK:
        if _COLLECTION is None:
            path = Path(CHROMA_PATH)
            path.mkdir(parents=True, exist_ok=True)

            _CLIENT = chromadb.PersistentClient(path=str(path))
            _COLLECTION = _CLIENT.get_or_create_collection(
                name=COLLECTION_NAME,
                embedding_function=DefaultEmbeddingFunction(),
                metadata={"hnsw:space": "cosine"},
            )

        return _COLLECTION


def task_document(task: dict[str, Any]) -> str:
    """Build the searchable document for a task."""
    title = str(task["title"]).strip()
    description = str(task.get("description") or "").strip()

    return f"{title}. {description}"


def task_content_hash(task: dict[str, Any]) -> str:
    """Compute a stable hash of the task fields indexed by ChromaDB."""
    payload = {
        "title": str(task["title"]).strip(),
        "description": str(task.get("description") or "").strip(),
        "status": str(task["status"]),
        "priority": str(task["priority"]),
        "due_date": (
            task["due_date"].isoformat()
            if hasattr(task.get("due_date"), "isoformat")
            else str(task.get("due_date") or "")
        ),
    }

    serialized = json.dumps(
        payload,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )

    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def task_metadata(task: dict[str, Any]) -> dict[str, str]:
    """Build Chroma-compatible metadata for a task."""
    due_date = task.get("due_date")

    if hasattr(due_date, "isoformat"):
        due_date_value = due_date.isoformat()
    else:
        due_date_value = str(due_date or "")

    return {
        "status": str(task["status"]),
        "priority": str(task["priority"]),
        "due_date": due_date_value,
        "content_hash": task_content_hash(task),
    }


def upsert_task(
    task: dict[str, Any],
    chroma_path: str | Path | None = None,
) -> None:
    """Insert or replace a task in the semantic-search index."""
    task_id = str(task["id"]).strip()

    if not task_id:
        raise ValueError("Task ID must not be empty.")

    collection = _get_collection(chroma_path)

    collection.upsert(
        ids=[task_id],
        documents=[task_document(task)],
        metadatas=[task_metadata(task)],
    )


def delete_task(
    task_id: str,
    chroma_path: str | Path | None = None,
) -> None:
    """Remove a task from the semantic-search index if it exists."""
    normalized_id = task_id.strip()

    if not normalized_id:
        raise ValueError("Task ID must not be empty.")

    collection = _get_collection(chroma_path)
    collection.delete(ids=[normalized_id])


def query_tasks(
    query_text: str,
    limit: int = 5,
    status: str | None = None,
    priority: str | None = None,
    exclude_done: bool = False,
    chroma_path: str | Path | None = None,
) -> list[dict[str, Any]]:
    """Search tasks semantically and return normalized ranked results."""
    normalized_query = query_text.strip()

    if not normalized_query:
        raise ValueError("Search query must not be empty.")

    if limit < 1:
        raise ValueError("Search limit must be positive.")

    collection = _get_collection(chroma_path)

    conditions: list[dict[str, Any]] = []

    if status is not None:
        conditions.append({"status": status})

    if priority is not None:
        conditions.append({"priority": priority})

    if exclude_done:
        conditions.append({"status": {"$ne": "done"}})

    where: dict[str, Any] | None = None

    if len(conditions) == 1:
        where = conditions[0]
    elif len(conditions) > 1:
        where = {"$and": conditions}

    total = collection.count()

    if total == 0:
        return []

    result = collection.query(
        query_texts=[normalized_query],
        n_results=min(limit, total),
        where=where,
        include=["documents", "metadatas", "distances"],
    )

    ids = result["ids"][0]
    documents = result["documents"][0]
    metadatas = result["metadatas"][0]
    distances = result["distances"][0]

    matches: list[dict[str, Any]] = []

    for task_id, document, metadata, distance in zip(
        ids,
        documents,
        metadatas,
        distances,
        strict=True,
    ):
        normalized_metadata = dict(metadata or {})
        cosine_distance = float(distance)

        matches.append(
            {
                "id": task_id,
                "document": document or "",
                "metadata": normalized_metadata,
                "distance": cosine_distance,
                "similarity": max(0.0, min(1.0, 1.0 - cosine_distance)),
            }
        )

    return matches


def get_indexed_tasks(
    chroma_path: str | Path | None = None,
) -> list[dict[str, Any]]:
    """Return all indexed task IDs and their metadata."""
    collection = _get_collection(chroma_path)
    result = collection.get(include=["metadatas"])

    return [
        {
            "id": task_id,
            "metadata": dict(metadata or {}),
        }
        for task_id, metadata in zip(
            result["ids"],
            result["metadatas"],
            strict=True,
        )
    ]


def reconcile(
    sqlite_tasks: list[dict[str, Any]],
    chroma_path: str | Path | None = None,
) -> dict[str, int | bool]:
    """Synchronize the Chroma index with the authoritative SQLite task list."""
    collection = _get_collection(chroma_path)

    indexed = get_indexed_tasks(chroma_path)
    indexed_by_id = {
        item["id"]: item["metadata"]
        for item in indexed
    }

    sqlite_by_id = {
        str(task["id"]): task
        for task in sqlite_tasks
    }

    upserted = 0
    unchanged = 0

    for task_id, task in sqlite_by_id.items():
        expected_hash = task_content_hash(task)
        existing_metadata = indexed_by_id.get(task_id)

        if (
            existing_metadata is not None
            and existing_metadata.get("content_hash") == expected_hash
        ):
            unchanged += 1
            continue

        upsert_task(task, chroma_path)
        upserted += 1

    orphaned_ids = sorted(set(indexed_by_id) - set(sqlite_by_id))

    if orphaned_ids:
        collection.delete(ids=orphaned_ids)

    final_count = collection.count()
    sqlite_count = len(sqlite_by_id)

    return {
        "upserted": upserted,
        "deleted": len(orphaned_ids),
        "unchanged": unchanged,
        "sqlite_count": sqlite_count,
        "chroma_count": final_count,
        "in_sync": sqlite_count == final_count,
    }