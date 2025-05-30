"""
Memex scripts package.

This package contains all the command-line scripts for the Memex system.
"""

# Package imports - no sys.path manipulation needed
# Modules within this package should use relative imports:
# - from . import memory_utils
# - from .memory_utils import load_cfg
# - from ..ui import shared_utils

__all__ = [
    'memory_utils',
    'task_store',
    'tasks',
    'add_memory',
    'add_snippet',
    'search_memory',
    'gen_memory_mdc',
    'index_codebase',
    'code_indexer_utils',
    'bootstrap_memory',
    'check_store_health',
    'init_store',
] 