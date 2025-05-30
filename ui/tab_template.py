"""
Template for creating new UI tab modules in the Memex system.
This module demonstrates the standard structure that all tab modules should follow.
"""
import gradio as gr
import logging
from typing import Dict, List, Any, Optional

# Import the shared utility functions
from .shared_utils import try_import_with_prefix, import_memory_utils

def create_template_tab(ts, cfg, data_integrity_error=None):
    """Creates a tab UI following the standard structure.
    
    Args:
        ts: TaskStore instance or None if there was an error
        cfg: Configuration dictionary 
        data_integrity_error: Error message or None if no errors
    
    Returns:
        dict: A dictionary containing references to the refresh function and components
    """
    # Import required functions
    try:
        # Get memory_utils functions and any other required imports
        memory_utils = import_memory_utils()
        search = memory_utils.search if hasattr(memory_utils, 'search') else None
        
        # Get other specific functions if needed
        some_function = try_import_with_prefix("scripts.module_name", "function_name")
    except Exception as e:
        logging.error(f"Error importing tab dependencies: {e}")
        memory_utils = None
        search = None
        some_function = None
    
    # Tab content starts here - DO NOT use gr.TabItem
    gr.Markdown("## Tab Title")
    
    # Create main UI components
    # Example: Search input and results display
    with gr.Row():
        search_input = gr.Textbox(
            label="Search Input",
            placeholder="Enter search terms...",
            lines=1
        )
        search_button = gr.Button("Search")
    
    # Results display
    results_display = gr.Markdown("Results will be displayed here...")
    
    # Refresh button (standard in all tabs)
    refresh_button = gr.Button("🔄 Refresh")
    
    # Define any internal helper functions
    def perform_search(query):
        """Search function that can be called by buttons."""
        if not search:
            return "❌ Search functionality not available."
        
        try:
            # Perform search logic here
            results = search(query, top_k=10)
            
            # Format results for display
            if not results:
                return "No results found."
            
            # Format the output
            output = f"### Search Results ({len(results)} found)\n\n"
            
            for i, (meta, score) in enumerate(results, 1):
                output += f"{i}. {meta.get('title', 'Untitled')} (Score: {score:.2f})\n\n"
                
            return output
        
        except Exception as e:
            error_msg = f"❌ Error performing search: {str(e)}"
            logging.error(error_msg)
            return error_msg
    
    # Programmatic refresh function that can be called from outside
    def refresh_tab():
        """Function to refresh the tab's content."""
        try:
            # Reset the UI to its default state
            search_input.value = ""
            results_display.value = "Results will be displayed here..."
            logging.info("Tab refreshed successfully")
            # Return None to avoid warning about too many outputs
            return None
        except Exception as e:
            logging.error(f"Error refreshing tab: {e}")
            return None
    
    # Connect UI events
    search_button.click(
        perform_search,
        inputs=[search_input],
        outputs=[results_display]
    )
    
    refresh_button.click(
        refresh_tab,
        inputs=None,
        outputs=None
    )
    
    # Initial load of data if needed
    if not data_integrity_error:
        try:
            # Load initial data if needed
            results_display.value = "Ready for search."
        except Exception as e:
            logging.error(f"Error in initial tab load: {e}")
            results_display.value = f"Error loading tab: {str(e)}"
    
    # Return references for main_app.py
    # IMPORTANT: All tabs must return this structure
    return {
        "refresh": refresh_tab,
        "components": {
            "search_input": search_input,
            "results_display": results_display
            # Include all components that might need to be accessed externally
        }
    }