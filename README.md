# TaskFlow — AI-Powered Task Manager

TaskFlow is an AI-powered task management application that lets users manage their tasks primarily through natural-language conversation. Instead of navigating multiple forms or menus, users can instruct the AI assistant to create tasks, update task details, change statuses, search for relevant tasks, and manage their workload.

The application combines a responsive single-page interface with a FastAPI backend, persistent SQLite storage, semantic retrieval using ChromaDB, and Google's Gemini API.

## Features

### AI-Powered Task Management

Users can interact with the TaskFlow assistant using natural language to:

- Create tasks with titles, descriptions, priorities, and due dates.
- List tasks and retrieve relevant information.
- Edit existing task details.
- Change task status.
- Update task priority.
- Mark tasks as completed.
- Delete tasks.
- Search for tasks using natural-language descriptions.
- Ask questions about overdue tasks and upcoming deadlines.

The assistant provides responses describing the result of each operation.

### Task Dashboard

The dashboard displays tasks alongside the AI conversation interface.

Task information includes:

- Task ID
- Title
- Description
- Status
- Priority
- Due date, when specified

Users can filter tasks by status, including all tasks, tasks to do, tasks in progress, and completed tasks.

### Semantic Search

TaskFlow uses ChromaDB to support semantic retrieval. This allows users to search by meaning rather than relying exclusively on exact keyword matches.

### Persistent Storage

SQLite serves as the authoritative source of task data. Task changes are stored in the database so that they persist across application refreshes and restarts.

### Responsive Interface

The single-page interface keeps the task dashboard and AI conversation accessible together. The chat conversation scrolls independently, and the message composer supports sending instructions using Enter and inserting new lines using Shift + Enter.

## Technology Stack

| Component            | Technology        | Purpose                                            |
| -------------------- | ----------------- | -------------------------------------------------- |
| Frontend             | React             | Component-based user interface                     |
| Programming language | TypeScript        | Type safety in frontend development                |
| Build tool           | Vite              | Frontend development server and build tooling      |
| Styling              | Tailwind CSS      | Responsive interface styling                       |
| Icons                | Lucide React      | Interface icons                                    |
| Backend              | FastAPI           | HTTP API and backend application logic             |
| Primary database     | SQLite            | Authoritative persistent task storage              |
| Vector database      | ChromaDB          | Semantic task retrieval                            |
| AI provider          | Google Gemini API | Natural-language understanding and agent responses |

### How an AI Task Operation Works

1. The user enters a natural-language instruction in the chat interface.
2. The frontend sends the instruction to the backend.
3. The backend processes the request using the Gemini API.
4. The agent determines the appropriate task operation and its parameters.
5. The backend validates the requested operation and resolves the target task.
6. When the operation is valid and unambiguous, the backend executes it.
7. SQLite stores the authoritative task state, and the semantic index is updated as appropriate.
8. The backend returns a response describing the outcome and the current task information.
9. The frontend updates the displayed tasks without requiring a manual page refresh.

The AI model interprets instructions, while backend logic remains responsible for validating and executing task operations.

## Task Data Model

Each task contains the following information:

| Field         | Description                   |
| ------------- | ----------------------------- |
| `id`          | Deterministic task identifier |
| `title`       | Task title                    |
| `description` | Optional task description     |
| `status`      | Current task status           |
| `priority`    | Task priority                 |
| `due_date`    | Optional task deadline        |
| `created_at`  | Task creation timestamp       |
| `updated_at`  | Last-update timestamp         |

### Task Statuses

- `todo` — The task has not been completed.
- `in_progress` — Work is underway.
- `done` — The task has been completed.

### Task Priorities

- `low`
- `medium`
- `high`

Task identifiers provide a consistent way to reference individual tasks. The backend should resolve ambiguous references before performing destructive operations.

## Getting Started

### Prerequisites

Install the following software before running TaskFlow:

- Python with a version supported by the backend dependencies.
- Node.js and npm.
- A Google Gemini API key.
- Git.

### 1. Clone the Repository

```bash
git clone https://github.com/tanvir-005/TaskFlow.git
cd TaskFlow
```

Replace the repository URL if your final repository uses a different name or URL.

### 2. Set Up the Backend

Navigate to the backend directory:

```bash
cd backend
```

Create and activate a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate
```

Install the backend dependencies using the package manager and dependency file included in the repository.

For example, if the project uses `requirements.txt`:

```bash
pip install -r requirements.txt
```

Configure the environment variables described in the next section.

**Start the backend:** Use the Uvicorn command matching the actual FastAPI application module in the repository. For example, if the application object is `app` in `main.py`:

```bash
uvicorn main:app --reload
```

The example assumes that `main.py` contains the FastAPI application object. Adjust the module path if your project uses a different entry point.

### 3. Set Up the Frontend

Open a second terminal and navigate to the frontend directory:

```bash
cd frontend
```

Install dependencies:

```bash
npm install
```

Start the development server:

```bash
npm run dev
```

Vite will display the local frontend address in the terminal. Open that address in your browser.

### 4. Verify the Application

Confirm that:

- The frontend loads successfully.
- The backend starts without errors.
- The frontend can communicate with the backend.
- Tasks appear in the dashboard.
- The chat interface accepts instructions.
- Task operations update the dashboard.
- Task data remains available after refreshing the page.

**Note:** The setup commands above are a template. Verify the backend entry point, dependency manager, environment variable names, and API configuration against the actual repository before submitting this README.

## Environment Configuration

TaskFlow requires a Gemini API key for AI-powered functionality.

Create a backend environment file

```env
GEMINI_API_KEY=your_gemini_api_key
```

## Using TaskFlow

### Create a Task

Enter a natural-language instruction describing the task, its priority, and optionally its deadline.

Example:

> i have to urgently write a letter within today

> i may go to cinema, not sure, create it anyway

### View Tasks

Ask the assistant to list all tasks or retrieve tasks matching a particular condition.

Example:

> Show all unfinished tasks related to documentation

> anything important remaining?

### Update a Task

Identify the task and specify the requested change.

Example:

> Change the priority of the API documentation task to low

> writing the letter is not so important i guess

### Change Task Status

Specify the task and its intended status.

Example:

> currently writting the letter

### Complete a Task

Example:

> Mark the weekly report as completed.

### Delete a Task

Identify the task to remove.

When a request could refer to multiple tasks, the assistant should ask the user to clarify which task they mean before deleting anything.

### Search Semantically

Describe the subject or purpose of the task rather than relying on its exact title.

Example:

> Find tasks related to preparing the project presentation.

The semantic retrieval system can help locate relevant tasks even when the wording differs from the original task title.

## Example Prompts

The following prompts demonstrate the intended range of natural-language interactions.

| No. | Prompt                                                             | Expected behavior                                                            |
| --- | ------------------------------------------------------------------ | ---------------------------------------------------------------------------- |
| 1   | Create a high-priority task to finish the demo tomorrow.           | Create a task with the requested title, priority, and due date.              |
| 2   | Show all unfinished tasks related to documentation.                | Retrieve relevant tasks and exclude completed tasks.                         |
| 3   | Move the demo task to in progress and mark the weekly report done. | Update the status of both identified tasks.                                  |
| 4   | Change the priority of the API task to low.                        | Update the priority of the intended task.                                    |
| 5   | Delete the task.                                                   | Ask for clarification if the target task cannot be identified unambiguously. |

These are representative test prompts, not a claim that every prompt has already passed testing. Record the actual results from your final demonstration.

## Validation and Error Handling

AI-generated instructions should not be executed blindly. The backend should validate the requested operation before changing task state.

Important validation cases include:

- Missing task titles during creation.
- Invalid status or priority values.
- Invalid or malformed due dates.
- Requests that reference nonexistent tasks.
- Ambiguous task references.
- Attempts to delete or update the wrong task.
- Invalid or incomplete structured agent actions.
- AI provider errors and network failures.
- Database or semantic-index failures.

The application should return clear, understandable error messages when an operation cannot be completed.

For ambiguous task references, especially when editing or deleting a task, the assistant should ask a clarification question instead of guessing.

## Persistence and Semantic Search

### SQLite: Authoritative Task State

SQLite stores the application's task records. It is the source of truth for task state, including status, priority, title, description, and due date.

The database allows task changes to survive page refreshes and application restarts.

### ChromaDB: Semantic Retrieval

ChromaDB provides vector-based retrieval for task search. It helps retrieve tasks that are conceptually related to a user's query.

The vector index complements SQLite rather than replacing it.

Task state should be read from the authoritative database when performing operations. The semantic index should be kept synchronized with changes to task records so that searches do not rely on stale task information.

## Limitations

Document the limitations observed in the final implementation. Potential areas to evaluate include:

- Dependence on network access and the Gemini API for AI-powered operations.
- AI interpretation errors when prompts are unclear.
- Semantic retrieval quality for short or ambiguous queries.
- Synchronization between the SQLite database and the ChromaDB index.
- Behavior when the AI provider or database is unavailable.

These are areas to assess, not assertions that each problem currently exists.

## Future Improvements

Potential improvements include:

- Automated integration and end-to-end tests for agent operations.
- More comprehensive validation of structured AI actions.
- Improved clarification workflows for ambiguous task references.
- Database and semantic-index consistency checks.
- More advanced task filtering and search controls.
- Better observability for agent decisions and operation failures.

## Assignment Compliance

The implementation is intended to address the assignment's core requirements:

- A single-page interface with the task list and chat visible together.
- Task creation, listing, editing, status changes, completion, and deletion through chat.
- Task title, optional description, status, priority, and optional due date.
- Semantic task retrieval using ChromaDB.
- Persistent task storage.
- Structured agent actions and input validation.
- Clear success and error responses.
- Clarification before ambiguous updates or deletions.
- Deterministic task IDs and a reliable source of truth.
- Three to five documented prompts, failures, and corrections.
- Repository link and setup instructions.
- Short demo video or live demonstration.

Thank you.