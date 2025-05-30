import gradio as gr
import logging
from typing import Dict, List, Any, Optional
import json

# Import the shared utility functions
from .shared_utils import try_import_with_prefix, import_memory_utils

# Import safe expression evaluator
from ..scripts.safe_eval import safe_eval, validate_expression

def create_search_tab(ts, cfg, data_integrity_error=None):
    """Creates a unified Search tab UI with essential filtering and display options.
    
    Args:
        ts: TaskStore instance
        cfg: Configuration dictionary
        data_integrity_error: Data integrity error message, if any
        
    Returns:
        dict: A dictionary containing references to the refresh function and components
    """
    # Import required functions
    try:
        # Get memory_utils functions
        memory_utils = import_memory_utils()
        search = memory_utils.search
        count_items = memory_utils.count_items
    except Exception as e:
        logging.error(f"Error importing search tab dependencies: {e}")
        search = None
        count_items = None
    
    # Title and description
    gr.Markdown("## Search & Advanced Filters")
    gr.Markdown("Search your knowledge base with powerful filtering options including status, priority, and content type filters.")
    
    # Search interface - prominent and simple
    with gr.Row():
        with gr.Column(scale=4):
            search_input = gr.Textbox(
                label="Search Query", 
                placeholder="Enter search term or leave empty to view all items...", 
                lines=1
            )
            
        with gr.Column(scale=1):
            search_button = gr.Button("🔍 Search", variant="primary")
    
    # Core Filters Section - Always visible essential filters
    with gr.Row():
        with gr.Column(scale=1):
            type_filter = gr.Dropdown(
                choices=["all", "task", "snippet", "note", "code_chunk"], 
                label="Content Type", 
                value="all"
            )
            
        with gr.Column(scale=1):
            status_filter = gr.Dropdown(
                choices=["all", "todo", "in_progress", "done"], 
                label="Status Filter", 
                value="all"
            )
                
        with gr.Column(scale=1):
            priority_filter = gr.Dropdown(
                choices=["all", "high", "medium", "low"], 
                label="Priority Filter", 
                value="all"
            )
            
        with gr.Column(scale=1):
            top_k = gr.Slider(
                minimum=5, 
                maximum=50, 
                value=10, 
                step=5, 
                label="Results per Page"
            )
    
    # Advanced options (initially collapsed)
    with gr.Accordion("Advanced Options", open=False):
        with gr.Row():
            with gr.Column(scale=1):
                language_filter = gr.Dropdown(
                    choices=["all", "python", "javascript", "typescript", "html", "css", "bash", "sql", "markdown", "java"], 
                    label="Language", 
                    value="all"
                )
                
            with gr.Column(scale=1):
                show_scores = gr.Checkbox(
                    label="Show Relevance Scores", 
                    value=True
                )
        
        with gr.Row():
            with gr.Column():
                custom_filter = gr.Textbox(
                    label="Custom Filter Expression", 
                    placeholder="Example: meta_item.get('type') == 'snippet' and 'api' in meta_item.get('content', '')",
                    lines=2,
                    info="Only safe operations: comparisons, boolean logic, get(), in, string methods"
                )
                
                with gr.Row():
                    validate_filter_btn = gr.Button("Validate", scale=1)
                    filter_validation_status = gr.Textbox(
                        label="Validation Status",
                        interactive=False,
                        scale=3
                    )
    
    # Display options and token tracking
    with gr.Row():
        with gr.Column(scale=2):
            display_format = gr.Radio(
                choices=["markdown", "detailed_json"],
                label="Display Format",
                value="markdown"
            )
        
        with gr.Column(scale=1):
            token_budget = gr.Markdown("**Search Tips:**\n- Use specific terms\n- Try different filters\n- Check custom expressions")
    
    # Results display with pagination
    gr.Markdown("### Results")
    search_results = gr.Markdown("Enter a search query and click Search.")
    
    # Pagination controls
    with gr.Row():
        prev_page_button = gr.Button("< Previous")
        page_indicator = gr.Markdown("Page 1")
        next_page_button = gr.Button("Next >")
    
    # Hidden state variables
    current_page = gr.State(value=1)
    total_results = gr.State(value=0)
    current_query = gr.State(value="")
    
    # Validate filter expression
    def validate_filter_expression(expression):
        if not expression.strip():
            return "ℹ️ No expression to validate"
        
        error = validate_expression(expression)
        if error:
            return f"❌ Invalid: {error}"
        else:
            return "✅ Valid expression"
    
    # Connect validation button
    validate_filter_btn.click(
        validate_filter_expression,
        inputs=[custom_filter],
        outputs=[filter_validation_status]
    )
    
    # Search function
    def perform_search(query, page, type_value, status_value, priority_value, language_value, 
                      max_results, use_scores, custom_filter_expr, display_fmt):
        if not search:
            return "❌ Search functionality not available.", "Page 1", 0, query
        
        try:
            # Build predicate based on filters
            def combined_predicate(meta_item):
                # Type filter
                if type_value != "all" and meta_item.get("type") != type_value:
                    return False
                
                # Status filter (applies to tasks primarily)
                if status_value != "all" and meta_item.get("status") != status_value:
                    return False
                
                # Priority filter (applies to tasks primarily)
                if priority_value != "all" and meta_item.get("priority", "").lower() != priority_value:
                    return False
                
                # Language filter (applies to snippets and code chunks)
                if language_value != "all" and meta_item.get("language", "").lower() != language_value:
                    return False
                
                # Custom filter if provided
                if custom_filter_expr.strip():
                    try:
                        return safe_eval(custom_filter_expr, {"meta_item": meta_item})
                    except Exception as e:
                        logging.error(f"Custom filter evaluation error: {e}")
                        # If the filter fails, we'll include the item by default
                        return True
                
                return True
            
            # Calculate offset for pagination
            page_size = max_results
            offset = (page - 1) * page_size
            
            # Run search with combined filters
            all_results = search(query, top_k=1000, pred=combined_predicate)
            total = len(all_results)
            
            # Get current page results
            page_results = all_results[offset:offset + page_size]
            
            # Format the results based on display format
            if not page_results:
                if total > 0:
                    return "No more results on this page.", f"Page {page} (end of results)", total, query
                else:
                    return "No results match your search criteria.", "Page 1", 0, query
            
            if display_fmt == "markdown":
                output = f"### Search Results ({total} total, showing {len(page_results)})\n\n"
                
                for i, (meta, score) in enumerate(page_results, offset + 1):
                    item_type = meta.get("type", "unknown")
                    item_id = meta.get("id", "unknown")
                    
                    # Add score if requested
                    score_text = f" (Score: {score:.2f})" if use_scores else ""
                    
                    if item_type == "task":
                        title = meta.get("title", "Untitled Task")
                        status = meta.get("status", "unknown")
                        priority = meta.get("priority", "")
                        
                        # Icons for visual distinction
                        status_icon = "✅" if status == "done" else "🔄" if status == "in_progress" else "⏱️"
                        priority_icon = "🔥" if priority.lower() == "high" else "⚡" if priority.lower() == "medium" else "🔄"
                        
                        output += f"#### {i}. Task: {title}{score_text}\n\n"
                        output += f"**Status**: {status_icon} {status.capitalize()}\n\n"
                        output += f"**Priority**: {priority_icon} {priority.capitalize()}\n\n"
                        
                        # Add description if available
                        desc = meta.get("description", "")
                        if desc:
                            # Don't truncate description anymore
                            output += f"**Description**: {desc}\n\n"
                    
                    elif item_type == "snippet" or item_type == "code_chunk":
                        language = meta.get("language", "")
                        content = meta.get("content", "")
                        title = meta.get("title", f"{item_type.capitalize()} {item_id}")
                        
                        # Don't truncate content anymore
                        # Format with syntax highlighting
                        output += f"#### {i}. {title}{score_text}\n\n"
                        if language:
                            output += f"**Language**: {language}\n\n"
                        
                        output += f"```{language}\n{content}\n```\n\n"
                    
                    elif item_type == "note":
                        title = meta.get("title", "Untitled Note")
                        content = meta.get("content", "")
                        
                        # Don't truncate content anymore
                        output += f"#### {i}. Note: {title}{score_text}\n\n"
                        output += content + "\n\n"
                    
                    else:
                        # Generic item display for unknown types
                        output += f"#### {i}. {item_type.capitalize()} {item_id}{score_text}\n\n"
                        
                        # Show relevant metadata fields
                        for key, value in meta.items():
                            if key not in ["id", "type"] and value:
                                # Don't truncate metadata values anymore
                                output += f"**{key}**: {value}\n\n"
                    
                    # Add separator between results
                    output += "---\n\n"
                
                return output, f"Page {page} of {(total + page_size - 1) // page_size}", total, query
            
            else:  # JSON format
                # Format as formatted JSON for easier reading
                formatted_results = []
                
                for meta, score in page_results:
                    result_dict = dict(meta)
                    
                    # Add score if requested
                    if use_scores:
                        result_dict["score"] = round(score, 4)
                    
                    # Don't truncate content in JSON anymore
                    formatted_results.append(result_dict)
                
                # Convert to formatted JSON string
                json_str = json.dumps(formatted_results, indent=2)
                output = f"### Search Results ({total} total, showing {len(page_results)})\n\n```json\n{json_str}\n```"
                
                return output, f"Page {page} of {(total + page_size - 1) // page_size}", total, query
        
        except Exception as e:
            error_message = f"❌ Error performing search: {str(e)}"
            logging.error(error_message)
            return error_message, "Page 1", 0, query
    
    # Navigation functions
    def go_to_prev_page(current_pg, stored_query, type_val, status_val, priority_val, 
                       language_val, max_results, use_scores, custom_filter_expr, 
                       display_fmt, total_res):
        if current_pg <= 1:
            return 1, search_results.value, page_indicator.value, total_res, stored_query
        
        new_page = current_pg - 1
        results, page_text, total, query = perform_search(
            stored_query, new_page, type_val, status_val, priority_val, 
            language_val, max_results, use_scores, custom_filter_expr, 
            display_fmt
        )
        
        return new_page, results, page_text, total, query
    
    def go_to_next_page(current_pg, stored_query, type_val, status_val, priority_val, 
                       language_val, max_results, use_scores, custom_filter_expr, 
                       display_fmt, total_res):
        # Calculate max page
        page_size = max_results
        max_page = (total_res + page_size - 1) // page_size if total_res > 0 else 1
        
        if current_pg >= max_page:
            return current_pg, search_results.value, page_indicator.value, total_res, stored_query
        
        new_page = current_pg + 1
        results, page_text, total, query = perform_search(
            stored_query, new_page, type_val, status_val, priority_val, 
            language_val, max_results, use_scores, custom_filter_expr, 
            display_fmt
        )
        
        return new_page, results, page_text, total, query
    
    # Handle search button click
    def handle_search_click(query, type_val, status_val, priority_val, language_val, 
                           max_results, use_scores, custom_filter_expr, display_fmt):
        # Reset to page 1 for new searches
        results, page_text, total, stored_query = perform_search(
            query, 1, type_val, status_val, priority_val, language_val,
            max_results, use_scores, custom_filter_expr, display_fmt
        )
        
        return 1, results, page_text, total, query
    
    # Connect buttons
    search_button.click(
        handle_search_click,
        inputs=[
            search_input, type_filter, status_filter, priority_filter,
            language_filter, top_k, show_scores, custom_filter,
            display_format
        ],
        outputs=[
            current_page, search_results, page_indicator, total_results, current_query
        ]
    )
    
    # Auto-trigger search when filters change for better UX
    type_filter.change(
        handle_search_click,
        inputs=[
            search_input, type_filter, status_filter, priority_filter,
            language_filter, top_k, show_scores, custom_filter,
            display_format
        ],
        outputs=[
            current_page, search_results, page_indicator, total_results, current_query
        ]
    )
    
    status_filter.change(
        handle_search_click,
        inputs=[
            search_input, type_filter, status_filter, priority_filter,
            language_filter, top_k, show_scores, custom_filter,
            display_format
        ],
        outputs=[
            current_page, search_results, page_indicator, total_results, current_query
        ]
    )
    
    priority_filter.change(
        handle_search_click,
        inputs=[
            search_input, type_filter, status_filter, priority_filter,
            language_filter, top_k, show_scores, custom_filter,
            display_format
        ],
        outputs=[
            current_page, search_results, page_indicator, total_results, current_query
        ]
    )
    
    prev_page_button.click(
        go_to_prev_page,
        inputs=[
            current_page, current_query, type_filter, status_filter, 
            priority_filter, language_filter, top_k, show_scores, 
            custom_filter, display_format, total_results
        ],
        outputs=[
            current_page, search_results, page_indicator, total_results, current_query
        ]
    )
    
    next_page_button.click(
        go_to_next_page,
        inputs=[
            current_page, current_query, type_filter, status_filter, 
            priority_filter, language_filter, top_k, show_scores, 
            custom_filter, display_format, total_results
        ],
        outputs=[
            current_page, search_results, page_indicator, total_results, current_query
        ]
    )
    
    # Refresh function for external use
    def refresh_search():
        return None
    
    # Return component references for main app
    return {
        "refresh": refresh_search,
        "components": {
            "search_input": search_input,
            "search_results": search_results,
            "type_filter": type_filter,
            "status_filter": status_filter,
            "page_indicator": page_indicator,
            "search_tips": token_budget,
            "priority_filter": priority_filter
        }
    }