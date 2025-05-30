# Memex System Overview for Claude

## Core Purpose

Memex is an intelligent project-context management system designed to enhance developer productivity when working with AI assistants, particularly Cursor IDE. It achieves this by:

1.  **Centralizing Project Knowledge:** Managing tasks, code snippets, notes, and developer preferences.
2.  **Automated Code Understanding:** Indexing the project's codebase into a searchable vector store.
3.  **Semantic Context Provision:** Dynamically generating a `memory.mdc` file that provides relevant, contextual information to the AI assistant based on active tasks or explicit focus.

## Main Components & Their Roles

1.  **`docs/` Directory:**
    *   Contains user-editable configuration files (`TASKS.yaml`, `PREFERENCES.yaml`).
    *   Houses system documentation (`DATA_FORMATS.md`, `TASK_PARSER.md`).
    *   This is the primary interface for users to define tasks and AI guidelines.

2.  **`scripts/` Directory - Backend Engine:**
    *   The core backend logic of Memex responsible for data management and processing.
    *   **Core Utilities:**
        *   `memory_utils.py`: Backbone for data persistence, FAISS operations, text embedding, metadata management
        *   `task_store.py`: Task management with CRUD operations, auto-incrementing IDs, YAML persistence
        *   `code_indexer_utils.py`: File-type specific chunking logic for semantic embedding
    *   **CLI Tools:** Complete command-line interface for all operations
        *   `tasks.py`: Task management (add, list, start, done, delete, note, complete_step)
        *   `add_memory.py`, `add_snippet.py`: Adding notes and code snippets
        *   `search_memory.py`: Semantic search across all memory items
        *   `gen_memory_mdc.py`: Context file generation for AI assistants
        *   `bootstrap_memory.py`: Project initialization and setup
        *   `index_codebase.py`: Codebase scanning and indexing
        *   `init_store.py`, `check_store_health.py`: Vector store management
    *   **Design Principles:** Separation of concerns, modularity, configuration-driven behavior, robust error handling

3.  **`ui/` Directory - Memex Hub:**
    *   Gradio-based web dashboard providing graphical interface for all Memex functionalities.
    *   **Architecture:**
        *   `main_app.py`: Main application orchestrator, launches Gradio server
        *   Individual tab modules (`*_tab.py`): Self-contained UI components following standardized structure
        *   `shared_utils.py`: Common helpers and robust import utilities
        *   `TAB_STRUCTURE.md`: Critical specification for tab development
        *   `tab_template.py`: Boilerplate for new tab creation
    *   **Design Focus:** User experience, modularity, performance, graceful error handling

4.  **`.cursor/` Directory (Generated):**
    *   The primary output for Cursor IDE integration.
    *   `rules/memory.mdc`: The context file read by Cursor.
    *   `vecstore/`: The FAISS vector index and associated metadata.
    *   This directory is typically generated in the parent of the `memex/` directory (i.e., the host project root).

5.  **Configuration (`memory.toml`):**
    *   The central configuration file for Memex.
    *   Defines file indexing patterns, context generation parameters, and paths to key files like `TASKS.yaml` and `PREFERENCES.yaml`.

## Key Data Flow & Workflow

1.  **User Input:** Users define tasks in `TASKS.yaml` (via UI or CLI), preferences in `PREFERENCES.yaml`, and add snippets/notes (via UI or CLI).
2.  **Configuration:** `memory.toml` guides system behavior, especially for indexing and context generation.
3.  **Indexing:**
    *   `index_codebase.py` scans project files (guided by `memory.toml`) and chunks them.
    *   Tasks, snippets, notes, and code chunks are converted to embeddings by `memory_utils.py` using Sentence Transformers.
    *   Embeddings and metadata are stored in the FAISS vector store (`.cursor/vecstore/`).
4.  **Context Generation (`gen_memory_mdc.py`):**
    *   Reads `PREFERENCES.yaml`.
    *   Loads active tasks from `TaskStore`.
    *   Formulates a semantic query based on active tasks (or a user-provided focus).
    *   Searches the vector store for relevant tasks, snippets, notes, and code chunks.
    *   Formats this information into Markdown and writes it to `.cursor/rules/memory.mdc`.
5.  **AI Assistant Usage:** Cursor IDE (or other compatible tools) reads `memory.mdc` to enhance its understanding and provide more relevant responses.

## Architectural Principles

*   **Modularity:** Core logic (scripts) should be separated from the presentation layer (UI). UI components should be self-contained tabs.
*   **Single Source of Truth:** `TASKS.yaml`, `PREFERENCES.yaml`, and `memory.toml` are primary sources for user-defined data and configuration. The vector store is the source for indexed items.
*   **Configurability:** System behavior should be largely controllable via `memory.toml`.
*   **Robustness:** Implement comprehensive error handling, logging, and data validation.
*   **User-Friendliness:** Provide both a powerful CLI and an intuitive UI (Memex Hub).
*   **Extensibility:** Design components to allow for future expansion (e.g., new memory types, different AI assistant integrations).

## Backend-UI Interaction Principles

*   **Data Flow Direction:** UI tabs read data through `TaskStore` and `memory_utils.py` functions. User actions trigger backend functions in relevant `scripts/` modules.
*   **Import Strategy:** UI uses `shared_utils.py` helpers like `import_memory_utils()` and `import_task_store()` for robust backend imports.
*   **State Management:** Backend data stores are the source of truth; minimize state in Gradio components.
*   **Error Handling:** UI tabs catch backend exceptions and display user-friendly messages. Handle `data_integrity_error` gracefully.

## Key Technical Details

*   **Path Management:** Use `pathlib.Path` for all file operations. Resolve relative to `ROOT` (memex directory) or `HOST_PROJECT_ROOT_FOR_SCAN`.
*   **FAISS Operations:** Use `IndexManager` (via `memory_utils.load_index()`) to avoid redundant index loading. Implement robust error handling and caching.
*   **Configuration:** All behavior should be controllable via `memory.toml` using `load_cfg()` from `memory_utils.py`.
*   **Task Management:** Ensure task ID uniqueness, auto-incrementing IDs, and proper sync with FAISS vector store.
*   **CLI Standards:** Use `argparse` for consistent command-line interfaces with helpful usage messages.

## Architectural Decisions Made

### UI Architecture Evolution
- **Tab Consolidation**: Successfully merged separate snippets/notes tabs into unified `memory_tab.py` for better user experience
- **Search Unification**: Integrated search_filters functionality into main `search_tab.py` to reduce UI complexity
- **Primary Workflow**: Established Focus tab as the main entry point for task-driven context generation
- **Tab Ordering**: Prioritized workflow tabs (Focus, Memory, Tasks) before utility tabs (Search, Preferences, Settings, Dashboard)

### Technical Implementation Choices
- **Standardized Tab Structure**: All tabs follow consistent pattern defined in `TAB_STRUCTURE.md`
- **Robust Import System**: Implemented fallback import mechanisms via `shared_utils.py` for different execution contexts
- **Error Handling Strategy**: Comprehensive data integrity checks with graceful degradation and user-friendly error messages
- **File Browser Integration**: Advanced file management capabilities integrated into Settings tab rather than separate utility

### Data Management Approach
- **Single Source of Truth**: YAML files for user data, FAISS vector store for indexed content
- **Path Resolution**: Configurable paths in `memory.toml` with proper handling of memex as subdirectory
- **ID Management**: Auto-incrementing task IDs with collision detection and resolution
- **Sync Strategy**: Tasks and memory items sync with vector store for semantic search capabilities

## Development Environment

*   **Environment**: This project is being developed in WSL (Windows Subsystem for Linux)
*   **Path Context**: `/mnt/c/Code/Cursor Memory/memex` maps to `C:\Code\Cursor Memory\memex` in Windows

## Critical Development Guidelines

*   **DO NOT** introduce code that directly modifies files outside the `memex/` directory, except for the `.cursor/` directory in the host project root.
*   **DO** ensure that all user-facing file paths configured in `memory.toml` (e.g., for `TASKS.yaml`, `PREFERENCES.yaml`, codebase `include` patterns) are handled correctly, especially when `memex` is used as a subdirectory. Paths should be relative to the `memex` root or clearly documented if relative to the host project.
*   **DO** maintain clear separation between data storage/management logic (in `scripts/`) and UI presentation (in `ui/`). The UI should call functions from `scripts/` rather than reimplementing logic.
*   **DO** follow the standardized tab structure defined in `ui/TAB_STRUCTURE.md` for all UI development.
*   **DO** implement comprehensive error handling, logging (using Python `logging` module), and data validation throughout.
*   **DO** ensure idempotency for operations like store initialization and indexing (safe to run multiple times).
*   **DO** maintain the established UI consolidation principles: unified Memory tab, integrated Search, Focus-first workflow.