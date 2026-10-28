"""Gemini-powered conversational agent for TaskFlow."""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from google import genai
from google.genai import errors, types

from app import db, tools
from app.config import (
    API_REQUEST_TIMEOUT_SECONDS,
    API_RETRY_DELAY_SECONDS,
    CHAT_HISTORY_LIMIT,
    GEMINI_API_KEY,
    GEMINI_MODEL,
    MAX_AGENT_ITERATIONS,
    APP_TIMEZONE,
)
from app.prompts import SYSTEM_PROMPT

logger = logging.getLogger(__name__)

MAX_HISTORY_MESSAGES = CHAT_HISTORY_LIMIT
MAX_TOOL_ITERATIONS = MAX_AGENT_ITERATIONS

SERVICE_UNAVAILABLE_MESSAGE = (
    "The AI service is unavailable. Check GEMINI_API_KEY and try again."
)

MAX_ERROR_MESSAGE = (
    "I couldn't complete that request because of an AI service error. "
    "Please try again."
)

TOOL_ERROR_RESULT: dict[str, Any] = {
    "ok": False,
    "status": "error",
    "message": "The requested action could not be completed.",
    "task": None,
    "tasks": None,
    "candidates": None,
}


def _get_client() -> genai.Client:
    """Create a Gemini client using the configured API key."""
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY is not configured.")

    if not GEMINI_MODEL:
        raise ValueError("GEMINI_MODEL is not configured.")

    return genai.Client(
        api_key=GEMINI_API_KEY,
        http_options=types.HttpOptions(
            timeout=API_REQUEST_TIMEOUT_SECONDS * 1000,
        ),
    )


def _get_date_context() -> tuple[str, str, str]:
    """Return today's date, weekday, and timezone for the system prompt."""
    timezone_name = getattr(APP_TIMEZONE, "key", None) or "Asia/Dhaka"

    try:
        timezone = (
            APP_TIMEZONE
            if isinstance(APP_TIMEZONE, ZoneInfo)
            else ZoneInfo(timezone_name)
        )
    except (ZoneInfoNotFoundError, ValueError):
        logger.exception(
            "Invalid application timezone: %s",
            timezone_name,
        )
        timezone_name = "Asia/Dhaka"
        timezone = ZoneInfo(timezone_name)

    now = datetime.now(timezone)

    return (
        now.strftime("%Y-%m-%d"),
        now.strftime("%A"),
        timezone_name,
    )


def _build_system_instruction() -> str:
    """Insert the current date and timezone into the system prompt."""
    today, weekday, timezone_name = _get_date_context()

    return SYSTEM_PROMPT.format(
        today=today,
        weekday=weekday,
        timezone=timezone_name,
    )


def _load_history(session_id: str) -> list[types.Content]:
    """Load recent chat history in Gemini's native content format."""
    messages = db.get_chat_history(
        session_id,
        limit=MAX_HISTORY_MESSAGES,
    )

    contents: list[types.Content] = []

    for message in messages:
        role = message.get("role")
        text = message.get("content", "")

        if role not in {"user", "assistant", "model"}:
            continue

        if not isinstance(text, str) or not text.strip():
            continue

        contents.append(
            types.Content(
                role="model" if role in {"assistant", "model"} else "user",
                parts=[types.Part.from_text(text=text)],
            )
        )

    return contents


def _dispatch_tool(
    name: str,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    """Execute a declared TaskFlow tool and return a structured result."""
    try:
        result = tools.dispatch_tool(name, arguments)

        if not isinstance(result, dict):
            logger.error(
                "Tool %s returned an unexpected result type: %s",
                name,
                type(result).__name__,
            )
            return {
                **TOOL_ERROR_RESULT,
                "message": "The requested action returned an invalid result.",
            }

        return result

    except Exception:
        logger.exception("Tool execution failed: %s", name)
        return dict(TOOL_ERROR_RESULT)


def _function_arguments(value: Any) -> dict[str, Any]:
    """Normalize Gemini function-call arguments into a dictionary."""
    if value is None:
        return {}

    if isinstance(value, dict):
        arguments = value
    elif hasattr(value, "model_dump"):
        arguments = value.model_dump(exclude_none=True)
    else:
        raise ValueError("Function-call arguments must be an object.")

    if not isinstance(arguments, dict):
        raise ValueError("Function-call arguments must be an object.")

    return arguments


def _status(result: dict[str, Any]) -> str:
    """Normalize a tool result status."""
    status = result.get("status")

    if status in {"success", "needs_clarification", "not_found"}:
        return str(status)

    if result.get("ok") is True:
        return "success"

    return "error"


def _task_id(result: dict[str, Any]) -> str | None:
    """Extract the affected task ID from a tool result."""
    task = result.get("task")

    if isinstance(task, dict):
        task_id = task.get("id")
        if isinstance(task_id, str):
            return task_id

    task_id = result.get("task_id")
    return task_id if isinstance(task_id, str) else None


def _task_title(result: dict[str, Any]) -> str | None:
    """Extract the affected task title from a tool result."""
    task = result.get("task")

    if isinstance(task, dict):
        title = task.get("title")
        if isinstance(title, str):
            return title

    return None


def _summarize_action(
    tool_name: str,
    result: dict[str, Any],
) -> str:
    """Create a concise action receipt for the frontend."""
    task_id = _task_id(result)
    title = _task_title(result)
    message = result.get("message")

    if tool_name == "ask_clarification":
        return str(message or "More information is needed.")

    if _status(result) == "needs_clarification":
        return str(message or "Please clarify which task you mean.")

    if _status(result) != "success":
        return str(message or "The action could not be completed.")

    if task_id and title:
        return f"{task_id}: {title}"

    if task_id:
        return task_id

    if isinstance(message, str) and message.strip():
        return message.strip()

    return f"{tool_name.replace('_', ' ').capitalize()} completed."


def _collect_candidates(
    result: dict[str, Any],
) -> list[dict[str, Any]]:
    """Normalize task candidates for clarification controls."""
    candidates = result.get("candidates")

    if not isinstance(candidates, list):
        return []

    normalized: list[dict[str, Any]] = []

    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue

        task_id = candidate.get("id")
        title = candidate.get("title")

        if not isinstance(task_id, str) or not isinstance(title, str):
            continue

        normalized.append(
            {
                "id": task_id,
                "title": title,
                "status": candidate.get("status", "unknown"),
                "priority": candidate.get("priority", "unknown"),
            }
        )

    return normalized


def _make_action(
    tool_name: str,
    result: dict[str, Any],
) -> dict[str, Any]:
    """Build a structured receipt for a tool invocation."""
    return {
        "tool": tool_name,
        "status": _status(result),
        "task_id": _task_id(result),
        "summary": _summarize_action(tool_name, result),
    }


def _build_clarification(
    actions: list[dict[str, Any]],
    results: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Return the first clarification request and its candidates."""
    for action, result in zip(actions, results):
        if action["status"] != "needs_clarification":
            continue

        candidates = _collect_candidates(result)
        question = result.get("message") or (
            "Which task do you mean? Please select one of the candidates."
        )

        return {
            "question": str(question),
            "candidates": candidates,
        }

    return None


def _fallback_reply(
    actions: list[dict[str, Any]],
    results: list[dict[str, Any]],
) -> str:
    """Produce a factual reply if Gemini provides no final text."""
    successful = [
        action for action in actions
        if action["status"] == "success"
    ]
    failed = [
        action for action in actions
        if action["status"] == "error"
    ]

    clarification = _build_clarification(actions, results)
    lines: list[str] = []

    if successful:
        lines.append("Completed:")
        lines.extend(
            f"- {action['summary']}"
            for action in successful
        )

    if clarification:
        lines.append(clarification["question"])
        lines.extend(
            f"- {candidate['id']}: {candidate['title']} "
            f"({candidate['status']}, {candidate['priority']})"
            for candidate in clarification["candidates"]
        )

    if failed:
        lines.append("Some actions could not be completed:")
        lines.extend(
            f"- {action['summary']}"
            for action in failed
        )

    if lines:
        return "\n".join(lines)

    return "I couldn't produce a response. Please try rephrasing your request."


def _contains_task_change(
    actions: list[dict[str, Any]],
) -> bool:
    """Check whether a successful mutating tool changed task data."""
    mutating_tools = {
        "create_task",
        "update_task",
        "set_status",
        "complete_task",
        "delete_task",
    }

    return any(
        action["tool"] in mutating_tools
        and action["status"] == "success"
        for action in actions
    )


def _changed_ids(
    actions: list[dict[str, Any]],
) -> list[str]:
    """Return unique IDs affected by successful task mutations."""
    mutating_tools = {
        "create_task",
        "update_task",
        "set_status",
        "complete_task",
        "delete_task",
    }

    changed: list[str] = []

    for action in actions:
        task_id = action.get("task_id")

        if (
            action["tool"] in mutating_tools
            and action["status"] == "success"
            and isinstance(task_id, str)
            and task_id not in changed
        ):
            changed.append(task_id)

    return changed


def _save_message(
    session_id: str,
    role: str,
    content: str,
    meta: dict[str, Any] | None = None,
) -> None:
    """Persist a chat message without hiding the main response on failure."""
    try:
        db.save_chat_message(
            session_id=session_id,
            role=role,
            content=content,
            meta=(
                json.dumps(meta, ensure_ascii=False, default=str)
                if meta is not None
                else None
            ),
        )
    except Exception:
        logger.exception(
            "Failed to save chat message for session %s",
            session_id,
        )


def _result(
    reply: str,
    actions: list[dict[str, Any]] | None = None,
    results: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build the stable response expected by the API and frontend."""
    action_list = actions or []
    result_list = results or []

    return {
        "reply": reply,
        "tasks_changed": _contains_task_change(action_list),
        "changed_ids": _changed_ids(action_list),
        "actions": action_list,
        "clarification": _build_clarification(
            action_list,
            result_list,
        ),
    }


def _generate_content(
    client: genai.Client,
    contents: list[types.Content],
) -> Any:
    """Request a Gemini response, retrying once for transient server errors."""
    for attempt in range(2):
        try:
            return client.models.generate_content(
                model=GEMINI_MODEL,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=_build_system_instruction(),
                    tools=tools.TOOLS,
                    temperature=0,
                ),
            )
        except errors.APIError as exc:
            code = getattr(exc, "code", None)

            if attempt == 0 and code in {429, 500, 502, 503, 504}:
                logger.warning(
                    "Gemini returned transient API error %s; retrying once.",
                    code,
                )
                time.sleep(API_RETRY_DELAY_SECONDS)
                continue

            raise

    raise RuntimeError("Gemini request failed after retry.")


def _response_text(response: Any) -> str:
    """Safely extract text from a Gemini response."""
    try:
        text = response.text
    except (ValueError, AttributeError):
        return ""

    return text.strip() if isinstance(text, str) else ""


def chat(session_id: str, message: str) -> dict[str, Any]:
    """Process a user message through Gemini's native function-calling loop."""
    session_id = session_id.strip() if isinstance(session_id, str) else ""
    message = message.strip() if isinstance(message, str) else ""

    if not session_id:
        return _result("A valid session ID is required.")

    if not message:
        return _result("Enter a message before sending it.")

    _save_message(session_id, "user", message)

    try:
        client = _get_client()
        contents = _load_history(session_id)

        # The current user message was saved before history was loaded.
        if not contents or not (
            contents[-1].role == "user"
            and contents[-1].parts
            and getattr(contents[-1].parts[0], "text", None) == message
        ):
            contents.append(
                types.Content(
                    role="user",
                    parts=[types.Part.from_text(text=message)],
                )
            )

        all_actions: list[dict[str, Any]] = []
        all_results: list[dict[str, Any]] = []

        for _ in range(MAX_TOOL_ITERATIONS):
            response = _generate_content(client, contents)

            candidates = getattr(response, "candidates", None)
            if not candidates:
                reply = _fallback_reply(all_actions, all_results)
                break

            model_content = candidates[0].content
            if model_content is None:
                reply = _fallback_reply(all_actions, all_results)
                break

            function_calls = [
                part.function_call
                for part in (model_content.parts or [])
                if getattr(part, "function_call", None) is not None
            ]

            if not function_calls:
                reply = _response_text(response)
                if not reply:
                    reply = _fallback_reply(all_actions, all_results)
                break

            # Preserve Gemini's original model content, including function calls.
            contents.append(model_content)

            function_response_parts: list[types.Part] = []

            for function_call in function_calls:
                name = function_call.name or "unknown_tool"

                try:
                    arguments = _function_arguments(function_call.args)
                    tool_result = _dispatch_tool(name, arguments)
                except (ValueError, TypeError):
                    logger.exception(
                        "Invalid Gemini function call: %s",
                        name,
                    )
                    tool_result = {
                        **TOOL_ERROR_RESULT,
                        "message": "The AI requested an invalid action.",
                    }

                all_results.append(tool_result)
                all_actions.append(_make_action(name, tool_result))

                # Gemini function responses must be returned as structured parts.
                safe_result = json.loads(
                    json.dumps(
                        tool_result,
                        ensure_ascii=False,
                        default=str,
                    )
                )

                function_response_parts.append(
                    types.Part.from_function_response(
                        name=name,
                        response=safe_result,
                    )
                )

            contents.append(
                types.Content(
                    role="user",
                    parts=function_response_parts,
                )
            )
        else:
            reply = _fallback_reply(all_actions, all_results)
            if not reply.strip():
                reply = (
                    "I reached the action limit for this message. "
                    "Please split the request into smaller steps."
                )

        result = _result(reply, all_actions, all_results)

        _save_message(
            session_id,
            "assistant",
            reply,
            meta={
                "actions": result["actions"],
                "clarification": result["clarification"],
                "changed_ids": result["changed_ids"],
            },
        )

        return result

    except ValueError as exc:
        logger.warning("TaskFlow agent configuration error: %s", exc)
        reply = SERVICE_UNAVAILABLE_MESSAGE

    except errors.APIError as exc:
        code = getattr(exc, "code", None)
        logger.exception("Gemini API request failed; code=%s", code)

        if code in {401, 403}:
            reply = SERVICE_UNAVAILABLE_MESSAGE
        elif code == 429:
            reply = (
                "The AI service rate limit was reached. "
                "Wait briefly and try again."
            )
        else:
            reply = MAX_ERROR_MESSAGE

    except (TimeoutError, OSError):
        logger.exception("Gemini request timed out or could not connect.")
        reply = (
            "The AI service timed out or could not be reached. "
            "Please try again."
        )

    except Exception:
        logger.exception("Unexpected TaskFlow Gemini agent error.")
        reply = MAX_ERROR_MESSAGE

    result = _result(reply)

    _save_message(
        session_id,
        "assistant",
        reply,
        meta=result,
    )

    return result


process_chat = chat