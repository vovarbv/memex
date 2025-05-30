# Memex Makefile for common operations
# Usage: make [target]

.PHONY: help ui tasks index generate search install install-dev clean test bootstrap health

# Default target
help:
	@echo "Memex - Project Memory System"
	@echo ""
	@echo "Available targets:"
	@echo "  make ui         - Launch the Memex Hub web interface"
	@echo "  make tasks      - Show task management help"
	@echo "  make index      - Index the codebase"
	@echo "  make reindex    - Re-index the codebase (clean index first)"
	@echo "  make generate   - Generate memory.mdc for Cursor"
	@echo "  make search     - Show search help"
	@echo "  make install    - Install Memex with pip"
	@echo "  make install-dev - Install Memex in development mode"
	@echo "  make clean      - Clean temporary files and caches"
	@echo "  make test       - Run tests"
	@echo "  make bootstrap  - Bootstrap a new project"
	@echo "  make health     - Check vector store health"
	@echo ""
	@echo "Examples:"
	@echo "  make ui"
	@echo "  make index"
	@echo "  make generate"

# Launch UI
ui:
	@echo "Starting Memex Hub UI..."
	@python memex_cli.py ui

# Task management
tasks:
	@python memex_cli.py tasks --help

# Index codebase
index:
	@echo "Indexing codebase..."
	@python memex_cli.py index_codebase

# Re-index codebase
reindex:
	@echo "Re-indexing codebase..."
	@python memex_cli.py index_codebase --reindex

# Generate memory.mdc
generate:
	@echo "Generating memory.mdc..."
	@python memex_cli.py gen_memory_mdc

# Search help
search:
	@python memex_cli.py search_memory --help

# Install Memex
install:
	@echo "Installing Memex..."
	@pip install -e .

# Install in development mode
install-dev:
	@echo "Installing Memex in development mode..."
	@pip install -e ".[agents]"

# Clean temporary files
clean:
	@echo "Cleaning temporary files..."
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@find . -type f -name "*.pyo" -delete 2>/dev/null || true
	@find . -type f -name "*.bak" -delete 2>/dev/null || true
	@find . -type f -name ".DS_Store" -delete 2>/dev/null || true
	@echo "Clean complete."

# Run tests
test:
	@echo "Running tests..."
	@python -m pytest tests/

# Bootstrap project
bootstrap:
	@echo "Bootstrapping project..."
	@python memex_cli.py bootstrap_memory

# Check vector store health
health:
	@echo "Checking vector store health..."
	@python memex_cli.py check_store_health

# Quick setup for new users
setup: install bootstrap
	@echo "Setup complete! Run 'make ui' to start the web interface."