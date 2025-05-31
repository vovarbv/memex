#!/usr/bin/env python
"""
Thread-safe wrapper for vector store operations.
This module provides thread-safe access to FAISS vector store operations
to prevent race conditions and data corruption in concurrent environments.
"""
from __future__ import annotations
import threading
import logging
import functools
import time
import os
from typing import Any, Callable, Dict, Optional, Tuple
from contextlib import contextmanager
import filelock
import pathlib

# Import the original memory_utils functions
try:
    from memory_utils import (
        add_or_replace as _add_or_replace,
        delete_vector as _delete_vector,
        delete_vectors_by_filter as _delete_vectors_by_filter,
        search as _search,
        count_items as _count_items,
        save_index as _save_index,
        load_index as _load_index,
        get_vec_dir,
        load_cfg
    )
except ImportError:
    from .memory_utils import (
        add_or_replace as _add_or_replace,
        delete_vector as _delete_vector,
        delete_vectors_by_filter as _delete_vectors_by_filter,
        search as _search,
        count_items as _count_items,
        save_index as _save_index,
        load_index as _load_index,
        get_vec_dir,
        load_cfg
    )


class VectorStoreLock:
    """
    Manages thread-safe access to vector store operations.
    Uses both in-process threading locks and file-based locks for multi-process safety.
    """
    
    def __init__(self):
        """Initialize the locking mechanism."""
        # In-process thread lock
        self._thread_lock = threading.RLock()
        
        # File-based lock for multi-process safety
        self._lock_file_path = None
        self._file_lock = None
        self._initialize_file_lock()
        
        # Statistics
        self._stats = {
            'read_operations': 0,
            'write_operations': 0,
            'lock_acquisitions': 0,
            'lock_wait_time': 0.0,
            'errors': 0
        }
    
    def _initialize_file_lock(self):
        """Initialize the file-based lock."""
        try:
            cfg = load_cfg()
            vec_dir = get_vec_dir(cfg)
            vec_dir.mkdir(parents=True, exist_ok=True)
            
            self._lock_file_path = vec_dir / ".vector_store.lock"
            self._file_lock = filelock.FileLock(str(self._lock_file_path), timeout=30)
        except Exception as e:
            logging.error(f"Failed to initialize file lock: {e}")
            # Fall back to thread lock only
            self._file_lock = None
    
    @contextmanager
    def read_lock(self):
        """
        Acquire a read lock for read-only operations.
        Multiple readers can hold the lock simultaneously.
        """
        start_time = time.time()
        
        try:
            # For simplicity, we use the same lock for reads and writes
            # In a production system, you might want to use a ReadWriteLock
            with self._thread_lock:
                if self._file_lock:
                    with self._file_lock.acquire(timeout=30):
                        self._stats['lock_acquisitions'] += 1
                        self._stats['lock_wait_time'] += time.time() - start_time
                        self._stats['read_operations'] += 1
                        yield
                else:
                    self._stats['lock_acquisitions'] += 1
                    self._stats['lock_wait_time'] += time.time() - start_time
                    self._stats['read_operations'] += 1
                    yield
        except filelock.Timeout:
            self._stats['errors'] += 1
            logging.error("Timeout acquiring file lock for read operation")
            raise TimeoutError("Could not acquire vector store lock within timeout period")
        except Exception as e:
            self._stats['errors'] += 1
            logging.error(f"Error in read lock: {e}")
            raise
    
    @contextmanager
    def write_lock(self):
        """
        Acquire an exclusive write lock for write operations.
        Only one writer can hold the lock at a time.
        """
        start_time = time.time()
        
        try:
            with self._thread_lock:
                if self._file_lock:
                    with self._file_lock.acquire(timeout=30):
                        self._stats['lock_acquisitions'] += 1
                        self._stats['lock_wait_time'] += time.time() - start_time
                        self._stats['write_operations'] += 1
                        yield
                else:
                    self._stats['lock_acquisitions'] += 1
                    self._stats['lock_wait_time'] += time.time() - start_time
                    self._stats['write_operations'] += 1
                    yield
        except filelock.Timeout:
            self._stats['errors'] += 1
            logging.error("Timeout acquiring file lock for write operation")
            raise TimeoutError("Could not acquire vector store lock within timeout period")
        except Exception as e:
            self._stats['errors'] += 1
            logging.error(f"Error in write lock: {e}")
            raise
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about lock usage."""
        return dict(self._stats)


# Global lock instance
_vector_store_lock = VectorStoreLock()


def with_read_lock(func: Callable) -> Callable:
    """Decorator to add read lock to a function."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        with _vector_store_lock.read_lock():
            return func(*args, **kwargs)
    return wrapper


def with_write_lock(func: Callable) -> Callable:
    """Decorator to add write lock to a function."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        with _vector_store_lock.write_lock():
            return func(*args, **kwargs)
    return wrapper


# Thread-safe versions of vector store operations

@with_write_lock
def add_or_replace(id_: int | str, text: str, metadata: dict):
    """
    Thread-safe version of add_or_replace.
    Adds or replaces a vector and its metadata.
    """
    return _add_or_replace(id_, text, metadata)


@with_write_lock
def delete_vector(id_: int | str):
    """
    Thread-safe version of delete_vector.
    Deletes a vector and its metadata by custom ID.
    """
    return _delete_vector(id_)


@with_write_lock
def delete_vectors_by_filter(pred: Callable[[dict], bool]):
    """
    Thread-safe version of delete_vectors_by_filter.
    Delete multiple vectors based on a predicate function.
    """
    return _delete_vectors_by_filter(pred)


@with_read_lock
def search(query: str, top_k: int = 5, pred: Optional[Callable[[dict], bool]] = None, offset: int = 0):
    """
    Thread-safe version of search.
    Search for text in the vector store.
    """
    return _search(query, top_k, pred, offset)


@with_read_lock
def count_items(pred: Optional[Callable[[dict], bool]] = None) -> int:
    """
    Thread-safe version of count_items.
    Count items in the vector store.
    """
    return _count_items(pred)


@with_read_lock
def load_index(force_reload: bool = False) -> Tuple[Any, dict]:
    """
    Thread-safe version of load_index.
    Load the FAISS index and metadata.
    """
    return _load_index(force_reload)


@with_write_lock
def save_index(index: Any, meta: dict) -> bool:
    """
    Thread-safe version of save_index.
    Save FAISS index and metadata to disk.
    """
    return _save_index(index, meta)


def get_lock_stats() -> Dict[str, Any]:
    """Get statistics about vector store lock usage."""
    return _vector_store_lock.get_stats()


# Atomic file operations for additional safety

def atomic_write(file_path: pathlib.Path, content: str, encoding: str = 'utf-8'):
    """
    Write content to a file atomically.
    Uses a temporary file and atomic rename to prevent partial writes.
    """
    temp_path = file_path.with_suffix('.tmp')
    
    try:
        # Write to temporary file
        temp_path.write_text(content, encoding=encoding)
        
        # Atomic rename (on POSIX systems)
        # On Windows, this might not be truly atomic but is still safer
        temp_path.replace(file_path)
    except Exception as e:
        # Clean up temporary file if it exists
        if temp_path.exists():
            try:
                temp_path.unlink()
            except:
                pass
        raise e


def atomic_read(file_path: pathlib.Path, encoding: str = 'utf-8') -> str:
    """
    Read content from a file with retry logic for concurrent access.
    """
    max_retries = 3
    retry_delay = 0.1
    
    for attempt in range(max_retries):
        try:
            return file_path.read_text(encoding=encoding)
        except (IOError, OSError) as e:
            if attempt < max_retries - 1:
                time.sleep(retry_delay * (attempt + 1))
            else:
                raise e


# Re-export commonly used functions from memory_utils
try:
    # Try relative import first (when imported as part of package)
    from .memory_utils import (
        embed,
        vec_dim,
        model,
        load_cfg,
        load_preferences,
        index_code_chunk,
        delete_code_chunks,
        generate_chunk_id,
        check_vector_store_integrity,
        get_index_manager_stats,
        ROOT,
        CFG_PATH
    )
except ImportError:
    # Try absolute import (when script is run directly)
    from memory_utils import (
        embed,
        vec_dim,
        model,
        load_cfg,
        load_preferences,
        index_code_chunk,
        delete_code_chunks,
        generate_chunk_id,
        check_vector_store_integrity,
        get_index_manager_stats,
        ROOT,
        CFG_PATH
    )


# Example usage and testing
if __name__ == "__main__":
    import concurrent.futures
    import random
    
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    def test_concurrent_operations():
        """Test concurrent vector store operations."""
        
        def add_item(item_id: int):
            """Add an item to the vector store."""
            try:
                result = add_or_replace(
                    f"test_item_{item_id}",
                    f"This is test content for item {item_id}",
                    {"type": "test", "id": f"test_item_{item_id}", "value": item_id}
                )
                logging.info(f"Added item {item_id}: {result}")
                return True
            except Exception as e:
                logging.error(f"Error adding item {item_id}: {e}")
                return False
        
        def search_items(query: str):
            """Search for items in the vector store."""
            try:
                results = search(query, top_k=5)
                logging.info(f"Search '{query}' found {len(results)} results")
                return len(results)
            except Exception as e:
                logging.error(f"Error searching '{query}': {e}")
                return 0
        
        # Test concurrent writes and reads
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            # Submit write operations
            write_futures = []
            for i in range(20):
                future = executor.submit(add_item, i)
                write_futures.append(future)
            
            # Submit read operations
            read_futures = []
            for _ in range(10):
                query = f"test content for item {random.randint(0, 19)}"
                future = executor.submit(search_items, query)
                read_futures.append(future)
            
            # Wait for all operations to complete
            concurrent.futures.wait(write_futures + read_futures)
        
        # Print statistics
        stats = get_lock_stats()
        print("\nLock Statistics:")
        for key, value in stats.items():
            print(f"  {key}: {value}")
    
    # Run the test
    test_concurrent_operations()