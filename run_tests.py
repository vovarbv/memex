#!/usr/bin/env python
"""
Test runner script that sets up the proper Python path for running tests.
This ensures all imports work correctly regardless of how the tests are run.
"""
import sys
import os
from pathlib import Path

# Add the memex directory to Python path
memex_dir = Path(__file__).parent
if str(memex_dir) not in sys.path:
    sys.path.insert(0, str(memex_dir))

# Add the parent directory to Python path (for absolute imports)
parent_dir = memex_dir.parent
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))

# Now run pytest
import pytest

if __name__ == "__main__":
    # Run pytest with any command line arguments passed to this script
    sys.exit(pytest.main(sys.argv[1:]))