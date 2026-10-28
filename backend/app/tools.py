"""Gemini function declarations and controlled task-service dispatch."""

from __future__ import annotations

import logging
from typing import Any

from google.genai import types
from pydantic import ValidationError

from app import task_service

logger = logging.getLogger(__name__)

STATUS_VALUES = ["todo", "in_progress", "done"]
PRIORITY_VALUES = ["low", "medium", "high"]


def _string_schema(
    description: str,
    *,
    enum: list[str] | None = None,
) -> types.Schema:
    """Build a string schema with an optional restricted set of values."""
    schema_data: dict[str, Any] = {
        "type": "STRING",
        "description": description,
    }

    if enum is not None:
        schema_data["enum"] = enum

    return types.Schema(**schema_data)


def _object_schema(
    properties: dict[str, types.Schema],
    *,
    required: list[str] | None = None,
) -> types.Schema:
    """Build an object schema for a Gemini function's parameters."""
    return types.Schema(
        type="OBJECT",
        properties=properties,
        required=required or [],
    )


def _function(
    name: str,
    description: str,
    properties: dict[str, types.Schema],
    *,
    required: list[str] | None = None,
) -> types.FunctionDeclaration:
    """Create a Gemini function declaration with a structured schema."""
    return types.FunctionDeclaration(
        name=name,
        description=description,
        parameters=_object_schema(properties, required=required),
    )


FUNCTION_DECLARATIONS: list[types.FunctionDeclaration] = [
    _function(
        "create_task",
        (
            "Create one task. Use an absolute ISO date in YYYY-MM-DD format "
            "for due_date. Default priority is medium and default status is todo."
        ),
        {
            "title": _string_schema("Task title, between 1 and 120 characters."),
            "description": _string_schema(
                "Optional task description, at most 1000 characters."
            ),
            "priority": _string_schema(
                "Task priority.", enum=PRIORITY_VALUES
            ),
            "status": _string_schema(
                "Initial task status.", enum=STATUS_VALUES
            ),
            "due_date": _string_schema(
                "Optional due date as a real calendar date in YYYY-MM-DD format."
            ),
        },
        required=["title"],
    ),
    _function(
        "list_tasks",
        (
            "List tasks using structured filters such as status, priority, "
            "due-date range, overdue status, or excluding completed tasks. "
            "Use this for requests based on task fields, not topic similarity."
        ),
        {
            "status": _string_schema(
                "Filter by task status.", enum=STATUS_VALUES
            ),
            "priority": _string_schema(
                "Filter by task priority.", enum=PRIORITY_VALUES
            ),
            "due_before": _string_schema(
                "Include tasks due on or before this ISO date, YYYY-MM-DD."
            ),
            "due_after": _string_schema(
                "Include tasks due on or after this ISO date, YYYY-MM-DD."
            ),
            "overdue_only": types.Schema(
                type="BOOLEAN",
                description="If true, return only overdue tasks that are not done.",
            ),
            "exclude_done": types.Schema(
                type="BOOLEAN",
                description="If true, exclude completed tasks.",
            ),
        },
    ),
    _function(
        "search_tasks",
        (
            "Find tasks by meaning using semantic search. Use for natural-language "
            "topics such as documentation, backend work, or design improvements. "
            "Optional status, priority, and completion filters narrow the results."
        ),
        {
            "query": _string_schema(
                "Natural-language description of the task topic or meaning."
            ),
            "status": _string_schema(
                "Optional status filter.", enum=STATUS_VALUES
            ),
            "priority": _string_schema(
                "Optional priority filter.", enum=PRIORITY_VALUES
            ),
            "exclude_done": types.Schema(
                type="BOOLEAN",
                description="If true, exclude completed tasks.",
            ),
            "limit": types.Schema(
                type="INTEGER",
                description="Maximum number of results, from 1 to 10; default 5.",
            ),
        },
        required=["query"],
    ),
    _function(
        "update_task",
        (
            "Update one existing task's title, description, priority, or due date. "
            "Identify it using a task ID or natural-language task reference. "
            "Use clear_due_date=true to remove its due date."
        ),
        {
            "task_ref": _string_schema(
                "Task ID or natural-language reference to the existing task."
            ),
            "title": _string_schema(
                "Replacement title, between 1 and 120 characters."
            ),
            "description": _string_schema(
                "Replacement description, at most 1000 characters."
            ),
            "priority": _string_schema(
                "Replacement priority.", enum=PRIORITY_VALUES
            ),
            "due_date": _string_schema(
                "Replacement due date as YYYY-MM-DD."
            ),
            "clear_due_date": types.Schema(
                type="BOOLEAN",
                description="If true, remove the current due date.",
            ),
        },
        required=["task_ref"],
    ),
    _function(
        "set_status",
        (
            "Change the status of one existing task. Resolve the task reference "
            "before making any change."
        ),
        {
            "task_ref": _string_schema(
                "Task ID or natural-language reference to the existing task."
            ),
            "status": _string_schema(
                "The requested task status.", enum=STATUS_VALUES
            ),
        },
        required=["task_ref", "status"],
    ),
    _function(
        "complete_task",
        "Mark one existing task as done after resolving its reference.",
        {
            "task_ref": _string_schema(
                "Task ID or natural-language reference to the existing task."
            ),
        },
        required=["task_ref"],
    ),
    _function(
        "delete_task",
        (
            "Delete exactly one existing task after resolving its reference. "
            "Never use repeated calls to delete multiple tasks unless the user "
            "explicitly confirmed the deletion in a previous turn."
        ),
        {
            "task_ref": _string_schema(
                "Task ID or natural-language reference to the existing task."
            ),
        },
        required=["task_ref"],
    ),
    _function(
        "ask_clarification",
        (
            "Ask the user for missing or ambiguous information instead of "
            "inventing details or guessing which task they mean."
        ),
        {
            "question": _string_schema(
                "A concise, specific question for the user."
            ),
            "options": types.Schema(
                type="ARRAY",
                description="Optional human-readable choices to show the user.",
                items=_string_schema("One possible answer or choice."),
            ),
        },
        required=["question"],
    ),
]

TOOLS: list[types.Tool] = [
    types.Tool(function_declarations=FUNCTION_DECLARATIONS)
]


def _to_json_value(value: Any) -> Any:
    """Convert Pydantic models and enums to JSON-compatible values."""
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")

    if isinstance(value, list):
        return [_to_json_value(item) for item in value]

    if isinstance(value, dict):
        return {
            str(key): _to_json_value(item)
            for key, item in value.items()
        }

    if hasattr(value, "value"):
        return value.value

    return value


def _envelope(
    *,
    ok: bool,
    status: str,
    message: str,
    task: Any = None,
    tasks: Any = None,
    candidates: Any = None,
) -> dict[str, Any]:
    """Build the standard response envelope used by all task tools."""
    return {
        "ok": ok,
        "status": status,
        "message": message,
        "task": _to_json_value(task) if task is not None else None,
        "tasks": _to_json_value(tasks) if tasks is not None else None,
        "candidates": (
            _to_json_value(candidates) if candidates is not None else None
        ),
    }


def _serialize_result(result: Any) -> dict[str, Any]:
    """Normalize an ActionResult into the standard tool response envelope."""
    data = _to_json_value(result)

    if not isinstance(data, dict):
        raise TypeError("Task service returned an invalid result.")

    status_value = data.get("status", "error")
    if hasattr(status_value, "value"):
        status_value = status_value.value

    status = str(status_value).lower()
    allowed_statuses = {
        "success",
        "needs_clarification",
        "not_found",
        "validation_error",
        "error",
    }

    if status not in allowed_statuses:
        status = "error"

    return _envelope(
        ok=bool(data.get("ok", status == "success")),
        status=status,
        message=str(data.get("message", "The task operation did not return a message.")),
        task=data.get("task"),
        tasks=data.get("tasks"),
        candidates=data.get("candidates"),
    )


def dispatch_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Validate and execute one Gemini tool call through the task service."""
    if not isinstance(arguments, dict):
        return _envelope(
            ok=False,
            status="validation_error",
            message="The tool arguments must be a JSON object.",
        )

    handlers = {
        "create_task": task_service.create_task,
        "list_tasks": task_service.list_tasks,
        "search_tasks": task_service.search_tasks,
        "update_task": task_service.update_task,
        "set_status": task_service.set_status,
        "complete_task": task_service.complete_task,
        "delete_task": task_service.delete_task,
    }

    if name == "ask_clarification":
        question = arguments.get("question")
        options = arguments.get("options", [])

        if not isinstance(question, str) or not question.strip():
            return _envelope(
                ok=False,
                status="validation_error",
                message="A clarification question is required.",
            )

        if not isinstance(options, list) or any(
            not isinstance(option, str) for option in options
        ):
            return _envelope(
                ok=False,
                status="validation_error",
                message="Clarification options must be a list of strings.",
            )

        message = question.strip()
        if options:
            message += "\n" + "\n".join(
                f"{index}. {option}" for index, option in enumerate(options, 1)
            )

        return _envelope(
            ok=False,
            status="needs_clarification",
            message=message,
        )

    handler = handlers.get(name)
    if handler is None:
        return _envelope(
            ok=False,
            status="error",
            message=f"Unknown tool: {name}.",
        )

    try:
        result = handler(**arguments)
        return _serialize_result(result)
    except (TypeError, ValueError, ValidationError):
        logger.info(
            "Rejected invalid arguments for task tool %s.",
            name,
            exc_info=True,
        )
        return _envelope(
            ok=False,
            status="validation_error",
            message="The supplied arguments are invalid. Check the task details and try again.",
        )
    except Exception:
        logger.exception("Task tool %s failed unexpectedly.", name)
        return _envelope(
            ok=False,
            status="error",
            message="The task operation could not be completed because of an internal error.",
        )