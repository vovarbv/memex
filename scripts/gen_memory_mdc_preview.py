"""
Preview functionality for memory.mdc generation.
This module provides functions to preview what will be included in memory.mdc
without actually writing the file.
"""

import logging
from typing import Dict, List, Any, Optional, Tuple

# Import required modules with robust importing
try:
    from memory_utils import load_cfg, load_preferences, ROOT
    from thread_safe_store import search
    from task_store import TaskStore
except ImportError:
    try:
        from .memory_utils import load_cfg, load_preferences, ROOT
        from .thread_safe_store import search
        from .task_store import TaskStore
    except ImportError:
        from scripts.memory_utils import load_cfg, load_preferences, ROOT
        from scripts.thread_safe_store import search
        from scripts.task_store import TaskStore

try:
    import tiktoken
    HAS_TIKTOKEN = True
except ImportError:
    HAS_TIKTOKEN = False
    logging.warning("tiktoken not available, token counting will be estimated")


def count_tokens(text: str) -> int:
    """Count tokens in text, with fallback to character-based estimation."""
    if HAS_TIKTOKEN:
        try:
            enc = tiktoken.get_encoding("cl100k_base")
            return len(enc.encode(text))
        except:
            pass
    
    # Fallback: estimate ~4 characters per token
    return len(text) // 4


def get_task_context_query(task_id: str, ts: TaskStore) -> Optional[str]:
    """Generate a context query from a specific task."""
    try:
        # Find the task
        task = None
        for t in ts.tasks:
            if hasattr(t, 'id') and str(t.id) == str(task_id):
                task = t
                break
        
        if not task:
            return None
        
        # Build query from task details
        query_parts = []
        
        # Add title
        if hasattr(task, 'title'):
            query_parts.append(task.title)
        
        # Add description
        if hasattr(task, 'description') and task.description:
            query_parts.append(task.description)
        
        # Add plan items (first few)
        if hasattr(task, 'plan') and task.plan:
            for step in task.plan[:3]:  # First 3 plan items
                query_parts.append(step)
        
        # Add recent notes
        if hasattr(task, 'notes') and task.notes:
            if isinstance(task.notes, list):
                query_parts.append(task.notes[-1])  # Most recent note
            elif isinstance(task.notes, str):
                query_parts.append(task.notes)
        
        return " ".join(query_parts)
        
    except Exception as e:
        logging.error(f"Error generating task context query: {e}")
        return None


def preview_context(task_id: Optional[str] = None, 
                   focus_query: Optional[str] = None,
                   max_items: int = 10) -> Dict[str, Any]:
    """
    Preview what context items will be included for a task.
    
    Args:
        task_id: ID of the task to focus on
        focus_query: Optional custom focus query
        max_items: Maximum number of items to return
        
    Returns:
        Dictionary with context items and statistics
    """
    result = {
        'success': False,
        'task': None,
        'preferences': {},
        'tasks': [],
        'snippets': [],
        'notes': [],
        'code_chunks': [],
        'stats': {
            'total_items': 0,
            'total_tokens': 0,
            'task_tokens': 0,
            'context_tokens': 0
        },
        'error': None
    }
    
    try:
        # Load configuration
        cfg = load_cfg()
        top_k_tasks = cfg.get("prompt", {}).get("top_k_tasks", 5)
        top_k_context = cfg.get("prompt", {}).get("top_k_context_items", max_items)
        
        # Load task store
        ts = TaskStore()
        
        # Get the focus task details
        if task_id:
            for t in ts.tasks:
                if hasattr(t, 'id') and str(t.id) == str(task_id):
                    task_dict = t.to_dict() if hasattr(t, 'to_dict') else {
                        'id': getattr(t, 'id', ''),
                        'title': getattr(t, 'title', ''),
                        'status': getattr(t, 'status', ''),
                        'priority': getattr(t, 'priority', ''),
                        'progress': getattr(t, 'progress', 0),
                        'description': getattr(t, 'description', ''),
                        'plan': getattr(t, 'plan', []),
                        'notes': getattr(t, 'notes', [])
                    }
                    result['task'] = task_dict
                    result['stats']['task_tokens'] = count_tokens(str(task_dict))
                    break
        
        # Load preferences
        try:
            prefs = load_preferences()
            if prefs:
                result['preferences'] = prefs
                result['stats']['preference_tokens'] = count_tokens(str(prefs))
        except:
            logging.warning("Could not load preferences")
        
        # Get other active tasks
        active_tasks = []
        for t in ts.tasks:
            if hasattr(t, 'status') and t.status in ['in_progress', 'todo']:
                if not task_id or str(t.id) != str(task_id):  # Don't duplicate focus task
                    task_dict = t.to_dict() if hasattr(t, 'to_dict') else {
                        'id': getattr(t, 'id', ''),
                        'title': getattr(t, 'title', ''),
                        'status': getattr(t, 'status', ''),
                        'priority': getattr(t, 'priority', '')
                    }
                    active_tasks.append(task_dict)
        
        # Sort by priority and limit
        priority_order = {'high': 0, 'medium': 1, 'low': 2}
        active_tasks.sort(key=lambda t: priority_order.get(t.get('priority', 'low'), 3))
        result['tasks'] = active_tasks[:top_k_tasks]
        
        # Generate search query
        query = None
        if task_id and not focus_query:
            query = get_task_context_query(task_id, ts)
        elif focus_query:
            query = focus_query
        
        if query:
            # Define predicates for different types
            def snippet_pred(meta):
                return meta.get('type') == 'snippet'
            
            def note_pred(meta):
                return meta.get('type') == 'note'
            
            def code_chunk_pred(meta):
                return meta.get('type') == 'code_chunk'
            
            # Search for each type
            try:
                # Get snippets
                snippet_results = search(query, top_k=5, pred=snippet_pred)
                for meta, score in snippet_results:
                    result['snippets'].append({
                        'id': meta.get('id'),
                        'title': meta.get('title', 'Untitled'),
                        'content': meta.get('content', ''),
                        'language': meta.get('language', ''),
                        'score': score
                    })
                
                # Get notes
                note_results = search(query, top_k=5, pred=note_pred)
                for meta, score in note_results:
                    result['notes'].append({
                        'id': meta.get('id'),
                        'title': meta.get('title', 'Untitled'),
                        'content': meta.get('content', ''),
                        'score': score
                    })
                
                # Get code chunks
                chunk_results = search(query, top_k=5, pred=code_chunk_pred)
                for meta, score in chunk_results:
                    result['code_chunks'].append({
                        'id': meta.get('id'),
                        'file_path': meta.get('file_path', ''),
                        'content': meta.get('content', ''),
                        'language': meta.get('language', ''),
                        'chunk_type': meta.get('chunk_type', ''),
                        'score': score
                    })
                    
            except Exception as e:
                logging.error(f"Error searching for context: {e}")
                result['error'] = f"Search error: {str(e)}"
        
        # Calculate statistics
        all_items = result['snippets'] + result['notes'] + result['code_chunks']
        result['stats']['total_items'] = len(result['tasks']) + len(all_items)
        
        # Calculate context tokens
        context_tokens = 0
        for item in all_items:
            context_tokens += count_tokens(item.get('content', ''))
        result['stats']['context_tokens'] = context_tokens
        result['stats']['total_tokens'] = (
            result['stats'].get('task_tokens', 0) + 
            result['stats'].get('preference_tokens', 0) +
            context_tokens
        )
        
        result['success'] = True
        
    except Exception as e:
        logging.error(f"Error generating context preview: {e}")
        result['error'] = str(e)
    
    return result


def format_preview_markdown(preview_data: Dict[str, Any]) -> str:
    """Format preview data as markdown for display."""
    if not preview_data.get('success'):
        return f"❌ Error: {preview_data.get('error', 'Unknown error')}"
    
    lines = ["# Memory Context Preview\n"]
    
    # Current task
    if preview_data.get('task'):
        task = preview_data['task']
        lines.append("## 🎯 Current Task\n")
        lines.append(f"**{task.get('title', 'Untitled')}**\n")
        if task.get('description'):
            lines.append(f"*{task['description']}*\n")
        lines.append(f"- Status: {task.get('status', 'unknown')}")
        lines.append(f"- Priority: {task.get('priority', 'medium')}")
        lines.append(f"- Progress: {task.get('progress', 0)}%\n")
    
    # Other active tasks
    if preview_data.get('tasks'):
        lines.append("## 📋 Other Active Tasks\n")
        for task in preview_data['tasks'][:3]:
            lines.append(f"- **{task.get('title')}** [{task.get('status')}]")
        lines.append("")
    
    # Relevant snippets
    if preview_data.get('snippets'):
        lines.append("## 💾 Relevant Code Snippets\n")
        for snippet in preview_data['snippets'][:3]:
            lines.append(f"### {snippet.get('title')}")
            lines.append(f"```{snippet.get('language', '')}")
            content = snippet.get('content', '')
            # Don't truncate content for preview - let the UI handle scrolling
            lines.append(content)
            lines.append("```\n")
    
    # Relevant notes
    if preview_data.get('notes'):
        lines.append("## 📝 Relevant Notes\n")
        for note in preview_data['notes'][:2]:
            lines.append(f"**{note.get('title')}**")
            content = note.get('content', '')
            # Don't truncate content for preview
            lines.append(f"{content}\n")
    
    # Code chunks
    if preview_data.get('code_chunks'):
        lines.append("## 🗂️ Relevant Code from Project\n")
        for chunk in preview_data['code_chunks'][:2]:
            lines.append(f"**{chunk.get('file_path', 'Unknown file')}**")
            lines.append(f"```{chunk.get('language', '')}")
            content = chunk.get('content', '')
            # Don't truncate content for preview
            lines.append(content)
            lines.append("```\n")
    
    return "\n".join(lines)


def format_preview_stats(preview_data: Dict[str, Any]) -> str:
    """Format preview statistics for display."""
    if not preview_data.get('success'):
        return "No statistics available"
    
    stats = preview_data.get('stats', {})
    lines = [
        f"**Total Context Items**: {stats.get('total_items', 0)}",
        f"**Estimated Tokens**: ~{stats.get('total_tokens', 0):,}",
        "",
        "**Breakdown**:",
        f"- Current Task: {stats.get('task_tokens', 0):,} tokens",
        f"- Other Tasks: {len(preview_data.get('tasks', []))} items",
        f"- Snippets: {len(preview_data.get('snippets', []))} items",
        f"- Notes: {len(preview_data.get('notes', []))} items",
        f"- Code Chunks: {len(preview_data.get('code_chunks', []))} items",
        "",
        f"**Context Quality**: {'🟢 Good' if stats.get('total_tokens', 0) < 8000 else '🟡 Large' if stats.get('total_tokens', 0) < 12000 else '🔴 Too Large'}"
    ]
    
    return "\n".join(lines)


# Test function
if __name__ == "__main__":
    # Test preview
    preview = preview_context()
    print(format_preview_markdown(preview))
    print("\n---\n")
    print(format_preview_stats(preview))