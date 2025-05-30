#!/usr/bin/env python
"""
Test suite for code_indexer_utils.py and index_codebase.py

This test suite verifies that code chunking works correctly for different file types
and that the indexing process adds the chunks to the vector database with the right metadata.
"""

import os
import pathlib
import unittest
import tempfile
import shutil
from unittest import mock
import ast

# Import modules to test
from ..scripts.code_indexer_utils import (
    chunk_python_file,
    chunk_markdown_file,
    chunk_text_file,
    generate_chunk_id
)

class TestCodeChunking(unittest.TestCase):
    """Test the code chunking functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create a temporary directory for test files
        self.temp_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        """Tear down test fixtures."""
        # Remove the temporary directory
        shutil.rmtree(self.temp_dir)
    
    def test_generate_chunk_id(self):
        """Test the generation of deterministic chunk IDs."""
        # Test with same inputs produces same ID
        id1 = generate_chunk_id("file.py", 10, 20)
        id2 = generate_chunk_id("file.py", 10, 20)
        self.assertEqual(id1, id2)
        
        # Test with different inputs produces different IDs
        id3 = generate_chunk_id("file.py", 10, 21)
        self.assertNotEqual(id1, id3)
        
        # Test with content hash
        id4 = generate_chunk_id("file.py", 10, 20, "abcdef")
        self.assertNotEqual(id1, id4)
    
    def test_chunk_python_file(self):
        """Test chunking a Python file into functions and classes."""
        # Create a test Python file
        py_file = pathlib.Path(self.temp_dir) / "test.py"
        python_content = """
#!/usr/bin/env python
\"\"\"
Test module docstring.
\"\"\"
import sys
import os

# Global variable
TEST_VAR = "test"

def function1():
    \"\"\"Function 1 docstring.\"\"\"
    return "Hello"

def function2(param):
    \"\"\"Function 2 docstring.\"\"\"
    return param + " World"

class TestClass:
    \"\"\"Test class docstring.\"\"\"
    
    def __init__(self):
        \"\"\"Init method docstring.\"\"\"
        self.value = "test"
    
    def method1(self):
        \"\"\"Method 1 docstring.\"\"\"
        return self.value
"""
        py_file.write_text(python_content)
        
        # Test chunking
        chunks = chunk_python_file(str(py_file))
        
        # We should have at least 1 module chunk and 3 function/method chunks
        self.assertTrue(len(chunks) >= 4)
        
        # Verify chunk metadata
        for chunk in chunks:
            self.assertIn("id", chunk)
            self.assertIn("type", chunk)
            self.assertEqual(chunk["type"], "code_chunk")
            self.assertIn("language", chunk)
            self.assertEqual(chunk["language"], "python")
            self.assertIn("content", chunk)
            self.assertIn("source_file", chunk)
            self.assertEqual(chunk["source_file"], str(py_file))
            self.assertIn("start_line", chunk)
            self.assertIn("end_line", chunk)
    
    def test_chunk_markdown_file(self):
        """Test chunking a Markdown file into sections."""
        # Create a test Markdown file
        md_file = pathlib.Path(self.temp_dir) / "test.md"
        markdown_content = """# Main Title

Introduction paragraph.

## Section 1

Section 1 content.

### Subsection 1.1

Subsection 1.1 content.

## Section 2

Section 2 content.
"""
        md_file.write_text(markdown_content)
        
        # Test chunking
        chunks = chunk_markdown_file(str(md_file))
        
        # We should have at least 4 chunks (main, section 1, subsection 1.1, section 2)
        self.assertTrue(len(chunks) >= 4)
        
        # Verify chunk metadata
        for chunk in chunks:
            self.assertIn("id", chunk)
            self.assertIn("type", chunk)
            self.assertEqual(chunk["type"], "code_chunk")
            self.assertIn("language", chunk)
            self.assertEqual(chunk["language"], "markdown")
            self.assertIn("content", chunk)
            self.assertIn("source_file", chunk)
            self.assertEqual(chunk["source_file"], str(md_file))
            self.assertIn("start_line", chunk)
            self.assertIn("end_line", chunk)
    
    def test_chunk_text_file(self):
        """Test chunking a plain text file."""
        # Create a test text file
        txt_file = pathlib.Path(self.temp_dir) / "test.txt"
        text_content = """This is a test file.
It contains some text that should be chunked.
The chunking strategy for text files is different from Python and Markdown.
It should use overlapping fixed-size chunks instead of semantic units.
Let's see if this works correctly.
"""
        txt_file.write_text(text_content)
        
        # Test chunking
        chunks = chunk_text_file(str(txt_file))
        
        # We should have at least 1 chunk
        self.assertTrue(len(chunks) >= 1)
        
        # Verify chunk metadata
        for chunk in chunks:
            self.assertIn("id", chunk)
            self.assertIn("type", chunk)
            self.assertEqual(chunk["type"], "code_chunk")
            self.assertIn("language", chunk)
            self.assertEqual(chunk["language"], "plaintext")
            self.assertIn("content", chunk)
            self.assertIn("source_file", chunk)
            self.assertEqual(chunk["source_file"], str(txt_file))
            self.assertIn("start_line", chunk)
            self.assertIn("end_line", chunk)

class TestIndexCodebase(unittest.TestCase):
    """Test the codebase indexing functionality."""
    
    @mock.patch('memex.scripts.memory_utils.add_or_replace')
    def test_index_code_chunk(self, mock_add_or_replace):
        """Test indexing a code chunk."""
        # Import the function to test
        from ..scripts.memory_utils import index_code_chunk
        
        # Test indexing a code chunk
        chunk_id = "test:chunk:id"
        content = "def test_function():\n    return 'test'"
        metadata = {
            "type": "code_chunk",
            "source_file": "test.py",
            "language": "python",
            "start_line": 1,
            "end_line": 2,
            "name": "test_function",
            "content": content
        }
        
        # Call the function
        result = index_code_chunk(chunk_id, content, metadata)
        
        # Verify the result
        self.assertEqual(result, chunk_id)
        
        # Verify that add_or_replace was called with the right arguments
        mock_add_or_replace.assert_called_once()
        args, kwargs = mock_add_or_replace.call_args
        self.assertEqual(args[0], chunk_id)
        self.assertIn("Python function `test_function`", args[1])
        self.assertEqual(args[2], metadata)
    
    def test_chunk_empty_file(self):
        """Test chunking an empty file."""
        # Create empty file
        empty_content = ""
        empty_file = self.temp_dir / "empty.py"
        empty_file.write_text(empty_content)
        
        # Test empty Python file
        chunks = chunk_python_file(str(empty_file))
        self.assertEqual(len(chunks), 0)
        
        # Test empty Markdown file
        empty_md = self.temp_dir / "empty.md"
        empty_md.write_text(empty_content)
        chunks = chunk_markdown_file(str(empty_md))
        self.assertEqual(len(chunks), 0)
    
    def test_chunk_large_file(self):
        """Test chunking a very large file."""
        # Create large Python file with many functions
        large_content = []
        for i in range(100):
            large_content.append(f"def function_{i}():")
            large_content.append(f"    '''Function {i} docstring'''")
            large_content.append(f"    print('Function {i}')")
            large_content.append(f"    return {i}")
            large_content.append("")  # Empty line
        
        large_file = self.temp_dir / "large.py"
        large_file.write_text("\n".join(large_content))
        
        # Chunk with specific max_lines
        chunks = chunk_python_file(str(large_file), max_lines=50)
        
        # Should have multiple chunks
        self.assertGreater(len(chunks), 1)
        
        # Each chunk should respect max_lines
        for chunk in chunks:
            lines = chunk["content"].count("\n") + 1
            self.assertLessEqual(lines, 50)
    
    def test_chunk_file_with_syntax_errors(self):
        """Test chunking files with syntax errors."""
        # Python file with syntax error
        syntax_error_content = """
def broken_function(:  # Missing parameter
    print("This won't parse")
    
def valid_function():
    return "This is valid"
"""
        error_file = self.temp_dir / "syntax_error.py"
        error_file.write_text(syntax_error_content)
        
        # Should still chunk the file, treating it as text
        chunks = chunk_python_file(str(error_file))
        
        # Should get at least one chunk
        self.assertGreater(len(chunks), 0)
        
        # Content should be preserved
        all_content = "\n".join(chunk["content"] for chunk in chunks)
        self.assertIn("broken_function", all_content)
        self.assertIn("valid_function", all_content)
    
    def test_find_files_to_index_patterns(self):
        """Test find_files_to_index with various include/exclude patterns."""
        from ..scripts.index_codebase import find_files_to_index
        
        # Create test file structure
        test_root = self.temp_dir / "test_project"
        test_root.mkdir()
        
        # Create various files
        (test_root / "src").mkdir()
        (test_root / "src" / "main.py").write_text("# Main file")
        (test_root / "src" / "utils.py").write_text("# Utils")
        
        (test_root / "tests").mkdir()
        (test_root / "tests" / "test_main.py").write_text("# Tests")
        
        (test_root / "node_modules").mkdir()
        (test_root / "node_modules" / "package.js").write_text("// Package")
        
        (test_root / ".git").mkdir()
        (test_root / ".git" / "config").write_text("# Git config")
        
        # Test with include all Python files, exclude node_modules and .git
        cfg = {
            "files": {
                "include": ["**/*.py"],
                "exclude": ["**/node_modules/**", "**/.git/**"]
            }
        }
        
        files = find_files_to_index(cfg, test_root)
        file_names = [f.name for f in files]
        
        # Should include Python files
        self.assertIn("main.py", file_names)
        self.assertIn("utils.py", file_names)
        self.assertIn("test_main.py", file_names)
        
        # Should not include excluded directories
        self.assertNotIn("package.js", file_names)
        self.assertNotIn("config", file_names)
    
    def test_chunk_metadata_generation(self):
        """Test that chunk metadata is correctly generated."""
        # Python file with various elements
        python_content = '''"""Module docstring"""

class TestClass:
    """Test class"""
    def method(self):
        pass

def standalone_function():
    """Standalone function"""
    return True

# Global variable
CONSTANT = 42
'''
        test_file = self.temp_dir / "test_metadata.py"
        test_file.write_text(python_content)
        
        chunks = chunk_python_file(str(test_file))
        
        # Verify metadata fields
        for chunk in chunks:
            self.assertIn("id", chunk)
            self.assertIn("source_file", chunk)
            self.assertIn("language", chunk)
            self.assertIn("start_line", chunk)
            self.assertIn("end_line", chunk)
            self.assertIn("name", chunk)
            self.assertIn("content", chunk)
            
            # Verify specific metadata
            self.assertEqual(chunk["language"], "python")
            self.assertTrue(chunk["source_file"].endswith("test_metadata.py"))
            self.assertIsInstance(chunk["start_line"], int)
            self.assertIsInstance(chunk["end_line"], int)
            self.assertGreater(chunk["end_line"], chunk["start_line"])

if __name__ == '__main__':
    unittest.main() 