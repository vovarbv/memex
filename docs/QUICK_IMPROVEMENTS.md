# Quick Improvements for One-Shot Memory Effectiveness

## 1. Temporal Relevance (Easy Win)

### Current Issue
All content is treated equally regardless of age.

### Quick Fix
Add recency weighting to search:

```python
# In memory_utils.py search function
def search_with_recency(query: str, top_k: int = 5, recency_weight: float = 0.3):
    results = search(query, top_k * 2)  # Get more results
    
    # Re-score with recency
    rescored = []
    current_time = time.time()
    
    for meta, score in results:
        # Calculate age in days
        created_at = meta.get('created_at', '')
        if created_at:
            age_days = (current_time - parse_timestamp(created_at)) / 86400
            recency_factor = math.exp(-0.1 * age_days)  # Decay factor
            new_score = score * (1 - recency_weight) + recency_factor * recency_weight
            rescored.append((meta, new_score))
        else:
            rescored.append((meta, score))
    
    # Re-sort and return top_k
    rescored.sort(key=lambda x: x[1], reverse=True)
    return rescored[:top_k]
```

## 2. Auto-Task Generation from Git

### Current Issue
Users must manually create and update tasks.

### Quick Fix
Add git commit monitor:

```python
# New file: scripts/git_task_monitor.py
import subprocess
from task_store import TaskStore

def extract_tasks_from_commits(last_n_commits=10):
    """Extract potential tasks from recent commit messages."""
    # Get recent commits
    result = subprocess.run(
        ['git', 'log', f'-{last_n_commits}', '--oneline'],
        capture_output=True, text=True
    )
    
    task_store = TaskStore()
    
    for line in result.stdout.strip().split('\n'):
        commit_hash, message = line.split(' ', 1)
        
        # Look for task indicators
        if any(keyword in message.lower() for keyword in ['fix', 'implement', 'add', 'update']):
            # Check if task already exists
            existing = [t for t in task_store.get_all_tasks() 
                       if similar(t.title, message)]
            
            if not existing:
                # Create new task
                task_store.add_task(Task(
                    title=message,
                    status="in_progress",
                    notes=[f"Auto-generated from commit {commit_hash}"]
                ))
```

## 3. Usage Tracking

### Current Issue
No tracking of which context is actually useful.

### Quick Fix
Add usage metrics to metadata:

```python
# In memory_utils.py
def track_usage(item_id: str):
    """Track when an item is included in context."""
    index, meta = load_index()
    
    if item_id in meta:
        # Update usage stats
        meta[item_id]['usage_count'] = meta[item_id].get('usage_count', 0) + 1
        meta[item_id]['last_used'] = datetime.now().isoformat()
        
        save_index(index, meta)
```

## 4. Smart Snippet Extraction

### Current Issue
Code snippets must be manually added.

### Quick Fix
Auto-extract from frequently edited code:

```python
# New file: scripts/auto_snippet_extractor.py
def extract_hot_functions(min_edits=3):
    """Extract functions that are frequently edited."""
    # Get git history
    hot_files = subprocess.run(
        ['git', 'log', '--name-only', '--pretty=format:', '-n', '100'],
        capture_output=True, text=True
    ).stdout.strip().split('\n')
    
    # Count edits per file
    file_counts = Counter(hot_files)
    
    # For hot files, extract functions
    for file, count in file_counts.items():
        if count >= min_edits and file.endswith('.py'):
            # Parse and extract functions
            functions = extract_functions(file)
            
            for func in functions:
                # Add as snippet if not exists
                add_snippet_if_new(func.code, func.name, file)
```

## 5. Context Effectiveness Tracking

### Current Issue
No feedback on whether generated context was useful.

### Quick Fix
Add feedback mechanism:

```python
# In gen_memory_mdc.py
def generate_mdc_with_tracking(focus_query=None):
    """Generate MDC and track what was included."""
    # Current generation logic...
    
    # Track what was included
    context_session = {
        'timestamp': datetime.now().isoformat(),
        'focus_query': focus_query,
        'included_items': [item['id'] for item in included_items],
        'total_tokens': total_tokens
    }
    
    # Save session for later feedback
    save_context_session(context_session)
    
    return mdc_content

# New CLI command to mark good/bad context
def mark_context_effectiveness(session_id, effective=True):
    """Mark whether a context session was effective."""
    session = load_context_session(session_id)
    
    # Update item scores based on effectiveness
    weight = 1.1 if effective else 0.9
    
    for item_id in session['included_items']:
        update_item_effectiveness_score(item_id, weight)
```

## Implementation Priority

### Week 1: Temporal Relevance
- Add recency weighting to search
- Update gen_memory_mdc.py to use it
- Test with different decay factors

### Week 2: Git Integration
- Implement git commit monitor
- Auto-generate tasks from commits
- Add git hooks for automatic updates

### Week 3: Usage Tracking
- Add usage counters to all items
- Track inclusion in context
- Update search to consider usage

### Week 4: Feedback Loop
- Implement context session tracking
- Add CLI commands for feedback
- Update scoring based on effectiveness

## Expected Impact

### Before (Current State)
- **Manual effort**: 30-60 min/week maintaining tasks/snippets
- **Context relevance**: ~60% useful content
- **Stale content**: Often includes outdated information

### After (With Quick Fixes)
- **Manual effort**: 5-10 min/week reviewing auto-generated content
- **Context relevance**: ~80% useful content
- **Fresh content**: Prioritizes recent and frequently used items

### ROI
- **Development time**: ~2-3 days per improvement
- **Benefit**: 50-80% reduction in manual maintenance
- **Payback period**: 2-4 weeks of usage