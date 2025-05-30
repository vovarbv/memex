# Memex UI Tab Structure Standard

This document defines the standard structure for UI tab modules in the Memex system. Following these standards ensures consistency across the UI, makes maintenance easier, and prevents common Gradio errors.

## Standard Tab Function Signature

All tab creation functions must have the following signature:

```python
def create_<tab_name>_tab(ts, cfg, data_integrity_error=None):
    """Creates the Tab UI components.
    
    Args:
        ts: TaskStore instance or None if there was an error
        cfg: Configuration dictionary
        data_integrity_error: Error message or None
    
    Returns:
        dict: A dictionary containing references to the refresh function and components
    """
```

- The function name should follow the pattern `create_<tab_name>_tab` (e.g., `create_dashboard_tab`, `create_search_tab`)
- All three parameters must be present, even if a particular tab doesn't use all of them
- `ts` is the TaskStore instance (or None if there was an error loading tasks)
- `cfg` is the configuration dictionary loaded from memory.toml
- `data_integrity_error` is an error message string or None if no errors

## Tab Content Structure

1. **Import required modules first:**
   ```python
   # Import required functions
   try:
       # Get memory_utils functions
       memory_utils = import_memory_utils()
       search = memory_utils.search
       
       # Get other specific functions
       some_function = try_import_with_prefix("scripts.module_name", "function_name")
   except Exception as e:
       logging.error(f"Error importing tab dependencies: {e}")
       search = None
       some_function = None
   ```

2. **Define UI components directly:**
   - Do NOT use `gr.TabItem(...)` - this is already handled in `main_app.py`
   - Start with a title using `gr.Markdown("## Tab Title")`
   - Define all UI components that will be visible in the tab

3. **Define event handler functions:**
   - Define all functions that respond to UI events (button clicks, etc.)
   - Ensure proper error handling within these functions

4. **Define a refresh function:**
   - All tabs must have a refresh function that updates the tab's content
   - The refresh function should handle errors gracefully
   - Return `None` to avoid Gradio warnings about unhandled return values

5. **Connect UI events:**
   - Connect buttons and other UI elements to their handler functions
   - For refresh buttons, use:
     ```python
     refresh_button.click(
         refresh_tab,
         inputs=None,
         outputs=None
     )
     ```

6. **Initial data loading:**
   - Only attempt to load initial data if there are no data integrity errors
   - Use try/except blocks to handle potential errors
   ```python
   if not data_integrity_error:
       try:
           # Load initial data
       except Exception as e:
           logging.error(f"Error loading initial data: {e}")
   ```

## Return Structure

All tab creation functions must return a dictionary with the following structure:

```python
return {
    "refresh": refresh_tab,
    "components": {
        "component_name_1": component_1,
        "component_name_2": component_2,
        # Additional components...
    }
}
```

- The `refresh` key must contain a callable function that refreshes the tab's content
- The `components` key must contain a dictionary of UI components that may need to be accessed externally
- The component names should be descriptive of their purpose (e.g., "search_input", "results_display")

## Special Case: Advanced Functions

If a tab needs to expose additional functionality beyond refresh:

1. Attach the functionality as an attribute to the refresh function:
   ```python
   refresh_tab.special_function = special_function
   ```

2. Document this in the function docstring

## Example Template

See `tab_template.py` for a complete example of a tab that follows these standards.

## Common Errors to Avoid

1. Nested `gr.TabItem` usage
2. Incorrect function signature 
3. Missing error handling
4. Not returning the proper dictionary structure
5. Not handling both success and error cases in UI functions