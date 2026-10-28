from datetime import date, timedelta

from app import db, task_service
from app.models import TaskCreate


def build_demo_tasks() -> list[dict]:
    today = date.today()

    return [
        {
            "title": "Write API documentation",
            "description": "Document all REST API endpoints, request bodies, responses, and error codes.",
            "priority": "high",
            "due_date": (today + timedelta(days=2)).isoformat(),
        },
        {
            "title": "Review API pull request",
            "description": "Review the pending API pull request, check edge cases, and leave feedback.",
            "priority": "high",
            "due_date": (today + timedelta(days=1)).isoformat(),
        },
        {
            "title": "Fix login validation bug",
            "description": "Fix the login form accepting invalid email addresses.",
            "priority": "high",
            "due_date": today.isoformat(),
        },
        {
            "title": "Prepare weekly progress report",
            "description": "Summarize completed work, current blockers, and next week's priorities.",
            "priority": "medium",
            "due_date": (today + timedelta(days=3)).isoformat(),
        },
        {
            "title": "Design dashboard layout",
            "description": "Create a responsive dashboard layout with task summaries and navigation.",
            "priority": "medium",
            "due_date": (today + timedelta(days=5)).isoformat(),
        },
        {
            "title": "Write unit tests for task creation",
            "description": "Test successful task creation and invalid task input.",
            "priority": "high",
            "due_date": (today + timedelta(days=2)).isoformat(),
        },
        {
            "title": "Optimize database queries",
            "description": "Review slow SQLite queries and add indexes where appropriate.",
            "priority": "medium",
            "due_date": (today + timedelta(days=7)).isoformat(),
        },
        {
            "title": "Deploy backend to staging",
            "description": "Deploy the latest backend build and verify the health endpoint.",
            "priority": "high",
            "due_date": (today + timedelta(days=4)).isoformat(),
        },
        {
            "title": "Update project README",
            "description": "Add installation instructions, environment variables, and development commands.",
            "priority": "low",
            "due_date": (today + timedelta(days=6)).isoformat(),
        },
        {
            "title": "Schedule team planning meeting",
            "description": "Arrange a meeting to discuss upcoming work and assign responsibilities.",
            "priority": "medium",
            "due_date": (today + timedelta(days=2)).isoformat(),
        },
        {
            "title": "Implement task search",
            "description": "Allow users to find tasks using natural-language descriptions.",
            "priority": "high",
            "due_date": (today + timedelta(days=5)).isoformat(),
        },
        {
            "title": "Review database schema",
            "description": "Check task, counter, and chat history tables for consistency.",
            "priority": "medium",
            "due_date": (today + timedelta(days=8)).isoformat(),
        },
        {
            "title": "Prepare presentation slides",
            "description": "Create slides explaining the project architecture and major features.",
            "priority": "low",
            "due_date": (today + timedelta(days=9)).isoformat(),
        },
        {
            "title": "Test task status transitions",
            "description": "Verify that tasks can move between todo, in_progress, and done.",
            "priority": "high",
            "due_date": (today + timedelta(days=3)).isoformat(),
        },
        {
            "title": "Buy groceries",
            "description": "Buy rice, eggs, vegetables, milk, and other household essentials.",
            "priority": "medium",
            "due_date": (today + timedelta(days=1)).isoformat(),
        },
        {
            "title": "Pay electricity bill",
            "description": "Pay the monthly electricity bill before the payment deadline.",
            "priority": "high",
            "due_date": (today + timedelta(days=2)).isoformat(),
        },
        {
            "title": "Clean up unused Python imports",
            "description": "Remove unused imports and simplify unnecessary code in the backend.",
            "priority": "low",
            "due_date": None,
        },
        {
            "title": "Investigate semantic search accuracy",
            "description": "Evaluate task retrieval quality and investigate incorrect search matches.",
            "priority": "high",
            "due_date": (today + timedelta(days=6)).isoformat(),
        },
        {
            "title": "Add error handling to chat endpoint",
            "description": "Handle invalid requests, model failures, and unexpected agent errors.",
            "priority": "high",
            "due_date": (today + timedelta(days=3)).isoformat(),
        },
        {
            "title": "Review weekly personal goals",
            "description": "Review personal progress and plan priorities for the coming week.",
            "priority": "low",
            "due_date": None,
        },
    ]


def main() -> None:
    db.initialize_default_database()

    existing_tasks = db.list_tasks()

    if existing_tasks:
        print(
            f"Seeding skipped: the database already contains "
            f"{len(existing_tasks)} tasks."
        )
        task_service.reconcile()
        print("Task index reconciliation completed.")
        return

    demo_tasks = build_demo_tasks()
    created_count = 0

    for task_data in demo_tasks:
        result = task_service.create_task(TaskCreate(**task_data))

        if not result.ok:
            raise RuntimeError(
                f"Failed to create demo task "
                f"'{task_data['title']}': {result.message}"
            )

        created_count += 1

    task_service.reconcile()

    print(f"Seed complete: {created_count} tasks created.")
    print("Task index reconciliation completed.")


if __name__ == "__main__":
    main()