"""SQLite persistence layer for TaskFlow."""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from app.config import DATABASE_PATH, DATA_DIR

_WRITE_LOCK = threading.Lock()


def utc_now() -> str:
    """Return the current UTC timestamp in ISO 8601 format."""
    return datetime.now(UTC).isoformat()


def get_connection(
    database_path: str | Path | None = None,
) -> sqlite3.Connection:
    """Open a SQLite connection with row access and foreign keys enabled."""
    path = Path(database_path) if database_path is not None else DATABASE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(
        str(path),
        timeout=30.0,
        isolation_level="DEFERRED",
    )
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 30000")

    return connection


def initialize_database(
    database_path: str | Path | None = None,
) -> None:
    """Create database tables and initialize the task ID counter."""
    path = Path(database_path) if database_path is not None else DATABASE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)

    with _WRITE_LOCK:
        connection = get_connection(path)

        try:
            connection.execute("PRAGMA journal_mode = WAL")

            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL
                        CHECK(length(trim(title)) BETWEEN 1 AND 120),
                    description TEXT NOT NULL DEFAULT ''
                        CHECK(length(description) <= 1000),
                    status TEXT NOT NULL
                        CHECK(status IN ('todo', 'in_progress', 'done')),
                    priority TEXT NOT NULL
                        CHECK(priority IN ('low', 'medium', 'high')),
                    due_date TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_tasks_status
                    ON tasks(status);

                CREATE INDEX IF NOT EXISTS idx_tasks_priority
                    ON tasks(priority);

                CREATE INDEX IF NOT EXISTS idx_tasks_due_date
                    ON tasks(due_date);

                CREATE TABLE IF NOT EXISTS counters (
                    name TEXT PRIMARY KEY,
                    value INTEGER NOT NULL CHECK(value >= 0)
                );

                INSERT OR IGNORE INTO counters (name, value)
                VALUES ('task_id', 0);

                CREATE TABLE IF NOT EXISTS chat_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL
                        CHECK(role IN ('user', 'assistant')),
                    content TEXT NOT NULL,
                    meta TEXT,
                    created_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_chat_session_id
                    ON chat_messages(session_id, id);
                """
            )

            connection.commit()
        finally:
            connection.close()


def _generate_task_id(connection: sqlite3.Connection) -> str:
    """Allocate a unique task ID inside an existing write transaction."""
    connection.execute(
        """
        UPDATE counters
        SET value = value + 1
        WHERE name = 'task_id'
        """
    )

    row = connection.execute(
        "SELECT value FROM counters WHERE name = 'task_id'"
    ).fetchone()

    if row is None:
        raise RuntimeError("The task ID counter has not been initialized.")

    return f"TASK-{row['value']:03d}"


def _serialize_task(task: dict[str, Any]) -> dict[str, Any]:
    """Convert SQLite task values into API-compatible Python values."""
    result = dict(task)

    if result.get("due_date"):
        result["due_date"] = date.fromisoformat(result["due_date"])

    return result


def create_task(
    title: str,
    description: str = "",
    status: str = "todo",
    priority: str = "medium",
    due_date: date | str | None = None,
    database_path: str | Path | None = None,
) -> dict[str, Any]:
    """Create a task and return its persisted representation."""
    path = Path(database_path) if database_path is not None else DATABASE_PATH

    if isinstance(due_date, date):
        due_date_value = due_date.isoformat()
    else:
        due_date_value = due_date

    timestamp = utc_now()

    with _WRITE_LOCK:
        connection = get_connection(path)

        try:
            connection.execute("BEGIN IMMEDIATE")
            task_id = _generate_task_id(connection)

            connection.execute(
                """
                INSERT INTO tasks (
                    id, title, description, status, priority,
                    due_date, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task_id,
                    title,
                    description,
                    status,
                    priority,
                    due_date_value,
                    timestamp,
                    timestamp,
                ),
            )

            row = connection.execute(
                "SELECT * FROM tasks WHERE id = ?",
                (task_id,),
            ).fetchone()

            connection.commit()

            if row is None:
                raise RuntimeError("The created task could not be retrieved.")

            return _serialize_task(dict(row))
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()


def get_task(
    task_id: str,
    database_path: str | Path | None = None,
) -> dict[str, Any] | None:
    """Retrieve one task by its exact ID."""
    path = Path(database_path) if database_path is not None else DATABASE_PATH
    connection = get_connection(path)

    try:
        row = connection.execute(
            "SELECT * FROM tasks WHERE id = ?",
            (task_id,),
        ).fetchone()

        return _serialize_task(dict(row)) if row is not None else None
    finally:
        connection.close()


def list_tasks(
    database_path: str | Path | None = None,
    status: str | None = None,
) -> list[dict[str, Any]]:
    """Retrieve tasks in a stable order, optionally filtered by status."""
    path = Path(database_path) if database_path is not None else DATABASE_PATH
    connection = get_connection(path)

    try:
        query = """
            SELECT *
            FROM tasks
        """
        parameters: tuple[str, ...] = ()

        if status is not None:
            query += " WHERE status = ?"
            parameters = (status,)

        query += """
            ORDER BY
                CASE WHEN status = 'done' THEN 1 ELSE 0 END,
                CASE WHEN due_date IS NULL THEN 1 ELSE 0 END,
                due_date ASC,
                CASE priority
                    WHEN 'high' THEN 0
                    WHEN 'medium' THEN 1
                    WHEN 'low' THEN 2
                END,
                id ASC
        """

        rows = connection.execute(query, parameters).fetchall()

        return [_serialize_task(dict(row)) for row in rows]
    finally:
        connection.close()


def update_task(
    task_id: str,
    changes: dict[str, Any],
    database_path: str | Path | None = None,
) -> dict[str, Any] | None:
    """Update permitted task fields and return the updated task."""
    allowed_fields = {
        "title",
        "description",
        "status",
        "priority",
        "due_date",
    }

    if not changes:
        raise ValueError("At least one field change is required.")

    unknown_fields = set(changes) - allowed_fields

    if unknown_fields:
        raise ValueError(
            f"Unsupported task fields: {', '.join(sorted(unknown_fields))}"
        )

    normalized_changes = dict(changes)

    if isinstance(normalized_changes.get("due_date"), date):
        normalized_changes["due_date"] = normalized_changes[
            "due_date"
        ].isoformat()

    path = Path(database_path) if database_path is not None else DATABASE_PATH

    with _WRITE_LOCK:
        connection = get_connection(path)

        try:
            connection.execute("BEGIN IMMEDIATE")

            existing = connection.execute(
                "SELECT id FROM tasks WHERE id = ?",
                (task_id,),
            ).fetchone()

            if existing is None:
                connection.commit()
                return None

            assignments = [
                f"{field} = ?" for field in normalized_changes
            ]
            assignments.append("updated_at = ?")

            values = list(normalized_changes.values())
            values.append(utc_now())
            values.append(task_id)

            connection.execute(
                f"""
                UPDATE tasks
                SET {", ".join(assignments)}
                WHERE id = ?
                """,
                values,
            )

            row = connection.execute(
                "SELECT * FROM tasks WHERE id = ?",
                (task_id,),
            ).fetchone()

            connection.commit()

            if row is None:
                raise RuntimeError("The updated task could not be retrieved.")

            return _serialize_task(dict(row))
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()


def delete_task(
    task_id: str,
    database_path: str | Path | None = None,
) -> bool:
    """Delete a task by ID and report whether it existed."""
    path = Path(database_path) if database_path is not None else DATABASE_PATH

    with _WRITE_LOCK:
        connection = get_connection(path)

        try:
            connection.execute("BEGIN IMMEDIATE")

            cursor = connection.execute(
                "DELETE FROM tasks WHERE id = ?",
                (task_id,),
            )

            connection.commit()
            return cursor.rowcount > 0
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()


def save_chat_message(
    session_id: str,
    role: str,
    content: str,
    meta: dict[str, Any] | None = None,
    database_path: str | Path | None = None,
) -> dict[str, Any]:
    """Persist a chat message and return the saved message."""
    if role not in {"user", "assistant"}:
        raise ValueError("Chat role must be 'user' or 'assistant'.")

    if not session_id.strip():
        raise ValueError("Session ID must not be empty.")

    if not content.strip():
        raise ValueError("Chat content must not be empty.")

    meta_json = json.dumps(meta, ensure_ascii=False) if meta is not None else None
    path = Path(database_path) if database_path is not None else DATABASE_PATH

    with _WRITE_LOCK:
        connection = get_connection(path)

        try:
            connection.execute("BEGIN IMMEDIATE")

            cursor = connection.execute(
                """
                INSERT INTO chat_messages (
                    session_id, role, content, meta, created_at
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (session_id, role, content, meta_json, utc_now()),
            )

            message_id = cursor.lastrowid

            row = connection.execute(
                "SELECT * FROM chat_messages WHERE id = ?",
                (message_id,),
            ).fetchone()

            connection.commit()

            if row is None:
                raise RuntimeError("The saved chat message could not be retrieved.")

            result = dict(row)

            if result["meta"] is not None:
                result["meta"] = json.loads(result["meta"])

            return result
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()


def get_chat_history(
    session_id: str,
    limit: int = 20,
    database_path: str | Path | None = None,
) -> list[dict[str, Any]]:
    """Retrieve the most recent chat messages in chronological order."""
    if limit < 1:
        raise ValueError("History limit must be positive.")

    path = Path(database_path) if database_path is not None else DATABASE_PATH
    connection = get_connection(path)

    try:
        rows = connection.execute(
            """
            SELECT *
            FROM (
                SELECT *
                FROM chat_messages
                WHERE session_id = ?
                ORDER BY id DESC
                LIMIT ?
            )
            ORDER BY id ASC
            """,
            (session_id, limit),
        ).fetchall()

        messages = []

        for row in rows:
            message = dict(row)

            if message["meta"] is not None:
                message["meta"] = json.loads(message["meta"])

            messages.append(message)

        return messages
    finally:
        connection.close()


def clear_chat_history(
    session_id: str,
    database_path: str | Path | None = None,
) -> int:
    """Delete a session's chat history and return the number removed."""
    path = Path(database_path) if database_path is not None else DATABASE_PATH

    with _WRITE_LOCK:
        connection = get_connection(path)

        try:
            connection.execute("BEGIN IMMEDIATE")

            cursor = connection.execute(
                "DELETE FROM chat_messages WHERE session_id = ?",
                (session_id,),
            )

            connection.commit()
            return cursor.rowcount
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()


def initialize_default_database() -> None:
    """Initialize the application's configured SQLite database."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    initialize_database(DATABASE_PATH)