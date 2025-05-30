#!/usr/bin/env python
"""
Memory-bounded IndexManager implementation with automatic cache eviction.
This module provides a memory-aware version of IndexManager that prevents
unbounded memory growth through size limits and TTL-based eviction.
"""
import sys
import time
import logging
import threading
import weakref
import gc
import psutil
from typing import Tuple, Dict, Any, Optional
from datetime import datetime, timedelta
import pathlib

# Import the necessary functions from memory_utils
# Use late imports to avoid circular dependency
import pathlib

# Store imported functions at module level after first import
_imported_functions = None

def get_memory_utils_functions():
    """Import memory_utils functions when needed to avoid circular imports."""
    global _imported_functions
    
    if _imported_functions is not None:
        return _imported_functions
        
    # Use relative import within the package
    from .memory_utils import (
        load_cfg,
        get_index_path,
        get_meta_path,
        _load_index_internal,
        ROOT
    )
    
    _imported_functions = (load_cfg, get_index_path, get_meta_path, _load_index_internal, ROOT)
    return _imported_functions


class MemoryBoundedIndexManager:
    """
    Memory-bounded version of IndexManager with automatic cache eviction.
    
    Features:
    - Maximum memory limit for cached indices
    - Time-to-live (TTL) for cached entries
    - Automatic eviction when memory limit is reached
    - Memory usage monitoring
    - Thread-safe operations
    """
    
    _instance = None
    _lock = threading.RLock()
    
    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialize()
            return cls._instance
    
    def _initialize(self):
        """Initialize the memory-bounded index manager."""
        # Configuration
        self.max_memory_mb = 500  # Maximum memory for indices in MB
        self.ttl_seconds = 3600   # Time-to-live for cached entries (1 hour)
        self.check_interval = 60  # How often to check for eviction (seconds)
        
        # Cache storage
        self.cache = {}  # key -> (index, meta, metadata)
        self.access_times = {}  # key -> last access time
        self.load_times = {}    # key -> load time
        self.cache_sizes = {}   # key -> estimated size in bytes
        
        # Statistics
        self.stats = {
            'loads': 0,
            'hits': 0,
            'evictions': 0,
            'eviction_checks': 0,
            'total_memory_bytes': 0,
            'peak_memory_bytes': 0
        }
        
        # Start background eviction thread
        self._start_eviction_thread()
    
    def _start_eviction_thread(self):
        """Start a background thread for periodic eviction checks."""
        def eviction_worker():
            while True:
                try:
                    time.sleep(self.check_interval)
                    self._check_and_evict()
                except Exception as e:
                    logging.error(f"Error in eviction thread: {e}")
        
        thread = threading.Thread(target=eviction_worker, daemon=True)
        thread.start()
    
    def _estimate_size(self, index, meta: dict) -> int:
        """Estimate the memory size of an index and metadata."""
        size = 0
        
        # Estimate FAISS index size
        if index is not None:
            try:
                # FAISS index size approximation
                # Each vector is d * 4 bytes (float32) + overhead
                d = index.d if hasattr(index, 'd') else 0
                ntotal = index.ntotal if hasattr(index, 'ntotal') else 0
                size += d * ntotal * 4 + 1024  # Add 1KB overhead
            except:
                size += 1024 * 1024  # Default 1MB if we can't estimate
        
        # Estimate metadata size
        if meta is not None:
            # Simple estimation based on string representation
            meta_str = str(meta)
            size += len(meta_str.encode('utf-8'))
        
        return size
    
    def _get_total_cache_size(self) -> int:
        """Get the total size of all cached items."""
        return sum(self.cache_sizes.values())
    
    def _check_and_evict(self):
        """Check memory usage and evict entries if necessary."""
        with self._lock:
            self.stats['eviction_checks'] += 1
            current_time = time.time()
            
            # Check for TTL expiration
            expired_keys = []
            for key, load_time in self.load_times.items():
                if current_time - load_time > self.ttl_seconds:
                    expired_keys.append(key)
            
            # Evict expired entries
            for key in expired_keys:
                self._evict_entry(key, reason="TTL expired")
            
            # Check memory limit
            total_size = self._get_total_cache_size()
            self.stats['total_memory_bytes'] = total_size
            self.stats['peak_memory_bytes'] = max(
                self.stats['peak_memory_bytes'], 
                total_size
            )
            
            if total_size > self.max_memory_mb * 1024 * 1024:
                # Need to evict based on LRU
                self._evict_lru(total_size)
            
            # Force garbage collection if memory usage is high
            process = psutil.Process()
            memory_info = process.memory_info()
            if memory_info.rss > self.max_memory_mb * 2 * 1024 * 1024:
                gc.collect()
    
    def _evict_lru(self, current_size: int):
        """Evict least recently used entries until under memory limit."""
        target_size = int(self.max_memory_mb * 0.8 * 1024 * 1024)  # Target 80% of limit
        
        # Sort by access time (oldest first)
        sorted_keys = sorted(
            self.access_times.keys(),
            key=lambda k: self.access_times[k]
        )
        
        for key in sorted_keys:
            if current_size <= target_size:
                break
            
            size = self.cache_sizes.get(key, 0)
            self._evict_entry(key, reason="Memory limit")
            current_size -= size
    
    def _evict_entry(self, key: str, reason: str = "Unknown"):
        """Evict a single cache entry."""
        if key in self.cache:
            # Clear the cache entry
            del self.cache[key]
            
            # Clear metadata
            if key in self.access_times:
                del self.access_times[key]
            if key in self.load_times:
                del self.load_times[key]
            if key in self.cache_sizes:
                del self.cache_sizes[key]
            
            self.stats['evictions'] += 1
            logging.info(f"Evicted cache entry '{key}': {reason}")
    
    def get_index_and_meta(self, force_reload: bool = False) -> Tuple[Any, dict]:
        """
        Get the FAISS index and metadata with memory-bounded caching.
        
        Args:
            force_reload: If True, force reload even if cached
            
        Returns:
            Tuple of (index, meta)
        """
        with self._lock:
            # Import required functions
            load_cfg, get_index_path, get_meta_path, _load_index_internal, ROOT = get_memory_utils_functions()
            
            cfg = load_cfg()
            index_path = get_index_path(cfg)
            meta_path = get_meta_path(cfg)
            
            # Create cache key
            cache_key = f"{index_path}:{meta_path}"
            
            # Check if we need to reload
            need_reload = force_reload
            
            if not need_reload and cache_key in self.cache:
                # Check if files have been modified
                try:
                    cached_entry = self.cache[cache_key]
                    cached_mtime = cached_entry[2].get('mtime', 0)
                    
                    current_index_mtime = index_path.stat().st_mtime if index_path.exists() else 0
                    current_meta_mtime = meta_path.stat().st_mtime if meta_path.exists() else 0
                    current_mtime = max(current_index_mtime, current_meta_mtime)
                    
                    if current_mtime > cached_mtime:
                        need_reload = True
                except Exception:
                    need_reload = True
            else:
                need_reload = True
            
            if need_reload:
                # Load from disk
                self.stats['loads'] += 1
                logging.info(f"Loading FAISS index and metadata from disk (load #{self.stats['loads']})")
                
                try:
                    index, meta = _load_index_internal()
                    
                    # Calculate metadata
                    current_time = time.time()
                    current_index_mtime = index_path.stat().st_mtime if index_path.exists() else 0
                    current_meta_mtime = meta_path.stat().st_mtime if meta_path.exists() else 0
                    current_mtime = max(current_index_mtime, current_meta_mtime)
                    
                    metadata = {
                        'mtime': current_mtime,
                        'load_time': current_time
                    }
                    
                    # Estimate size
                    size = self._estimate_size(index, meta)
                    
                    # Store in cache
                    self.cache[cache_key] = (index, meta, metadata)
                    self.access_times[cache_key] = current_time
                    self.load_times[cache_key] = current_time
                    self.cache_sizes[cache_key] = size
                    
                    # Check if we need immediate eviction
                    self._check_and_evict()
                    
                    return index, meta
                    
                except Exception as e:
                    logging.error(f"Failed to load index and metadata: {e}")
                    raise
            else:
                # Use cached version
                self.stats['hits'] += 1
                self.access_times[cache_key] = time.time()
                
                cached_entry = self.cache[cache_key]
                logging.debug(f"Using cached FAISS index and metadata (hit #{self.stats['hits']})")
                
                return cached_entry[0], cached_entry[1]
    
    def invalidate(self, specific_path: Optional[str] = None):
        """
        Invalidate cached indices.
        
        Args:
            specific_path: If provided, only invalidate entries matching this path
        """
        with self._lock:
            if specific_path:
                # Invalidate specific entries
                keys_to_remove = [
                    key for key in self.cache.keys()
                    if specific_path in key
                ]
                for key in keys_to_remove:
                    self._evict_entry(key, reason="Manual invalidation")
            else:
                # Clear all cache
                self.cache.clear()
                self.access_times.clear()
                self.load_times.clear()
                self.cache_sizes.clear()
                logging.info("All cached indices invalidated")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive statistics about the cache."""
        with self._lock:
            current_size = self._get_total_cache_size()
            
            return {
                'loads': self.stats['loads'],
                'hits': self.stats['hits'],
                'hit_rate': self.stats['hits'] / max(1, self.stats['hits'] + self.stats['loads']),
                'evictions': self.stats['evictions'],
                'eviction_checks': self.stats['eviction_checks'],
                'cache_entries': len(self.cache),
                'current_memory_mb': current_size / (1024 * 1024),
                'peak_memory_mb': self.stats['peak_memory_bytes'] / (1024 * 1024),
                'max_memory_mb': self.max_memory_mb,
                'ttl_seconds': self.ttl_seconds
            }
    
    def set_limits(self, max_memory_mb: Optional[int] = None, ttl_seconds: Optional[int] = None):
        """
        Update memory and TTL limits.
        
        Args:
            max_memory_mb: Maximum memory in megabytes
            ttl_seconds: Time-to-live in seconds
        """
        with self._lock:
            if max_memory_mb is not None:
                self.max_memory_mb = max_memory_mb
                logging.info(f"Updated max memory limit to {max_memory_mb} MB")
            
            if ttl_seconds is not None:
                self.ttl_seconds = ttl_seconds
                logging.info(f"Updated TTL to {ttl_seconds} seconds")
            
            # Trigger immediate eviction check
            self._check_and_evict()


# Create a singleton instance
_memory_bounded_index_manager = MemoryBoundedIndexManager()


# Wrapper functions for compatibility
def get_index_and_meta(force_reload: bool = False) -> Tuple[Any, dict]:
    """Get the FAISS index and metadata using memory-bounded caching."""
    return _memory_bounded_index_manager.get_index_and_meta(force_reload)


def invalidate_cache(specific_path: Optional[str] = None):
    """Invalidate the cache."""
    _memory_bounded_index_manager.invalidate(specific_path)


def get_cache_stats() -> Dict[str, Any]:
    """Get cache statistics."""
    return _memory_bounded_index_manager.get_stats()


def set_cache_limits(max_memory_mb: Optional[int] = None, ttl_seconds: Optional[int] = None):
    """Set cache limits."""
    _memory_bounded_index_manager.set_limits(max_memory_mb, ttl_seconds)


# Example usage and testing
if __name__ == "__main__":
    import json
    
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    # Test the memory-bounded cache
    print("Testing memory-bounded IndexManager...")
    
    # Set aggressive limits for testing
    set_cache_limits(max_memory_mb=10, ttl_seconds=30)
    
    # Load index multiple times
    for i in range(5):
        print(f"\nIteration {i+1}:")
        
        try:
            index, meta = get_index_and_meta()
            print(f"  Loaded index with {index.ntotal if index else 0} vectors")
            
            # Show stats
            stats = get_cache_stats()
            print(f"  Cache stats: {json.dumps(stats, indent=2)}")
            
            # Sleep to test TTL
            if i == 2:
                print("  Sleeping for 35 seconds to test TTL...")
                time.sleep(35)
        except Exception as e:
            print(f"  Error: {e}")
        
        time.sleep(2)
    
    # Final stats
    print("\nFinal cache statistics:")
    print(json.dumps(get_cache_stats(), indent=2))