#!/usr/bin/env python
"""
Tests for the memory-bounded IndexManager.
"""
import pytest
import pathlib
import time
import threading
from unittest.mock import Mock, patch, MagicMock

from ..scripts.memory_bounded_index_manager import (
    MemoryBoundedIndexManager,
    get_index_and_meta,
    invalidate_cache,
    get_cache_stats,
    set_cache_limits
)


class MockIndex:
    """Mock FAISS index for testing."""
    def __init__(self, d=128, ntotal=1000):
        self.d = d
        self.ntotal = ntotal


class TestMemoryBoundedIndexManager:
    """Test cases for the MemoryBoundedIndexManager."""
    
    @patch('memex.scripts.memory_bounded_index_manager._load_index_internal')
    @patch('memex.scripts.memory_bounded_index_manager.get_index_path')
    @patch('memex.scripts.memory_bounded_index_manager.get_meta_path')
    def test_basic_caching(self, mock_meta_path, mock_index_path, mock_load):
        """Test basic caching functionality."""
        # Setup mocks
        mock_index_path.return_value = pathlib.Path("/fake/index.faiss")
        mock_meta_path.return_value = pathlib.Path("/fake/metadata.json")
        mock_index = MockIndex()
        mock_meta = {"test": "data"}
        mock_load.return_value = (mock_index, mock_meta)
        
        # Create manager
        manager = MemoryBoundedIndexManager()
        
        # First load should hit disk
        index1, meta1 = manager.get_index_and_meta()
        assert mock_load.call_count == 1
        assert index1.d == 128
        assert meta1["test"] == "data"
        
        # Second load should use cache
        index2, meta2 = manager.get_index_and_meta()
        assert mock_load.call_count == 1  # No additional load
        assert index2 is index1  # Same object
        assert meta2 is meta1
        
        # Check stats
        stats = manager.get_stats()
        assert stats['loads'] == 1
        assert stats['hits'] == 1
        assert stats['cache_entries'] == 1
    
    @patch('memex.scripts.memory_bounded_index_manager._load_index_internal')
    def test_force_reload(self, mock_load):
        """Test force reload functionality."""
        mock_load.return_value = (MockIndex(), {"version": 1})
        
        manager = MemoryBoundedIndexManager()
        
        # Initial load
        index1, meta1 = manager.get_index_and_meta()
        assert meta1["version"] == 1
        
        # Change return value
        mock_load.return_value = (MockIndex(), {"version": 2})
        
        # Normal load should use cache
        index2, meta2 = manager.get_index_and_meta()
        assert meta2["version"] == 1  # Still cached
        
        # Force reload should hit disk
        index3, meta3 = manager.get_index_and_meta(force_reload=True)
        assert meta3["version"] == 2  # New data
        assert mock_load.call_count == 2
    
    @patch('memex.scripts.memory_bounded_index_manager._load_index_internal')
    def test_ttl_eviction(self, mock_load):
        """Test time-to-live eviction."""
        mock_load.return_value = (MockIndex(), {"data": "test"})
        
        manager = MemoryBoundedIndexManager()
        manager.ttl_seconds = 1  # Very short TTL for testing
        
        # Load data
        manager.get_index_and_meta()
        assert len(manager.cache) == 1
        
        # Wait for TTL to expire
        time.sleep(1.5)
        
        # Trigger eviction check
        manager._check_and_evict()
        
        # Cache should be empty
        assert len(manager.cache) == 0
        assert manager.get_stats()['evictions'] == 1
    
    @patch('memex.scripts.memory_bounded_index_manager._load_index_internal')
    def test_memory_limit_eviction(self, mock_load):
        """Test memory limit eviction."""
        # Create large mock data
        large_meta = {"data": "x" * 1000000}  # ~1MB
        mock_load.return_value = (MockIndex(), large_meta)
        
        manager = MemoryBoundedIndexManager()
        manager.max_memory_mb = 2  # Low limit for testing
        
        # Load multiple entries that exceed memory limit
        for i in range(5):
            # Mock different paths to create different cache entries
            with patch('memex.scripts.memory_bounded_index_manager.get_index_path') as mock_path:
                mock_path.return_value = pathlib.Path(f"/fake/index_{i}.faiss")
                manager.get_index_and_meta()
        
        # Check that eviction happened
        stats = manager.get_stats()
        assert stats['evictions'] > 0
        assert stats['cache_entries'] < 5  # Some entries were evicted
    
    def test_lru_eviction_order(self):
        """Test that LRU eviction works correctly."""
        manager = MemoryBoundedIndexManager()
        
        # Mock the cache with known access times
        manager.cache = {
            "old": (None, {}, {}),
            "middle": (None, {}, {}),
            "new": (None, {}, {})
        }
        manager.access_times = {
            "old": 100,
            "middle": 200,
            "new": 300
        }
        manager.load_times = {
            "old": 100,
            "middle": 200,
            "new": 300
        }
        manager.cache_sizes = {
            "old": 1000,
            "middle": 1000,
            "new": 1000
        }
        
        # Force eviction with low target
        manager.max_memory_mb = 0.002  # 2KB limit
        manager._evict_lru(3000)  # Current size 3KB
        
        # Old entry should be evicted first
        assert "old" not in manager.cache
        assert "middle" in manager.cache or "new" in manager.cache
    
    def test_invalidate_cache(self):
        """Test cache invalidation."""
        manager = MemoryBoundedIndexManager()
        
        # Add some cache entries
        manager.cache = {
            "/path1/index.faiss:/path1/meta.json": (None, {}, {}),
            "/path2/index.faiss:/path2/meta.json": (None, {}, {})
        }
        manager.access_times = {
            "/path1/index.faiss:/path1/meta.json": 100,
            "/path2/index.faiss:/path2/meta.json": 200
        }
        
        # Invalidate specific path
        manager.invalidate("/path1")
        assert len(manager.cache) == 1
        assert "/path2/index.faiss:/path2/meta.json" in manager.cache
        
        # Invalidate all
        manager.invalidate()
        assert len(manager.cache) == 0
        assert len(manager.access_times) == 0
    
    def test_size_estimation(self):
        """Test memory size estimation."""
        manager = MemoryBoundedIndexManager()
        
        # Test with mock index
        mock_index = MockIndex(d=128, ntotal=1000)
        meta = {"key": "value" * 100}
        
        size = manager._estimate_size(mock_index, meta)
        
        # Should be roughly 128 * 1000 * 4 bytes for vectors plus metadata
        assert size > 500000  # At least 500KB
        assert size < 1000000  # Less than 1MB
    
    def test_statistics_tracking(self):
        """Test that statistics are properly tracked."""
        manager = MemoryBoundedIndexManager()
        
        # Reset stats
        manager.stats = {
            'loads': 0,
            'hits': 0,
            'evictions': 0,
            'eviction_checks': 0,
            'total_memory_bytes': 0,
            'peak_memory_bytes': 0
        }
        
        # Simulate some operations
        manager.stats['loads'] = 5
        manager.stats['hits'] = 15
        manager.stats['evictions'] = 2
        
        stats = manager.get_stats()
        
        assert stats['loads'] == 5
        assert stats['hits'] == 15
        assert stats['hit_rate'] == 0.75  # 15/(15+5)
        assert stats['evictions'] == 2
    
    def test_set_limits(self):
        """Test updating cache limits."""
        manager = MemoryBoundedIndexManager()
        
        # Set new limits
        manager.set_limits(max_memory_mb=100, ttl_seconds=7200)
        
        assert manager.max_memory_mb == 100
        assert manager.ttl_seconds == 7200
        
        # Set only memory limit
        manager.set_limits(max_memory_mb=200)
        assert manager.max_memory_mb == 200
        assert manager.ttl_seconds == 7200  # Unchanged
        
        # Set only TTL
        manager.set_limits(ttl_seconds=3600)
        assert manager.max_memory_mb == 200  # Unchanged
        assert manager.ttl_seconds == 3600


class TestModuleFunctions:
    """Test module-level wrapper functions."""
    
    def test_get_index_and_meta_wrapper(self):
        """Test the module-level get_index_and_meta function."""
        with patch.object(MemoryBoundedIndexManager, 'get_index_and_meta') as mock_method:
            mock_method.return_value = (MockIndex(), {"test": "data"})
            
            index, meta = get_index_and_meta()
            
            assert index.d == 128
            assert meta["test"] == "data"
            mock_method.assert_called_once_with(force_reload=False)
    
    def test_get_cache_stats_wrapper(self):
        """Test the module-level get_cache_stats function."""
        expected_stats = {"loads": 10, "hits": 20}
        
        with patch.object(MemoryBoundedIndexManager, 'get_stats') as mock_method:
            mock_method.return_value = expected_stats
            
            stats = get_cache_stats()
            
            assert stats == expected_stats
            mock_method.assert_called_once()
    
    def test_set_cache_limits_wrapper(self):
        """Test the module-level set_cache_limits function."""
        with patch.object(MemoryBoundedIndexManager, 'set_limits') as mock_method:
            set_cache_limits(max_memory_mb=50, ttl_seconds=1800)
            
            mock_method.assert_called_once_with(max_memory_mb=50, ttl_seconds=1800)


class TestConcurrency:
    """Test concurrent access to the cache."""
    
    @patch('memex.scripts.memory_bounded_index_manager._load_index_internal')
    def test_concurrent_access(self, mock_load):
        """Test that concurrent access is thread-safe."""
        mock_load.return_value = (MockIndex(), {"concurrent": "test"})
        
        manager = MemoryBoundedIndexManager()
        results = []
        errors = []
        
        def access_cache(thread_id):
            try:
                for i in range(5):
                    index, meta = manager.get_index_and_meta()
                    results.append((thread_id, i, meta.get("concurrent")))
                    time.sleep(0.01)
            except Exception as e:
                errors.append((thread_id, str(e)))
        
        # Launch multiple threads
        threads = []
        for i in range(5):
            t = threading.Thread(target=access_cache, args=(i,))
            threads.append(t)
            t.start()
        
        # Wait for all threads
        for t in threads:
            t.join()
        
        # Check results
        assert len(errors) == 0  # No errors
        assert len(results) == 25  # 5 threads * 5 accesses
        
        # All results should have the correct data
        for thread_id, iteration, value in results:
            assert value == "test"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])