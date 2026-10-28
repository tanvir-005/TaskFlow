"""Centralized configuration for the TaskFlow backend."""

from __future__ import annotations

import os
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_DIR.parent

load_dotenv(BACKEND_DIR / ".env")

DATA_DIR = BACKEND_DIR / "data"
DATABASE_PATH = DATA_DIR / "tasks.db"
CHROMA_PATH = DATA_DIR / "chroma"

APP_TIMEZONE_NAME = os.getenv("APP_TIMEZONE", "Asia/Dhaka")

try:
    APP_TIMEZONE = ZoneInfo(APP_TIMEZONE_NAME)
except (ZoneInfoNotFoundError, ValueError) as exc:
    raise RuntimeError(
        f"Invalid APP_TIMEZONE configuration: {APP_TIMEZONE_NAME!r}"
    ) from exc

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()

RESOLVE_MIN = float(os.getenv("RESOLVE_MIN", "0.55"))
RESOLVE_GAP = float(os.getenv("RESOLVE_GAP", "0.12"))
CANDIDATE_MIN = float(os.getenv("CANDIDATE_MIN", "0.35"))

SEMANTIC_WEIGHT = float(os.getenv("SEMANTIC_WEIGHT", "0.7"))
LEXICAL_WEIGHT = float(os.getenv("LEXICAL_WEIGHT", "0.3"))

RESOLVER_THRESHOLDS = (
    RESOLVE_MIN,
    RESOLVE_GAP,
    CANDIDATE_MIN,
)

HYBRID_WEIGHTS = (
    SEMANTIC_WEIGHT,
    LEXICAL_WEIGHT,
)

MAX_TASK_TITLE_LENGTH = 120
MAX_TASK_DESCRIPTION_LENGTH = 1000
MAX_CHAT_MESSAGE_LENGTH = 1000
MAX_SEARCH_RESULTS = 10
DEFAULT_SEARCH_RESULTS = 5
MAX_AGENT_ITERATIONS = 6
CHAT_HISTORY_LIMIT = 20
API_REQUEST_TIMEOUT_SECONDS = 30
API_RETRY_DELAY_SECONDS = 1.5


def validate_configuration() -> None:
    """Validate configuration values that affect application correctness."""
    if not GEMINI_MODEL:
        raise RuntimeError("GEMINI_MODEL must not be empty.")

    if not (
        0.0 <= RESOLVE_MIN <= 1.0
        and 0.0 <= RESOLVE_GAP <= 1.0
        and 0.0 <= CANDIDATE_MIN <= 1.0
    ):
        raise RuntimeError(
            "Resolver thresholds must be between 0.0 and 1.0."
        )

    if CANDIDATE_MIN > RESOLVE_MIN:
        raise RuntimeError(
            "CANDIDATE_MIN must not exceed RESOLVE_MIN."
        )

    if (
        SEMANTIC_WEIGHT < 0.0
        or LEXICAL_WEIGHT < 0.0
        or SEMANTIC_WEIGHT + LEXICAL_WEIGHT <= 0.0
    ):
        raise RuntimeError(
            "Hybrid weights must be non-negative and their sum "
            "must be greater than zero."
        )

    if MAX_TASK_TITLE_LENGTH < 1 or MAX_TASK_DESCRIPTION_LENGTH < 0:
        raise RuntimeError("Task length limits are invalid.")

    if MAX_CHAT_MESSAGE_LENGTH < 1:
        raise RuntimeError("The chat message length limit is invalid.")

    if MAX_SEARCH_RESULTS < 1 or not (
        1 <= DEFAULT_SEARCH_RESULTS <= MAX_SEARCH_RESULTS
    ):
        raise RuntimeError("Search result limits are invalid.")

    if MAX_AGENT_ITERATIONS < 1 or CHAT_HISTORY_LIMIT < 1:
        raise RuntimeError("Agent iteration and history limits must be positive.")

    if (
        API_REQUEST_TIMEOUT_SECONDS <= 0
        or API_RETRY_DELAY_SECONDS < 0
    ):
        raise RuntimeError("API timeout and retry delay settings are invalid.")

    if abs(SEMANTIC_WEIGHT + LEXICAL_WEIGHT - 1.0) > 1e-9:
        raise RuntimeError(
            "SEMANTIC_WEIGHT and LEXICAL_WEIGHT must sum to 1.0."
        )