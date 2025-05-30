#!/usr/bin/env python
"""
Migration script to update imports from memory_utils to thread_safe_store.
This ensures all vector store operations use thread-safe wrappers.
"""
import os
import re
import pathlib
import logging
from typing import List, Tuple

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Functions that need to be replaced with thread-safe versions
THREAD_SAFE_FUNCTIONS = {
    'add_or_replace',
    'delete_vector',
    'delete_vectors_by_filter',
    'search',
    'count_items',
    'save_index',
    'load_index'
}

# Files to exclude from migration
EXCLUDE_FILES = {
    'memory_utils.py',  # The original module
    'thread_safe_store.py',  # The thread-safe wrapper itself
    'migrate_to_thread_safe.py',  # This migration script
    'test_memory_utils.py',  # Tests that test the original functions
}


def find_python_files(root_dir: pathlib.Path) -> List[pathlib.Path]:
    """Find all Python files in the project."""
    python_files = []
    
    for file_path in root_dir.rglob('*.py'):
        # Skip excluded files
        if file_path.name in EXCLUDE_FILES:
            continue
        
        # Skip test files that specifically test memory_utils
        if 'test' in file_path.parts and 'memory_utils' in file_path.name:
            continue
            
        python_files.append(file_path)
    
    return python_files


def update_imports(file_path: pathlib.Path, dry_run: bool = False) -> List[str]:
    """Update imports in a Python file to use thread-safe versions."""
    changes = []
    
    try:
        content = file_path.read_text(encoding='utf-8')
        original_content = content
        
        # Pattern to match various import styles
        patterns = [
            # from memory_utils import function
            (r'from\s+(?:\.)?memory_utils\s+import\s+([^#\n]+)',
             'from_import'),
            # from scripts.memory_utils import function
            (r'from\s+scripts\.memory_utils\s+import\s+([^#\n]+)',
             'from_scripts_import'),
            # from memex.scripts.memory_utils import function
            (r'from\s+memex\.scripts\.memory_utils\s+import\s+([^#\n]+)',
             'from_memex_import'),
            # import memory_utils
            (r'^import\s+memory_utils\s*$',
             'direct_import'),
            # import scripts.memory_utils
            (r'^import\s+scripts\.memory_utils\s*$',
             'scripts_import'),
        ]
        
        for pattern, import_type in patterns:
            matches = list(re.finditer(pattern, content, re.MULTILINE))
            
            for match in reversed(matches):  # Process in reverse to maintain positions
                if import_type in ['from_import', 'from_scripts_import', 'from_memex_import']:
                    imports_str = match.group(1)
                    
                    # Parse the imported items
                    imports = [item.strip() for item in imports_str.split(',')]
                    
                    # Separate thread-safe functions from others
                    thread_safe_imports = []
                    other_imports = []
                    
                    for imp in imports:
                        # Handle 'as' aliases
                        base_name = imp.split(' as ')[0].strip()
                        
                        if base_name in THREAD_SAFE_FUNCTIONS:
                            thread_safe_imports.append(imp)
                        else:
                            other_imports.append(imp)
                    
                    if thread_safe_imports:
                        # Build new import statements
                        new_imports = []
                        
                        # Keep non-thread-safe imports from memory_utils
                        if other_imports:
                            if import_type == 'from_import':
                                new_imports.append(f"from memory_utils import {', '.join(other_imports)}")
                            elif import_type == 'from_scripts_import':
                                new_imports.append(f"from scripts.memory_utils import {', '.join(other_imports)}")
                            elif import_type == 'from_memex_import':
                                new_imports.append(f"from memex.scripts.memory_utils import {', '.join(other_imports)}")
                        
                        # Add thread-safe imports
                        if import_type == 'from_import':
                            new_imports.append(f"from thread_safe_store import {', '.join(thread_safe_imports)}")
                        elif import_type == 'from_scripts_import':
                            new_imports.append(f"from scripts.thread_safe_store import {', '.join(thread_safe_imports)}")
                        elif import_type == 'from_memex_import':
                            new_imports.append(f"from memex.scripts.thread_safe_store import {', '.join(thread_safe_imports)}")
                        
                        # Replace the import
                        new_import_line = '\n'.join(new_imports)
                        content = content[:match.start()] + new_import_line + content[match.end():]
                        
                        changes.append(f"Updated import: {match.group(0)} -> {new_import_line}")
                
                elif import_type in ['direct_import', 'scripts_import']:
                    # For direct imports, we need to check usage in the file
                    # This is more complex and might need manual review
                    changes.append(f"Warning: Direct import found that may need manual review: {match.group(0)}")
        
        # Check if there were any changes
        if content != original_content:
            if not dry_run:
                file_path.write_text(content, encoding='utf-8')
                logging.info(f"Updated {file_path}")
            else:
                logging.info(f"Would update {file_path}")
        
    except Exception as e:
        logging.error(f"Error processing {file_path}: {e}")
        changes.append(f"Error: {e}")
    
    return changes


def main(dry_run: bool = False):
    """Main migration function."""
    # Find the memex root directory
    script_dir = pathlib.Path(__file__).resolve().parent
    memex_root = script_dir.parent
    
    logging.info(f"Starting migration in {memex_root}")
    logging.info(f"Dry run: {dry_run}")
    
    # Find all Python files
    python_files = find_python_files(memex_root)
    logging.info(f"Found {len(python_files)} Python files to check")
    
    # Process each file
    all_changes = []
    for file_path in python_files:
        changes = update_imports(file_path, dry_run)
        if changes:
            all_changes.extend([(file_path, change) for change in changes])
    
    # Report results
    if all_changes:
        logging.info(f"\nTotal changes: {len(all_changes)}")
        for file_path, change in all_changes:
            logging.info(f"  {file_path.relative_to(memex_root)}: {change}")
    else:
        logging.info("No changes needed")
    
    # Create a summary report
    if not dry_run and all_changes:
        report_path = memex_root / "migration_report.txt"
        with open(report_path, 'w') as f:
            f.write("Thread-Safe Migration Report\n")
            f.write("=" * 50 + "\n\n")
            for file_path, change in all_changes:
                f.write(f"{file_path.relative_to(memex_root)}:\n  {change}\n\n")
        logging.info(f"Migration report saved to {report_path}")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Migrate to thread-safe vector store operations")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be changed without making changes")
    
    args = parser.parse_args()
    main(dry_run=args.dry_run)