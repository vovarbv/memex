# Memory Management in Memex

## Overview

The Memex vector store includes sophisticated memory management to prevent memory exhaustion when working with large FAISS indices. The memory-bounded IndexManager automatically manages cache size and evicts old entries to stay within configured limits.

## The Problem

Without proper memory management, the IndexManager could:
- Hold large FAISS indices in memory indefinitely
- Accumulate multiple versions of indices after updates
- Eventually exhaust available memory, causing crashes
- Degrade system performance due to excessive memory usage

## The Solution

The memory-bounded IndexManager provides:

### 1. Memory Limits
- **Default limit**: 500MB for cached indices
- **Configurable**: Adjust based on your system's resources
- **Automatic eviction**: Removes least recently used (LRU) entries when limit is reached

### 2. Time-Based Eviction
- **Default TTL**: 1 hour for cached entries
- **Configurable**: Adjust based on your usage patterns
- **Automatic cleanup**: Background thread removes expired entries

### 3. Memory Monitoring
- **Real-time tracking**: Monitor current memory usage
- **Peak tracking**: See the highest memory usage
- **Process monitoring**: Triggers garbage collection when needed

## Configuration

### Setting Memory Limits

```python
from memory_utils import set_index_cache_limits

# Set maximum cache size to 1GB and TTL to 30 minutes
set_index_cache_limits(max_memory_mb=1024, ttl_seconds=1800)
```

### In Configuration File

Add to your `memory.toml`:

```toml
[cache]
max_memory_mb = 1024  # Maximum memory for index cache in MB
ttl_seconds = 1800    # Time-to-live for cached entries in seconds
```

## Monitoring

### Cache Statistics

```python
from memory_utils import get_index_cache_stats

stats = get_index_cache_stats()
print(f"Cache hits: {stats['hits']}")
print(f"Cache hit rate: {stats['hit_rate']:.2%}")
print(f"Current memory usage: {stats['current_memory_mb']:.1f} MB")
print(f"Peak memory usage: {stats['peak_memory_mb']:.1f} MB")
print(f"Cache entries: {stats['cache_entries']}")
print(f"Evictions: {stats['evictions']}")
```

### Dashboard Display

The Memex web dashboard shows cache statistics including:
- Current memory usage
- Cache hit rate
- Number of evictions
- Peak memory usage

## Eviction Strategies

### 1. TTL Eviction
Entries are automatically removed after their time-to-live expires:
- Prevents stale data from consuming memory
- Ensures fresh data after updates
- Configurable based on update frequency

### 2. LRU Eviction
When memory limit is reached, least recently used entries are removed:
- Keeps frequently accessed indices in memory
- Removes indices that haven't been used recently
- Maintains 80% of limit as target after eviction

### 3. Manual Eviction
Force cache clearing when needed:

```python
from memory_bounded_index_manager import invalidate_cache

# Clear all cached indices
invalidate_cache()

# Clear specific path only
invalidate_cache(specific_path="/path/to/index")
```

## Best Practices

### 1. Size Your Cache Appropriately

Consider:
- Available system memory
- Size of your FAISS indices
- Number of concurrent projects
- Access patterns

Example sizing:
```python
# For a system with 8GB RAM and indices ~200MB each
set_index_cache_limits(max_memory_mb=1024)  # Allow up to 5 indices cached

# For a system with limited memory
set_index_cache_limits(max_memory_mb=256)  # Conservative limit
```

### 2. Adjust TTL Based on Usage

```python
# For frequently updated indices
set_index_cache_limits(ttl_seconds=600)  # 10 minutes

# For stable indices
set_index_cache_limits(ttl_seconds=7200)  # 2 hours

# For development/testing
set_index_cache_limits(ttl_seconds=300)  # 5 minutes
```

### 3. Monitor Memory Usage

Regular monitoring helps optimize settings:

```python
import time
from memory_utils import get_index_cache_stats

def monitor_cache_performance():
    """Monitor cache performance over time."""
    for _ in range(10):
        stats = get_index_cache_stats()
        
        print(f"Memory: {stats['current_memory_mb']:.1f}/{stats['max_memory_mb']} MB "
              f"| Hit rate: {stats['hit_rate']:.2%} "
              f"| Entries: {stats['cache_entries']}")
        
        if stats['current_memory_mb'] > stats['max_memory_mb'] * 0.9:
            print("⚠️  Warning: Approaching memory limit")
        
        time.sleep(60)
```

## Performance Impact

### Benefits
- **Faster repeated access**: Cached indices load instantly
- **Reduced I/O**: Fewer disk reads for frequently used indices
- **Better resource utilization**: Memory used efficiently

### Trade-offs
- **Memory overhead**: Cache management structures
- **Eviction cost**: Small CPU overhead for LRU tracking
- **Background thread**: Minimal CPU for periodic checks

## Troubleshooting

### High Memory Usage

If memory usage is too high:

1. **Reduce cache size**:
   ```python
   set_index_cache_limits(max_memory_mb=256)
   ```

2. **Reduce TTL**:
   ```python
   set_index_cache_limits(ttl_seconds=900)  # 15 minutes
   ```

3. **Clear cache manually**:
   ```python
   invalidate_cache()
   ```

### Low Hit Rate

If cache hit rate is low:

1. **Increase cache size** (if memory allows):
   ```python
   set_index_cache_limits(max_memory_mb=1024)
   ```

2. **Increase TTL**:
   ```python
   set_index_cache_limits(ttl_seconds=3600)
   ```

3. **Check access patterns** - frequent path changes reduce hit rate

### Memory Leaks

If memory usage grows beyond limits:

1. **Check for old processes** holding references
2. **Force garbage collection**:
   ```python
   import gc
   gc.collect()
   ```
3. **Restart the application** if necessary

## Advanced Configuration

### Custom Eviction Check Interval

For fine-tuned control, modify the eviction check interval:

```python
from memory_bounded_index_manager import _memory_bounded_index_manager

# Check every 30 seconds instead of default 60
_memory_bounded_index_manager.check_interval = 30
```

### Memory Estimation Tuning

The system estimates memory usage for FAISS indices. If estimates are inaccurate:

```python
# Override size estimation for specific index types
def custom_size_estimator(index, meta):
    # Your custom logic
    return estimated_bytes

_memory_bounded_index_manager._estimate_size = custom_size_estimator
```

## Integration with Thread Safety

The memory-bounded IndexManager works seamlessly with thread-safe operations:

```python
from thread_safe_store import add_or_replace, search

# Thread-safe operations automatically use memory-bounded caching
result = add_or_replace("id", "content", {"type": "doc"})
results = search("query")
```

Both systems work together to provide:
- Thread-safe access to cached indices
- Memory-bounded storage
- Consistent performance under load