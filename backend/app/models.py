"""Pydantic models, enums, and validation for TaskFlow."""

from __future__ import annotations

import re
from datetime import date
from enum import Enum
from typing import Annotated

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from app.config import (
    MAX_CHAT_MESSAGE_LENGTH,
    MAX_TASK_DESCRIPTION_LENGTH,
    MAX_TASK_TITLE_LENGTH,
)


class TaskStatus(str, Enum):
    """Supported task lifecycle statuses."""

    TODO = "todo"
    IN_PROGRESS = "in_progress"
    DONE = "done"


class TaskPriority(str, Enum):
    """Supported task priority levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ResultStatus(str, Enum):
    """Supported operation result statuses."""

    SUCCESS = "success"
    NEEDS_CLARIFICATION = "needs_clarification"
    NOT_FOUND = "not_found"
    VALIDATION_ERROR = "validation_error"
    ERROR = "error"


TaskTitle = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=MAX_TASK_TITLE_LENGTH,
    ),
]

TaskDescription = Annotated[
    str,
    StringConstraints(max_length=MAX_TASK_DESCRIPTION_LENGTH),
]

ChatMessageText = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=MAX_CHAT_MESSAGE_LENGTH,
    ),
]

TaskReference = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=500),
]

SessionIdentifier = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=100),
]

TaskIdentifier = Annotated[
    str,
    StringConstraints(pattern=r"^TASK-\d{3,}$"),
]


class StrictModel(BaseModel):
    """Base model that rejects unexpected fields."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class TaskCreate(StrictModel):
    """Validated input for creating a task."""

    title: TaskTitle
    description: TaskDescription = ""
    status: TaskStatus = TaskStatus.TODO
    priority: TaskPriority = TaskPriority.MEDIUM
    due_date: date | None = None

    @field_validator("due_date", mode="before")
    @classmethod
    def validate_due_date_input(cls, value: object) -> object:
        """Accept ISO date strings or date objects, but reject other types."""
        if value is None or isinstance(value, date):
            return value

        if isinstance(value, str):
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
                raise ValueError("due_date must use YYYY-MM-DD format.")

            try:
                return date.fromisoformat(value)
            except ValueError as exc:
                raise ValueError(
                    "due_date must be a real calendar date."
                ) from exc

        raise ValueError(
            "due_date must be an ISO date string or null."
        )


class TaskUpdate(StrictModel):
    """Validated input for updating existing task fields."""

    title: TaskTitle | None = None
    description: TaskDescription | None = None
    priority: TaskPriority | None = None
    due_date: date | None = None
    clear_due_date: bool = False
    status: TaskStatus | None = None

    @field_validator("title")
    @classmethod
    def validate_optional_title(cls, value: str | None) -> str | None:
        """Reject an explicitly supplied null title."""
        if value is None:
            raise ValueError("title cannot be null.")
        return value

    @field_validator("description")
    @classmethod
    def validate_optional_description(
        cls, value: str | None
    ) -> str | None:
        """Reject an explicitly supplied null description."""
        if value is None:
            raise ValueError("description cannot be null.")
        return value

    @field_validator("priority")
    @classmethod
    def validate_optional_priority(
        cls, value: TaskPriority | None
    ) -> TaskPriority | None:
        """Reject an explicitly supplied null priority."""
        if value is None:
            raise ValueError("priority cannot be null.")
        return value

    @field_validator("due_date", mode="before")
    @classmethod
    def validate_optional_due_date(cls, value: object) -> object:
        """Validate supplied dates without interpreting null as a date."""
        if value is None or isinstance(value, date):
            return value

        if isinstance(value, str):
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
                raise ValueError("due_date must use YYYY-MM-DD format.")

            try:
                return date.fromisoformat(value)
            except ValueError as exc:
                raise ValueError(
                    "due_date must be a real calendar date."
                ) from exc

        raise ValueError(
            "due_date must be an ISO date string or null."
        )

    @model_validator(mode="after")
    def validate_update_fields(self) -> TaskUpdate:
        """Require at least one actual field change."""
        fields = self.model_fields_set
        mutable_fields = {
            "title",
            "description",
            "priority",
            "due_date",
            "clear_due_date",
            "status",
        }

        if not fields.intersection(mutable_fields) and not self.clear_due_date:
            raise ValueError("At least one update field must be provided.")

        if self.clear_due_date and self.due_date is not None:
            raise ValueError(
                "Provide due_date or clear_due_date, not both."
            )

        if self.clear_due_date and "due_date" in fields:
            raise ValueError(
                "Provide due_date or clear_due_date, not both."
            )

        return self


class Task(StrictModel):
    """Complete task representation returned by the application."""

    id: TaskIdentifier
    title: TaskTitle
    description: TaskDescription = ""
    status: TaskStatus
    priority: TaskPriority
    due_date: date | None = None
    created_at: str
    updated_at: str


class TaskFilters(StrictModel):
    """Structured filters for listing tasks."""

    status: TaskStatus | None = None
    priority: TaskPriority | None = None
    due_before: date | None = None
    due_after: date | None = None
    overdue_only: bool = False
    exclude_done: bool = False

    @model_validator(mode="after")
    def validate_date_range(self) -> TaskFilters:
        """Ensure date filters describe a valid inclusive range."""
        if (
            self.due_before is not None
            and self.due_after is not None
            and self.due_after > self.due_before
        ):
            raise ValueError(
                "due_after must not be later than due_before."
            )

        return self


class TaskCandidate(StrictModel):
    """Minimal task details shown during ambiguity resolution."""

    id: TaskIdentifier
    title: TaskTitle
    status: TaskStatus
    priority: TaskPriority
    due_date: date | None = None


class ActionResult(StrictModel):
    """Standard envelope for individual agent tool results."""

    ok: bool
    status: ResultStatus
    message: str
    task: Task | None = None
    tasks: list[Task] | None = None
    candidates: list[TaskCandidate] | None = None

    @model_validator(mode="after")
    def validate_result_status(self) -> ActionResult:
        """Keep the success flag consistent with the result status."""
        if self.ok != (self.status == ResultStatus.SUCCESS):
            raise ValueError(
                "ok must be true exactly when status is success."
            )
        return self


class ChatRequest(StrictModel):
    """Request body for sending a message to the AI assistant."""

    session_id: SessionIdentifier
    message: ChatMessageText


class ActionReceipt(StrictModel):
    """Summary of an individual tool action for the UI."""

    tool: str
    status: ResultStatus
    task_id: TaskIdentifier | None = None
    summary: str


class Clarification(StrictModel):
    """Clarification request returned by the agent."""

    question: str
    candidates: list[TaskCandidate] = Field(default_factory=list)


class AgentResult(StrictModel):
    """Complete agent response returned by the chat endpoint."""

    reply: str
    tasks_changed: bool = False
    changed_ids: list[TaskIdentifier] = Field(default_factory=list)
    actions: list[ActionReceipt] = Field(default_factory=list)
    clarification: Clarification | None = None
    tasks: list[Task] = Field(default_factory=list)


class ChatMessage(StrictModel):
    """Persisted chat message returned by the history endpoint."""

    id: int
    session_id: SessionIdentifier
    role: str
    content: str
    meta: dict[str, object] | None = None
    created_at: str


class HealthResponse(StrictModel):
    """Health and synchronization status of the application."""

    status: str
    sqlite_count: int
    chroma_count: int
    in_sync: bool
    model: str