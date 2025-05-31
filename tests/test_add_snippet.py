import pytest
from unittest.mock import patch, MagicMock, mock_open
import io
import os

from scripts.add_snippet import add_snippet_logic, load_from_file


@pytest.fixture
def mock_add_or_replace():
    with patch('scripts.add_snippet.add_or_replace') as mock:
        yield mock


def test_add_snippet_logic_basic(mock_add_or_replace):
    """Test adding a basic snippet"""
    # Set up the mock to return a snippet ID
    mock_add_or_replace.return_value = "snippet123"
    
    # Call the function with correct parameters
    result = add_snippet_logic(
        content="def test_function():\n    return 'Hello, World!'",
        lang="python",
        source_desc="Test function"
    )
    
    # Verify the result
    assert result == "snippet123"
    
    # Verify add_or_replace was called
    mock_add_or_replace.assert_called_once()
    args = mock_add_or_replace.call_args[0]
    
    # Check the content was passed correctly
    assert "def test_function()" in args[1]
    
    # Check metadata
    metadata = args[2]
    assert metadata["type"] == "snippet"
    assert metadata["language"] == "python"
    assert metadata["source"] == "Test function"
    assert "timestamp" in metadata


def test_add_snippet_logic_with_custom_id(mock_add_or_replace):
    """Test adding a snippet with a custom ID"""
    custom_id = "custom_snippet_id"
    mock_add_or_replace.return_value = custom_id
    
    # Call the function with a custom ID
    result = add_snippet_logic(
        content="SELECT * FROM users;",
        lang="sql",
        source_desc="Query all users",
        custom_id=custom_id
    )
    
    # Verify the result
    assert result == custom_id
    
    # Verify add_or_replace was called with the custom ID
    mock_add_or_replace.assert_called_once()
    assert mock_add_or_replace.call_args[0][0] == custom_id


def test_add_snippet_logic_with_source_file(mock_add_or_replace):
    """Test adding a snippet with source file path"""
    mock_add_or_replace.return_value = "snippet789"
    
    # Call the function with source file path (source_desc="manual" to use file path)
    result = add_snippet_logic(
        content="console.log('Hello');",
        lang="javascript",
        source_desc="manual",  # This triggers using source_file_path
        source_file_path="/path/to/file.js"
    )
    
    # Verify the result
    assert result == "snippet789"
    
    # Check metadata includes file path as source
    metadata = mock_add_or_replace.call_args[0][2]
    assert metadata["source"] == "/path/to/file.js"


def test_add_snippet_logic_empty_content(mock_add_or_replace):
    """Test handling of empty content"""
    # Call with empty content
    result = add_snippet_logic(
        content="",
        lang="python"
    )
    
    # Should return None for empty content
    assert result is None
    
    # add_or_replace should not be called
    mock_add_or_replace.assert_not_called()


def test_add_snippet_logic_error_handling(mock_add_or_replace):
    """Test error handling"""
    # Set up mock to raise an exception
    mock_add_or_replace.side_effect = Exception("Vector store error")
    
    # Call the function
    result = add_snippet_logic(
        content="some code",
        lang="python"
    )
    
    # Should return None on error
    assert result is None


def test_load_from_file_whole_file():
    """Test loading an entire file"""
    with patch('pathlib.Path.is_file', return_value=True):
        with patch('pathlib.Path.read_text', return_value="file content"):
            content, file_path, lang = load_from_file("test.py")
            
            assert content == "file content"
            assert file_path == "test.py"
            assert lang == "py"


def test_load_from_file_with_line_range():
    """Test loading specific lines from a file"""
    file_content = "line1\nline2\nline3\nline4\nline5"
    
    with patch('pathlib.Path.is_file', return_value=True):
        with patch('pathlib.Path.open', mock_open(read_data=file_content)):
            # Test single line
            content, file_path, lang = load_from_file("test.py:2")
            assert content.strip() == "line2"
            assert file_path == "test.py"  # Path without line spec
            
            # Reset mock
            with patch('pathlib.Path.open', mock_open(read_data=file_content)):
                # Test line range
                content, file_path, lang = load_from_file("test.py:2-4")
                assert "line2" in content
                assert "line3" in content
                assert "line4" in content
                assert file_path == "test.py"  # Path without line spec


def test_load_from_file_not_found():
    """Test handling of non-existent file"""
    with patch('pathlib.Path.is_file', return_value=False):
        with pytest.raises(FileNotFoundError):
            load_from_file("nonexistent.py")


def test_load_from_file_invalid_line_spec():
    """Test handling of invalid line specifications"""
    with patch('pathlib.Path.is_file', return_value=True):
        # Test that non-numeric line specs are treated as file paths
        with patch('pathlib.Path.read_text', return_value="file content"):
            content, file_path, lang = load_from_file("test.py:abc")
            # Should treat the whole thing as a filename
            assert file_path == "test.py:abc"
            assert content == "file content"