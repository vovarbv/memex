# Project Memory System (v1.0.0)

**An intelligent project-context management system to boost development productivity using AI assistants like Cursor IDE.**

This project provides a suite of tools for creating, managing, and leveraging your project's "memory." This memory consists of:

1.  **Tasks:** Current tasks, their status, execution plan, and notes.  
2.  **Code Snippets:** Important or frequently used pieces of code.  
3.  **Notes:** Arbitrary facts, ideas, or contextual information.  
4.  **Preferences:** General guidelines for the AI assistant (e.g., coding style, key technologies).  
5.  **Code Chunks:** Automatically indexed and chunked code from your project.

All of this information is embedded and stored in a vector database (FAISS), enabling semantic search. The system automatically generates a `memory.mdc` file that Cursor IDE can use to provide more relevant context when generating code or answering queries.

## Key Features

*   **Centralized Task Store:** Manage tasks in a human-readable `docs/TASKS.yaml` format.  
*   **Context-Aware Snippets:** Save and quickly access code fragments.  
*   **Flexible Notes:** Record any textual information for future reference.  
*   **Semantic Search:** Query tasks, snippets, notes, and code chunks based on their semantic relevance to your query.  
*   **Cursor IDE Integration:** Auto-generate `memory.mdc` for AI context injection.  
*   **Code Indexing:** Automatically scan your codebase, chunk files by logical units (functions, classes, sections), and index them for semantic search.
*   **Configurable:** Customize via `memory.toml` (included files for indexing, prompt parameters, etc.).  
*   **CLI Interface:** Convenient commands for managing tasks, adding memory, and generating `memory.mdc`.  
*   **Web Dashboard:** User-friendly Gradio UI for managing tasks, snippets, notes, and preferences without command-line usage.
*   **Automatic Bootstrapping:** The `bootstrap_memory.py` script for quick project setup.
*   **Drop-in Module:** Can be installed as a subdirectory in existing projects with minimal configuration.
*   **Free-Text Task Input:** Natural language-like syntax for quickly creating tasks with a single text input.
*   **Modular UI Architecture:** Tab-based UI with clean separation of concerns for easier maintenance and extension.

## How It Works

1. **Memory Storage:** All memory items (tasks, snippets, notes, code chunks) are stored in a FAISS vector store with metadata.
2. **Semantic Indexing:** Each memory item is converted into an embedding vector using a sentence transformer.
3. **Task-Driven Context:** When generating `memory.mdc`, the system uses your active tasks to query the vector store and retrieve the most relevant context.
4. **Dynamic Context Selection:** The system automatically selects the most relevant tasks, snippets, notes, and code chunks based on your current focus.
5. **Cursor IDE Integration:** The generated `memory.mdc` file is placed in the `.cursor/rules/` directory, where Cursor automatically picks it up.

## Project Structure

```
# When installed as a standalone project:
project-root/
├─ .cursor/                    # Directory for Cursor IDE and vector store
│  ├─ rules/memory.mdc         # Auto-generated context file for Cursor
│  └─ vecstore/                # FAISS storage (index.faiss, metadata.json)
├─ docs/                       # User-editable documents
│  ├─ TASKS.yaml               # Tasks file (managed via CLI tasks.py)
│  ├─ PREFERENCES.yaml         # Project preferences file
│  └─ DATA_FORMATS.md          # Documentation of data structures
├─ scripts/                    # Executable system scripts
│  ├─ memory\_utils.py          # Common utilities (config, FAISS, embeddings)
│  ├─ task\_store.py            # Module for interacting with TASKS.yaml
│  ├─ tasks.py                 # CLI for task management
│  ├─ add\_memory.py            # CLI for adding arbitrary notes
│  ├─ add\_snippet.py           # CLI for adding code snippets
│  ├─ search\_memory.py         # CLI for vector-database search
│  ├─ gen\_memory\_mdc.py        # CLI for generating memory.mdc
│  ├─ bootstrap\_memory.py      # CLI for initializing the project
│  ├─ index\_codebase.py        # CLI for scanning and indexing project files
│  ├─ code\_indexer\_utils.py    # Utilities for chunking code files
│  ├─ init\_store.py            # CLI for initializing the vector store
│  └─ check\_store\_health.py    # CLI for verifying vector store integrity
├─ ui/                         # UI components for web dashboard
│  ├─ main\_app.py              # Main application for the modular Gradio UI
│  ├─ dashboard\_tab.py         # Dashboard tab UI components
│  ├─ tasks\_tab.py             # Tasks tab UI components
│  ├─ snippets\_tab.py          # Snippets tab UI components 
│  ├─ notes\_tab.py             # Notes tab UI components
│  ├─ search\_tab.py            # Search tab UI components
│  ├─ preferences\_tab.py       # Preferences tab UI components
│  ├─ settings\_tab.py          # Settings tab UI components
│  └─ shared\_utils.py          # Shared utilities for UI tabs
├─ tests/                      # Test files
│  ├─ test\_code\_indexer.py     # Tests for code indexing
│  ├─ test\_memory\_utils.py     # Tests for memory utils module
│  └─ test\_free\_text\_parser.py # Tests for free-text task parser
├─ memory.toml                 # System configuration file
└─ requirements.txt            # Python dependencies

# When installed as a subdirectory in an existing project:
host-project/
├─ .cursor/                    # Directory for Cursor IDE and vector store (created in host project)
│  ├─ rules/memory.mdc         # Auto-generated context file for Cursor
│  └─ vecstore/                # FAISS storage (index.faiss, metadata.json)
├─ src/                        # Your host project source code
├─ memex/                      # The memex subdirectory
│  ├─ docs/                    # User-editable documents
│  │  ├─ TASKS.yaml            # Tasks file
│  │  └─ PREFERENCES.yaml      # Project preferences file
│  ├─ scripts/                 # Executable system scripts
│  │  └─ ...                   # All the script files
│  ├─ ui/                      # UI components
│  │  └─ ...                   # All the UI modules
│  └─ memory.toml              # System configuration file (includes paths relative to host project)
└─ ...                         # Other host project files
```

## Requirements

*   Python 3.9+ (3.11 recommended)  
*   Core dependencies listed in `requirements.txt`:
    *   `sentence-transformers` - For embedding text
    *   `faiss-cpu` (or `faiss-gpu` if you have a GPU) - Vector database
    *   `tiktoken` - For token counting
    *   `PyYAML` - For YAML file handling
    *   `tomli` and `tomli-w` - For TOML file handling
    *   `gradio` - For the web dashboard UI
*   Optional agent-related dependencies in `requirements-agents.txt`:
    *   `embedchain`, `crewai`, `litellm`, `mcp-agent`, etc.

## Installation

### Option 1: As a Standalone Project

1.  **Clone the repository:**
    ```bash
    git clone <your-repo-url>
    cd <project-name>
    ```

2.  **Create and activate a virtual environment (recommended):**
    ```bash
    python -m venv .venv
    source .venv/bin/activate  # Linux/macOS
    # .venv\Scripts\activate   # Windows
    ```

3.  **Install dependencies:**
    
    For core functionality (recommended for most users):
    ```bash
    pip install -r requirements.txt
    ```
    
    For all features including experimental agent functionality:
    ```bash
    pip install -r requirements-agents.txt
    ```
    
    If you installed from setup.py:
    ```bash
    pip install -e .           # Core only
    pip install -e .[agents]   # With agent features
    ```

4.  **Initial project setup (bootstrap):**  
    This script will scan your project, create/update `memory.toml` with suggested indexing patterns, and generate empty `docs/TASKS.yaml` and `docs/PREFERENCES.yaml` if missing.
    ```bash
    python memex_cli.py bootstrap_memory
    ```
    _Review the generated `memory.toml` and adjust the `files.include` and `files.exclude` patterns as needed._

5.  **Initialize the vector store:**  
    This command creates the FAISS files in `.cursor/vecstore/`.
    ```bash
    python memex_cli.py init_store
    ```

6.  **Index the codebase:**
    This command scans your project files based on patterns in `memory.toml`, chunks them, and adds them to the FAISS store for semantic search.
    ```bash
    python memex_cli.py index_codebase
    # To re-index and replace existing code chunks:
    python memex_cli.py index_codebase --reindex
    # For more detailed output:
    python memex_cli.py index_codebase --verbose
    ```
    The indexed code chunks will be semantically searchable and included in the generated `memory.mdc` file based on relevance to active tasks.

### Option 2: As a Subdirectory in an Existing Project

1.  **Clone or copy the repository into your host project:**
    ```bash
    # From your host project root
    git clone <memex-repo-url> memex
    # OR copy the memex folder into your project
    ```

2.  **Install dependencies (if not already present in host project):**
    ```bash
    # Install dependencies into your host project's environment
    pip install -r memex/requirements.txt
    ```

3.  **Run bootstrap from the host project root:**
    ```bash
    # From your host project root
    python memex/memex.py bootstrap
    # Or: python memex/memex_cli.py bootstrap_memory
    ```
    This will:
    - Scan your *host project files* (excluding the `memex` subdirectory itself).
    - Create/update `memex/memory.toml`. The `files.include` patterns will be relative to the `memex` directory (e.g., `../src/**/*.py`) to point to host project files.
    - The `system` section in `memex/memory.toml` will be configured to output `.cursor` to the host project root (e.g., `cursor_output_dir_relative_to_memex_root = ".."`).
    - Generate empty `memex/docs/TASKS.yaml` and `memex/docs/PREFERENCES.yaml` if missing.
    
    _Review the generated `memex/memory.toml` and adjust the `[files].include` patterns and `[system]` paths as needed._

4.  **Initialize the vector store:**
    ```bash
    # From your host project root
    python memex/memex.py init
    # Or: python memex/memex_cli.py init_store
    ```
    This will create the FAISS files in your host project's `.cursor/vecstore/` directory.

5.  **Index your codebase:**
    ```bash
    # From your host project root
    python memex/memex.py index
    # Or: python memex/memex_cli.py index_codebase
    
    # To re-index:
    python memex/memex.py index --reindex
    ```
    This will scan and index your host project files according to the patterns in `memex/memory.toml`.

## Usage

### Running Memex Scripts

Memex provides multiple ways to run its scripts, depending on your setup and preferences:

#### Method 1: Using the Launcher Scripts (Recommended)

The easiest way to run Memex commands is using the provided launcher scripts:

**On Windows:**
```bash
# From anywhere if memex is in your PATH
memex.bat ui
memex.bat tasks add "New feature"
memex.bat index --reindex

# Or from the memex directory
.\memex.bat ui
```

**On Linux/macOS:**
```bash
# Make the script executable first
chmod +x memex.sh

# Then run from anywhere if memex is in your PATH
memex.sh ui
memex.sh tasks add "New feature"
memex.sh index --reindex

# Or from the memex directory
./memex.sh ui
```

#### Method 2: Using Python Scripts Directly

**From the memex directory:**
```bash
cd memex
python memex.py ui                    # Launch the web UI
python memex.py tasks add "New task"  # Add a task
python memex.py index                 # Index codebase
python memex.py generate              # Generate memory.mdc

# Or run scripts directly
python memex_cli.py tasks add "New task"
python run_script.py ui
```

**From the parent/host project directory:**
```bash
# If memex is a subdirectory of your project
python memex/memex.py ui
python memex/memex_cli.py tasks add "New task"
python memex/run_script.py ui
```

#### Method 3: As Python Modules

**From the parent directory (where memex package is visible):**
```bash
python -m memex.scripts.tasks add "New task"
python -m memex.scripts.index_codebase --reindex
python -m memex.run_script ui
```

#### Method 4: Using Installed Console Scripts

If you've installed memex with `pip install -e .`:
```bash
# Available from anywhere
memex-ui                    # Launch the web UI
memex-tasks add "New task"  # Task management
memex-index --reindex       # Index codebase
memex-generate              # Generate memory.mdc
memex-search "query"        # Search memory
memex-snippet "code"        # Add code snippet
memex-note "reminder"       # Add a note
```

#### Common Issues and Solutions

**"ModuleNotFoundError: No module named 'memex'"**
- This occurs when running from within the memex directory
- Solution: Use `python memex.py` or run from the parent directory

**"ImportError: attempted relative import with no known parent package"**
- This occurs when running a script directly that uses relative imports
- Solution: Use one of the launcher methods above

**Scripts not found**
- Ensure you're in the correct directory
- Check that the scripts have execute permissions on Linux/macOS

### 1. Task Management (`memex_cli.py tasks`)

The `tasks.py` script offers a CLI for task operations. Tasks are stored in `docs/TASKS.yaml` and auto-synced to the vector DB.

Example commands (use any of the methods from "Running Memex Scripts" above):
```bash
# Using the launcher (recommended)
python memex.py tasks add "Build login page" --plan "Create HTML form;Implement API endpoint;Write tests"

# From memex directory
cd memex && python memex_cli.py tasks add "Build login page"

# From host project root
python memex/memex.py tasks add "Build login page"
```

Tasks support these fields:
- `id`: Unique identifier for the task
- `title`: Brief description of the task
- `status`: Current state ("todo", "in_progress", "done", "blocked", "deferred")
- `progress`: Percentage complete (0-100)
- `plan`: List of steps to complete the task
- `done_steps`: List of completed steps
- `notes`: List of notes about the task
- `priority`: Task priority ("high", "medium", "low")
- `tags`: List of tags for categorizing tasks

For detailed information about the Task data structure and custom fields, see [docs/DATA_FORMATS.md](docs/DATA_FORMATS.md).

*   **Add a new task:**
    ```bash
    python memex_cli.py tasks add "Build login page" --plan "Create HTML form;Implement API endpoint;Write tests"
    ```

*   **Start a task:**
    ```bash
    python memex_cli.py tasks start <task_id>
    ```

*   **Update task progress:**
    ```bash
    python memex_cli.py tasks bump <task_id> <delta_progress>
    # e.g.: python memex_cli.py tasks bump 1 25
    ```

*   **Complete a task:**
    ```bash
    python memex_cli.py tasks done <task_id>
    ```

*   **Delete a task:**
    ```bash
    python memex_cli.py tasks delete <task_id>
    ```

*   **Add a note to a task:**
    ```bash
    python memex_cli.py tasks note <task_id> "Discussed with designer; need mockup revisions."
    ```

*   **List tasks:**
    ```bash
    python memex_cli.py tasks list
    python memex_cli.py tasks list --status in_progress   # Only in-progress tasks
    python memex_cli.py tasks list --details             # Show plan & notes
    ```

### 2. Adding Memory Entries

*   **Add an arbitrary note/fact (`scripts/add_memory.py`):**
    ```bash
    python memex_cli.py add_memory "The key auth API is at /auth/v1"
    python memex_cli.py add_memory "Using PostgreSQL version 15" --type fact --id db_version_note
    ```

*   **Add a code snippet (`scripts/add_snippet.py`):**
    *   From a string:
        ```bash
        python memex_cli.py add_snippet "def hello():\n  print('world')" --lang py
        ```
    *   From a file (or part of it):
        ```bash
        python memex_cli.py add_snippet --from src/utils/helpers.py:10-25  # Lines 10–25
        python memex_cli.py add_snippet --from src/config.py             # Entire file
        ```
        
    *   When using memex as a subdirectory, you can access files in your host project. The path provided to `--from` is relative to your current working directory when executing the script:
        ```bash
        # Example when your Current Working Directory (CWD) is host-project/memex/
        python memex_cli.py add_snippet --from ../src/utils/helpers.py:10-25
        
        # Example when your CWD is host-project/
        python memex/scripts/add_snippet.py --from src/utils/helpers.py:10-25
        ```

### 3. Searching Memory (`scripts/search_memory.py`)

Performs semantic search across all vector-stored entries.

```bash
python scripts/search_memory.py "how user authentication is implemented"
python scripts/search_memory.py "database configuration" -k 3 --type note
```

### 4. Generating Cursor Context (`scripts/gen_memory_mdc.py`)

Gathers data from `docs/PREFERENCES.yaml`, active tasks in `docs/TASKS.yaml`, and relevant snippets/notes from the vector store, then writes `.cursor/rules/memory.mdc`.

```bash
python memex_cli.py gen_memory_mdc
```

The system uses two methods to determine which context items to include:

1. **Task-Driven Context (Default):** When run without arguments, it automatically derives a context query from your active tasks, retrieving snippets, notes, and code chunks that are most relevant to what you're currently working on.

2. **Focus-Based Context:** Specify a focus query to override the task-driven approach:
```bash
python memex_cli.py gen_memory_mdc --focus "user authentication flow"
```

When memex is installed as a subdirectory:
```bash
# From the memex directory
python memex_cli.py gen_memory_mdc

# From the host project root
python memex/scripts/gen_memory_mdc.py
```

**Tip:** Configure a Git pre-commit hook to run this script automatically so `memory.mdc` stays up to date.

Example pre-commit hook (`.git/hooks/pre-commit`):

For standalone installation:
```bash
#!/bin/sh
echo "Generating memory.mdc..."
# Ensure virtualenv is active or python is available
# source .venv/bin/activate # if needed
python memex_cli.py gen_memory_mdc
if [ $? -ne 0 ]; then
  echo "Failed to generate memory.mdc, commit aborted."
  exit 1
fi
git add .cursor/rules/memory.mdc
echo "memory.mdc updated and staged."
exit 0
```

For subdirectory installation:
```bash
#!/bin/sh
echo "Generating memory.mdc..."
# Ensure virtualenv is active or python is available
# source .venv/bin/activate # if needed
python memex/scripts/gen_memory_mdc.py
if [ $? -ne 0 ]; then
  echo "Failed to generate memory.mdc, commit aborted."
  exit 1
fi
git add .cursor/rules/memory.mdc
echo "memory.mdc updated and staged."
exit 0
```

*Make the hook executable:*

```bash
chmod +x .git/hooks/pre-commit
```

### 5. Preferences File (`docs/PREFERENCES.yaml`)

Edit this file to set general preferences and instructions for the AI assistant. For example:

```yaml
# docs/PREFERENCES.yaml
coding_style: "PEP 8 with a max line length of 100 characters."
primary_language: "Python 3.11"
database_type: "PostgreSQL"
testing_framework: "pytest"
key_libraries:
  - "FastAPI for APIs"
  - "Pydantic for data validation"
important_note: "Always include docstrings for public functions and classes."
```

### 6. Configuration File (`memory.toml`)

Controls system behavior. Key sections:

* `[files]`

  * `include`: Glob patterns for files to index (e.g., for auto-snippet addition).
  * `exclude`: Glob patterns for files/directories to skip.

* `[prompt]`

  * `max_tokens`: Max tokens for `memory.mdc` (default: 10000).
  * `top_k_tasks`: Number of active tasks to include in context (default: 5).
  * `top_k_snippets`: Number of relevant snippets/notes/code chunks to include (default: 5).

* `[tasks]`

  * `file`: Path to the tasks file (default: `"docs/TASKS.yaml"`).
  * `tag_prefix`: Legacy prefix for task tags in markdown format (default: `"- "`).

* `[preferences]`

  * `file`: Path to the preferences file (default: `"docs/PREFERENCES.yaml"`).

* `[system]`

  * `cursor_output_dir_relative_to_memex_root`: (String, default: `".."`). Specifies the path where the `.cursor` directory (containing `vecstore` and `rules/memory.mdc`) will be created, relative to the `memex` directory (where `memory.toml` resides). A value of `".."` places it in the parent directory of `memex`.
  * `tasks_file_relative_to_memex_root`: (String, default: `"docs/TASKS.yaml"`). Path to the `TASKS.yaml` file, relative to the `memex` directory.
  * `preferences_file_relative_to_memex_root`: (String, default: `"docs/PREFERENCES.yaml"`). Path to the `PREFERENCES.yaml` file, relative to the `memex` directory.

When installed as a subdirectory, the `include` patterns in `[files]` section will have relative paths like `../src/**/*.py` that point to files in the host project.

### 7. Vector Store Health Check (`scripts/check_store_health.py`)

The `check_store_health.py` script checks the integrity of the FAISS vector database and its metadata, helping diagnose any data corruption issues:

```bash
# Basic health check
python memex_cli.py check_store_health

# Detailed diagnostic information
python memex_cli.py check_store_health --verbose

# Output in JSON format (useful for integrations)
python memex_cli.py check_store_health --json

# Suppress informational output, show only errors
python memex_cli.py check_store_health --quiet
```

This utility validates:
- Synchronization between FAISS vectors and metadata
- Proper mapping between custom IDs and FAISS IDs
- Existence of vectors for all mapped IDs
- Integrity of the entire storage system

If corruption is detected, the tool provides guidance on potential fixes.

### 8. Codebase Indexing (`scripts/index_codebase.py`)

The `index_codebase.py` script scans your project files according to patterns in `memory.toml`, chunks them into semantic units (functions, classes, sections, etc.), and adds them to the FAISS vector store for semantic search:

```bash
# Basic indexing
python scripts/index_codebase.py

# Re-index (delete existing code chunks first)
python scripts/index_codebase.py --reindex

# Show detailed progress information
python scripts/index_codebase.py --verbose
```

When memex is installed as a subdirectory:
```bash
# From the host project root
python memex/run_script.py index_codebase

# Or with options
python memex/run_script.py index_codebase --reindex --verbose
```

This script:
- Reads the `files.include` and `files.exclude` patterns from `memory.toml`
- Intelligently chunks files based on their type:
  - **Python files**: Chunks by functions and classes using AST parsing
  - **Markdown files**: Chunks by sections (headings) or paragraphs
  - **Other text files**: Chunks by fixed-size overlapping segments
- Adds each chunk to the FAISS vector store with appropriate metadata
- When `--reindex` is used, removes all existing code chunks before indexing
- Provides progress reporting with `--verbose` option

The indexed code chunks are semantically searchable and will be included in the generated `memory.mdc` file based on relevance to active tasks, providing the AI assistant with important context from your codebase.

You can also trigger the codebase indexing process from the Settings tab in the Memex Hub web dashboard.

## Memex Hub - Web Dashboard

The Memex Hub provides a user-friendly web interface for managing your project memory. It's the recommended way to interact with the system for most day-to-day operations.

### Launching the Web Dashboard

```bash
# From the project root
python run_script.py ui

# Or if you're using memex as a subdirectory
python memex/run_script.py ui
```

This will start a local Gradio server, typically on http://0.0.0.0:7860. Open this URL in your browser to access the dashboard.

### Features

The Memex Hub dashboard includes several sections:

* **Dashboard**: 
  * Overview with key statistics (tasks, snippets, notes)
  * Active tasks list showing current in-progress tasks
  * Vector store health indicator
  * Quick access to generate memory.mdc
  * Programmable refresh for real-time updates
* **Search Memory**: 
  * Semantic search across tasks, snippets, and notes with filtering options
  * Advanced filters by task status, snippet language, and content
  * Full content display for notes and properly formatted code blocks
  * Improved display formatting for better readability
* **Tasks**: 
  * View, add, edit, and delete tasks with status filtering
  * **New! Free-text task input** for quick task creation with natural syntax
  * Edit task details including title, status, progress percentage, plan steps, and notes
  * Mark tasks as done or in progress
  * Initial data loads automatically when opening the tab
* **Snippets**: 
  * Browse, add, edit, and delete code snippets with language filtering
  * Upload snippets directly from files with automatic language detection
  * Edit existing snippets with full code editor support
* **Notes**: 
  * View, add, edit, and delete notes with type filtering
  * Custom ID support for better organization
  * Edit existing notes with rich text area
* **Preferences**: 
  * Edit your PREFERENCES.yaml file directly in the browser
  * Auto-load capabilities for better user experience 
  * Path resolution fixes for reliable operation
* **Settings**: 
  * Configure system settings
  * View and edit memory.toml configuration
  * Generate memory.mdc for Cursor IDE integration
  * Vector store health check with detailed diagnostics and suggestions
  * Reinitialize vector store if needed
  * Fix for data integrity error handling with retry capabilities

All operations provide immediate visual feedback through toast notifications and status messages for a better user experience. If data integrity issues are detected, a convenient "Retry Data Load" button allows refreshing the app state without restarting.

### Free-Text Task Input

The new free-text task input feature allows you to quickly create tasks using a simple, intuitive syntax:

```
Implement login form validation
plan: Create validation rules; Write validation functions; Add error messages; Test edge cases
status: in_progress
progress: 35%
priority: high
tags: #frontend #auth
notes: Use client-side validation first, then add server-side validation. 
Reference the design specs for error message styling.
```

This creates a complete task with all fields populated. The enhanced parser supports:

- **Smart keyword recognition** - case-insensitive, flexible positioning
- **Multiple input formats** - numbered lists, semicolons, quotes, commas, hashtags
- **Automatic normalization** - converts variations like "wip" to "in_progress" 
- **Preview functionality** - see how your task will be parsed before saving

The "Preview Task" button allows you to verify how your free-text input will be interpreted before committing it to the task store.

For detailed information about the free-text task syntax, see [docs/DATA_FORMATS.md](docs/DATA_FORMATS.md).

### Workflow Example

1. Use the **Tasks** tab to create and manage your project tasks
2. Add code snippets through the **Snippets** tab (either by pasting code or uploading files)
3. Store important project information as notes in the **Notes** tab
4. Set project preferences in the **Preferences** tab
5. Use the search functionality to find relevant information
6. Generate an updated memory.mdc from the **Dashboard** or **Settings** tab

The web dashboard makes it easier to manage your project memory without remembering command-line syntax, especially for team members who prefer graphical interfaces.

## Working with Cursor IDE

Once `.cursor/rules/memory.mdc` is generated, Cursor IDE will automatically pick it up. When interacting with the AI (e.g., writing code via Ctrl+K or chatting via Ctrl+L), the contents of `memory.mdc` are included in the context to help the AI provide more accurate, project-specific answers.

## Quick Start

### Standalone Installation

```bash
# 0. Install (see Installation section above)
# python -m venv .venv && source .venv/bin/activate
# pip install -r requirements.txt

# 1. One-time project setup
python memex_cli.py bootstrap_memory
python memex_cli.py init_store

# 2. Launch the web dashboard (recommended)
python memex_cli.py ui
# Then open http://localhost:7860 in your browser

# Alternative: Use any of the wrapper scripts
python memex.py ui       # Cross-platform Python wrapper
./memex.sh ui           # Unix/Linux/macOS wrapper  
memex.bat ui            # Windows wrapper
make ui                 # Makefile shortcut

# 3. Add your first task (via CLI or web UI)
python memex_cli.py tasks add "Set up initial documentation" --plan "Write README;Describe installation;Add usage examples"
# Or use the web dashboard Tasks tab

# 4. (Optional) Add a code snippet
python memex_cli.py add_snippet --from src/main.py:1-10  # Lines 1-10
# Or use the web dashboard Snippets tab to upload files

# 5. Index your codebase
python memex_cli.py index_codebase
# Or use the Settings tab in the web dashboard

# 6. Generate Cursor context file
python memex_cli.py gen_memory_mdc
# Or use the Generate button in the web dashboard

# 7. Open the project in Cursor IDE
#    The .cursor/rules/memory.mdc file will be automatically used
```

### Subdirectory Installation

```bash
# Assuming you're in your host project root

# 1. Clone memex into your project as a subdirectory
git clone <memex-repo-url> memex
# OR copy the memex folder into your project

# 2. Install dependencies (if needed)
pip install -r memex/requirements.txt

# 3. One-time project setup (run from host project root)
python memex/memex_cli.py bootstrap_memory
# Review memex/memory.toml - ensure `files.include` targets your host project
# source files (e.g., `../src/**/*.py`) and `system` paths are correct.
python memex/memex_cli.py init_store
# This will create .cursor/vecstore in your host project root.

# 4. Launch the web dashboard (recommended for subdirectory setup)
python memex/memex_cli.py ui
# Then open http://localhost:7860 in your browser

# Alternative: Use wrapper scripts
python memex/memex.py ui    # Cross-platform Python wrapper
./memex/memex.sh ui        # Unix/Linux/macOS wrapper
memex/memex.bat ui         # Windows wrapper

# 5. Add your first task (via CLI or web UI)
python memex/memex_cli.py tasks add "Set up initial integration" --plan "Add memex;Configure paths;Test integration"
# Or use the web dashboard Tasks tab

# 6. Index your codebase
python memex/memex_cli.py index_codebase
# Or use the Settings tab in the web dashboard

# 7. Generate Cursor context file
python memex/memex_cli.py gen_memory_mdc
# Or use the Generate button in the web dashboard

# 8. Open the project in Cursor IDE
#    The .cursor/rules/memory.mdc file will be automatically used
```

## Troubleshooting

### Common Issues

**ModuleNotFoundError when importing memex**
- **Issue**: Getting "No module named 'memex'" when trying to import
- **Cause**: Running from within the memex directory where `memex.py` file shadows the package
- **Solution**: 
  - Run from the parent directory: `cd .. && python -m memex.scripts.tasks`
  - Or use the launcher: `python memex.py tasks`
  - Or install the package: `pip install -e .`

**Scripts fail with import errors**
- **Issue**: ImportError or ModuleNotFoundError when running scripts
- **Cause**: Python can't find the memex package modules
- **Solution**:
  - Use the launcher scripts: `python memex.py <command>`
  - Or run as modules: `python -m memex.scripts.<script_name>`
  - Avoid running scripts directly from the scripts directory

**Permission denied on Linux/macOS**
- **Issue**: "Permission denied" when running shell scripts
- **Solution**: Make scripts executable: `chmod +x memex.sh`

**Web UI won't start**
- **Issue**: Gradio server fails to launch
- **Possible causes**:
  - Port 7860 is already in use
  - Missing dependencies
- **Solution**:
  - Check if port is free: `netstat -an | grep 7860`
  - Reinstall requirements: `pip install -r requirements.txt`
  - Try a different port by modifying the launch command

**Memory tab shows no items**
- **Issue**: The Memory tab in the web UI displays no items even when data exists
- **Cause**: Metadata stored in old format (keyed by FAISS IDs instead of custom IDs)
- **Solution**:
  - Check for the issue: `python memex_cli.py check_store_health`
  - If "CRITICAL MISMATCH" errors are reported, run migration: `python scripts/migrate_faiss_keyed_metadata.py`
  - Verify the fix: `python memex_cli.py check_store_health`

**Vector store corruption**
- **Issue**: Errors when accessing the vector store
- **Solution**:
  - Run health check: `python memex.py check-health`
  - Reinitialize if needed: `python memex.py init --force`
  - Re-index your codebase: `python memex.py index --reindex`

### Getting Help

1. Check the [docs/](docs/) directory for detailed documentation
2. Run scripts with `--help` flag for usage information
3. Check existing issues on GitHub
4. Create a new issue with:
   - Your OS and Python version
   - Complete error message
   - Steps to reproduce

## Roadmap (v1.1+)

* **Cursor Task Panel:** Interactive task management panel directly in the IDE.
* **Web Dashboard Enhancements:** Additional features for the Gradio UI such as task visualization, bulk operations, and advanced filtering.
* **Auto Snippet Addition:** Cursor plugin/extension to add snippets via selection and command.
* **Increased Test Coverage:** Aim for ≥ 80% code coverage.
* **Encrypted Vecstore:** Enhanced security for corporate environments.
* **Smarter Snippet Selection:** Context-aware snippet inclusion based on the open file or recent activity.

## Contributing

Suggestions, bug reports, and pull requests are welcome!

## License

MIT License

Copyright (c) 2024 vovarbv
