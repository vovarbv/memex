import gradio as gr
import logging
from typing import Dict, List, Any, Optional, Tuple
import re

# Import the shared utility functions
from .shared_utils import try_import_with_prefix, import_memory_utils, format_success_message, format_error_message, format_warning_message

def create_memory_tab(ts, cfg, data_integrity_error=None):
    """Creates the unified Memory tab for managing snippets and notes.
    
    Based on README.md philosophy:
    - Zero-friction capture
    - No titles needed (auto-generated from content)
    - Simple, clean interface
    - Focus on content, not metadata
    """
    # Import required functions
    try:
        memory_utils = import_memory_utils()
        search = getattr(memory_utils, 'search', None)
        add_or_replace = getattr(memory_utils, 'add_or_replace', None)
        count_items = getattr(memory_utils, 'count_items', None)
        
        # Log what we got
        logging.info(f"Memory tab imports: search={search is not None}, add_or_replace={add_or_replace is not None}, count_items={count_items is not None}")
        
        if not search:
            logging.error("search function is None - memory tab will not work correctly")
        
        # Try to import optional functions with individual error handling
        add_memory_func = None
        add_snippet_func = None
        get_task_context_query = None
        
        try:
            add_memory_module = try_import_with_prefix("add_memory", ["scripts.", ".scripts.", "memex.scripts."])
            if add_memory_module and hasattr(add_memory_module, 'add_memory_logic'):
                add_memory_func = add_memory_module.add_memory_logic
        except Exception as e:
            logging.warning(f"Could not import add_memory: {e}")
            
        try:
            add_snippet_module = try_import_with_prefix("add_snippet", ["scripts.", ".scripts.", "memex.scripts."])
            if add_snippet_module and hasattr(add_snippet_module, 'add_snippet_logic'):
                add_snippet_func = add_snippet_module.add_snippet_logic
        except Exception as e:
            logging.warning(f"Could not import add_snippet: {e}")
            
        try:
            preview_module = try_import_with_prefix("gen_memory_mdc_preview", ["scripts.", ".scripts.", "memex.scripts."])
            if preview_module and hasattr(preview_module, 'get_task_context_query'):
                get_task_context_query = preview_module.get_task_context_query
        except Exception as e:
            logging.warning(f"Could not import gen_memory_mdc_preview: {e}")
            
    except Exception as e:
        logging.error(f"Critical error importing core memory tab dependencies: {e}")
        # Only reset core functions if there's a critical error
        if not search:
            search = None
            add_or_replace = None
            count_items = None
    
    # Header
    gr.Markdown("## 💾 Memory Hub")
    gr.Markdown("*Unified interface for all your memory items - snippets, notes, and context*")
    
    if data_integrity_error:
        gr.Markdown(f"⚠️ **Data Issue**: {data_integrity_error}")
        gr.Markdown("Some features may be limited. Please check your data files.")
    
    # Quick capture section - simplified per README
    with gr.Group():
        gr.Markdown("### ⚡ Quick Capture")
        gr.Markdown("*Paste code or write notes - type is auto-detected*")
        
        # Universal capture box
        capture_content = gr.Textbox(
            label="",
            placeholder="Paste code snippet or type note...",
            lines=8,
            max_lines=15
        )
        
        with gr.Row():
            # Type detection and capture
            with gr.Column(scale=1):
                type_override = gr.Dropdown(
                    choices=[("Auto-detect", "auto"), ("Code", "code"), ("Note", "note")],
                    value="auto",
                    label="Type"
                )
                
                language_detected = gr.Textbox(
                    label="Language",
                    placeholder="Auto-detected for code",
                    interactive=True
                )
                
            # Capture button and status
            with gr.Column(scale=2):
                capture_button = gr.Button("💾 Capture to Memory", variant="primary", size="lg")
                capture_status = gr.Markdown("")
                
        # Hidden fields for compatibility
        capture_title = gr.Textbox(value="", visible=False)
        capture_tags = gr.Textbox(value="", visible=False)
        detected_type = gr.Markdown(visible=False)
    
    # Search and filter section
    with gr.Group():
        gr.Markdown("### 🔍 Search & Browse")
        
        with gr.Row():
            search_query = gr.Textbox(
                label="Search Memory",
                placeholder="Search all your memory items...",
                scale=3
            )
            
            search_button = gr.Button("🔍 Search", scale=1)
            
        with gr.Row():
            # Task filter (NEW!)
            task_filter = gr.Dropdown(
                choices=[("All Items", "all")],
                value="all",
                label="🎯 Filter by Task",
                info="Show items related to a specific task"
            )
            
            # Type filter
            type_filter = gr.Dropdown(
                choices=[
                    ("All Types", "all"),
                    ("Code Snippets", "snippet"),
                    ("Notes & Text", "note"),
                    ("Code Chunks", "code_chunk")
                ],
                value="all",
                label="Type Filter"
            )
            
            # Language filter (for code items)
            language_filter = gr.Dropdown(
                choices=[("All Languages", "all")],
                value="all",
                label="Language Filter"
            )
            
        with gr.Row():            
            # Usage filter
            usage_filter = gr.Dropdown(
                choices=[
                    ("All Items", "all"),
                    ("Recently Used", "recent"),
                    ("Frequently Used", "frequent"),
                    ("Unused", "unused")
                ],
                value="all",
                label="Usage Filter"
            )
            
            # Sort options
            sort_option = gr.Dropdown(
                choices=[
                    ("Relevance", "relevance"),
                    ("Recently Added", "recent"),
                    ("Most Used", "usage"),
                    ("Alphabetical", "alpha")
                ],
                value="relevance",
                label="Sort By"
            )
    
    # Results section
    with gr.Group():
        gr.Markdown("### 📋 Memory Items")
        
        # Results summary
        results_summary = gr.Markdown("Loading memory items...")
        
        # Results display
        results_display = gr.HTML("")
        
        # Pagination controls - improved layout
        with gr.Row():
            with gr.Column(scale=1):
                prev_button = gr.Button("← Previous", variant="secondary")
            with gr.Column(scale=2, elem_classes=["center-text"]):
                page_info = gr.Markdown("Page 1 of 1")
            with gr.Column(scale=1):
                next_button = gr.Button("Next →", variant="secondary")
        
        # Quick Stats
        gr.Markdown("### 📊 Statistics")
        quick_stats = gr.Markdown("Loading statistics...")
    
    # State management
    current_page = gr.State(value=1)
    last_search_results = gr.State(value=[])
    total_pages_state = gr.State(value=1)
    
    # Helper functions
    def detect_content_type(content: str) -> Tuple[str, str, str]:
        """Auto-detect content type, language, and suggest title."""
        content = content.strip()
        
        if not content:
            return "note", "", ""
        
        # Check for code patterns
        code_indicators = [
            r'^(import|from|#include|using|package)',
            r'(def|function|class|interface|struct)\s+\w+',
            r'[{}\[\]();]',
            r'^\s*(if|for|while|try|catch)\s*\(',
            r'//|/\*|\*\/|#\s|"""',
        ]
        
        is_code = any(re.search(pattern, content, re.MULTILINE | re.IGNORECASE) 
                     for pattern in code_indicators)
        
        # Detect language for code
        language = ""
        if is_code:
            if re.search(r'(def |import |from |\.py$)', content):
                language = "python"
            elif re.search(r'(function |var |let |const |\.js$)', content):
                language = "javascript"
            elif re.search(r'(public class|import java)', content):
                language = "java"
            elif re.search(r'(#include|int main|std::)', content):
                language = "cpp"
            elif re.search(r'(\$\w+|echo |\.php$)', content):
                language = "php"
            elif re.search(r'(SELECT|FROM|WHERE|INSERT)', content, re.IGNORECASE):
                language = "sql"
            elif re.search(r'(<html|<div|<script)', content, re.IGNORECASE):
                language = "html"
            elif re.search(r'(\.css$|{[^}]*:[^}]*})', content):
                language = "css"
            else:
                language = "text"
        
        # Don't generate title per README - keep it simple
        title = ""
        
        return "code" if is_code else "note", language, title
    
    def format_memory_items(items: List[Dict], page: int = 1, per_page: int = 10) -> Tuple[str, str, int]:
        """Format memory items for display - showing ID as title or existing title."""
        if not items:
            return "<p>No memory items found. Try adjusting your search or filters.</p>", "No items found", 1
        
        # Pagination
        total_pages = (len(items) + per_page - 1) // per_page
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        page_items = items[start_idx:end_idx]
        
        # Format items with clean, simple design
        html_parts = []
        for i, item in enumerate(page_items):
            item_type = item.get('type', 'unknown')
            content = item.get('content', '')
            # Handle both flat structure (language at top level) and nested structure (language in metadata)
            language = item.get('language', '')
            if not language and 'metadata' in item:
                language = item['metadata'].get('language', '')
            score = item.get('score', 0)
            item_id = item.get('id', 'N/A')
            is_semantic_search = item.get('is_semantic_search', False)
            
            # Use title if available, otherwise use ID
            title = item.get('title', '') or item_id
            
            # Clean content - remove duplicate ID lines
            cleaned_content = content
            content_lines = content.strip().split('\n')
            
            # Remove any lines that are just the ID (with or without #)
            filtered_lines = []
            for line in content_lines:
                line_stripped = line.strip()
                if line_stripped != f"#{item_id}" and line_stripped != item_id:
                    filtered_lines.append(line)
            
            cleaned_content = '\n'.join(filtered_lines).strip()
            
            # Type icon
            type_icons = {
                'snippet': '🔧',
                'note': '📝',
                'code_chunk': '📁'
            }
            icon = type_icons.get(item_type, '📄')
            
            # Clean display with title
            html_parts.append(f"""
            <div style="border: 1px solid #e0e0e0; border-radius: 6px; margin: 8px 0; background: #ffffff; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
                <div style="display: flex; justify-content: space-between; align-items: center; padding: 10px 12px; border-bottom: 1px solid #f0f0f0;">
                    <div style="display: flex; align-items: center; gap: 8px;">
                        <span style="font-size: 14px;">{icon}</span>
                        <span style="font-weight: 500; color: #333; word-break: break-all;">
                            {title}
                        </span>
                        <span style="background: #f5f5f5; color: #666; padding: 3px 10px; border-radius: 14px; font-size: 12px; font-weight: 500;">
                            {item_type.replace('_', ' ').upper()}
                        </span>
                        {f'<span style="background: #e8f5e9; color: #2e7d32; padding: 3px 10px; border-radius: 14px; font-size: 12px;">{language}</span>' if language else ''}
                    </div>
                    <div style="font-size: 11px; color: #999;">
                        {f'relevance: {score:.3f}' if is_semantic_search and score != 1.0 else f'#{item_id}' if item_id != 'N/A' else ''}
                    </div>
                </div>
                <div style="padding: 12px; background: #f8f9fa; font-family: 'SF Mono', Consolas, monospace; white-space: pre-wrap; max-height: 400px; overflow-y: auto; font-size: 13px; line-height: 1.5;">
{cleaned_content}
                </div>
            </div>
            """)
        
        results_html = "\n".join(html_parts)
        
        # Summary
        summary = f"Showing {len(page_items)} of {len(items)} memory items (Page {page} of {total_pages})"
        
        return results_html, summary, total_pages
    
    def search_memory_items(query: str = "", task_filter: str = "all", type_filter: str = "all", language_filter: str = "all", 
                           usage_filter: str = "all", sort_option: str = "relevance") -> List[Dict]:
        """Search and filter memory items."""
        logging.info(f"[memory_tab] search_memory_items called with query='{query}', task_filter='{task_filter}', has_query={bool(query.strip())}")
        
        if not search:
            logging.error("[memory_tab] search function is None - cannot perform search")
            return []
        
        try:
            # Handle task-based filtering
            if task_filter != "all" and get_task_context_query:
                # Use the task to generate a semantic query
                task_query = get_task_context_query(task_filter, ts)
                if task_query:
                    logging.info(f"[memory_tab] Using task-based query: '{task_query}'")
                    # Override the query with task context
                    query = task_query
                else:
                    logging.warning(f"[memory_tab] Could not generate query for task {task_filter}")
                    return []
            # Define predicates for filtering
            def create_predicate(type_filter, language_filter):
                def predicate(meta):
                    # Type filter
                    if type_filter != "all":
                        actual_type = meta.get('type', '')
                        if type_filter == "snippet":
                            if actual_type not in ['snippet', 'code_snippet']:
                                return False
                        elif type_filter == "note":
                            if actual_type not in ['note', 'memory']:
                                return False
                        elif type_filter == "code_chunk":
                            if actual_type != 'code_chunk':
                                return False
                        else:
                            if actual_type != type_filter:
                                return False
                    
                    # Language filter
                    if language_filter != "all":
                        # Handle both flat structure (language at top level) and nested structure (language in metadata)
                        lang = meta.get('language', '')
                        if not lang and 'metadata' in meta:
                            lang = meta['metadata'].get('language', '')
                        if lang.lower() != language_filter.lower():
                            return False
                    
                    return True
                return predicate
            
            # Search with appropriate predicate
            predicate = create_predicate(type_filter, language_filter)
            
            if query.strip():
                results = search(query, top_k=100, pred=predicate)
                items = []
                for meta, score in results:
                    meta['score'] = score
                    meta['is_semantic_search'] = True
                    items.append(meta)
                
                # Debug log for search results
                logging.info(f"[memory_tab] Semantic search with query '{query}' returned {len(items)} items")
            else:
                # Get all items if no query - increase limit to get all items
                logging.info(f"[memory_tab] Searching with empty query, type_filter='{type_filter}', language_filter='{language_filter}'")
                
                # First try without predicate to see what we get
                if type_filter == "all" and language_filter == "all":
                    # No filtering needed
                    results = search("", top_k=10000, pred=None)
                else:
                    # Apply filters
                    results = search("", top_k=10000, pred=predicate)
                
                items = []
                if results:
                    logging.info(f"[memory_tab] Raw search returned {len(results)} results")
                    # Debug: Log types of first few items
                    for i, (meta, score) in enumerate(results[:5]):
                        logging.info(f"[memory_tab] Raw result {i}: type='{meta.get('type')}', id='{meta.get('id')}'")
                    
                    for meta, score in results:
                        # Mark whether this was a semantic search (with query) or browsing (no query)
                        meta['score'] = score
                        meta['is_semantic_search'] = bool(query.strip())
                        items.append(meta)
                else:
                    logging.warning("[memory_tab] Search returned None or empty results")
            
            # Log the number of items found
            logging.info(f"[memory_tab] Search found {len(items)} items for query='{query}', type_filter='{type_filter}', language_filter='{language_filter}'")
            
            # Apply usage filter
            if usage_filter == "recent":
                items = [item for item in items if item.get('usage_count', 0) > 0]
            elif usage_filter == "frequent":
                items = [item for item in items if item.get('usage_count', 0) > 5]
            elif usage_filter == "unused":
                items = [item for item in items if item.get('usage_count', 0) == 0]
            
            # Sort items
            if sort_option == "recent":
                items.sort(key=lambda x: x.get('timestamp', 0), reverse=True)
            elif sort_option == "usage":
                items.sort(key=lambda x: x.get('usage_count', 0), reverse=True)
            elif sort_option == "alpha":
                items.sort(key=lambda x: x.get('content', '')[:50].lower())
            # Default is relevance (already sorted by search score)
            
            return items
            
        except Exception as e:
            logging.error(f"Error searching memory items: {e}")
            return []
    
    def get_quick_stats(items: List[Dict]) -> str:
        """Generate quick statistics about memory items."""
        if not items:
            return "No items to analyze"
        
        # Count by type
        type_counts = {}
        total_usage = 0
        languages = set()
        
        for item in items:
            item_type = item.get('type', 'unknown')
            type_counts[item_type] = type_counts.get(item_type, 0) + 1
            total_usage += item.get('usage_count', 0)
            
            # Handle both flat and nested language field
            lang = item.get('language')
            if not lang and 'metadata' in item:
                lang = item.get('metadata', {}).get('language')
            if lang:
                languages.add(lang)
        
        stats_lines = [
            f"**Total Items**: {len(items)}",
            f"**Languages**: {len(languages)}",
            "",
            "**By Type**:"
        ]
        
        for item_type, count in sorted(type_counts.items()):
            stats_lines.append(f"- {item_type.replace('_', ' ').title()}: {count}")
        
        return "\n".join(stats_lines)
    
    # Event handlers
    def on_content_change(content: str):
        """Handle content change in capture box - auto-detect type."""
        if not content.strip():
            return "", ""
        
        content_type, language, _ = detect_content_type(content)
        return language if content_type == "code" else ""
    
    def on_capture(content, type_override, language, title, tags):
        """Capture memory item."""
        if not content.strip():
            return format_warning_message("Please enter some content to capture"), content, language, title, tags
        
        try:
            # Auto-detect if needed
            if type_override == "auto":
                detected_type, detected_lang, _ = detect_content_type(content)
                actual_type = detected_type
                if detected_type == "code" and detected_lang and not language:
                    language = detected_lang
            else:
                actual_type = type_override
            
            # Add the item
            if actual_type == "code":
                if add_snippet_func:
                    success, message = add_snippet_func(content, language=language)
                else:
                    return format_error_message("Snippet capture not available"), content, language, title, tags
            else:
                if add_memory_func:
                    success, message = add_memory_func(content)
                else:
                    return format_error_message("Note capture not available"), content, language, title, tags
            
            if success:
                return (
                    format_success_message(message),
                    "",  # Clear content
                    "",  # Clear language
                    "",  # Clear title
                    ""   # Clear tags
                )
            else:
                return format_error_message(message), content, language, title, tags
                
        except Exception as e:
            logging.error(f"Error capturing memory item: {e}")
            return format_error_message(f"Capture failed: {str(e)}"), content, language, title, tags
    
    def on_search(query: str, task_filter: str, type_filter: str, language_filter: str, usage_filter: str, sort_option: str, page: int = 1):
        """Handle search and filtering."""
        items = search_memory_items(query, task_filter, type_filter, language_filter, usage_filter, sort_option)
        results_html, summary, total_pages = format_memory_items(items, page)
        stats = get_quick_stats(items)
        page_text = f"Page {page} of {total_pages}"
        
        # Update pagination button states
        prev_interactive = page > 1
        next_interactive = page < total_pages
        
        return (
            results_html,           # results_display
            summary,               # results_summary
            stats,                 # quick_stats
            page_text,            # page_info
            items,                # last_search_results
            page,                 # current_page
            total_pages,          # total_pages_state
            gr.update(interactive=prev_interactive),  # prev_button
            gr.update(interactive=next_interactive)   # next_button
        )
    
    def on_prev_page(query: str, task_filter: str, type_filter: str, language_filter: str, usage_filter: str, sort_option: str, current_pg: int, total_pages: int):
        """Handle previous page navigation."""
        new_page = max(1, current_pg - 1)
        return on_search(query, task_filter, type_filter, language_filter, usage_filter, sort_option, new_page)
    
    def on_next_page(query: str, task_filter: str, type_filter: str, language_filter: str, usage_filter: str, sort_option: str, current_pg: int, total_pages: int):
        """Handle next page navigation."""
        new_page = min(total_pages, current_pg + 1) if total_pages > 0 else 1
        return on_search(query, task_filter, type_filter, language_filter, usage_filter, sort_option, new_page)
    
    # Function to populate task filter dropdown
    def get_task_choices():
        """Get choices for task filter dropdown."""
        choices = [("All Items", "all")]
        try:
            if ts and hasattr(ts, 'tasks'):
                for task in ts.tasks:
                    if hasattr(task, 'status') and task.status in ['in_progress', 'todo']:
                        task_id = getattr(task, 'id', 'unknown')
                        task_title = getattr(task, 'title', f'Task {task_id}')
                        # Truncate long titles
                        if len(task_title) > 50:
                            task_title = task_title[:47] + "..."
                        choices.append((f"#{task_id}: {task_title}", str(task_id)))
        except Exception as e:
            logging.error(f"Error loading tasks for filter: {e}")
        return choices
    
    # Populate task filter
    task_filter.choices = get_task_choices()
    
    # Connect event handlers
    capture_content.change(
        on_content_change,
        inputs=[capture_content],
        outputs=[language_detected]
    )
    
    capture_button.click(
        on_capture,
        inputs=[capture_content, type_override, language_detected, capture_title, capture_tags],
        outputs=[capture_status, capture_content, language_detected, capture_title, capture_tags]
    )
    
    search_button.click(
        on_search,
        inputs=[search_query, task_filter, type_filter, language_filter, usage_filter, sort_option, current_page],
        outputs=[results_display, results_summary, quick_stats, page_info, last_search_results, current_page, total_pages_state, prev_button, next_button]
    )
    
    # Pagination handlers
    prev_button.click(
        on_prev_page,
        inputs=[search_query, task_filter, type_filter, language_filter, usage_filter, sort_option, current_page, total_pages_state],
        outputs=[results_display, results_summary, quick_stats, page_info, last_search_results, current_page, total_pages_state, prev_button, next_button]
    )
    
    next_button.click(
        on_next_page,
        inputs=[search_query, task_filter, type_filter, language_filter, usage_filter, sort_option, current_page, total_pages_state],
        outputs=[results_display, results_summary, quick_stats, page_info, last_search_results, current_page, total_pages_state, prev_button, next_button]
    )
    
    # Auto-search on filter changes (reset to page 1)
    def on_filter_change(query: str, task_f: str, type_f: str, lang_f: str, usage_f: str, sort_o: str):
        return on_search(query, task_f, type_f, lang_f, usage_f, sort_o, 1)
    
    for component in [task_filter, type_filter, language_filter, usage_filter, sort_option]:
        component.change(
            on_filter_change,
            inputs=[search_query, task_filter, type_filter, language_filter, usage_filter, sort_option],
            outputs=[results_display, results_summary, quick_stats, page_info, last_search_results, current_page, total_pages_state, prev_button, next_button]
        )
    
    # Initial load
    def refresh_memory():
        """Refresh the memory tab."""
        try:
            # Get all items without filtering
            items = search_memory_items()
            logging.info(f"[memory_tab] refresh_memory: Found {len(items)} items")
            
            # Debug: Log first few items
            if items:
                for i, item in enumerate(items[:3]):
                    logging.info(f"[memory_tab] Sample item {i}: type={item.get('type')}, id={item.get('id')}, has_content={bool(item.get('content'))}, is_semantic={item.get('is_semantic_search', False)}, score={item.get('score', 0)}")
            
            results_html, summary, total_pages = format_memory_items(items)
            stats = get_quick_stats(items)
            prev_interactive = False  # Page 1
            next_interactive = total_pages > 1
            return (
                results_html,           # results_display
                summary,               # results_summary
                stats,                 # quick_stats
                f"Page 1 of {total_pages}",  # page_info
                items,                # last_search_results
                1,                    # current_page
                total_pages,          # total_pages_state
                gr.update(interactive=prev_interactive),  # prev_button
                gr.update(interactive=next_interactive)   # next_button
            )
        except Exception as e:
            logging.error(f"[memory_tab] Error in refresh_memory: {e}", exc_info=True)
            raise
    
    # Load initial data
    try:
        # First check if we can count items
        if count_items:
            total_count = count_items()
            logging.info(f"[memory_tab] Total items in index: {total_count}")
        
        # Initial load with all items (no filtering)
        items = search_memory_items()
        results_html, summary, total_pages = format_memory_items(items)
        stats = get_quick_stats(items)
        
        results_display.value = results_html
        results_summary.value = summary
        quick_stats.value = stats
        page_info.value = f"Page 1 of {total_pages}"
        prev_button.interactive = False  # Page 1
        next_button.interactive = total_pages > 1
        
        # Initialize state variables
        current_page.value = 1
        last_search_results.value = items
        total_pages_state.value = total_pages
    except Exception as e:
        logging.error(f"Error loading initial memory data: {e}")
        results_display.value = "<p>Error loading memory items</p>"
        results_summary.value = "Error loading data"
        quick_stats.value = "Statistics unavailable"
    
    # Return references
    return {
        "refresh": refresh_memory,
        "components": {
            "capture_content": capture_content,
            "search_query": search_query,
            "task_filter": task_filter,
            "results_display": results_display,
            "results_summary": results_summary,
            "quick_stats": quick_stats,
            "capture_status": capture_status
        }
    }