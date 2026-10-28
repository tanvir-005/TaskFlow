"""FastAPI application entry point for TaskFlow."""

import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app import db, vector_store
from app.config import GEMINI_MODEL

logger = logging.getLogger(__name__)

BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = BACKEND_DIR.parent
FRONTEND_DIST = PROJECT_DIR / "frontend" / "dist"


class ChatRequest(BaseModel):
    """Request body for a chat message."""

    session_id: str = Field(min_length=1, max_length=200)
    message: str = Field(min_length=1, max_length=1000)


def _initialize_database() -> None:
    """Initialize the SQLite database."""
    initializer = getattr(db, "initialize_database", None)

    if not callable(initializer):
        initializer = getattr(db, "init_db", None)

    if not callable(initializer):
        raise RuntimeError(
            "No database initialization function was found in app.db."
        )

    initializer()


def _reconcile_vector_store() -> None:
    """Synchronize ChromaDB with the authoritative SQLite task list."""
    reconcile = getattr(vector_store, "reconcile", None)

    if callable(reconcile):
        sqlite_tasks = db.list_tasks()
        reconcile(sqlite_tasks)


@asynccontextmanager
async def lifespan(application: FastAPI):
    """Initialize application resources during startup."""
    logging.basicConfig(level=logging.INFO)

    logger.info("Starting TaskFlow API.")

    _initialize_database()

    try:
        _reconcile_vector_store()
        logger.info("ChromaDB reconciliation completed.")
    except Exception:
        logger.exception(
            "ChromaDB reconciliation failed during startup."
        )

    yield

    logger.info("Shutting down TaskFlow API.")


app = FastAPI(
    title="TaskFlow API",
    description="AI-powered task management API.",
    version="1.0.0",
    lifespan=lifespan,
)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    """Return consistent JSON for request validation errors."""
    return JSONResponse(
        status_code=422,
        content={
            "ok": False,
            "status": "validation_error",
            "message": "The request contains invalid or missing fields.",
            "errors": exc.errors(),
        },
    )


@app.exception_handler(Exception)
async def general_exception_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    """Log unexpected exceptions and return a generic error."""
    logger.exception("Unhandled application exception.")

    return JSONResponse(
        status_code=500,
        content={
            "ok": False,
            "status": "error",
            "message": "An unexpected server error occurred.",
        },
    )


def _dispatch_list_tasks(
    status: str | None = None,
) -> dict[str, Any]:
    """Retrieve tasks through the task tool dispatcher."""
    from app import tools

    arguments: dict[str, Any] = {}

    if status is not None:
        arguments["status"] = status

    result = tools.dispatch_tool("list_tasks", arguments)

    if not isinstance(result, dict):
        raise RuntimeError(
            "The list_tasks tool returned an invalid response."
        )

    return result


def _get_task_list(
    status: str | None = None,
) -> list[dict[str, Any]]:
    """Extract the task list from the list_tasks tool response."""
    result = _dispatch_list_tasks(status)

    if result.get("ok") is False:
        raise RuntimeError(
            result.get("message", "Failed to retrieve tasks.")
        )

    tasks = result.get("tasks", [])

    if not isinstance(tasks, list):
        raise RuntimeError(
            "The list_tasks tool returned an invalid task list."
        )

    return tasks


def _get_sqlite_count() -> int:
    """Return the number of tasks in SQLite."""
    return len(db.list_tasks())


def _get_collection_count() -> int | None:
    """Return the number of documents in ChromaDB."""
    collection_getter = getattr(
        vector_store,
        "_get_collection",
        None,
    )

    if not callable(collection_getter):
        return None

    collection = collection_getter()
    return collection.count()


def _get_sync_status(
    sqlite_count: int,
    chroma_count: int | None,
) -> bool | None:
    """Compare SQLite and ChromaDB document counts."""
    if chroma_count is None:
        return None

    return sqlite_count == chroma_count


@app.get("/api/health")
async def health_check() -> dict[str, Any]:
    """Return API health and task-index synchronization information."""
    try:
        sqlite_count = _get_sqlite_count()
    except Exception:
        logger.exception("Failed to count SQLite tasks.")
        raise HTTPException(
            status_code=500,
            detail="Failed to read tasks from SQLite.",
        )

    try:
        chroma_count = _get_collection_count()
    except Exception:
        logger.exception("Failed to count ChromaDB documents.")
        chroma_count = None

    return {
        "status": "ok",
        "sqlite_count": sqlite_count,
        "chroma_count": chroma_count,
        "in_sync": _get_sync_status(sqlite_count, chroma_count),
        "model": GEMINI_MODEL,
    }


@app.get("/api/tasks")
async def get_tasks(
    status: str | None = Query(
        default=None,
        description="Optional task status filter.",
    ),
) -> dict[str, Any]:
    """Return tasks, optionally filtered by status."""
    try:
        tasks = _get_task_list(status)
    except Exception:
        logger.exception("Failed to retrieve tasks.")
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve tasks.",
        )

    return {
        "ok": True,
        "tasks": tasks,
        "count": len(tasks),
    }


@app.post("/api/chat")
async def chat(request: ChatRequest) -> dict[str, Any]:
    """Send a message to the TaskFlow AI agent."""
    from app.agent import chat as agent_chat

    try:
        result = agent_chat(
            session_id=request.session_id,
            message=request.message,
        )

        tasks = _get_task_list()

        if isinstance(result, dict):
            response: dict[str, Any] = dict(result)
        else:
            response = {
                "ok": True,
                "status": "success",
                "message": str(result),
            }

        response["tasks"] = tasks

        return response

    except HTTPException:
        raise
    except Exception:
        logger.exception("Chat request failed.")
        raise HTTPException(
            status_code=500,
            detail="The chat request could not be completed.",
        )


@app.get("/api/chat/history")
async def get_chat_history(
    session_id: str = Query(min_length=1, max_length=200),
) -> dict[str, Any]:
    """Return conversation history for a session."""
    try:
        history = db.get_chat_history(session_id)
    except Exception:
        logger.exception("Failed to retrieve chat history.")
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve chat history.",
        )

    parsed_history: list[dict[str, Any]] = []

    for item in history:
        entry = dict(item)

        meta = entry.get("meta")

        if isinstance(meta, str):
            try:
                entry["meta"] = json.loads(meta)
            except json.JSONDecodeError:
                entry["meta"] = {}

        parsed_history.append(entry)

    return {
        "ok": True,
        "session_id": session_id,
        "messages": parsed_history,
        "count": len(parsed_history),
    }


@app.delete("/api/chat/history")
async def delete_chat_history(
    session_id: str = Query(min_length=1, max_length=200),
) -> dict[str, Any]:
    """Delete conversation history for a session."""
    clearer = getattr(db, "clear_chat_history", None)

    if not callable(clearer):
        clearer = getattr(db, "delete_chat_history", None)

    if not callable(clearer):
        raise HTTPException(
            status_code=501,
            detail="Chat history deletion is not implemented.",
        )

    try:
        clearer(session_id)
    except Exception:
        logger.exception("Failed to delete chat history.")
        raise HTTPException(
            status_code=500,
            detail="Failed to delete chat history.",
        )

    return {
        "ok": True,
        "status": "success",
        "message": "Chat history cleared.",
        "session_id": session_id,
    }


# Serve the production frontend when its build exists.
if FRONTEND_DIST.is_dir():
    assets_dir = FRONTEND_DIST / "assets"

    if assets_dir.is_dir():
        app.mount(
            "/assets",
            StaticFiles(directory=assets_dir),
            name="assets",
        )


@app.get("/{path:path}", include_in_schema=False)
async def frontend_fallback(path: str) -> Any:
    """Serve frontend files or the SPA entry point."""
    # API routes should never fall through to the frontend.
    if path == "api" or path.startswith("api/"):
        raise HTTPException(
            status_code=404,
            detail="API endpoint not found.",
        )

    if FRONTEND_DIST.is_dir():
        requested_file = (FRONTEND_DIST / path).resolve()
        frontend_root = FRONTEND_DIST.resolve()

        # Prevent paths from escaping the frontend build directory.
        if (
            requested_file != frontend_root
            and frontend_root not in requested_file.parents
        ):
            raise HTTPException(
                status_code=404,
                detail="File not found.",
            )

        if requested_file.is_file():
            return FileResponse(requested_file)

        index_file = FRONTEND_DIST / "index.html"

        if index_file.is_file():
            return FileResponse(index_file)

    return JSONResponse(
        status_code=404,
        content={
            "ok": False,
            "status": "not_found",
            "message": (
                "Frontend build not found. "
                "Run the Vite development server during development."
            ),
        },
    )