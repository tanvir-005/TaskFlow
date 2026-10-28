"""Task business logic, task-reference resolution, and SQLite/Chroma synchronization."""

from __future__ import annotations

import logging
import re
import sqlite3
from datetime import date, datetime
from typing import Any

from pydantic import ValidationError

from app import db, vector_store
from app.config import (
    APP_TIMEZONE,
    CANDIDATE_MIN,
    LEXICAL_WEIGHT,
    RESOLVE_GAP,
    RESOLVE_MIN,
    SEMANTIC_WEIGHT,
)
from app.models import (
    ActionResult,
    ResultStatus,
    Task,
    TaskCandidate,
    TaskCreate,
    TaskUpdate,
)

logger = logging.getLogger(__name__)

_TASK_ID_PATTERN = re.compile(r"^TASK-\d+$", re.IGNORECASE)

_STOPWORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "by",
        "for",
        "from",
        "i",
        "in",
        "is",
        "it",
        "me",
        "my",
        "of",
        "on",
        "or",
        "please",
        "task",
        "tasks",
        "that",
        "the",
        "this",
        "to",
        "up",
        "with",
    }
)


def _make_result(
    *,
    ok: bool,
    status: ResultStatus,
    message: str,
    task: dict[str, Any] | None = None,
    tasks: list[dict[str, Any]] | None = None,
    candidates: list[dict[str, Any]] | None = None,
) -> ActionResult:
    """Build a validated, consistent result envelope."""
    return ActionResult(
        ok=ok,
        status=status,
        message=message,
        task=Task.model_validate(task) if task is not None else None,
        tasks=[Task.model_validate(item) for item in tasks]
        if tasks is not None
        else None,
        candidates=[
            TaskCandidate.model_validate(item) for item in candidates
        ]
        if candidates is not None
        else None,
    )


def _validation_message(exc: ValidationError) -> str:
    """Extract a readable message from the first validation error."""
    errors = exc.errors()

    if not errors:
        return "The supplied task information is invalid."

    field = str(errors[0]["loc"][-1]).replace("_", " ")
    message = str(errors[0]["msg"]).removeprefix("Value error, ")

    return f"Invalid {field}: {message}"


def _candidate_from_task(task: dict[str, Any]) -> dict[str, Any]:
    """Return the fields displayed when asking the user to identify a task."""
    return {
        "id": task["id"],
        "title": task["title"],
        "status": task["status"],
        "priority": task["priority"],
        "due_date": task.get("due_date"),
    }


def _tokens(text: str) -> set[str]:
    """Return normalized words after removing common stopwords."""
    return {
        token
        for token in re.findall(r"[a-z0-9]+", text.casefold())
        if token not in _STOPWORDS
    }


def _lexical_overlap(task_ref: str, task: dict[str, Any]) -> float:
    """Calculate the fraction of meaningful reference tokens in a task."""
    reference_tokens = _tokens(task_ref)

    if not reference_tokens:
        return 0.0

    task_text = f"{task['title']} {task.get('description') or ''}"
    task_tokens = _tokens(task_text)

    return len(reference_tokens & task_tokens) / len(reference_tokens)


def _sync_upsert(task: dict[str, Any]) -> bool:
    """Synchronize a persisted task with Chroma and report success."""
    try:
        vector_store.upsert_task(task)
        return True
    except Exception:
        logger.exception("Failed to synchronize task %s with ChromaDB.", task["id"])
        return False


def create_task(
    title: str,
    description: str = "",
    priority: str = "medium",
    status: str = "todo",
    due_date: str | date | None = None,
) -> ActionResult:
    """Validate and create a task, then synchronize its search document."""
    try:
        validated = TaskCreate(
            title=title,
            description=description,
            priority=priority,
            status=status,
            due_date=due_date,
        )
        values = validated.model_dump(mode="json")
        task = db.create_task(**values)
    except ValidationError as exc:
        return _make_result(
            ok=False,
            status=ResultStatus.VALIDATION_ERROR,
            message=_validation_message(exc),
        )
    except (sqlite3.Error, ValueError):
        logger.exception("Failed to create a task.")
        return _make_result(
            ok=False,
            status=ResultStatus.ERROR,
            message="The task could not be saved. Please try again.",
        )

    if not _sync_upsert(task):
        return _make_result(
            ok=False,
            status=ResultStatus.ERROR,
            message=(
                f"{task['id']} was saved, but its search index could not be "
                "updated. The index can be repaired by reconciliation."
            ),
            task=task,
        )

    message = f"Created {task['id']}: {task['title']}."

    if task.get("due_date") and task["due_date"] < datetime.now(
        APP_TIMEZONE
    ).date():
        message += " (note: this date is in the past)"

    return _make_result(
        ok=True,
        status=ResultStatus.SUCCESS,
        message=message,
        task=task,
    )


def list_tasks(
    status: str | None = None,
    priority: str | None = None,
    due_before: str | date | None = None,
    due_after: str | date | None = None,
    overdue_only: bool = False,
    exclude_done: bool = False,
) -> ActionResult:
    """List tasks using structured filters without semantic ranking."""
    today = datetime.now(APP_TIMEZONE).date()

    try:
        all_tasks = db.list_tasks(status=status)
    except sqlite3.Error:
        logger.exception("Failed to list tasks.")
        return _make_result(
            ok=False,
            status=ResultStatus.ERROR,
            message="Tasks could not be loaded. Please try again.",
        )

    before_value = (
        date.fromisoformat(due_before)
        if isinstance(due_before, str)
        else due_before
    )
    after_value = (
        date.fromisoformat(due_after)
        if isinstance(due_after, str)
        else due_after
    )

    filtered: list[dict[str, Any]] = []

    for task in all_tasks:
        task_due = task.get("due_date")

        if exclude_done and task["status"] == "done":
            continue

        if priority is not None and task["priority"] != priority:
            continue

        if overdue_only:
            if task["status"] == "done" or task_due is None or task_due >= today:
                continue

        if before_value is not None:
            if task_due is None or task_due > before_value:
                continue

        if after_value is not None:
            if task_due is None or task_due < after_value:
                continue

        filtered.append(task)

    return _make_result(
        ok=True,
        status=ResultStatus.SUCCESS,
        message=f"Found {len(filtered)} task(s).",
        tasks=filtered,
    )


def search_tasks(
    query: str,
    status: str | None = None,
    priority: str | None = None,
    exclude_done: bool = False,
    limit: int = 5,
) -> ActionResult:
    """Search the Chroma index and return current task records from SQLite."""
    normalized_query = query.strip()

    if not normalized_query:
        return _make_result(
            ok=False,
            status=ResultStatus.VALIDATION_ERROR,
            message="Search query must not be empty.",
        )

    if not 1 <= limit <= 10:
        return _make_result(
            ok=False,
            status=ResultStatus.VALIDATION_ERROR,
            message="Search limit must be between 1 and 10.",
        )

    try:
        matches = vector_store.query_tasks(
            query_text=normalized_query,
            limit=limit,
            status=status,
            priority=priority,
            exclude_done=exclude_done,
        )

        tasks: list[dict[str, Any]] = []

        for match in matches:
            task = db.get_task(match["id"])

            if task is not None:
                tasks.append(task)

    except Exception:
        logger.exception("Semantic task search failed.")
        return _make_result(
            ok=False,
            status=ResultStatus.ERROR,
            message="Task search is temporarily unavailable. Please try again.",
        )

    return _make_result(
        ok=True,
        status=ResultStatus.SUCCESS,
        message=f"Found {len(tasks)} matching task(s).",
        tasks=tasks,
    )


def resolve_task_ref(task_ref: str) -> ActionResult:
    """Resolve an exact task ID, exact title, or semantic reference safely."""
    normalized_ref = task_ref.strip()

    if not normalized_ref:
        return _make_result(
            ok=False,
            status=ResultStatus.VALIDATION_ERROR,
            message="Task reference must not be empty.",
        )

    if _TASK_ID_PATTERN.fullmatch(normalized_ref):
        try:
            task = db.get_task(normalized_ref.upper())
        except sqlite3.Error:
            logger.exception("Failed to look up task ID %s.", normalized_ref)
            return _make_result(
                ok=False,
                status=ResultStatus.ERROR,
                message="The task could not be looked up. Please try again.",
            )

        if task is None:
            return _make_result(
                ok=False,
                status=ResultStatus.NOT_FOUND,
                message=f"No task exists with ID {normalized_ref.upper()}.",
            )

        return _make_result(
            ok=True,
            status=ResultStatus.SUCCESS,
            message=f"Resolved {task['id']}: {task['title']}.",
            task=task,
        )

    try:
        all_tasks = db.list_tasks()
    except sqlite3.Error:
        logger.exception("Failed to load tasks for reference resolution.")
        return _make_result(
            ok=False,
            status=ResultStatus.ERROR,
            message="The task could not be looked up. Please try again.",
        )

    exact_matches = [
        task
        for task in all_tasks
        if task["title"].strip().casefold() == normalized_ref.casefold()
    ]

    if len(exact_matches) == 1:
        task = exact_matches[0]
        return _make_result(
            ok=True,
            status=ResultStatus.SUCCESS,
            message=f"Resolved {task['id']}: {task['title']}.",
            task=task,
        )

    try:
        semantic_matches = vector_store.query_tasks(
            query_text=normalized_ref,
            limit=5,
        )
    except Exception:
        logger.exception("Semantic reference resolution failed.")
        return _make_result(
            ok=False,
            status=ResultStatus.ERROR,
            message="Task matching is temporarily unavailable. Please try again.",
        )

    scored_matches: list[tuple[float, dict[str, Any]]] = []

    for match in semantic_matches:
        try:
            task = db.get_task(match["id"])
        except sqlite3.Error:
            logger.exception("Failed to retrieve candidate task %s.", match["id"])
            return _make_result(
                ok=False,
                status=ResultStatus.ERROR,
                message="Task matching is temporarily unavailable. Please try again.",
            )

        if task is None:
            continue

        semantic_similarity = float(match["similarity"])
        lexical_similarity = _lexical_overlap(normalized_ref, task)

        score = (
            SEMANTIC_WEIGHT * semantic_similarity
            + LEXICAL_WEIGHT * lexical_similarity
        )

        scored_matches.append((score, task))

    scored_matches.sort(
        key=lambda item: (
            -item[0],
            item[1]["id"],
        )
    )

    if not scored_matches:
        return _make_result(
            ok=False,
            status=ResultStatus.NOT_FOUND,
            message=f"No task matched '{normalized_ref}'. Try a different description.",
        )

    best_score, best_task = scored_matches[0]
    second_score = scored_matches[1][0] if len(scored_matches) > 1 else 0.0

    if (
        best_score >= RESOLVE_MIN
        and best_score - second_score >= RESOLVE_GAP
    ):
        return _make_result(
            ok=True,
            status=ResultStatus.SUCCESS,
            message=f"Resolved {best_task['id']}: {best_task['title']}.",
            task=best_task,
        )

    if best_score >= CANDIDATE_MIN:
        candidates = [
            _candidate_from_task(task)
            for score, task in scored_matches
            if score >= CANDIDATE_MIN
        ][:3]

        if candidates:
            return _make_result(
                ok=False,
                status=ResultStatus.NEEDS_CLARIFICATION,
                message=(
                    f"More than one task may match '{normalized_ref}'. "
                    "Please identify the intended task."
                ),
                candidates=candidates,
            )

    return _make_result(
        ok=False,
        status=ResultStatus.NOT_FOUND,
        message=f"No task matched '{normalized_ref}'. Try a more specific description.",
    )


def update_task(
    task_ref: str,
    title: str | None = None,
    description: str | None = None,
    priority: str | None = None,
    due_date: str | date | None = None,
    clear_due_date: bool = False,
) -> ActionResult:
    """Resolve a task, validate changes, persist them, and update Chroma."""
    resolution = resolve_task_ref(task_ref)

    if not resolution.ok or resolution.task is None:
        return resolution

    try:
        supplied: dict[str, Any] = {}

        if title is not None:
            supplied["title"] = title
        if description is not None:
            supplied["description"] = description
        if priority is not None:
            supplied["priority"] = priority
        if due_date is not None:
            supplied["due_date"] = due_date
        if clear_due_date:
            supplied["clear_due_date"] = True

        validated = TaskUpdate(**supplied)
        changes = validated.model_dump(mode="json", exclude_unset=True)
        should_clear_due_date = changes.pop("clear_due_date", False)

        if should_clear_due_date:
            changes["due_date"] = None

        task = db.update_task(resolution.task.id, changes)

    except ValidationError as exc:
        return _make_result(
            ok=False,
            status=ResultStatus.VALIDATION_ERROR,
            message=_validation_message(exc),
        )
    except (sqlite3.Error, ValueError):
        logger.exception("Failed to update task %s.", resolution.task.id)
        return _make_result(
            ok=False,
            status=ResultStatus.ERROR,
            message="The task could not be updated. Please try again.",
        )

    if task is None:
        return _make_result(
            ok=False,
            status=ResultStatus.NOT_FOUND,
            message=f"Task {resolution.task.id} no longer exists.",
        )

    if not _sync_upsert(task):
        return _make_result(
            ok=False,
            status=ResultStatus.ERROR,
            message=(
                f"{task['id']} was updated, but its search index could not be "
                "updated. The index can be repaired by reconciliation."
            ),
            task=task,
        )

    return _make_result(
        ok=True,
        status=ResultStatus.SUCCESS,
        message=f"Updated {task['id']}: {task['title']}.",
        task=task,
    )


def set_status(task_ref: str, status: str) -> ActionResult:
    """Resolve a task and change its status after validating the requested value."""
    resolution = resolve_task_ref(task_ref)

    if not resolution.ok or resolution.task is None:
        return resolution

    try:
        validated = TaskUpdate(status=status)
        changes = validated.model_dump(mode="json", exclude_unset=True)
        task = db.update_task(resolution.task.id, changes)
    except ValidationError as exc:
        return _make_result(
            ok=False,
            status=ResultStatus.VALIDATION_ERROR,
            message=_validation_message(exc),
        )
    except (sqlite3.Error, ValueError):
        logger.exception("Failed to change status for %s.", resolution.task.id)
        return _make_result(
            ok=False,
            status=ResultStatus.ERROR,
            message="The task status could not be changed. Please try again.",
        )

    if task is None:
        return _make_result(
            ok=False,
            status=ResultStatus.NOT_FOUND,
            message=f"Task {resolution.task.id} no longer exists.",
        )

    if not _sync_upsert(task):
        return _make_result(
            ok=False,
            status=ResultStatus.ERROR,
            message=(
                f"{task['id']} was updated, but its search index could not be "
                "updated. The index can be repaired by reconciliation."
            ),
            task=task,
        )

    return _make_result(
        ok=True,
        status=ResultStatus.SUCCESS,
        message=f"Changed {task['id']} to {task['status']}.",
        task=task,
    )


def complete_task(task_ref: str) -> ActionResult:
    """Resolve a task and mark it as done."""
    return set_status(task_ref, "done")


def delete_task(task_ref: str) -> ActionResult:
    """Resolve exactly one task, then delete it from SQLite and Chroma."""
    resolution = resolve_task_ref(task_ref)

    if not resolution.ok or resolution.task is None:
        return resolution

    task = resolution.task

    try:
        deleted = db.delete_task(task.id)
    except sqlite3.Error:
        logger.exception("Failed to delete task %s.", task.id)
        return _make_result(
            ok=False,
            status=ResultStatus.ERROR,
            message="The task could not be deleted. Please try again.",
        )

    if not deleted:
        return _make_result(
            ok=False,
            status=ResultStatus.NOT_FOUND,
            message=f"Task {task.id} no longer exists.",
        )

    try:
        vector_store.delete_task(task.id)
    except Exception:
        logger.exception("Deleted task %s but failed to remove its index entry.", task.id)
        return _make_result(
            ok=False,
            status=ResultStatus.ERROR,
            message=(
                f"{task.id} was deleted, but its search index entry could not "
                "be removed. The index can be repaired by reconciliation."
            ),
        )

    return _make_result(
        ok=True,
        status=ResultStatus.SUCCESS,
        message=f"Deleted {task.id}: {task.title}.",
    )


def reconcile() -> dict[str, int | bool]:
    """Repair ChromaDB so its indexed tasks match SQLite."""
    try:
        tasks = db.list_tasks()
        result = vector_store.reconcile(tasks)
    except Exception:
        logger.exception("Task index reconciliation failed.")
        raise

    logger.info(
        "Task index reconciliation complete: %s upserted, %s deleted, "
        "%s unchanged; SQLite=%s, Chroma=%s.",
        result["upserted"],
        result["deleted"],
        result["unchanged"],
        result["sqlite_count"],
        result["chroma_count"],
    )

    return result