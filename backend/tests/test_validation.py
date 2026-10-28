"""Tests for TaskFlow's Pydantic request validation."""

from datetime import date

import pytest
from pydantic import ValidationError

from app.models import TaskCreate, TaskPriority, TaskStatus


def test_empty_title_is_rejected():
    """A task title must contain non-whitespace characters."""
    with pytest.raises(ValidationError):
        TaskCreate(title="")


def test_whitespace_only_title_is_rejected():
    """Whitespace must not count as a valid title."""
    with pytest.raises(ValidationError):
        TaskCreate(title="   ")


def test_title_longer_than_120_characters_is_rejected():
    """Task titles must respect the configured maximum length."""
    with pytest.raises(ValidationError):
        TaskCreate(title="T" * 121)


def test_valid_title_is_accepted():
    """A valid title must produce a valid task request."""
    task = TaskCreate(title="Prepare project report")

    assert task.title == "Prepare project report"


def test_invalid_priority_is_rejected():
    """Priority must be one of the supported enum values."""
    with pytest.raises(ValidationError):
        TaskCreate(
            title="Prepare project report",
            priority="urgent",
        )


def test_invalid_status_is_rejected():
    """Status must be one of the supported enum values."""
    with pytest.raises(ValidationError):
        TaskCreate(
            title="Prepare project report",
            status="cancelled",
        )


def test_invalid_calendar_date_is_rejected():
    """A due date must represent a real calendar date."""
    with pytest.raises(ValidationError):
        TaskCreate(
            title="Prepare project report",
            due_date="2026-02-30",
        )


def test_valid_due_date_is_accepted():
    """A valid ISO calendar date must be parsed successfully."""
    task = TaskCreate(
        title="Prepare project report",
        due_date="2026-11-05",
    )

    assert task.due_date == date(2026, 11, 5)


def test_supported_enum_values_are_available():
    """The task enums must expose the expected supported values."""
    assert {status.value for status in TaskStatus} == {
        "todo",
        "in_progress",
        "done",
    }

    assert {priority.value for priority in TaskPriority} == {
        "low",
        "medium",
        "high",
    }