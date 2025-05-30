"""
Test suite for migrate_to_thread_safe.py script.

This test suite verifies that the migration script correctly identifies and replaces
memory_utils imports with thread_safe_store imports for the specified functions.
"""

import pytest
import tempfile
from pathlib import Path

# Import the actual functions and constants from the migration script
from ..scripts.migrate_to_thread_safe import (
    update_imports,
    find_python_files,
    THREAD_SAFE_FUNCTIONS,
    EXCLUDE_FILES
)


class TestMigrateToThreadSafe:
    """Test the migrate_to_thread_safe script functionality."""
    
    def test_exclude_files(self):
        """Test that EXCLUDE_FILES contains expected files."""
        expected_excludes = {
            'memory_utils.py',
            'thread_safe_store.py',
            'migrate_to_thread_safe.py',
            'test_memory_utils.py'
        }
        
        assert expected_excludes.issubset(EXCLUDE_FILES)
    
    def test_thread_safe_functions_list(self):
        """Test that THREAD_SAFE_FUNCTIONS contains expected functions."""
        expected_functions = {
            'add_or_replace',
            'delete_vector',
            'delete_vectors_by_filter',
            'search',
            'count_items',
            'load_index',
            'save_index'
        }
        
        assert expected_functions == THREAD_SAFE_FUNCTIONS
    
    def test_update_imports_basic(self, tmp_path):
        """Test updating a file with basic imports."""
        test_file = tmp_path / "test_module.py"
        original_content = """from memory_utils import add_or_replace, search, delete_vector
from some_other_module import other_function

def test_function():
    add_or_replace("id", "text", {})
    results = search("query")
    delete_vector("id")
"""
        test_file.write_text(original_content)
        
        # Process the file
        changes = update_imports(test_file, dry_run=False)
        
        assert len(changes) > 0
        
        # Check the modified content
        modified_content = test_file.read_text()
        
        # Should replace the import
        assert "from thread_safe_store import add_or_replace, search, delete_vector" in modified_content
        assert "from some_other_module import other_function" in modified_content
    
    def test_update_imports_mixed(self, tmp_path):
        """Test updating a file with mixed function imports."""
        test_file = tmp_path / "test_module.py"
        original_content = """from memory_utils import add_or_replace, load_cfg, search

def test_function():
    cfg = load_cfg()
    add_or_replace("id", "text", {})
"""
        test_file.write_text(original_content)
        
        changes = update_imports(test_file, dry_run=False)
        
        assert len(changes) > 0
        
        modified_content = test_file.read_text()
        
        # Should have both imports now
        assert "from memory_utils import load_cfg" in modified_content
        assert "from thread_safe_store import add_or_replace, search" in modified_content
    
    def test_update_imports_scripts_prefix(self, tmp_path):
        """Test updating imports with scripts prefix."""
        test_file = tmp_path / "test_module.py"
        original_content = """from scripts.memory_utils import add_or_replace, search

def test_function():
    add_or_replace("id", "text", {})
"""
        test_file.write_text(original_content)
        
        changes = update_imports(test_file, dry_run=False)
        
        assert len(changes) > 0
        
        modified_content = test_file.read_text()
        
        # Should update to use scripts prefix
        assert "from scripts.thread_safe_store import add_or_replace, search" in modified_content
    
    def test_update_imports_dry_run(self, tmp_path):
        """Test dry run mode doesn't modify files."""
        test_file = tmp_path / "test_module.py"
        original_content = """from memory_utils import add_or_replace

def test_function():
    add_or_replace("id", "text", {})
"""
        test_file.write_text(original_content)
        
        # Process with dry_run=True
        changes = update_imports(test_file, dry_run=True)
        
        assert len(changes) > 0
        
        # File should not be modified
        assert test_file.read_text() == original_content
    
    def test_find_python_files(self, tmp_path):
        """Test finding Python files while respecting exclusions."""
        # Create test directory structure
        (tmp_path / "scripts").mkdir()
        (tmp_path / "tests").mkdir()
        
        # Create various files
        (tmp_path / "good_file.py").write_text("# Python file")
        (tmp_path / "scripts" / "module.py").write_text("# Module")
        (tmp_path / "scripts" / "memory_utils.py").write_text("# Should be excluded")
        (tmp_path / "scripts" / "thread_safe_store.py").write_text("# Should be excluded")
        (tmp_path / "tests" / "test_something.py").write_text("# Test file")
        (tmp_path / "tests" / "test_memory_utils.py").write_text("# Should be excluded")
        (tmp_path / "not_python.txt").write_text("Not Python")
        
        # Find Python files
        files = find_python_files(tmp_path)
        file_names = [f.name for f in files]
        
        # Check inclusions
        assert "good_file.py" in file_names
        assert "module.py" in file_names
        assert "test_something.py" in file_names
        
        # Check exclusions
        assert "memory_utils.py" not in file_names
        assert "thread_safe_store.py" not in file_names
        assert "test_memory_utils.py" not in file_names
        assert "not_python.txt" not in file_names