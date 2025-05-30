import gradio as gr
import logging
from typing import List, Dict, Any
from pathlib import Path

# Configure logging for the UI app if necessary
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Import UI modules using package imports
from .focus_tab import create_focus_tab
from .memory_tab import create_memory_tab
from .dashboard_tab import create_dashboard_tab
from .tasks_tab import create_tasks_tab
from .search_tab import create_search_tab
from .preferences_tab import create_preferences_tab
from .settings_tab import create_settings_tab

# Import scripts modules using package imports
from ..scripts.task_store import TaskStore, DuplicateTaskIDError
from ..scripts.memory_utils import load_cfg, ROOT, check_vector_store_integrity
from ..scripts.thread_safe_store import count_items

def launch_ui():
    """Launches the Memex Gradio UI with modular tab structure."""
    logging.info("Starting Memex UI launch process...")
    
    

    logging.info("Creating TaskStore instance...")
    
    # Add error handling for TaskStore initialization
    ts = None
    data_integrity_error = None
    try:
        ts = TaskStore()  # Instantiate once
    except DuplicateTaskIDError as e:
        data_integrity_error = str(e)
        logging.critical(f"Data integrity error when loading tasks: {e}")
    except Exception as e:
        data_integrity_error = f"Unexpected error loading tasks: {str(e)}"
        logging.critical(f"Unexpected error when loading tasks: {e}")
    
    # Load configuration
    cfg = load_cfg()
    logging.info("Loading configuration completed")

    # Create the Gradio app
    logging.info("Initializing Gradio interface...")
    with gr.Blocks(title="Memex Hub", theme=gr.themes.Soft()) as demo:
        gr.Markdown("# Memex Hub")
        
        # Store references to tab components that need to be auto-loaded
        tab_references = {}
        
        # Display data integrity error if present
        if data_integrity_error:
            error_message = f"""
            ## ⚠️ Data Integrity Error Detected
            
            **Error:** {data_integrity_error}
            
            **Action Required:** Please check your `TASKS.yaml` file for duplicate task IDs or other data issues.
            
            **File Location:** {str(ROOT / cfg.get("system", {}).get("tasks_file_relative_to_memex_root", "docs/TASKS.yaml"))}
            
            Some features of the UI may be unavailable until this issue is resolved.
            """
            gr.Markdown(error_message, elem_id="data-integrity-error")
            
            # Add a refresh button to retry data load after manual fixes
            with gr.Row():
                retry_load_button = gr.Button("Retry Data Load / Refresh App State", variant="primary")
                retry_status = gr.Markdown("")
            
            def retry_data_load():
                try:
                    # Attempt to re-instantiate TaskStore
                    nonlocal ts, data_integrity_error
                    ts = TaskStore()
                    data_integrity_error = None
                    
                    # Verify vector store integrity
                    store_health = check_vector_store_integrity() if check_vector_store_integrity else {"status": "unknown"}
                    
                    # If we got here without exception, the error is resolved
                    gr.Info("Data integrity issues resolved. App state refreshed successfully!")
                    
                    # Refresh the UI state
                    # This is a simplified implementation - in a full version, we would refresh all tabs
                    refresh_dashboard_if_possible()
                    
                    # Return success message and hide the error message
                    return "✅ Data integrity issues resolved. You may now use all app features. Please switch between tabs to refresh their content."
                except DuplicateTaskIDError as e:
                    # Still have the same issue
                    data_integrity_error = str(e)
                    gr.Warning(f"Data integrity issues still present: {e}")
                    return f"❌ Data integrity issues still present: {e}"
                except Exception as e:
                    # Some other error
                    data_integrity_error = f"Unexpected error: {str(e)}"
                    gr.Error(f"Error refreshing app state: {e}")
                    return f"❌ Error refreshing app state: {e}"
            
            retry_load_button.click(
                retry_data_load,
                outputs=[retry_status]
            )
        
        # Function to refresh dashboard tab if available
        def refresh_dashboard_if_possible():
            if 'dashboard' in tab_references and hasattr(tab_references['dashboard'], 'refresh'):
                try:
                    # Call the refresh function directly
                    refresh_func = tab_references['dashboard']['refresh']
                    refresh_func()
                    logging.info("Dashboard refreshed successfully via refresh_dashboard_if_possible")
                except Exception as e:
                    logging.error(f"Error refreshing dashboard: {e}")
        
        with gr.Tabs() as tabs:
            # Create the Focus tab - NEW PRIMARY TAB
            with gr.Tab("🎯 Focus", id="focus-tab"):
                focus_tab = create_focus_tab(ts, cfg, data_integrity_error)
                if focus_tab and isinstance(focus_tab, dict) and 'refresh' in focus_tab:
                    tab_references['focus'] = focus_tab
            
            # Create the Memory tab - unified interface for snippets and notes
            with gr.Tab("💾 Memory", id="memory-tab"):
                memory_tab = create_memory_tab(ts, cfg, data_integrity_error)
                if memory_tab and isinstance(memory_tab, dict):
                    tab_references['memory'] = memory_tab
            
            # Create the Tasks tab - put this third as it's a primary function
            with gr.Tab("📋 Tasks", id="tasks-tab"):
                tasks_tab = create_tasks_tab(ts, cfg, data_integrity_error)
                if tasks_tab and isinstance(tasks_tab, dict):
                    tab_references['tasks'] = tasks_tab
            
            # Create the Search tab with advanced filters
            with gr.Tab("🔍 Search & Filters", id="search-tab"):
                search_tab = create_search_tab(ts, cfg, data_integrity_error)
                if search_tab and isinstance(search_tab, dict):
                    tab_references['search'] = search_tab
            
            # Create the Preferences tab - this now returns references we need
            with gr.Tab("🎨 Preferences", id="preferences-tab"):
                preferences_tab = create_preferences_tab(ts, cfg, data_integrity_error)
                if preferences_tab and isinstance(preferences_tab, dict):
                    tab_references['preferences'] = preferences_tab
            
            # Create the Settings tab
            with gr.Tab("⚙️ Settings", id="settings-tab"):
                settings_tab = create_settings_tab(ts, cfg, data_integrity_error)
                if settings_tab and isinstance(settings_tab, dict):
                    tab_references['settings'] = settings_tab
            
            # Create the Dashboard tab - moved to last as it's less important now
            with gr.Tab("📊 Dashboard", id="dashboard-tab"):
                dashboard_tab = create_dashboard_tab(ts, cfg, data_integrity_error)
                if dashboard_tab and isinstance(dashboard_tab, dict):
                    tab_references['dashboard'] = dashboard_tab
    
        # Demo load function - called after the interface is created
        # This is used to auto-load content like preferences
        def load_preferences_on_startup():
            try:
                # Auto-load preferences if available
                if 'preferences' in tab_references and hasattr(tab_references['preferences']['refresh'], 'load_preferences'):
                    load_fn = tab_references['preferences']['refresh'].load_preferences
                    components = tab_references['preferences']['components']
                    
                    # Call the load function
                    results = load_fn()
                    
                    # Update the components with the results
                    if len(results) >= 3 and all(components.values()):
                        components['display'].value = results[0]
                        components['edit'].value = results[1]
                        components['status'].value = results[2]
                        logging.info("Successfully auto-loaded preferences on startup")
            except Exception as e:
                logging.error(f"Error auto-loading preferences on startup: {e}")
        
        # Register the load function
        demo.load(fn=load_preferences_on_startup)
    
    # Return the demo app
    return demo

def launch_ui_cli():
    """Entry point for console script."""
    demo = launch_ui()
    demo.launch(show_error=True)

# Entry point when called directly
if __name__ == "__main__":
    launch_ui_cli() 