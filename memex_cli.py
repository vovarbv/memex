#!/usr/bin/env python
"""
Memex Command Line Interface (CLI) - Professional entry point for all Memex operations.
This provides a unified, professional interface for project memory management.

Usage: python memex_cli.py <command> [arguments...]

Examples:
    python memex_cli.py ui
    python memex_cli.py tasks add "New task" --plan "Step 1;Step 2"  
    python memex_cli.py index_codebase --reindex
    python memex_cli.py gen_memory_mdc

Available Commands:
    ui              - Launch the Memex Hub web interface
    tasks           - Manage project tasks
    index_codebase  - Index project codebase for search
    gen_memory_mdc  - Generate memory.mdc for Cursor IDE
    search_memory   - Search across all memory items
    add_snippet     - Add code snippets to memory
    add_memory      - Add notes/facts to memory
    bootstrap_memory- Initialize Memex in a new project
    init_store      - Initialize the vector store
    check_store_health - Verify vector store integrity
"""
import os
import sys
import importlib
import traceback
from pathlib import Path

# Set up proper import paths
current_dir = Path(__file__).parent
parent_dir = current_dir.parent

# Add paths to ensure imports work correctly
if str(current_dir) not in sys.path:
    sys.path.insert(0, str(current_dir))
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))

def run_script():
    """Main entry point for running various scripts within the memex ecosystem.
    
    Usage:
        python memex_cli.py <script_name> [args...]
        python memex_cli.py --help
        
    Examples:
        python memex_cli.py ui
        python memex_cli.py tasks
        python memex_cli.py index_codebase
    """
    if len(sys.argv) < 2 or sys.argv[1] in ["--help", "-h", "help"]:
        scripts = [
            "ui (Launch the Memex UI)",
            "tasks (Task management)",
            "gen_memory_mdc (Generate memory.mdc)",
            "index_codebase (Index codebase for search)",
            "add_snippet (Add code snippet)",
            "add_memory (Add note/memory)",
            "search_memory (Search vector store)",
            "bootstrap_memory (Initialize project)",
            "init_store (Initialize vector store)",
            "check_store_health (Check vector store health)",
            "check_indexed_files (Check which files are indexed)"
        ]
        print("Memex - Project Memory System")
        print("Usage: python memex_cli.py <script_name> [args...]")
        print("\nAvailable scripts:")
        for script in scripts:
            print(f"  - {script}")
        print("\nExamples:")
        print("  python memex_cli.py ui")
        print("  python memex_cli.py tasks add 'New task'")
        print("  python memex_cli.py index_codebase --reindex")
        return 0
    
    script_name = sys.argv[1]
    script_args = sys.argv[2:]
    
    # Special handling for UI
    if script_name.lower() in ["ui", "app", "app_ui"]:
        return launch_ui()
    
    # Remove .py extension if present
    if script_name.endswith(".py"):
        script_name = script_name[:-3]
    
    # Try to run the specified script
    try:
        # Try different import strategies
        script_module = None
        try:
            # When run as part of the package from parent directory
            print(f"Loading script: {script_name}")
            script_module = importlib.import_module(f"memex.scripts.{script_name}")
        except (ImportError, ModuleNotFoundError):
            try:
                # When run directly from within memex directory
                script_module = importlib.import_module(f"scripts.{script_name}")
            except (ImportError, ModuleNotFoundError):
                # Last resort: try direct import from scripts directory
                scripts_dir = current_dir / "scripts"
                if str(scripts_dir) not in sys.path:
                    sys.path.insert(0, str(scripts_dir))
                script_module = importlib.import_module(script_name)
        
        # Try to call main function if it exists
        if hasattr(script_module, "main"):
            return script_module.main(script_args)
        elif hasattr(script_module, "run"):
            return script_module.run(script_args)
        elif hasattr(script_module, "make"):
            return script_module.make()
        else:
            print(f"Error: Could not find an entry point (main, run, make) in {script_name}")
            return 1
    except ImportError as e:
        print(f"Error: Script '{script_name}' not found. Error details: {e}")
        return 1
    except Exception as e:
        print(f"Error running script '{script_name}': {e}")
        traceback.print_exc()
        return 1

def launch_ui():
    """Launch the UI interface."""
    try:
        print("Launching Memex Hub UI...")
        
        # Try different import strategies
        launch_ui_func = None
        try:
            # When run as part of the package from parent directory
            from memex.ui.main_app import launch_ui as launch_ui_func
        except (ImportError, ModuleNotFoundError):
            try:
                # When run directly from within memex directory
                from ui.main_app import launch_ui as launch_ui_func
            except (ImportError, ModuleNotFoundError):
                # Last resort: try importing main_app directly and calling its function
                import ui.main_app as main_app
                launch_ui_func = main_app.launch_ui
        
        if launch_ui_func is None:
            raise ImportError("Could not import launch_ui function")
            
        ui_demo = launch_ui_func()
        ui_demo.launch(share=False, show_error=True)
        return 0
    except Exception as e:
        print(f"Error launching UI: {e}")
        traceback.print_exc()
        return 1

def main():
    """Entry point for console script."""
    exit_code = run_script()
    sys.exit(exit_code if isinstance(exit_code, int) else 0)

if __name__ == "__main__":
    main() 