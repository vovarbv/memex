#!/usr/bin/env python
"""
Cross-platform launcher for Memex.
This is a simple wrapper that delegates to the main Memex CLI.

Usage:
    python memex.py [command] [arguments...]
    
Examples:
    python memex.py ui
    python memex.py tasks add "New task"
    python memex.py index_codebase --reindex
"""

import sys
import subprocess
from pathlib import Path

def main():
    """Simple wrapper that calls memex_cli.py with all arguments."""
    script_dir = Path(__file__).parent
    memex_cli_path = script_dir / "memex_cli.py"
    
    # Build the command: python memex_cli.py [all arguments]
    cmd = [sys.executable, str(memex_cli_path)] + sys.argv[1:]
    
    # Execute and return the exit code
    try:
        return subprocess.call(cmd)
    except KeyboardInterrupt:
        return 130  # Standard exit code for Ctrl+C
    except Exception as e:
        print(f"Error launching Memex: {e}", file=sys.stderr)
        return 1

if __name__ == "__main__":
    sys.exit(main())