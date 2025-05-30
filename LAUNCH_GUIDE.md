# Memex Launch Guide

This guide explains the various ways to launch and use Memex.

## Quick Start

### Method 1: Main CLI (Recommended)
```bash
python memex_cli.py ui
```

### Method 2: Cross-Platform Wrappers
All platform-specific wrappers delegate to the main Memex CLI:

**Cross-platform Python:**
```bash
python memex.py ui
```

**Windows:**
```cmd
memex.bat ui
```

**Unix/Linux/macOS:**
```bash
./memex.sh ui
```

### Method 3: Make (if you have Make installed)
```bash
make ui
```

## After Installation (pip install -e .)

Once installed, you can use console commands:
```bash
memex-ui                  # Launch UI
memex-tasks add "Task"    # Add a task
memex-index              # Index codebase
memex-generate           # Generate memory.mdc
memex-search "query"     # Search memory
```

## Common Commands

All entry points use the same professional Memex CLI:

| Command | Description | Example |
|---------|-------------|---------|
| `ui` | Launch web interface | `python memex_cli.py ui` |
| `tasks` | Manage tasks | `python memex_cli.py tasks add "New feature"` |
| `index_codebase` | Index codebase | `python memex_cli.py index_codebase --reindex` |
| `gen_memory_mdc` | Generate memory.mdc | `python memex_cli.py gen_memory_mdc` |
| `search_memory` | Search memory | `python memex_cli.py search_memory "authentication"` |

## First Time Setup

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Bootstrap the project:**
   ```bash
   python memex_cli.py bootstrap_memory
   ```

3. **Initialize the vector store:**
   ```bash
   python memex_cli.py init_store
   ```

4. **Launch the UI:**
   ```bash
   python memex_cli.py ui
   ```

## Using Make

If you have Make installed, you can use these shortcuts:

```bash
make help        # Show all available commands
make ui          # Launch UI
make index       # Index codebase
make reindex     # Re-index codebase
make generate    # Generate memory.mdc
make setup       # Run full setup (install + bootstrap)
make clean       # Clean temporary files
```

## Tips

- The UI runs on http://localhost:7860 by default
- Use `Ctrl+C` to stop the UI server
- All data is stored in `.cursor/vecstore/` in your project root
- Configuration is in `memex/memory.toml`