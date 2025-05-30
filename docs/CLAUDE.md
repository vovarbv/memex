# Memex `docs/` Directory Overview for Claude

## Core Purpose

The `docs/` directory serves as the central repository for user-managed data files and essential system documentation for the Memex project.

## Key Files and Their Roles

1.  **`TASKS.yaml`:**
    *   **Purpose:** This is the primary file where users' tasks are stored in a human-readable YAML format.
    *   **Management:** It is managed by the `TaskStore` class (`memex/scripts/task_store.py`) and interacted with via the `tasks.py` CLI and the "Tasks" tab in the Memex Hub UI.
    *   **Structure:** Contains a top-level `tasks:` key, which holds a list of task objects. Each task object should adhere to the structure defined in `Task` dataclass and documented in `DATA_FORMATS.md`.
    *   **Criticality:** The format and integrity of this file are crucial for task management functionality. Errors in this file (e.g., duplicate IDs, malformed YAML) can disrupt the TaskStore and UI.

2.  **`PREFERENCES.yaml`:**
    *   **Purpose:** Stores user-defined guidelines, coding styles, key technologies, and other preferences intended to guide the AI assistant.
    *   **Management:** Users edit this file directly or via the "Preferences" tab in the Memex Hub UI.
    *   **Usage:** Loaded by `memory_utils.load_preferences()` and incorporated into the `memory.mdc` file by `gen_memory_mdc.py`.
    *   **Structure:** A simple key-value YAML structure.

3.  **`DATA_FORMATS.md`:**
    *   **Purpose:** System documentation detailing the data structures used within Memex, especially for `TASKS.yaml` and the metadata associated with items in the vector store (snippets, notes, code chunks).
    *   **Maintenance:** This file should be kept up-to-date by developers whenever data structures are modified or new ones are introduced. It's a reference for both users and developers (including AI programmers).

4.  **`TASK_PARSER.md`:**
    *   **Purpose:** System documentation explaining the syntax and capabilities of the free-text task parser (`parse_free_text_task` in `memex/scripts/tasks.py`).
    *   **Maintenance:** Should be updated by developers whenever the free-text parsing logic is enhanced or changed.

5.  **`.task_id_counter` (Obsolete):**
    *   **Purpose:** Previously stored the next available ID for new tasks.
    *   **Note:** This file is no longer used. The `TaskStore` class now manages task IDs internally by finding the highest existing ID and incrementing it. This file can be safely deleted if it exists.

## Principles for Files in `docs/`

*   **User-Editable Files (`TASKS.yaml`, `PREFERENCES.yaml`):**
    *   Should be human-readable and easy to understand.
    *   Their structure should be well-documented in `DATA_FORMATS.md`.
    *   The system should be resilient to minor formatting issues but strict about data integrity (e.g., unique task IDs).
*   **Documentation Files (`*.md`):**
    *   Should be clear, concise, and accurate.
    *   Must be maintained by developers to reflect the current state of the system.
*   **Path Configuration:** The paths to `TASKS.yaml` and `PREFERENCES.yaml` are configurable in `memory.toml` under the `[system]` section (e.g., `tasks_file_relative_to_memex_root`). The default location is within `memex/docs/`.