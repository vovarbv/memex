# Thread Safety in Memex

## Overview

The Memex vector store now includes comprehensive thread safety measures to prevent data corruption and race conditions when multiple threads or processes access the store simultaneously.

## Why Thread Safety Matters

Without proper synchronization, concurrent operations can lead to:
- **Data Corruption**: Partial writes or inconsistent state
- **Lost Updates**: One thread's changes overwriting another's
- **Index Inconsistency**: FAISS index and metadata getting out of sync
- **Crashes**: Accessing data structures in an invalid state

## Implementation

### Two-Level Locking

The thread-safe implementation uses two levels of locking:

1. **Thread Locks (threading.RLock)**: For synchronization within a single process
2. **File Locks (filelock.FileLock)**: For synchronization across multiple processes

### Lock Types

- **Read Lock**: Used for operations that only read data (search, count)
  - Multiple readers can hold the lock simultaneously (in theory)
  - Readers wait if a writer holds the lock

- **Write Lock**: Used for operations that modify data (add, update, delete)
  - Only one writer can hold the lock at a time
  - Writers wait for all readers and other writers

### Atomic File Operations

Metadata files are written atomically to prevent corruption:
1. Write to a temporary file
2. Atomically rename to the target file
3. Clean up on failure

## Usage

### Importing Thread-Safe Functions

Instead of importing from `memory_utils`, import from `thread_safe_store`:

```python
# OLD (not thread-safe)
from memory_utils import add_or_replace, search, delete_vector

# NEW (thread-safe)
from thread_safe_store import add_or_replace, search, delete_vector
```

### Available Thread-Safe Functions

All major vector store operations have thread-safe versions:

```python
# Adding/updating vectors
result = add_or_replace(id="doc_123", text="Document content", metadata={"type": "document"})

# Searching
results = search(query="python programming", top_k=10)

# Deleting
success = delete_vector(id="doc_123")

# Counting items
count = count_items(pred=lambda x: x.get("type") == "document")

# Bulk deletion
deleted, failed, total = delete_vectors_by_filter(pred=lambda x: x.get("status") == "archived")
```

### Lock Statistics

Monitor lock usage and performance:

```python
from thread_safe_store import get_lock_stats

stats = get_lock_stats()
print(f"Read operations: {stats['read_operations']}")
print(f"Write operations: {stats['write_operations']}")
print(f"Lock acquisitions: {stats['lock_acquisitions']}")
print(f"Average wait time: {stats['lock_wait_time'] / stats['lock_acquisitions']:.3f}s")
```

## Migration

To migrate existing code to use thread-safe operations:

```bash
# Dry run to see what would change
python scripts/migrate_to_thread_safe.py --dry-run

# Apply the migration
python scripts/migrate_to_thread_safe.py
```

## Best Practices

### 1. Always Use Thread-Safe Wrappers
Never directly import from `memory_utils` for operations that modify or read the vector store.

### 2. Keep Lock Duration Short
Don't perform long-running operations while holding a lock:

```python
# BAD: Long operation inside lock
def process_documents(docs):
    for doc in docs:
        content = fetch_from_api(doc.url)  # Slow network call
        add_or_replace(doc.id, content, doc.metadata)  # Inside lock!

# GOOD: Prepare data outside lock
def process_documents(docs):
    # Fetch all content first
    doc_data = []
    for doc in docs:
        content = fetch_from_api(doc.url)
        doc_data.append((doc.id, content, doc.metadata))
    
    # Then add to store quickly
    for id, content, metadata in doc_data:
        add_or_replace(id, content, metadata)
```

### 3. Handle Lock Timeouts
Operations may timeout if they can't acquire a lock:

```python
from thread_safe_store import add_or_replace

try:
    result = add_or_replace(id, text, metadata)
except TimeoutError:
    print("Could not acquire lock - vector store may be busy")
    # Retry logic or error handling
```

### 4. Batch Operations When Possible
Reduce lock contention by batching related operations:

```python
# Instead of many individual deletes
for id in ids_to_delete:
    delete_vector(id)  # Each acquires a lock

# Use a filter for bulk deletion
delete_vectors_by_filter(lambda x: x.get("id") in ids_to_delete)  # One lock acquisition
```

## Performance Considerations

### Lock Overhead
Thread-safe operations have a small overhead due to lock acquisition. In most cases, this is negligible compared to the actual operation time.

### Concurrent Reads
Multiple threads can search simultaneously without blocking each other (in theory, implementation uses RLock which may serialize).

### Write Serialization
Write operations are serialized - only one write can happen at a time. This ensures consistency but may impact throughput in write-heavy workloads.

## Debugging

### Lock Contention
If operations are slow, check for lock contention:

```python
import time
from thread_safe_store import search, get_lock_stats

start_stats = get_lock_stats()
start_time = time.time()

# Perform operations
results = search("test query")

elapsed = time.time() - start_time
end_stats = get_lock_stats()

wait_time = end_stats['lock_wait_time'] - start_stats['lock_wait_time']
print(f"Operation took {elapsed:.3f}s, waited {wait_time:.3f}s for lock")
```

### Deadlock Prevention
The implementation uses reentrant locks (RLock) to prevent deadlocks when the same thread needs to acquire the lock multiple times.

## Testing Concurrent Access

Test your application with concurrent access:

```python
import concurrent.futures
from thread_safe_store import add_or_replace, search

def stress_test():
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        # Mix of reads and writes
        futures = []
        
        # Writers
        for i in range(100):
            future = executor.submit(add_or_replace, f"item_{i}", f"content_{i}", {"id": i})
            futures.append(future)
        
        # Readers
        for i in range(200):
            future = executor.submit(search, f"content_{i % 100}", top_k=5)
            futures.append(future)
        
        # Wait for completion
        concurrent.futures.wait(futures)
        
        print("Stress test completed successfully")

stress_test()
```

## Limitations

1. **Not Distributed**: The file lock only works on the same filesystem. For distributed systems, use a distributed lock manager.

2. **Lock Timeout**: Operations timeout after 30 seconds of waiting for a lock. Adjust if needed for your use case.

3. **No Read Parallelism**: Current implementation uses RLock which doesn't distinguish between readers and writers. True read parallelism would require a ReadWriteLock implementation.

4. **Performance Impact**: Heavy write workloads may see reduced throughput due to serialization.