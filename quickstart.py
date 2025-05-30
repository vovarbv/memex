#!/usr/bin/env python
"""
Quickstart script for Memex - launches UI with a single command.
No arguments needed - just run this file!

Usage:
    python quickstart.py
    
This will:
1. Check dependencies
2. Initialize the vector store if needed
3. Launch the Memex Hub UI
"""

import sys
import os
import subprocess
from pathlib import Path

def check_dependencies():
    """Check if required dependencies are installed."""
    try:
        import gradio
        import faiss
        import sentence_transformers
        return True
    except ImportError as e:
        print(f"Missing dependency: {e}")
        print("\nPlease install dependencies first:")
        print("  pip install -r requirements.txt")
        return False

def init_store_if_needed():
    """Initialize vector store if it doesn't exist."""
    project_root = Path(__file__).parent.parent
    vecstore_dir = project_root / ".cursor" / "vecstore"
    
    if not (vecstore_dir / "index.faiss").exists():
        print("Initializing vector store...")
        memex_cli = Path(__file__).parent / "memex_cli.py"
        subprocess.run([sys.executable, str(memex_cli), "init_store"], check=True)
        print("Vector store initialized!")

def launch_ui():
    """Launch the Memex UI."""
    print("\n🚀 Starting Memex Hub...")
    print("=" * 50)
    memex_cli = Path(__file__).parent / "memex_cli.py"
    subprocess.run([sys.executable, str(memex_cli), "ui"])

def main():
    """Main entry point."""
    print("Memex Quickstart")
    print("=" * 50)
    
    # Check dependencies
    if not check_dependencies():
        return 1
    
    # Initialize store if needed
    try:
        init_store_if_needed()
    except Exception as e:
        print(f"Warning: Could not initialize vector store: {e}")
        print("You may need to run 'python scripts/init_store.py' manually.")
    
    # Launch UI
    try:
        launch_ui()
    except KeyboardInterrupt:
        print("\n\nMemex UI stopped.")
    except Exception as e:
        print(f"\nError launching UI: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())