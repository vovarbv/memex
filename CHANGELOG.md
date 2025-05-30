# Memex Changelog

## [Unreleased]

### Security
- **CRITICAL**: Fixed remote code execution vulnerability in search_tab.py by replacing `eval()` with a safe expression evaluator
  - Added new `safe_eval.py` module that restricts expressions to safe operations only
  - Allowed operations include: comparisons, boolean logic, string methods, and safe built-ins
  - Blocked dangerous operations: imports, exec/eval, file operations, and attribute manipulation
  - Added expression validation UI to help users write correct filter expressions
  - Added comprehensive test suite for the safe evaluator

- **CRITICAL**: Fixed race conditions in vector store operations that could lead to data corruption
  - Added `thread_safe_store.py` module with thread-safe wrappers for all vector store operations
  - Implemented both thread locks (for in-process safety) and file locks (for multi-process safety)
  - Added atomic file operations for metadata writes
  - Includes retry logic and proper error handling
  - Added comprehensive test suite for concurrent operations

- **CRITICAL**: Fixed memory leak in IndexManager that could lead to memory exhaustion
  - Created `memory_bounded_index_manager.py` with automatic cache eviction
  - Implemented memory limits (default 500MB) and TTL-based eviction (default 1 hour)
  - Added LRU eviction when memory limit is reached
  - Includes memory usage monitoring and garbage collection triggers
  - Background thread periodically checks and evicts stale entries

### Added
- Expression validation button in the Search tab's advanced filter section
- Help text explaining which operations are allowed in custom filters
- Thread-safe wrappers for all vector store operations
- Lock statistics tracking for monitoring concurrent access
- Migration script `migrate_to_thread_safe.py` to update existing code
- `filelock` dependency for cross-process synchronization
- Memory-bounded IndexManager with automatic cache eviction
- Cache statistics and monitoring capabilities
- Configurable memory limits and TTL for cached indices
- `psutil` dependency for memory monitoring

### Changed
- Custom filter expressions now use a safe Python subset instead of full Python
- Updated placeholder text and labels to reflect the safe expression syntax
- Vector store operations now use thread-safe wrappers by default