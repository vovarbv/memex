#!/bin/bash
# Memex launcher for Unix/Linux/macOS
# This is a simple wrapper that delegates to the main Memex CLI

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Simple wrapper: just pass all arguments to memex_cli.py
exec python "$SCRIPT_DIR/memex_cli.py" "$@"