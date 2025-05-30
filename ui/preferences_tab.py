import gradio as gr
import logging
import sys
import importlib
import yaml
import pathlib

# Import the shared utility functions
from .shared_utils import try_import_with_prefix, import_memory_utils

def create_preferences_tab(ts, cfg, data_integrity_error=None):
    """Creates the Preferences tab UI with YAML display and edit.
    
    Args:
        ts: TaskStore instance (not used in this tab)
        cfg: Configuration dictionary
        data_integrity_error: Data integrity error message, if any (not used in this tab)
        
    Returns:
        dict: A dictionary containing references to the load function and components
    """
    # Import required constants
    try:
        # Get memory_utils module and constants
        memory_utils = import_memory_utils()
        ROOT = memory_utils.ROOT
        load_preferences = memory_utils.load_preferences if hasattr(memory_utils, 'load_preferences') else None
    except Exception as e:
        logging.error(f"Error importing preferences tab dependencies: {e}")
        ROOT = pathlib.Path.cwd()
        load_preferences = None
    
    # Tab content starts here
    gr.Markdown("## Preferences")
        
    # Display and edit components
    preferences_display = gr.Code(language="yaml", label="PREFERENCES.yaml (Current)", lines=10)
    preferences_edit = gr.Textbox(lines=10, label="Edit Preferences (YAML format)")
        
    # Action buttons
    with gr.Row():
        load_prefs_button = gr.Button("Load Preferences")
        save_prefs_button = gr.Button("Save Preferences")
        
    prefs_status = gr.Markdown("")
        
    def load_preferences_yaml():
        try:
            # Get preferences file path from configuration
            preferences_path = cfg.get("system", {}).get(
                "preferences_file_relative_to_memex_root", 
                cfg.get("preferences", {}).get("file", "docs/PREFERENCES.yaml")
            )
            
            # Resolve full path - handle both relative to memex and absolute
            if ROOT:
                full_path = ROOT / preferences_path
            else:
                full_path = pathlib.Path(preferences_path)
                
            # Check if file exists
            if not full_path.exists():
                return "", "", f"❌ Preferences file not found at {full_path}"
                
            # Load preferences from file
            with open(full_path, 'r', encoding='utf-8') as f:
                prefs_content = f.read()
                
            # Return the content for display, edit, and a success status
            success_msg = f"✅ Successfully loaded preferences from: {full_path}"
            logging.info(success_msg)
            return prefs_content, prefs_content, success_msg
            
        except Exception as e:
            error_msg = f"❌ Error loading preferences: {str(e)}"
            logging.error(error_msg)
            return "", "", error_msg
    
    def save_preferences_yaml(edited_content):
        try:
            # Validate YAML
            try:
                yaml.safe_load(edited_content)
            except yaml.YAMLError as e:
                return "", f"❌ Invalid YAML: {str(e)}"
                
            # Get preferences file path from configuration
            preferences_path = cfg.get("system", {}).get(
                "preferences_file_relative_to_memex_root", 
                cfg.get("preferences", {}).get("file", "docs/PREFERENCES.yaml")
            )
            
            # Resolve full path
            if ROOT:
                full_path = ROOT / preferences_path
            else:
                full_path = pathlib.Path(preferences_path)
                
            # Create directory if it doesn't exist
            full_path.parent.mkdir(parents=True, exist_ok=True)
                
            # Save preferences to file
            with open(full_path, 'w', encoding='utf-8') as f:
                f.write(edited_content)
                
            # Return success message
            success_msg = f"✅ Successfully saved preferences to: {full_path}"
            logging.info(success_msg)
            return edited_content, success_msg
            
        except Exception as e:
            error_msg = f"❌ Error saving preferences: {str(e)}"
            logging.error(error_msg)
            return "", error_msg
    
    # Connect buttons to functions
    load_prefs_button.click(
        load_preferences_yaml,
        outputs=[preferences_display, preferences_edit, prefs_status]
    )
    
    save_prefs_button.click(
        save_preferences_yaml,
        inputs=[preferences_edit],
        outputs=[preferences_display, prefs_status]
    )
    
    # Create a proper refresh function with the load_preferences attribute
    def refresh_preferences():
        try:
            # Load the preferences
            prefs_content, edit_content, status_msg = load_preferences_yaml()
            
            # Update the components
            preferences_display.value = prefs_content
            preferences_edit.value = edit_content
            prefs_status.value = status_msg
            
            # Return None to avoid warning about too many outputs
            return None
        except Exception as e:
            logging.error(f"Error refreshing preferences: {e}")
            return None
    
    # Attach the load_preferences_yaml function as an attribute of refresh_preferences
    refresh_preferences.load_preferences = load_preferences_yaml
    
    # Auto-load preferences on tab creation
    try:
        initial_content, initial_edit, initial_status = load_preferences_yaml()
        preferences_display.value = initial_content
        preferences_edit.value = initial_edit
        prefs_status.value = initial_status
    except Exception as e:
        logging.error(f"Error auto-loading preferences: {e}")
        prefs_status.value = f"⚠️ Failed to auto-load preferences: {str(e)}"
    
    # Return references that can be used by main_app.py
    return {
        "refresh": refresh_preferences,
        "components": {
            "display": preferences_display,
            "edit": preferences_edit,
            "status": prefs_status
        }
    }