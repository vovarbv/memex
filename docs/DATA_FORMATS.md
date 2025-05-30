# Data Formats and Structures

This document describes the data structures used in the Memex project, particularly the YAML files and their respective fields.

## `Task` Data Structure

Tasks in Memex are represented by the `Task` dataclass in `task_store.py` and stored in `docs/TASKS.yaml`. Each task has the following fields:

### Core Fields

| Field | Type | Description | Default |
|-------|------|-------------|---------|
| `id` | `int` | Unique identifier for the task | Auto-generated |
| `title` | `str` | Brief description of the task | Required |
| `status` | `str` | Current state of the task | `"todo"` |
| `progress` | `int` | Percentage complete (0-100) | `0` |
| `plan` | `List[str]` | List of steps to complete the task | `[]` |
| `done_steps` | `List[str]` | List of completed steps from the plan | `[]` |
| `notes` | `List[str]` | List of notes about the task | `[]` |
| `created_at` | `str` | ISO 8601 timestamp of task creation | Current time |
| `updated_at` | `str` | ISO 8601 timestamp of last update | Current time |

### Extended Fields

The following fields were added to support better task management:

| Field | Type | Description | Default |
|-------|------|-------------|---------|
| `priority` | `str` | Task priority level | `None` |
| `tags` | `List[str]` | List of tags for categorizing tasks | `[]` |

### Example Task

```yaml
- id: 1
  title: Implement login page
  status: in_progress
  progress: 45
  plan:
    - Create login form HTML
    - Style form with CSS
    - Implement form validation
    - Connect to authentication API
  done_steps:
    - Create login form HTML
    - Style form with CSS
  notes:
    - Need to handle error messages gracefully
    - Auth API uses JWT tokens
  priority: high
  tags:
    - frontend
    - auth
  created_at: '2024-02-15T12:34:56.789012+00:00'
  updated_at: '2024-02-16T09:45:23.456789+00:00'
```

## Field Usage Guidelines

### Status Values

The `status` field accepts the following values:
- `todo`: Task is planned but not started
- `in_progress`: Task is actively being worked on
- `done`: Task is completed
- `blocked`: Task is blocked by external factors
- `deferred`: Task is postponed for later
- `pending`: Task is waiting for review or other action

### Priority Values

The `priority` field accepts the following values:
- `high`: Task is urgent or critical
- `medium`: Task is important but not urgent
- `low`: Task is neither urgent nor critical

### Tags

Tags can be any string values that help categorize tasks. Common examples include:
- Technology areas (`frontend`, `backend`, `database`)
- Project phases (`planning`, `implementation`, `testing`)
- Feature areas (`auth`, `payments`, `user-management`)

## Custom Fields Handling

If you add custom fields to tasks in the YAML file that are not defined in the `Task` dataclass:

1. Fields defined in the `Task` dataclass will be preserved during load/save operations.
2. Custom fields not defined in the dataclass will be **lost** when the task is loaded and saved through the `TaskStore` interface.

To add custom fields permanently:
1. Modify the `Task` dataclass in `task_store.py`
2. Add the field with appropriate type and default value
3. Update the `to_dict()` and `from_dict()` methods to include the new field

This ensures your custom fields persist across all operations.

## Free-Text Task Input Syntax

Memex supports a natural language-like syntax for quickly adding tasks through a single text input. This provides a more intuitive and faster way to create tasks compared to filling out multiple form fields.

### Basic Syntax Rules

1. **First line is always the task title** (required)
2. **Keywords are followed by a colon** and then the value for that field
3. **Multiple values can be separated by semicolons or newlines**
4. **Any text after all recognized keywords is treated as notes**

### Supported Keywords

| Keyword | Description | Format | Example |
|---------|-------------|--------|---------|
| `plan:` | Steps to complete the task | Semicolon-separated list, numbered list, or newline-separated | `plan: Step 1; Step 2; Step 3` |
| `status:` | Task status | Any variation of: todo, in_progress, done, pending, blocked, deferred | `status: in_progress` |
| `progress:` | Completion percentage | Number from 0-100 with optional % sign | `progress: 25%` |
| `priority:` | Priority level | One of: high, medium, low (or abbreviations) | `priority: high` |
| `tags:` | Task categories | Space or comma-separated list, can use hashtags or quotes | `tags: #frontend #ui` |
| `notes:` | Additional notes | Free text, can span multiple lines | `notes: Remember to check browser compatibility` |

### Enhanced Parsing Features

#### Flexible Plan Formats
The parser now supports multiple formats for specifying plans:

* **Semicolon-separated:** `plan: Step 1; Step 2; Step 3`
* **Numbered list:** `plan: 1. First step 2. Second step 3. Third step`
* **Newline-separated:** 
  ```
  plan: Design UI layout
  Implement components
  Add event handlers
  ```

#### Flexible Status Values
Status values are normalized automatically, so various formats are supported:

* **Different separators:** `in-progress`, `in_progress`, `in progress`
* **Common synonyms:**  
  * `todo`: `to-do`, `to do`, `not started`
  * `in_progress`: `wip`, `started`, `working`
  * `done`: `completed`, `finished`
  * `pending`: `on hold`, `waiting`
  * `blocked`: `stuck`
  * `deferred`: `postponed`
* **Case insensitivity:** `STATUS: Done` is recognized the same as `status: done`

#### Priority Abbreviations
Priority values can be abbreviated:

* `high`: `h`, `hi`, `important`, `urgent`, `critical`
* `medium`: `m`, `med`, `normal`, `moderate`
* `low`: `l`, `lo`, `minor`

#### Smart Progress Parsing
Progress values are flexible and automatically normalized:

* **Percentage sign:** Both `33%` and `33` are recognized as 33%
* **Decimal values:** `33.3%` is rounded to 33%
* **Range limiting:** Values outside the 0-100 range are clamped

#### Rich Tag Handling
Tags can be specified in multiple formats:

* **Hashtag style:** `tags: #frontend #backend #api`
* **Comma-separated:** `tags: frontend, backend, api`
* **Quoted multi-word tags:** `tags: "user authentication" api "error handling"`

### Example Input

```
Implement login form validation
plan: Create validation rules; Write validation functions; Add error messages; Test edge cases
status: in-progress
progress: 35%
priority: high
tags: #frontend, #auth, "form validation"
notes: Use client-side validation first, then add server-side validation. 
Reference the design specs for error message styling.
```

### Preview Feature

In the UI, you can use the "Preview Task" button to see how your free-text input will be parsed before saving. This helps ensure your task will be created with the exact properties you intended.

### Test Cases

The parser is thoroughly tested against various input formats to ensure reliable parsing. If you encounter any parsing issues, please report them with your input example.

## Code Chunking Strategy

Memex supports indexing the codebase into the FAISS vector store for semantic search capabilities. The code and content files are broken down into manageable chunks for embedding.

### Chunking Methods by File Type

| File Type | Chunking Strategy | Description |
|-----------|-------------------|-------------|
| Python (`.py`) | Function/Class Level | Uses the `ast` module to parse Python files and chunk them by functions and classes. Each function or class becomes an individual chunk. |
| Markdown (`.md`) | Section Level | Chunks by headings (e.g., `# Section`, `## Subsection`) or by paragraphs if no clear section structure exists. |
| Other Text (`.txt`, `.json`, `.yaml`, etc.) | Fixed-Size Overlapping | Chunks by fixed-size overlapping text segments (e.g., 200-300 words or ~1000 characters, with 20-30 words overlap). |

### Chunk Metadata Structure

Each chunk stored in the FAISS vector store includes the following metadata:

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `id` | `str` | Deterministic ID based on file path and content identifier | `"memex/scripts/tasks.py:function:create_task"` |
| `type` | `str` | Type of the chunk | `"code_chunk"`, `"markdown_section"`, `"text_chunk"` |
| `source_file` | `str` | Path to the source file | `"memex/scripts/tasks.py"` |
| `language` | `str` | Programming or markup language | `"python"`, `"markdown"`, `"plaintext"` |
| `start_line` | `int` | Starting line in the source file | `42` |
| `end_line` | `int` | Ending line in the source file | `78` |
| `name` | `str` | Name of the function, class, or section (if applicable) | `"create_task"`, `"## Installation"` |
| `content` | `str` | Raw content of the chunk | The actual code or text snippet |

### Example Chunks

#### Python Function Chunk
```json
{
  "id": "memex/scripts/tasks.py:function:create_task",
  "type": "code_chunk",
  "source_file": "memex/scripts/tasks.py",
  "language": "python",
  "start_line": 42,
  "end_line": 78,
  "name": "create_task",
  "content": "def create_task(title, plan=None, status='todo'):\n    \"\"\"Create a new task with the given title and plan.\"\"\"\n    # Function implementation...\n    return task"
}
```

#### Markdown Section Chunk
```json
{
  "id": "memex/README.md:section:installation",
  "type": "markdown_section",
  "source_file": "memex/README.md",
  "language": "markdown",
  "start_line": 24,
  "end_line": 35,
  "name": "## Installation",
  "content": "## Installation\n\nTo install Memex, run:\n\n```bash\npip install -r requirements.txt\n```"
}
```

#### Text Chunk
```json
{
  "id": "memex/docs/example.txt:chunk:0",
  "type": "text_chunk",
  "source_file": "memex/docs/example.txt",
  "language": "plaintext",
  "start_line": 1,
  "end_line": 15,
  "name": null,
  "content": "This is an example of a plain text file that will be chunked into fixed-size segments for indexing..."
}
```

### Usage in `memory.mdc` Generation

When generating the `memory.mdc` file, these code chunks are retrieved from the FAISS store based on semantic relevance to the current context. The system uses two primary modes for determining this relevance:

1. **Task-Driven Context Retrieval (Default):** When no explicit focus query is provided, the system automatically derives a context query from your active tasks. It extracts key information from task titles and pending steps to identify and retrieve the most relevant code chunks, notes, and snippets from your project memory.

2. **Focus-Based Context Retrieval:** When an explicit `--focus` query is provided, it overrides the task-driven approach and retrieves context based solely on that query.

This ensures that the AI has access to the most relevant parts of the codebase when working on specific tasks, even without you having to specify a focus query manually. The task-driven approach keeps the context aligned with your current work priorities.

## Vector Store Metadata Structure

The Memex system stores all memory items (tasks, snippets, notes, code chunks) in a FAISS vector database with associated metadata. Understanding the metadata structure is crucial for troubleshooting and data integrity.

### Metadata Storage in `metadata.json`

When loaded into the `meta` object by `memory_utils.py`, the `metadata.json` file has the following structure:

1. **Item Metadata Storage:**
   - Each memory item's metadata is stored using its **custom string ID** as the key
   - Format: `meta[custom_id_str] = item_metadata_dict`
   - Example: `meta["note_abc123"] = {"id": "note_abc123", "type": "note", "text": "...", ...}`

2. **ID Mapping Tables:**
   - `_custom_to_faiss_id_map_`: Maps custom string IDs to FAISS integer IDs
   - `_faiss_id_to_custom_id_map_`: Maps FAISS integer IDs back to custom string IDs
   - These are internal system structures for managing the relationship between user-friendly IDs and FAISS's numeric indexing

### Correct Metadata Format Example

```json
{
  "_custom_to_faiss_id_map_": {
    "note_important": 101,
    "task_login": 102,
    "snippet_validation": 103
  },
  "_faiss_id_to_custom_id_map_": {
    "101": "note_important",
    "102": "task_login", 
    "103": "snippet_validation"
  },
  "note_important": {
    "id": "note_important",
    "type": "note",
    "text": "Remember to use HTTPS for all API calls",
    "timestamp": "2024-01-15T10:30:00"
  },
  "task_login": {
    "id": "task_login",
    "type": "task",
    "title": "Implement user login",
    "status": "in_progress"
  },
  "snippet_validation": {
    "id": "snippet_validation",
    "type": "snippet",
    "text": "def validate_email(email): return '@' in email",
    "language": "python"
  }
}
```

### Old (Incorrect) Metadata Format

In older versions, metadata was incorrectly keyed by FAISS IDs instead of custom IDs:

```json
{
  "_custom_to_faiss_id_map_": {
    "note_important": 101,
    "task_login": 102
  },
  "101": {
    "id": "note_important",
    "type": "note",
    "text": "..."
  },
  "102": {
    "id": "task_login", 
    "type": "task",
    "title": "..."
  }
}
```

This old format causes the Memory tab to show no items because the search function looks for metadata under custom ID keys, not FAISS ID keys.

### Troubleshooting Metadata Issues

If the Memory tab shows no items despite having data:

1. **Run Health Check:**
   ```bash
   python scripts/check_store_health.py
   ```
   This will detect if metadata is using the old keying format.

2. **Migrate Old Format:**
   ```bash
   python scripts/migrate_faiss_keyed_metadata.py --dry-run  # Preview changes
   python scripts/migrate_faiss_keyed_metadata.py           # Perform migration
   ```

3. **Verify Fix:**
   ```bash
   python scripts/check_store_health.py
   ```
   After migration, the health check should report no keying issues.

### Data Integrity Requirements

For proper functioning:
- Each item in `_custom_to_faiss_id_map_` must have corresponding metadata under `meta[custom_id]`
- Each item should NOT have metadata under `meta[str(faiss_id)]` (old format)
- The `id` field within each item's metadata should match its custom ID key
- All FAISS IDs in the mapping tables should have corresponding vectors in the FAISS index 