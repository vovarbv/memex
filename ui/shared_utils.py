"""
Shared utilities for the UI tabs.
Contains common imports and helper functions to ensure consistent behavior across tabs.
"""

import importlib
import logging
import sys
from typing import Any, Callable, Dict, List, Optional, Tuple, Union
import pathlib

def try_import_with_prefix(module_name: str, prefixes: Optional[List[str]] = None) -> Any:
    """Helper function to attempt imports with different prefixes.
    
    This function is kept for backward compatibility but now primarily uses
    the standard package import path.
    
    Args:
        module_name: Name of the module to import
        prefixes: List of prefixes to try (ignored, kept for compatibility)
        
    Returns:
        The imported module
        
    Raises:
        ImportError: If the import fails
    """
    # Always use the proper package path
    return importlib.import_module(f"memex.scripts.{module_name}")

# Import fundamental modules with proper package imports
def import_memory_utils():
    """Import the thread_safe_store module as memory_utils replacement.
    
    This ensures all UI operations use thread-safe vector store operations.
    Falls back to regular memory_utils if thread_safe_store fails to import.
    """
    try:
        # Import thread_safe_store instead of memory_utils for thread safety
        from ..scripts import thread_safe_store
        logging.info("Successfully imported thread_safe_store for memory operations")
        return thread_safe_store
    except ImportError as e:
        logging.warning(f"Failed to import thread_safe_store: {e}, falling back to memory_utils")
        try:
            # Fall back to regular memory_utils
            from ..scripts import memory_utils
            logging.info("Successfully imported memory_utils as fallback")
            return memory_utils
        except ImportError as e2:
            logging.error(f"Failed to import both thread_safe_store and memory_utils: {e2}")
            # Return a dummy module with functions that safely handle the error case
            class DummyMemoryUtils:
                def check_vector_store_integrity(self):
                    return {
                        'status': 'error',
                        'issues': [f"Failed to import memory modules: thread_safe_store ({e}), memory_utils ({e2})"],
                        'summary': {
                            'faiss_index_size': 0,
                            'metadata_entries': 'N/A',
                        }
                    }
                
                def search(self, *args, **kwargs):
                    return []
                
                def count_items(self, *args, **kwargs):
                    return 0
                
                def add_or_replace(self, *args, **kwargs):
                    return False
                
                def delete_vector(self, *args, **kwargs):
                    return False
                
            return DummyMemoryUtils()

def import_task_store():
    """Import the task_store module using package imports."""
    try:
        # Use relative import from the UI package to the scripts package
        from ..scripts import task_store
        return task_store
    except ImportError as e:
        logging.error(f"Failed to import task_store: {e}")
        raise

def import_task_store_module():
    """Alias for import_task_store for backward compatibility."""
    return import_task_store()

def import_required_functions(required_functions: Dict[str, Tuple[str, str]]) -> Dict[str, Any]:
    """Import required functions and return them as a dictionary.
    
    Args:
        required_functions: Dictionary mapping function names to (module_name, import_name) tuples
        
    Returns:
        Dictionary mapping function names to imported functions
    """
    imported_functions = {}
    for function_name, (module_name, import_name) in required_functions.items():
        try:
            imported_functions[function_name] = try_import_with_prefix(module_name, import_name)
        except Exception as e:
            logging.error(f"Error importing {function_name} from {module_name}: {e}")
            imported_functions[function_name] = None
    
    return imported_functions

def ensure_path_exists(path: Union[str, pathlib.Path]) -> pathlib.Path:
    """Ensure that a path exists, creating parent directories if necessary.
    
    Args:
        path: Path to ensure exists
        
    Returns:
        Path object for the ensured path
    """
    path_obj = pathlib.Path(path)
    path_obj.parent.mkdir(parents=True, exist_ok=True)
    return path_obj

def format_error_message(error: Exception) -> str:
    """Format an error message for display in the UI.
    
    Args:
        error: Exception to format
        
    Returns:
        Formatted error message
    """
    return f"❌ Error: {str(error)}"

def format_success_message(message: str) -> str:
    """Format a success message for display in the UI.
    
    Args:
        message: Message to format
        
    Returns:
        Formatted success message
    """
    return f"✅ {message}"

def format_warning_message(message: str) -> str:
    """Format a warning message for display in the UI.
    
    Args:
        message: Message to format
        
    Returns:
        Formatted warning message
    """
    return f"⚠️ {message}"

def improve_code_chunk_visualization(code_chunk):
    """Improve code chunk visualization with syntax highlighting.
    
    Args:
        code_chunk: A code chunk object with language and content attributes
        
    Returns:
        A string with markdown formatting for syntax highlighting
    """
    language = getattr(code_chunk, 'language', 'text')
    content = getattr(code_chunk, 'content', '')
    
    highlighted = f"""```{language}
{content}
```"""
    return highlighted

def update_ui_panel():
    """Update the UI panel with new filters.
    
    Returns:
        A tuple of (search_filters, token_display)
    """
    # Add search filters
    search_filters = {
        'status': ['todo', 'in_progress', 'done', 'all'],
        'priority': ['high', 'medium', 'low', 'all'],
        'type': ['code_chunk', 'snippet', 'note', 'all']
    }
    # Implement token budget display
    token_display = 'Token usage: {}/{}'
    return search_filters, token_display 