# Project Memory System (v1.0.0)

**An intelligent project-context management system to boost development productivity using AI assistants like Cursor IDE.**

This project provides a suite of tools for creating, managing, and leveraging your project's "memory." This memory consists of:

1.  **Tasks:** Current tasks, their status, execution plan, and notes.  
2.  **Code Snippets:** Important or frequently used pieces of code.  
3.  **Notes:** Arbitrary facts, ideas, or contextual information.  
4.  **Preferences:** General guidelines for the AI assistant (e.g., coding style, key technologies).  

All of this information is embedded and stored in a vector database (FAISS), enabling semantic search. The system automatically generates a `memory.mdc` file that Cursor IDE can use to provide more relevant context when generating code or answering queries.

## Key Features

*   **Centralized Task Store:** Manage tasks in a human-readable `docs/TASKS.yaml` format.  
*   **Context-Aware Snippets:** Save and quickly access code fragments.  
*   **Flexible Notes:** Record any textual information for future reference.  
*   **Semantic Search:** Query tasks, snippets, and notes based on their semantic relevance to your query.  
*   **Cursor IDE Integration:** Auto-generate `memory.mdc` for AI context injection.  
*   **Configurable:** Customize via `memory.toml` (included files for indexing, prompt parameters, etc.).  
*   **CLI Interface:** Convenient commands for managing tasks, adding memory, and generating `memory.mdc`.  
*   **Automatic Bootstrapping:** The `bootstrap_memory.py` script for quick project setup.

## Project Structure

```

project-root/
├─ .cursor/                    # Directory for Cursor IDE and vector store
│  ├─ rules/memory.mdc         # Auto-generated context file for Cursor
│  └─ vecstore/                # FAISS storage (index.faiss, metadata.json)
├─ docs/                       # User-editable documents
│  ├─ TASKS.yaml               # Tasks file (managed via CLI tasks.py)
│  └─ PREFERENCES.yaml         # Project preferences file
├─ scripts/                    # Executable system scripts
│  ├─ memory\_utils.py          # Common utilities (config, FAISS, embeddings)
│  ├─ task\_store.py            # Module for interacting with TASKS.yaml
│  ├─ tasks.py                 # CLI for task management
│  ├─ add\_memory.py            # CLI for adding arbitrary notes
│  ├─ add\_snippet.py           # CLI for adding code snippets
│  ├─ search\_memory.py         # CLI for vector-database search
│  ├─ gen\_memory\_mdc.py        # CLI for generating memory.mdc
│  ├─ bootstrap\_memory.py      # CLI for initializing the project
│  └─ init\_store.py            # CLI for initializing the vector store
├─ memory.toml                 # System configuration file
└─ requirements.txt            # Python dependencies

```

## Requirements

*   Python 3.9+ (3.11 recommended)  
*   Core dependencies listed in `requirements.txt`:
    *   `sentence-transformers` - For embedding text
    *   `faiss-cpu` (or `faiss-gpu` if you have a GPU) - Vector database
    *   `tiktoken` - For token counting
    *   `PyYAML` - For YAML file handling
    *   `tomli` and `tomli-w` - For TOML file handling
*   Optional agent-related dependencies in `requirements-agents.txt`:
    *   `embedchain`, `crewai`, `litellm`, `mcp-agent`, etc.

## Installation

1.  **Clone the repository (or copy the files into your project):**  
    If this is a standalone repo:
    ```bash
    git clone <your-repo-url>
    cd <project-name>
    ```
    If integrating into an existing project, copy the `scripts/`, `docs/` directories (with empty `TASKS.yaml` and `PREFERENCES.yaml`) and the `requirements.txt` and `memory.toml` files (or let `bootstrap_memory.py` generate them).

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
    This script will scan your project, create/update `memory.toml` with suggested indexing paths, and generate empty `docs/TASKS.yaml` and `docs/PREFERENCES.yaml` if missing.
    ```bash
    python scripts/bootstrap_memory.py
    ```
    _Review the generated `memory.toml` and adjust the `files.include` and `files.exclude` sections as needed._

5.  **Initialize the vector store:**  
    This command creates the FAISS files in `.cursor/vecstore/`.
    ```bash
    python scripts/init_store.py
    ```

## Usage

### 1. Task Management (`scripts/tasks.py`)

The `tasks.py` script offers a CLI for task operations. Tasks are stored in `docs/TASKS.yaml` and auto-synced to the vector DB.

*   **Add a new task:**
    ```bash
    python scripts/tasks.py add "Build login page" --plan "Create HTML form;Implement API endpoint;Write tests"
    ```

*   **Start a task:**
    ```bash
    python scripts/tasks.py start <task_id>
    ```

*   **Update task progress:**
    ```bash
    python scripts/tasks.py bump <task_id> <delta_progress>
    # e.g.: python scripts/tasks.py bump 1 25
    ```

*   **Complete a task:**
    ```bash
    python scripts/tasks.py done <task_id>
    ```

*   **Delete a task:**
    ```bash
    python scripts/tasks.py delete <task_id>
    ```

*   **Add a note to a task:**
    ```bash
    python scripts/tasks.py note <task_id> "Discussed with designer; need mockup revisions."
    ```

*   **List tasks:**
    ```bash
    python scripts/tasks.py list
    python scripts/tasks.py list --status in_progress   # Only in-progress tasks
    python scripts/tasks.py list --details             # Show plan & notes
    ```

### 2. Adding Memory Entries

*   **Add an arbitrary note/fact (`scripts/add_memory.py`):**
    ```bash
    python scripts/add_memory.py "The key auth API is at /auth/v1"
    python scripts/add_memory.py "Using PostgreSQL version 15" --type fact --id db_version_note
    ```

*   **Add a code snippet (`scripts/add_snippet.py`):**
    *   From a string:
        ```bash
        python scripts/add_snippet.py "def hello():\n  print('world')" --lang py
        ```
    *   From a file (or part of it):
        ```bash
        python scripts/add_snippet.py --from src/utils/helpers.py:10-25  # Lines 10–25
        python scripts/add_snippet.py --from src/config.py             # Entire file
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
python scripts/gen_memory_mdc.py
```

**Tip:** Configure a Git pre-commit hook to run this script automatically so `memory.mdc` stays up to date.

Example pre-commit hook (`.git/hooks/pre-commit`):

```bash
#!/bin/sh
echo "Generating memory.mdc..."
# Ensure virtualenv is active or python is available
# source .venv/bin/activate # if needed
python scripts/gen_memory_mdc.py
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

  * `max_tokens`: Max tokens for `memory.mdc`.
  * `top_k_tasks`: Number of active tasks to include.
  * `top_k_snippets`: Number of relevant snippets to include.

* `[tasks]`

  * `file`: Path to the tasks file (relative to project root).

* `[preferences]`

  * `file`: Path to the preferences file.

## Working with Cursor IDE

Once `.cursor/rules/memory.mdc` is generated, Cursor IDE will automatically pick it up. When interacting with the AI (e.g., writing code via Ctrl+K or chatting via Ctrl+L), the contents of `memory.mdc` are included in the context to help the AI provide more accurate, project-specific answers.

## Quick Start

```bash
# 0. Install (see above)
# python -m venv .venv && source .venv/bin/activate
# pip install -r requirements.txt

# 1. One-time project setup
python scripts/bootstrap_memory.py
python scripts/init_store.py  # Ensure vecstore is created

# 2. Add your first task
python scripts/tasks.py add "Set up initial documentation" --plan "Write README;Describe installation;Add usage examples"

# 3. (Optional) Add a snippet from an existing file
# Suppose you have src/main.py
# mkdir -p src && echo -e "def main():\n    print('Hello from main')\n\nif __name__ == '__main__':\n    main()" > src/main.py
python scripts/add_snippet.py --from src/main.py:1-2  # Adds the first two lines

# 4. Generate Cursor context file
python scripts/gen_memory_mdc.py

# 5. Open the project in Cursor IDE
#    Ensure .cursor/rules/memory.mdc is visible and in use.
```

## Roadmap (v1.1+)

* **Cursor Task Panel:** Interactive task management panel directly in the IDE.
* **Auto Snippet Addition:** Cursor plugin/extension to add snippets via selection and command.
* **Increased Test Coverage:** Aim for ≥ 80% code coverage.
* **Encrypted Vecstore:** Enhanced security for corporate environments.
* **Smarter Snippet Selection:** Context-aware snippet inclusion based on the open file or recent activity.

## Contributing

Suggestions, bug reports, and pull requests are welcome!

## License

\[Specify your license here, e.g., MIT, Apache 2.0]

```