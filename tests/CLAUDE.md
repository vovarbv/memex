# Memex `tests/` Directory Overview for Claude

## Core Purpose

The `tests/` directory contains all automated tests for the Memex system. The primary goal is to ensure the reliability, correctness, and robustness of the backend scripts and core utility functions.

## Key Responsibilities

1.  **Unit Testing:** Testing individual functions and classes in isolation to verify their specific logic.
2.  **Integration Testing:** Testing the interaction between different modules and components of the Memex system (e.g., ensuring `TaskStore` correctly interacts with `memory_utils` for FAISS syncing).
3.  **Coverage:** Aiming for high test coverage across the `memex/scripts/` directory.
4.  **Bug Prevention:** Writing tests for reported bugs to prevent regressions.
5.  **Documentation by Example:** Tests often serve as a form of documentation, showing how modules are intended to be used.

## Test Structure and Naming Conventions

*   Test files should generally mirror the structure of the `scripts/` directory. For a module `memex/scripts/foo.py`, the corresponding test file should be `memex/tests/test_foo.py`.
*   Test functions should be prefixed with `test_` (e.g., `def test_my_function():`).
*   Test classes (if used, e.g., with `unittest.TestCase`) should be prefixed with `Test` (e.g., `class TestMyClass(unittest.TestCase):`).

## Key Test Files and Their Focus

*   **`test_memory_utils.py` / `test_memory_utils_integration.py` / `test_vector_store_id_handling.py`:**
    *   These files (or a consolidated version) should thoroughly test `memory_utils.py`.
    *   Focus on:
        *   FAISS index creation, loading, saving.
        *   `add_or_replace` and `delete_vector` logic, especially with custom string and numeric IDs.
        *   Correctness of `_custom_to_faiss_id_map_` and `_faiss_id_to_custom_id_map_`.
        *   `search()` functionality: empty queries, queries with predicates, top_k, offset.
        *   `check_vector_store_integrity()` for various valid and corrupted states.
        *   Embedding generation (can be mocked if model loading is slow for unit tests).
*   **`test_task_store.py`:**
    *   Tests the `TaskStore` class and `Task` dataclass from `task_store.py`.
    *   Focus on:
        *   Loading tasks from valid, empty, and malformed `TASKS.yaml` files.
        *   CRUD operations: `add_task`, `get_task_by_id`, `update_task`, `delete_task`.
        *   ID generation and handling (uniqueness).
        *   `complete_step` logic and its effect on task progress and status.
        *   Serialization (`to_dict`) and deserialization (`from_dict`).
*   **`test_free_text_parser.py`:**
    *   Tests the `parse_free_text_task` function from `tasks.py`.
    *   Should cover all syntax variations and edge cases described in `TASK_PARSER.md`.
*   **`test_code_indexer.py` (Example - currently missing, but should exist):**
    *   Tests `code_indexer_utils.py` and `index_codebase.py` logic.
    *   Focus on:
        *   Correct chunking of different file types (Python, Markdown, plain text).
        *   Handling of `min_lines`, `max_lines` for chunking.
        *   Correct generation of chunk IDs and metadata.
        *   `find_files_to_index` logic with various `include`/`exclude` patterns.
        *   `--reindex` functionality.
*   **`test_gen_memory_mdc.py` (Example - currently missing, but should exist):**
    *   Tests the logic in `gen_memory_mdc.py`.
    *   Focus on:
        *   Correct inclusion of preferences.
        *   Selection and formatting of active tasks.
        *   Query formulation from active tasks.
        *   Retrieval and formatting of context items (snippets, notes, code chunks).
        *   Enforcement of `max_tokens` limit.
        *   Handling of `--focus` queries.
*   **`test_add_snippet.py` / `test_snippet_note_indexing.py`:**
    *   Test `add_snippet_logic` and `add_memory_item_logic` to ensure snippets and notes are correctly added to FAISS with appropriate metadata and are searchable.
*   **`conftest.py`:**
    *   Contains pytest fixtures for setting up test environments (e.g., temporary directories, mock configurations, pre-populated `TaskStore` instances or FAISS indexes).

## Testing Framework and Practices

*   **Framework:** `pytest` is the primary testing framework.
*   **Mocking:** Use `pytest-mock` (or `unittest.mock`) to isolate units and mock external dependencies or slow operations (like model loading or actual FAISS writes for pure unit tests).
*   **Fixtures (`conftest.py`):** Utilize pytest fixtures to provide reusable setup and teardown for tests (e.g., creating temporary `memory.toml`, `TASKS.yaml`, or FAISS stores).
*   **Assertions:** Use clear and specific assertions (`assert result == expected`).
*   **Coverage:** Aim for high test coverage. Use `pytest-cov` to measure and report coverage.
*   **CI Integration:** Tests should be automatically run in a CI environment (e.g., GitHub Actions as defined in `.github/workflows/run-tests.yml`).
*   **Test Data:** Use small, well-defined sample data files in a `tests/fixtures/` subdirectory for tests that require file input.

## Goals for AI Programmer Working on Tests

*   **Increase Coverage:** Identify untested code paths and add tests for them.
*   **Improve Robustness:** Add tests for edge cases, invalid inputs, and error conditions.
*   **Refactor Existing Tests:** If tests are unclear, brittle, or inefficient, refactor them.
*   **Write New Tests:** When new features are added or existing ones modified in `scripts/`, corresponding tests must be added or updated.