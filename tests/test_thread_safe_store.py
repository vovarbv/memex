#!/usr/bin/env python
"""
Tests for thread-safe vector store operations.
"""
import pytest
import pathlib
import threading
import concurrent.futures
import time
import random
from unittest.mock import patch, MagicMock

from ..scripts.thread_safe_store import (
    VectorStoreLock,
    add_or_replace,
    delete_vector,
    search,
    count_items,
    get_lock_stats,
    atomic_write,
    atomic_read
)


class TestVectorStoreLock:
    """Test cases for the VectorStoreLock class."""
    
    def test_read_lock_acquisition(self):
        """Test that read locks can be acquired."""
        lock = VectorStoreLock()
        
        with lock.read_lock():
            # Should be able to acquire read lock
            assert True
        
        stats = lock.get_stats()
        assert stats['read_operations'] == 1
        assert stats['lock_acquisitions'] == 1
    
    def test_write_lock_acquisition(self):
        """Test that write locks can be acquired."""
        lock = VectorStoreLock()
        
        with lock.write_lock():
            # Should be able to acquire write lock
            assert True
        
        stats = lock.get_stats()
        assert stats['write_operations'] == 1
        assert stats['lock_acquisitions'] == 1
    
    def test_multiple_read_locks(self):
        """Test that multiple read locks can be held (in theory)."""
        lock = VectorStoreLock()
        results = []
        
        def read_operation(op_id):
            with lock.read_lock():
                results.append(f"read_{op_id}_start")
                time.sleep(0.01)  # Simulate work
                results.append(f"read_{op_id}_end")
        
        # Launch multiple read operations
        threads = []
        for i in range(3):
            t = threading.Thread(target=read_operation, args=(i,))
            threads.append(t)
            t.start()
        
        # Wait for all threads
        for t in threads:
            t.join()
        
        # All reads should complete
        assert len(results) == 6  # 3 reads * 2 events each
    
    def test_write_lock_exclusivity(self):
        """Test that write locks are exclusive."""
        lock = VectorStoreLock()
        results = []
        
        def write_operation(op_id):
            with lock.write_lock():
                results.append(f"write_{op_id}_start")
                time.sleep(0.05)  # Simulate work
                results.append(f"write_{op_id}_end")
        
        # Launch multiple write operations
        threads = []
        for i in range(3):
            t = threading.Thread(target=write_operation, args=(i,))
            threads.append(t)
            t.start()
        
        # Wait for all threads
        for t in threads:
            t.join()
        
        # Check that writes don't overlap
        for i in range(0, len(results), 2):
            assert results[i].endswith('_start')
            assert results[i+1].endswith('_end')
            # Same ID for start and end
            assert results[i].split('_')[1] == results[i+1].split('_')[1]


class TestThreadSafeOperations:
    """Test thread-safe vector store operations."""
    
    @patch('memex.scripts.thread_safe_store._add_or_replace')
    def test_add_or_replace_thread_safe(self, mock_add):
        """Test that add_or_replace uses locks."""
        mock_add.return_value = "test_id"
        
        result = add_or_replace("test_id", "test content", {"type": "test"})
        
        assert result == "test_id"
        mock_add.assert_called_once_with("test_id", "test content", {"type": "test"})
        
        # Check that lock was used
        stats = get_lock_stats()
        assert stats['write_operations'] > 0
    
    @patch('memex.scripts.thread_safe_store._search')
    def test_search_thread_safe(self, mock_search):
        """Test that search uses read locks."""
        mock_search.return_value = [("item1", 0.9), ("item2", 0.8)]
        
        result = search("test query", top_k=5)
        
        assert len(result) == 2
        mock_search.assert_called_once()
        
        # Check that lock was used
        stats = get_lock_stats()
        assert stats['read_operations'] > 0
    
    @patch('memex.scripts.thread_safe_store._add_or_replace')
    @patch('memex.scripts.thread_safe_store._search')
    def test_concurrent_operations(self, mock_search, mock_add):
        """Test concurrent read and write operations."""
        # Set up mocks
        mock_add.return_value = "success"
        mock_search.return_value = []
        
        results = {'adds': 0, 'searches': 0, 'errors': 0}
        
        def add_items():
            try:
                for i in range(5):
                    add_or_replace(f"item_{i}", f"content_{i}", {"id": i})
                    results['adds'] += 1
                    time.sleep(0.01)
            except Exception as e:
                results['errors'] += 1
        
        def search_items():
            try:
                for i in range(10):
                    search(f"query_{i}", top_k=3)
                    results['searches'] += 1
                    time.sleep(0.005)
            except Exception as e:
                results['errors'] += 1
        
        # Run concurrent operations
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            futures = []
            # Submit write operations
            for _ in range(2):
                futures.append(executor.submit(add_items))
            # Submit read operations
            for _ in range(2):
                futures.append(executor.submit(search_items))
            
            # Wait for all to complete
            concurrent.futures.wait(futures)
        
        # Verify results
        assert results['adds'] == 10  # 2 threads * 5 items
        assert results['searches'] == 20  # 2 threads * 10 searches
        assert results['errors'] == 0


class TestAtomicOperations:
    """Test atomic file operations."""
    
    def test_atomic_write_and_read(self, tmp_path):
        """Test atomic write and read operations."""
        test_file = tmp_path / "test.txt"
        content = "Hello, atomic world!"
        
        # Atomic write
        atomic_write(test_file, content)
        
        # Verify file exists
        assert test_file.exists()
        
        # Atomic read
        read_content = atomic_read(test_file)
        assert read_content == content
    
    def test_atomic_write_failure_cleanup(self, tmp_path):
        """Test that temporary files are cleaned up on failure."""
        test_file = tmp_path / "test.txt"
        temp_file = test_file.with_suffix('.tmp')
        
        # Make the directory read-only to force a failure
        # This is tricky to test cross-platform, so we'll mock it
        with patch('pathlib.Path.replace') as mock_replace:
            mock_replace.side_effect = OSError("Permission denied")
            
            with pytest.raises(OSError):
                atomic_write(test_file, "content")
            
            # Temp file should be cleaned up
            assert not temp_file.exists()
    
    def test_concurrent_atomic_operations(self, tmp_path):
        """Test concurrent atomic writes don't corrupt the file."""
        test_file = tmp_path / "concurrent.txt"
        
        def write_content(thread_id):
            content = f"Thread {thread_id} content\n" * 100
            atomic_write(test_file, content)
            # Read it back
            read_back = atomic_read(test_file)
            # Content should be complete (not corrupted)
            assert len(read_back.split('\n')) >= 100
        
        # Run concurrent writes
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(write_content, i) for i in range(10)]
            concurrent.futures.wait(futures)
        
        # Final file should exist and be readable
        final_content = atomic_read(test_file)
        assert test_file.exists()
        assert len(final_content) > 0


class TestLockStatistics:
    """Test lock statistics tracking."""
    
    def test_statistics_tracking(self):
        """Test that lock statistics are properly tracked."""
        # Get initial stats
        initial_stats = get_lock_stats()
        initial_reads = initial_stats.get('read_operations', 0)
        initial_writes = initial_stats.get('write_operations', 0)
        
        # Perform some operations
        with patch('memex.scripts.thread_safe_store._search', return_value=[]):
            search("test", top_k=1)
        
        with patch('memex.scripts.thread_safe_store._add_or_replace', return_value="id"):
            add_or_replace("id", "text", {})
        
        # Check updated stats
        final_stats = get_lock_stats()
        assert final_stats['read_operations'] > initial_reads
        assert final_stats['write_operations'] > initial_writes
        assert final_stats['lock_acquisitions'] >= 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])