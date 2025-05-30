#!/usr/bin/env python
"""
Generates .cursor/rules/memory.mdc based on top-K tasks/snippets + preferences.
"""
import os
import textwrap
import pathlib
import tiktoken
import logging
import sys
import argparse
from typing import List, Dict, Any, Tuple, Optional

# Use proper package imports
try:
    # When run as a module within the package
    from .memory_utils import load_cfg, load_preferences, ROOT, get_cursor_output_base_path
    from .thread_safe_store import search
    from .task_store import TaskStore
except ImportError:
    # When run as a script or from outside the package
    try:
        from memex.scripts.memory_utils import load_cfg, load_preferences, ROOT, get_cursor_output_base_path
        from memex.scripts.thread_safe_store import search
        from memex.scripts.task_store import TaskStore
    except ImportError as e:
        logging.error(f"Failed to import required modules: {e}")
        sys.exit(1)

# ───────────────────────────────────────── Logging Setup ────
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt="%Y-%m-%d %H:%M:%S"
)

# ───────────────────────────────────────── Helper Formatters ────

def _format_task_for_mdc(task: dict) -> list[str]:
    """Formats a single task into a list of Markdown lines."""
    task_lines = []
    title = task.get('title', 'Untitled Task')
    progress = task.get('progress', 0)
    task_id = task.get('id', 'N/A')
    task_lines.append(f"- #{task_id} {title} — {progress}%")

    plan = task.get("plan", [])
    done_steps = task.get("done_steps", [])
    
    # Add completion summary if the task has a plan
    if plan:
        completion_summary = f"  * Completion: {len(done_steps)}/{len(plan)} steps done."
        task_lines.append(completion_summary)
    
    # Show pending steps as next steps
    pending_steps = [step for step in plan if step not in done_steps]
    if pending_steps:
        task_lines.append("  * Next steps:")
        for step in pending_steps[:3]:  # Show at most 3 next steps
            task_lines.append(f"    - {step}")
    
    # Optionally show completed steps (if any)
    if done_steps:
        # We can show all completed steps or limit to a certain number
        # Let's limit to 2 to avoid overwhelming the memory.mdc
        task_lines.append("  * Completed steps:")
        for step in done_steps[:2]:  # Show at most 2 completed steps
            task_lines.append(f"    - ✓ {step}")
        if len(done_steps) > 2:
            task_lines.append(f"    - ... and {len(done_steps) - 2} more")

    # Add the last note if available
    notes = task.get("notes", "")
    
    # Handle notes as either a string or a list
    if isinstance(notes, list) and notes:
        last_note = notes[-1]  # Get the last note from the list
        task_lines.append(f"  * Last note: {textwrap.shorten(last_note, width=120, placeholder='...')}")
    elif isinstance(notes, str) and notes.strip():
        last_note_line = notes.strip().splitlines()[-1]
        task_lines.append(f"  * Last note: {textwrap.shorten(last_note_line, width=120, placeholder='...')}")
    
    return task_lines

def _format_context_item_for_mdc(meta: dict) -> list[str]:
    """
    Formats a single context item (snippet, note, or code chunk) into a list of Markdown lines.
    Enhanced to properly handle code_chunk type.
    """
    item_lines = []
    item_type = meta.get("type")
    item_id = meta.get("id", "N/A")
    
    if item_type == "snippet":
        item_source = meta.get("source", "unknown")
        item_language = meta.get("language", "text")
        item_raw_content = meta.get("raw_content", "")
        
        # Create a well-formatted header
        item_lines.append(f"### 📝 Code Snippet: {item_source}")
        item_lines.append(f"**Language:** {item_language} | **ID:** {item_id}")
        item_lines.append("")
        
        # Format the code with markdown code blocks
        item_lines.append(f"```{item_language}")
        item_lines.append(item_raw_content)
        item_lines.append("```")
    
    elif item_type == "note":
        item_text = meta.get("text", "")
        timestamp = meta.get("timestamp", "")
        time_info = f" | **Added:** {timestamp}" if timestamp else ""
        
        item_lines.append(f"### 📋 Development Note")
        item_lines.append(f"**ID:** {item_id}{time_info}")
        item_lines.append("")
        # Note text should be appended line by line if it's multiline, or as a block.
        # Wrap long lines for better readability
        wrapped_text = textwrap.fill(item_text, width=100)
        item_lines.append(wrapped_text)
        
    elif item_type == "code_chunk":
        # Handle code chunks from code indexing
        source_file = meta.get("source_file", "unknown file")
        language = meta.get("language", "text")
        start_line = meta.get("start_line", "?")
        end_line = meta.get("end_line", "?")
        name = meta.get("name", "")
        content = meta.get("content", "")
        
        # Create a descriptive header
        if name:
            item_lines.append(f"### 🔧 {language.title()}: `{name}`")
            item_lines.append(f"**File:** `{source_file}` | **Lines:** {start_line}-{end_line} | **ID:** {item_id}")
        else:
            item_lines.append(f"### 🔧 Code from `{source_file}`")
            item_lines.append(f"**Language:** {language} | **Lines:** {start_line}-{end_line} | **ID:** {item_id}")
        item_lines.append("")
        
        # Format the code with markdown code blocks including language
        item_lines.append(f"```{language}")
        item_lines.append(content)
        item_lines.append("```")
    
    # Add a newline after each formatted item for separation, handled by joining with \n\n later if needed
    return item_lines

def _formulate_query_from_active_tasks(active_tasks: List[Dict[str, Any]], max_tasks: int = 5, max_plan_items: int = 3) -> str:
    """
    Formulate a rich context query string from active tasks, combining titles, pending steps, and relevant notes.
    
    Args:
        active_tasks: List of active task dictionaries
        max_tasks: Maximum number of tasks to include in the query
        max_plan_items: Maximum number of plan items to include per task
        
    Returns:
        Query string for FAISS search
    """
    if not active_tasks:
        return ""
    
    query_parts = []
    
    # Use only a limited number of tasks to keep the query focused
    for i, task in enumerate(active_tasks[:max_tasks]):
        # For the first task, add more weight to its parts (it's likely the most important)
        # Start with the task title
        title = task.get("title", "").strip()
        if title:
            # Repeat the title for the first task to give it more weight
            if i == 0:
                query_parts.append(title)
                query_parts.append(title)  # Repeat for emphasis
            else:
                query_parts.append(title)
        
        # Add a subset of plan items that aren't completed yet
        plan = task.get("plan", [])
        done_steps = task.get("done_steps", [])
        pending_steps = [step for step in plan if step not in done_steps]
        
        # Add just a few pending steps to the query to keep it focused
        for step in pending_steps[:max_plan_items]:
            query_parts.append(step)
        
        # Add the most recent note (if any) for additional context
        notes = task.get("notes", [])
        if isinstance(notes, list) and notes:
            # Add only the most recent note
            query_parts.append(notes[-1])
        elif isinstance(notes, str) and notes.strip():
            # Single string note - add if present
            query_parts.append(notes)
            
        # Add keywords related to priority to help with context
        priority = task.get("priority", "")
        if priority == "high":
            query_parts.append("urgent important critical priority")
    
    # Join all parts with spaces
    query = " ".join(query_parts)
    
    # Log the query for debugging
    logging.debug(f"Generated context query from tasks: {query[:100]}...")
    
    return query

def _generate_project_structure_block(cfg: dict) -> str:
    """
    Generate a project structure overview showing indexed files and directories.
    
    Args:
        cfg: Configuration dictionary
        
    Returns:
        Formatted markdown string showing the project structure
    """
    try:
        from pathlib import Path
        import os
        
        # Get the host project root (where .cursor directory is created)
        cursor_base = get_cursor_output_base_path(cfg)
        
        # Get include/exclude patterns from config
        include_patterns = cfg.get("files", {}).get("include", [])
        exclude_patterns = cfg.get("files", {}).get("exclude", [])
        
        if not include_patterns:
            return ""
        
        structure_lines = ["## Indexed Project Structure"]
        structure_lines.append("")
        structure_lines.append("The following files and directories are indexed and available for context:")
        structure_lines.append("")
        
        # Show include patterns
        structure_lines.append("### Included Patterns")
        for pattern in include_patterns[:10]:  # Limit to first 10 patterns
            structure_lines.append(f"- `{pattern}`")
        if len(include_patterns) > 10:
            structure_lines.append(f"- ... and {len(include_patterns) - 10} more patterns")
        structure_lines.append("")
        
        # Try to show actual indexed files if available from vector store
        try:
            # Get indexed files from vector store metadata
            from memory_utils import load_index
            index, meta = load_index()
            
            if meta:
                # Extract unique source files from code chunks
                indexed_files = set()
                custom_to_faiss_map = meta.get("_custom_to_faiss_id_map_", {})
                
                for custom_id in custom_to_faiss_map.keys():
                    if custom_id in meta:
                        item_meta = meta[custom_id]
                        if item_meta.get("type") == "code_chunk":
                            source_file = item_meta.get("source_file", "")
                            if source_file:
                                indexed_files.add(source_file)
                
                if indexed_files:
                    # Group by directory for better organization
                    file_tree = {}
                    for file_path in sorted(indexed_files):
                        parts = Path(file_path).parts
                        current = file_tree
                        for part in parts[:-1]:  # All but the filename
                            if part not in current:
                                current[part] = {}
                            current = current[part]
                        # Add the filename
                        filename = parts[-1] if parts else file_path
                        current[filename] = None  # None indicates it's a file
                    
                    structure_lines.append("### Currently Indexed Files")
                    structure_lines.extend(_format_file_tree(file_tree, max_depth=3))
                    structure_lines.append("")
                    structure_lines.append(f"**Total indexed files:** {len(indexed_files)}")
                    structure_lines.append("")
        
        except Exception as e:
            logging.debug(f"Could not load indexed files from vector store: {e}")
            # Fallback to just showing patterns
            pass
        
        # Add information about vector store stats
        try:
            vector_stats = _get_vector_store_stats()
            if vector_stats:
                structure_lines.append("### Vector Store Statistics")
                structure_lines.append(f"- **Code chunks:** {vector_stats.get('code_chunks', 0)}")
                structure_lines.append(f"- **Snippets:** {vector_stats.get('snippets', 0)}")
                structure_lines.append(f"- **Notes:** {vector_stats.get('notes', 0)}")
                structure_lines.append(f"- **Total indexed items:** {vector_stats.get('total_items', 0)}")
                structure_lines.append("")
        except Exception as e:
            logging.debug(f"Could not load vector store stats: {e}")
        
        structure_lines.append("---")
        structure_lines.append("")
        
        return "\n".join(structure_lines)
        
    except Exception as e:
        logging.error(f"Error generating project structure block: {e}")
        return ""

def _format_file_tree(tree: dict, indent: str = "", max_depth: int = 3, current_depth: int = 0) -> list[str]:
    """
    Format a file tree dictionary into markdown list format.
    
    Args:
        tree: Dictionary representing the file tree
        indent: Current indentation string
        max_depth: Maximum depth to display
        current_depth: Current depth level
        
    Returns:
        List of formatted strings
    """
    lines = []
    
    if current_depth >= max_depth:
        if tree:
            lines.append(f"{indent}- ...")
        return lines
    
    # Sort items: directories first, then files
    items = sorted(tree.items(), key=lambda x: (x[1] is None, x[0]))
    
    for name, subtree in items[:20]:  # Limit to 20 items per level
        if subtree is None:  # It's a file
            lines.append(f"{indent}- 📄 `{name}`")
        else:  # It's a directory
            lines.append(f"{indent}- 📁 **{name}/**")
            if subtree:  # Has contents
                lines.extend(_format_file_tree(subtree, indent + "  ", max_depth, current_depth + 1))
    
    if len(tree) > 20:
        lines.append(f"{indent}- ... and {len(tree) - 20} more items")
    
    return lines

def _get_vector_store_stats() -> dict:
    """
    Get statistics about the vector store contents.
    
    Returns:
        Dictionary with counts of different item types
    """
    try:
        from memory_utils import load_index
        index, meta = load_index()
        
        if not meta:
            return {}
        
        stats = {
            'code_chunks': 0,
            'snippets': 0,
            'notes': 0,
            'tasks': 0,
            'other': 0,
            'total_items': 0
        }
        
        custom_to_faiss_map = meta.get("_custom_to_faiss_id_map_", {})
        
        for custom_id in custom_to_faiss_map.keys():
            if custom_id in meta:
                item_meta = meta[custom_id]
                item_type = item_meta.get("type", "other")
                
                if item_type == "code_chunk":
                    stats['code_chunks'] += 1
                elif item_type == "snippet":
                    stats['snippets'] += 1
                elif item_type in ["note", "memory"]:
                    stats['notes'] += 1
                elif item_type == "task":
                    stats['tasks'] += 1
                else:
                    stats['other'] += 1
                
                stats['total_items'] += 1
        
        return stats
        
    except Exception as e:
        logging.debug(f"Error getting vector store stats: {e}")
        return {}

# ───────────────────────────────────────── Main Logic ────
def make(focus=None, quiet=False) -> tuple[bool, str, str]:
    """
    Generates memory.mdc file based on tasks, snippets, and preferences.
    
    Args:
        focus: Optional focus query for context search
        quiet: If True, suppress console output and return status instead
    
    Returns:
        Tuple of (success, message, path)
    """
    try:
        cfg = load_cfg()
    except Exception as e:
        error_msg = f"Failed to load configuration: {e}. Aborting mdc generation."
        logging.critical(error_msg)
        if not quiet:
            print(f"❌ {error_msg}")
            sys.exit(1)
        return False, error_msg, ""

    max_total_tokens = cfg.get("prompt", {}).get("max_tokens", 10000)
    top_tasks_k = cfg.get("prompt", {}).get("top_k_tasks", 5)
    top_k_context = cfg.get("prompt", {}).get("top_k_context_items", 5)

    logging.info(f"Generation settings: max_tokens={max_total_tokens}, top_k_tasks={top_tasks_k}, top_k_context={top_k_context}")

    try:
        enc = tiktoken.get_encoding("cl100k_base")
    except Exception as e:
        error_msg = f"Failed to load tiktoken encoder: {e}. Aborting."
        logging.critical(error_msg)
        if not quiet:
            print(f"❌ {error_msg}")
            sys.exit(1)
        return False, error_msg, ""

    final_mdc_parts = []
    current_total_tokens = 0

    # 0. Header with AI context interpretation guide
    header_block = """

# Project Memory Context

This file contains the most relevant context for the current development session. Use this information to understand:
- **Project preferences and guidelines** for consistent development
- **Active tasks** that are currently being worked on
- **Relevant code and documentation** from the indexed codebase
- **Project structure** showing what's indexed and available

## How to Interpret This Context

- **Preferences**: Development guidelines, coding standards, and project-specific requirements
- **Active Tasks**: Current work items with their progress and next steps
- **Task-Relevant Context**: Code, snippets, and notes most relevant to active tasks
- **Focus-Based Context**: Specific context when a focus query is provided
- **Indexed Structure**: Overview of the codebase organization and indexed content

---

"""
    header_tokens = len(enc.encode(header_block))
    if current_total_tokens + header_tokens <= max_total_tokens:
        final_mdc_parts.append(header_block)
        current_total_tokens += header_tokens
        logging.debug(f"Added enhanced header: {header_tokens} tokens, total now {current_total_tokens}")
    else:
        logging.warning("Not enough token budget for even the header. MDC will be empty or malformed.")
        # Early exit or proceed to write minimal file? For now, proceed.

    # 1. Indexed Project Structure
    if current_total_tokens < max_total_tokens:
        try:
            structure_block = _generate_project_structure_block(cfg)
            if structure_block:
                structure_tokens = len(enc.encode(structure_block))
                if current_total_tokens + structure_tokens <= max_total_tokens:
                    final_mdc_parts.append(structure_block)
                    current_total_tokens += structure_tokens
                    logging.debug(f"Added project structure: {structure_tokens} tokens, total now {current_total_tokens}")
                else:
                    logging.info(f"Project structure section ({structure_tokens} tokens) exceeds remaining token budget. Skipping.")
        except Exception as e:
            logging.error(f"Error generating project structure: {e}")

    # 2. Preferences
    if current_total_tokens < max_total_tokens:
        try:
            prefs = load_preferences(cfg, ROOT)
            if prefs:
                prefs_lines = ["## Development Guidelines & Preferences", "", "Follow these project-specific guidelines:"]
                for k, v in prefs.items():
                    prefs_lines.append(f"- **{k}**: {v}")
                prefs_lines.append("") # Blank line after section
                
                prefs_block = "\n".join(prefs_lines) + "\n" # Add a newline to the very end of the block
                prefs_tokens = len(enc.encode(prefs_block))

                if current_total_tokens + prefs_tokens <= max_total_tokens:
                    final_mdc_parts.append(prefs_block)
                    current_total_tokens += prefs_tokens
                    logging.debug(f"Added preferences: {prefs_tokens} tokens, total now {current_total_tokens}")
                else:
                    logging.info(f"Preferences section (approx {prefs_tokens} tokens) exceeds remaining token budget. Skipping.")
            else:
                logging.info("No preferences found or 'preferences.file' not configured.")
        except Exception as e:
            logging.error(f"Error loading preferences: {e}")

    # 3. Active Tasks
    active_yaml_tasks_data = []
    if current_total_tokens < max_total_tokens:
        try:
            # Use TaskStore instead of load_tasks()
            task_store = TaskStore()
            all_yaml_tasks = task_store.get_all_tasks_as_dicts()
            active_yaml_tasks_data = [t for t in all_yaml_tasks if t.get("status") == "in_progress"]
            active_yaml_tasks_data = sorted(
                active_yaml_tasks_data,
                key=lambda t: (-t.get("progress", 0), t.get("updated_at", "")),
                reverse=True
            )[:top_tasks_k]
            
            logging.info(f"Found {len(active_yaml_tasks_data)} active tasks out of {len(all_yaml_tasks)} total tasks")

            if active_yaml_tasks_data:
                tasks_section_lines = ["## Active Tasks", "", "Current work in progress:"]
                tasks_section_header_str = "\n".join(tasks_section_lines) + "\n" # Header plus one newline
                tasks_section_header_tokens = len(enc.encode(tasks_section_header_str))
                
                temp_task_md_parts = []
                current_tasks_section_tokens = 0

                # Check if even the section header can fit
                if current_total_tokens + tasks_section_header_tokens <= max_total_tokens:
                    for task_data in active_yaml_tasks_data:
                        task_md_lines = _format_task_for_mdc(task_data)
                        # Each task is a list of lines; join them, add newline, then find tokens
                        task_md_segment = "\n".join(task_md_lines) + "\n" 
                        task_tokens = len(enc.encode(task_md_segment))
                        
                        logging.debug(f"Task #{task_data.get('id')}: '{task_data.get('title')}' requires {task_tokens} tokens")

                        # Total for section includes its own items + header, check against overall budget
                        if current_total_tokens + tasks_section_header_tokens + current_tasks_section_tokens + task_tokens <= max_total_tokens:
                            temp_task_md_parts.append(task_md_segment)
                            current_tasks_section_tokens += task_tokens
                        else:
                            logging.info(f"Task '{task_data.get('title','N/A')}' exceeds token budget. Stopping task additions.")
                            break
                    
                    if temp_task_md_parts:
                        full_tasks_section_str = tasks_section_header_str + "".join(temp_task_md_parts) + "\n" # Ensure newline after section
                        # Recalculate actual tokens for the constructed section to be precise
                        actual_full_tasks_section_tokens = len(enc.encode(full_tasks_section_str))
                        
                        # Final check with actual tokens
                        if current_total_tokens + actual_full_tasks_section_tokens <= max_total_tokens:
                            final_mdc_parts.append(full_tasks_section_str)
                            current_total_tokens += actual_full_tasks_section_tokens
                            logging.info(f"Added {len(temp_task_md_parts)} tasks to memory.mdc, used {actual_full_tasks_section_tokens} tokens.")
                        else:
                            logging.warning(f"Final tasks section: Calculated {current_total_tokens + actual_full_tasks_section_tokens} tokens exceed budget {max_total_tokens}. Section skipped.")
                    else:
                        logging.info("No tasks could fit within the token budget.")
                else:
                    logging.info(f"Tasks section header alone ({tasks_section_header_tokens} tokens) would exceed remaining token budget.")
            else:
                logging.info("No in-progress tasks found.")
        except Exception as e:
            logging.error(f"Error adding tasks to memory.mdc: {e}")

    # 3. Context (Snippets, Notes, and Code Chunks)
    context_results = []
    derived_query = None
    
    # Try to derive context from active tasks if no focus query is provided
    if current_total_tokens < max_total_tokens and not focus and active_yaml_tasks_data:
        try:
            # Derive a context query from active tasks when no focus is provided
            derived_query = _formulate_query_from_active_tasks(active_yaml_tasks_data)
            logging.info(f"Derived context query from active tasks: '{derived_query[:100]}...' ({len(derived_query)} chars)")
            
            if derived_query:
                # Use the derived query for FAISS search with appropriate predicate
                def context_predicate(meta_item):
                    item_type = meta_item.get("type", "")
                    # Only include code_chunk, snippet, and note types
                    return item_type in ["code_chunk", "snippet", "note"]
                
                # Search based on the derived query with the predicate
                logging.info(f"Searching for context with derived query, top_k={top_k_context}")
                search_results = search(derived_query, top_k=top_k_context, pred=context_predicate)
                
                if search_results:
                    logging.info(f"Found {len(search_results)} context items relevant to active tasks")
                    
                    # Format context items
                    context_section_lines = ["## Task-Relevant Context", "", "Code, snippets, and documentation most relevant to your current tasks:"]
                    context_section_header_str = "\n".join(context_section_lines) + "\n"
                    context_section_header_tokens = len(enc.encode(context_section_header_str))
                    
                    temp_context_md_parts = []
                    current_context_section_tokens = 0
                    
                    if current_total_tokens + context_section_header_tokens <= max_total_tokens:
                        for meta, score in search_results:
                            # Use updated _format_context_item_for_mdc that handles all types
                            item_md_lines = _format_context_item_for_mdc(meta)
                            # Each item is a list of lines; join them with double newlines for better separation
                            item_md_segment = "\n".join(item_md_lines) + "\n\n" 
                            item_tokens = len(enc.encode(item_md_segment))
                            
                            # Add logging to trace retrieved items
                            item_id = meta.get('id', 'N/A')
                            item_type = meta.get('type', 'unknown')
                            logging.info(f"Retrieved context item: type={item_type}, id={item_id}, score={score:.4f}, tokens={item_tokens}")
                            
                            if current_total_tokens + context_section_header_tokens + current_context_section_tokens + item_tokens <= max_total_tokens:
                                temp_context_md_parts.append(item_md_segment)
                                current_context_section_tokens += item_tokens
                                context_results.append(meta)
                            else:
                                logging.info(f"Context item ID {item_id} ({item_type}) exceeds token budget. Stopping context additions.")
                                break
                        
                        if temp_context_md_parts:
                            full_context_section_str = context_section_header_str + "".join(temp_context_md_parts)
                            # Recalculate actual tokens
                            actual_full_context_section_tokens = len(enc.encode(full_context_section_str))
                            
                            if current_total_tokens + actual_full_context_section_tokens <= max_total_tokens:
                                final_mdc_parts.append(full_context_section_str)
                                current_total_tokens += actual_full_context_section_tokens
                                logging.info(f"Added {len(context_results)} task-relevant context items to memory.mdc. Used {actual_full_context_section_tokens} tokens.")
                            else:
                                logging.warning(f"Final task-relevant context section: Calculated {current_total_tokens + actual_full_context_section_tokens} tokens exceed budget. Section skipped.")
                        else:
                            logging.info("No task-relevant context items could fit within token budget.")
                    else:
                        logging.info(f"Task-relevant context section header ({context_section_header_tokens} tokens) would exceed token budget.")
                else:
                    logging.info(f"No results found for derived task query: {derived_query[:100]}...")
            else:
                logging.info("Could not derive a meaningful context query from active tasks.")
        except Exception as e:
            logging.error(f"Error adding task-derived context to memory.mdc: {e}")
    
    # Use focus query if provided (original behavior)
    if current_total_tokens < max_total_tokens and focus:
        try:
            # Update search predicate to include code_chunk, snippet, and note types
            def context_predicate(meta_item):
                item_type = meta_item.get("type", "")
                return item_type in ["code_chunk", "snippet", "note"]
                
            # Search based on focus with the updated predicate
            logging.info(f"Searching for context with focus query: '{focus}', top_k={top_k_context}")
            search_results = search(focus, top_k=top_k_context, pred=context_predicate)
            
            # Format context items
            if search_results:
                logging.info(f"Found {len(search_results)} context items for focus '{focus}'")
                
                context_section_lines = ["## Focus-Based Context", "", f"Code and documentation relevant to: **{focus}**"]
                context_section_header_str = "\n".join(context_section_lines) + "\n"
                context_section_header_tokens = len(enc.encode(context_section_header_str))
                
                temp_context_md_parts = []
                current_context_section_tokens = 0
                
                if current_total_tokens + context_section_header_tokens <= max_total_tokens:
                    for meta, score in search_results:
                        # Use updated _format_context_item_for_mdc that handles all types
                        item_md_lines = _format_context_item_for_mdc(meta)
                        # Each item is a list of lines; join them with double newlines for better separation
                        item_md_segment = "\n".join(item_md_lines) + "\n\n" 
                        item_tokens = len(enc.encode(item_md_segment))
                        
                        # Add logging to trace retrieved items
                        item_id = meta.get('id', 'N/A')
                        item_type = meta.get('type', 'unknown')
                        logging.info(f"Retrieved context item: type={item_type}, id={item_id}, score={score:.4f}, tokens={item_tokens}")
                        
                        if current_total_tokens + context_section_header_tokens + current_context_section_tokens + item_tokens <= max_total_tokens:
                            temp_context_md_parts.append(item_md_segment)
                            current_context_section_tokens += item_tokens
                            context_results.append(meta)
                        else:
                            logging.info(f"Context item ID {item_id} ({item_type}) exceeds token budget. Stopping context additions.")
                            break
                    
                    if temp_context_md_parts:
                        full_context_section_str = context_section_header_str + "".join(temp_context_md_parts)
                        # Recalculate actual tokens
                        actual_full_context_section_tokens = len(enc.encode(full_context_section_str))
                        
                        if current_total_tokens + actual_full_context_section_tokens <= max_total_tokens:
                            final_mdc_parts.append(full_context_section_str)
                            current_total_tokens += actual_full_context_section_tokens
                            logging.info(f"Added {len(context_results)} focus-based context items to memory.mdc. Used {actual_full_context_section_tokens} tokens.")
                        else:
                            logging.warning(f"Final focus-based context section: Calculated {current_total_tokens + actual_full_context_section_tokens} tokens exceed budget. Section skipped.")
                    else:
                        logging.info("No focus-based context items could fit within token budget.")
                else:
                    logging.info(f"Focus-based context section header ({context_section_header_tokens} tokens) would exceed token budget.")
            else:
                logging.info(f"No results found for focus query: {focus}")
        except Exception as e:
            logging.error(f"Error adding focus-based context to memory.mdc: {e}")
    
    # 4. Write the final MDC file
    try:
        cursor_base = get_cursor_output_base_path(cfg)
        cursor_dir = cursor_base / ".cursor"
        rules_dir = cursor_dir / "rules"
        
        # Create all necessary directories
        rules_dir.mkdir(parents=True, exist_ok=True)
        
        # Define output path
        output_path = rules_dir / "memory.mdc"
        
        # Write output
        mdc_content = "".join(final_mdc_parts)
        output_path.write_text(mdc_content, encoding="utf-8")
        
        # Determine the context source for the success message
        context_source = "focus query" if focus else "active tasks" if derived_query else "no context"
        success_msg = f"Generated memory.mdc with {current_total_tokens} tokens. Contains {len(active_yaml_tasks_data)} tasks and {len(context_results)} context items from {context_source}."
        logging.info(success_msg)
        if not quiet:
            print(f"✅ {success_msg}")
        
        return True, success_msg, str(output_path)
    
    except Exception as e:
        error_msg = f"Failed to write memory.mdc file: {e}"
        logging.error(error_msg)
        if not quiet:
            print(f"❌ {error_msg}")
        return False, error_msg, ""

def main(args=None):
    """CLI entry point - makes it easier to use within the memex ecosystem."""
    parser = argparse.ArgumentParser(description="Generate memory.mdc based on tasks and preferences")
    parser.add_argument("--focus", "-f", help="Optional focus query to get relevant snippets/notes")
    parser.add_argument("--quiet", "-q", action="store_true", help="Suppress console output")
    parser.add_argument("--debug", "-d", action="store_true", help="Enable debug logging")
    parsed_args = parser.parse_args(args)
    
    # Set debug logging if requested
    if parsed_args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        logging.debug("Debug logging enabled")
    
    # This will exit with an error code if make() returns False and quiet=False
    make(focus=parsed_args.focus, quiet=parsed_args.quiet)

# Wrapper function for UI usage
def generate_mdc_logic(quiet=True, preview_only=False, focus_task_id=None):
    """
    Wrapper function for UI to generate memory.mdc with additional options.
    
    Args:
        quiet: If True, suppress console output
        preview_only: If True, return context items without saving file
        focus_task_id: Optional task ID to focus context on
        
    Returns:
        Tuple of (success, message, context_items)
    """
    # For now, just call make() - we'll enhance this later
    if preview_only:
        # TODO: Implement preview mode that returns context items without saving
        return True, "Preview mode not yet implemented", {}
    
    # Generate focus query from task if provided
    focus = None
    if focus_task_id:
        try:
            ts = TaskStore()
            task = ts.get_task(focus_task_id) if hasattr(ts, 'get_task') else None
            if task:
                focus = task.get('title', '') if isinstance(task, dict) else getattr(task, 'title', '')
        except:
            pass
    
    success, message, path = make(focus=focus, quiet=quiet)
    return success, message, {}

if __name__ == "__main__":
    main()