Okay, Senior Developer! Based on the project's current state, here's a set of tasks for our AI programmer to prepare Memex for its first robust push. The focus is on stability, code quality, testing, and ensuring core features work as intended.

## Memex "First Push" Polish Tasks:

### Category 1: Code Quality & Refactoring

1.  **Standardize Import System:**
    *   **Goal:** Ensure consistent and robust import mechanisms across the project, reflecting its package structure.
    *   **Affected Files:** All `.py` files in `scripts/`, `ui/`, and `tests/`. Pay special attention to `memex_cli.py`, `shared_utils.py`, and individual script/test files that might use `sys.path` manipulations.
    *   **Sub-tasks:**
        *   Audit all Python files for current import styles.
        *   Prioritize using package-relative imports (e.g., `from ..scripts import module_name`) or absolute imports from the `memex` top-level package (e.g., `from memex.scripts import module_name`) where `pip install -e .` makes `memex` available.
        *   Refactor or remove usages of `shared_utils.try_import_with_prefix` if simpler, direct imports can be achieved through consistent package structure.
        *   Eliminate `sys.path.insert(0, ...)` calls in scripts and tests. Tests should run correctly via `pytest` (which handles paths) or `python -m pytest`. Scripts should be runnable as modules or via `memex_cli.py`.
        *   Update `scripts/__init__.py` and `ui/__init__.py` if necessary to correctly define package exports.

2.  **Consolidate Path Handling Logic:**
    *   **Goal:** Ensure all file paths are resolved consistently and robustly, considering standalone vs. subdirectory deployment.
    *   **Affected Files:** `memory_utils.py`, `memory.toml`, `bootstrap_memory.py`, `index_codebase.py`, `gen_memory_mdc.py`, UI tabs interacting with files (e.g., `preferences_tab.py`, `settings_tab.py`).
    *   **Sub-tasks:**
        *   Verify that `memory_utils.ROOT` (memex directory) and path-generating functions (e.g., `get_vec_dir`, `get_tasks_file_path`) are the single source of truth for critical paths.
        *   Ensure all file operations correctly use these resolved paths.
        *   Confirm that `bootstrap_memory.py` correctly sets up `[files].include` and `[system]` paths in `memory.toml` for both standalone and subdirectory scenarios. The use of `rel_prefix = os.path.relpath(HOST_PROJECT_ROOT_FOR_SCAN, ROOT)` seems correct but should be verified in action.
        *   Check that `index_codebase.py` correctly interprets `files.include` patterns relative to the `HOST_PROJECT_ROOT_FOR_SCAN` when `../` is used.

3.  **Enhance Error Handling & Logging:**
    *   **Goal:** Improve robustness and provide clearer feedback to users and developers.
    *   **Affected Files:** Core scripts (`memory_utils.py`, `task_store.py`, `tasks.py`, `index_codebase.py`, etc.) and all UI tab files (`ui/*.py`).
    *   **Sub-tasks:**
        *   Review critical functions for `try...except` blocks. Ensure specific exceptions are caught where possible.
        *   Use Python's `logging` module consistently. Remove `print()` statements used for debugging/logging in backend scripts; use `logging.debug()`, `logging.info()`, etc.
        *   In UI tabs, ensure backend errors are caught and displayed to the user gracefully (e.g., via `gr.Warning`, `gr.Error`, or updating a status `gr.Markdown` component) instead of raw tracebacks. Leverage `shared_utils.format_error_message`.
        *   Verify `TaskStore` gracefully handles `DuplicateTaskIDError` and other YAML parsing issues, as hinted in `ui/main_app.py`.

4.  **Refactor Ad-hoc Debugging Scripts:**
    *   **Goal:** Integrate useful testing logic into the formal test suite or remove obsolete scripts.
    *   **Affected Files:** `debug_memory_display.py`, `test_memory_fix.py`, `test_search_debug.py`, `test_search_detailed.py`.
    *   **Sub-tasks:**
        *   Analyze each script. If it performs unique checks not covered by existing `pytest` tests (especially regarding vector store content, ID mapping, and search result consistency), adapt its logic into new `pytest` test cases within an appropriate `tests/test_*.py` file.
        *   If a script's functionality is now fully covered by other tests (e.g., `test_memory_utils.py`'s `test_search_empty_query_retrieves_all_correctly_keyed_items`) or UI features, remove the script.

### Category 2: Testing & Validation

1.  **Improve Test Coverage for Core Modules:**
    *   **Goal:** Ensure critical backend components are thoroughly tested.
    *   **Affected Files:** `tests/test_memory_utils.py`, `tests/test_task_store.py`, `tests/test_memory_bounded_index_manager.py`, `tests/test_thread_safe_store.py`, `tests/test_safe_eval.py`.
    *   **Sub-tasks:**
        *   **`memory_utils.py`**: Verify tests for `add_or_replace` with different ID types, `delete_vectors_by_filter`, `search` (especially empty query, predicates, offset), `count_items`, and correct metadata keying (custom ID vs. FAISS ID). Ensure `check_vector_store_integrity` is robustly tested for various scenarios (e.g., mismatched IDs, orphaned data, old metadata format).
        *   **`task_store.py`**: Augment `test_task_store.py` to cover: handling of `TASKS.yaml` with duplicate IDs (should raise `DuplicateTaskIDError`), edge cases in `next_id` calculation, behavior with empty or non-existent `TASKS.yaml`.
        *   **`memory_bounded_index_manager.py`**: Review `test_memory_bounded_index_manager.py`. Ensure tests rigorously check TTL and memory limit-based eviction, especially LRU logic. Test statistics reporting.
        *   **`thread_safe_store.py`**: Review `test_thread_safe_store.py`. Ensure comprehensive testing of concurrent read/write operations and lock statistics.
        *   **`safe_eval.py`**: Review `test_safe_eval.py`. Ensure it covers all allowed and explicitly disallowed operations.

2.  **Enhance Tests for Script Logic & CLI Tools:**
    *   **Goal:** Validate the core logic of user-facing scripts.
    *   **Affected Files:** `tests/test_tasks.py`, `tests/test_gen_memory_mdc.py`, `tests/test_code_indexer.py`, `tests/test_add_snippet.py`, `tests/test_add_memory.py`, `tests/test_bootstrap_memory.py`, `tests/test_check_store_health.py`.
    *   **Sub-tasks:**
        *   **`tasks.py`**: `test_tasks.py` uses `*_logic` functions. Ensure these tests fully cover interactions with `TaskStore` and that FAISS sync/delete calls (`sync_task_vector`, `delete_task_vector`) are correctly triggered (mocking `add_or_replace` and `delete_vector` from `thread_safe_store`).
        *   **`gen_memory_mdc.py`**: `test_gen_memory_mdc.py` should verify:
            *   Correct formulation of `_formulate_query_from_active_tasks`.
            *   Accurate token counting and enforcement of `max_tokens`.
            *   Proper inclusion and formatting of tasks, preferences, snippets, notes, and code chunks.
            *   Correct behavior of `--focus` query, overriding task-driven context.
        *   **`code_indexer_utils.py` & `index_codebase.py`**: `test_code_indexer.py` should:
            *   Test `find_files_to_index` with various include/exclude patterns (mock `os.walk`).
            *   Test each file chunker (`chunk_python_file`, `chunk_markdown_file`, `chunk_text_file`) with diverse file content and edge cases (empty files, very large files, files with unusual syntax).
            *   Verify correct metadata generation for chunks (ID, source_file, language, line numbers, name).
        *   **`add_snippet.py` & `add_memory.py`**: Tests like `test_add_snippet.py` and `test_add_memory.py` should ensure items are added with correct metadata (`type`, `id`, `timestamp`, etc.) and are searchable.
        *   **`bootstrap_memory.py`**: `test_bootstrap_memory.py` needs to simulate different project structures (standalone, memex as subdir) and verify `memory.toml` generation, especially `files.include` and `system.*_relative_to_memex_root` paths.
        *   **`check_store_health.py`**: `test_check_store_health.py` should create mock FAISS/metadata states representing various issues (old format, missing vectors, orphaned metadata) and assert that the script detects them correctly.

3.  **Verify Migration Script Tests:**
    *   **Goal:** Ensure data migration scripts are reliable.
    *   **Affected Files:** `tests/test_migrate_faiss_keyed_metadata.py`, (Consider adding tests for `scripts/migrate_to_thread_safe.py`).
    *   **Sub-tasks:**
        *   Confirm `test_migrate_faiss_keyed_metadata.py` robustly tests migration from old FAISS ID-keyed metadata to new custom ID-keyed metadata, including dry-run and actual migration.
        *   Create tests for `scripts/migrate_to_thread_safe.py` to ensure it correctly identifies and replaces `memory_utils` imports with `thread_safe_store` imports for the specified functions, handling various import styles (e.g., `from .memory_utils import X`, `import memory_utils`, aliased imports).

### Category 3: Configuration and Setup

1.  **Review `memory.toml` Defaults and Structure:**
    *   **Goal:** Ensure `memory.toml` is clear, and defaults are sensible.
    *   **Affected Files:** `memory.toml`, `memory_utils.DEFAULT_BOOTSTRAP_CFG_STRUCTURE`, `bootstrap_memory.py`.
    *   **Sub-tasks:**
        *   Review `DEFAULT_BOOTSTRAP_CFG_STRUCTURE` in `memory_utils.py` to ensure it's a comprehensive template for a new `memory.toml`.
        *   Check the default `exclude` patterns in `memory.toml` and `bootstrap_memory.py` for completeness (e.g., common build artifacts, OS-specific files). The current list in `memory.toml` is quite extensive and looks good.
        *   Verify that `bootstrap_memory.py` correctly merges existing `memory.toml` settings with defaults when updating.

2.  **Standardize Script Launchers & Setup:**
    *   **Goal:** Ensure a consistent and clear way to run Memex scripts and set up the project.
    *   **Affected Files:** `memex_cli.py`, `memex.py`, `memex.sh`, `memex.bat`, `quickstart.py`, `Makefile`, `setup.py`, `README.md`, `LAUNCH_GUIDE.md`.
    *   **Sub-tasks:**
        *   Confirm `memex_cli.py` is the central dispatcher for all commands. The other launchers (`memex.py`, `.sh`, `.bat`) should simply delegate to it.
        *   Update `setup.py`'s `console_scripts` to ensure all primary user-facing scripts are exposed as commands after `pip install -e .`.
        *   Review `quickstart.py` for simplicity and correctness. It should reliably set up a basic working Memex instance.
        *   Ensure `Makefile` commands correctly invoke `memex_cli.py`.
        *   Update `README.md` and `LAUNCH_GUIDE.md` to reflect the standardized way of running commands, prioritizing `memex_cli.py` or the wrappers.

3.  **Refine `.gitignore`:**
    *   **Goal:** Ensure all generated and local-only files are ignored.
    *   **Affected Files:** `.gitignore`.
    *   **Sub-tasks:**
        *   Verify that test-generated temporary files (e.g., from `tmp_path` in `pytest`) and fixture-related temporary files are covered.
        *   Ensure `.cursor/vecstore/` and `.cursor/rules/memory.mdc` are in `.gitignore` as they are generated. (Current `.gitignore` has this).
        *   Confirm `docs/.task_id_counter` is in `.gitignore` if it's still being generated (though it might be obsolete).

### Category 4: Documentation

1.  **Update Core System Documentation:**
    *   **Goal:** Ensure technical documentation accurately reflects the current system.
    *   **Affected Files:** `docs/DATA_FORMATS.md`, `docs/TASK_PARSER.md`, `docs/CLAUDE.md`, `docs/MEMORY_MANAGEMENT.md`, `docs/THREAD_SAFETY.md`, `docs/UI_UX_ROADMAP.md`.
    *   **Sub-tasks:**
        *   **`DATA_FORMATS.md`**: Ensure it accurately describes the `Task` dataclass fields, and the metadata structure for snippets, notes, and especially `code_chunk`s (including `id`, `type`, `source_file`, `language`, `start_line`, `end_line`, `name`, `content`). Emphasize that item metadata is keyed by custom string IDs in `metadata.json`.
        *   **`TASK_PARSER.md`**: Verify against `scripts/tasks.py`'s `parse_free_text_task` for accuracy of supported keywords and formats.
        *   **`docs/CLAUDE.md`**: Review for overall accuracy of system description, data flow, and components. Remove mention of `docs/.task_id_counter` if it's truly obsolete.
        *   **`MEMORY_MANAGEMENT.md` & `THREAD_SAFETY.md`**: Update to accurately describe the `MemoryBoundedIndexManager` and `ThreadSafeStore` implementations, their configuration, and usage.
        *   **`UI_UX_ROADMAP.md`**: This document states "All major UI components are implemented and functional." Re-title it to something like "UI/UX Current State & Future Vision" to reflect its nature as a snapshot and potential future ideas, rather than an active roadmap for unimplemented core features.

2.  **Align User-Facing Documentation:**
    *   **Goal:** Ensure `README.md` and `LAUNCH_GUIDE.md` are accurate for new users.
    *   **Sub-tasks:**
        *   Verify installation instructions, especially regarding `requirements.txt`.
        *   Ensure command examples for task management, indexing, MDC generation, etc., use the primary CLI (`memex_cli.py` or wrappers).
        *   Confirm descriptions of `memory.toml` sections are accurate.
        *   Update the "How It Works" and "Project Structure" sections in `README.md` if necessary.

3.  **Improve Code Documentation (Docstrings & Type Hints):**
    *   **Goal:** Enhance code readability and maintainability.
    *   **Affected Files:** All key Python modules in `scripts/` and `ui/`.
    *   **Sub-tasks:**
        *   Iterate through major functions and classes, adding or improving docstrings using a consistent style (e.g., Google style).
        *   Add or complete type hints for function signatures and important variables.

### Category 5: Stability and Final Checks

1.  **Resolve Memory Tab Display Issue (Final Verification):**
    *   **Goal:** Ensure the Memory tab reliably displays all relevant items.
    *   **Affected Files:** `ui/memory_tab.py`, `scripts/memory_utils.py` (search logic), `scripts/migrate_faiss_keyed_metadata.py`.
    *   **Sub-tasks:**
        *   Confirm that `memory_tab.py::search_memory_items` (when called with an empty query and default filters) correctly uses `memory_utils.search`.
        *   Verify `memory_utils.search` correctly handles empty queries by iterating over `meta.get("_custom_to_faiss_id_map_", {})` and retrieving metadata items using their *custom string IDs* as keys from the `meta` dictionary.
        *   Ensure that `add_or_replace` in `memory_utils.py` *always* stores item metadata in the main `meta` dictionary keyed by the *custom string ID*, not the FAISS integer ID. The `test_memory_utils.py` has `test_search_empty_query_retrieves_all_correctly_keyed_items` for this.
        *   Run `test_search_detailed.py` and `debug_memory_display.py` (or their pytest equivalents) to confirm behavior with actual data.

2.  **Task ID Generation Consistency:**
    *   **Goal:** Ensure task IDs are generated reliably by `TaskStore`.
    *   **Affected Files:** `scripts/task_store.py`, `scripts/tasks.py`.
    *   **Sub-tasks:**
        *   Confirm that `TaskStore.add_task` is the sole mechanism for assigning new task IDs and that it correctly finds the current max ID to determine the next one.
        *   Remove any usage or reliance on `docs/.task_id_counter` from all scripts. Delete the file if it's not used.

3.  **Final Review of `FLAWS_TO_FIX.md`:**
    *   **Goal:** Ensure all critical and high-priority flaws identified have been demonstrably fixed and tested.
    *   **Sub-tasks:**
        *   Verify `eval()` in `search_tab.py` is replaced with `safe_eval` and tested.
        *   Verify `thread_safe_store.py` is used for all vector store read/write operations from UI and scripts.
        *   Verify `MemoryBoundedIndexManager` is integrated and tested.

This set of tasks should bring the project to a much more polished and reliable state for its first push. Good luck to the AI programmer!