import pytest
from unittest.mock import patch, MagicMock, mock_open
import io
import os

from scripts.add_snippet import add_snippet_logic, detect_language, extract_from_file


@pytest.fixture
def mock_add_or_replace():
    with patch('scripts.add_snippet.add_or_replace') as mock:
        yield mock


def test_detect_language_by_extension():
    """Test language detection from file extension"""
    assert detect_language("test.py") == "python"
    assert detect_language("script.js") == "javascript"
    assert detect_language("style.css") == "css"
    assert detect_language("config.json") == "json"
    assert detect_language("doc.md") == "markdown"
    assert detect_language("query.sql") == "sql"
    assert detect_language("config.yml") == "yaml"
    assert detect_language("config.yaml") == "yaml"
    assert detect_language("script.sh") == "bash"
    assert detect_language("unknown.xyz") == "text"  # Default for unknown extension


def test_detect_language_by_content():
    """Test language detection from code content"""
    assert detect_language(None, "def hello(): print('world')") == "python"
    assert detect_language(None, "function hello() { console.log('world'); }") == "javascript"
    assert detect_language(None, "body { color: red; }") == "css"
    assert detect_language(None, "SELECT * FROM users WHERE id = 1;") == "sql"
    assert detect_language(None, "# Title\n\nThis is markdown") == "markdown"
    assert detect_language(None, "<?php echo 'Hello'; ?>") == "php"
    assert detect_language(None, "<html><body>Hello</body></html>") == "html"
    assert detect_language(None, "this is just plain text") == "text"  # Default for undetectable content


@patch('builtins.open')
def test_extract_from_file_whole_file(mock_open):
    """Test extracting content from a whole file"""
    file_content = "line 1\nline 2\nline 3\nline 4\nline 5"
    mock_open.return_value = io.StringIO(file_content)
    
    content = extract_from_file("test.py")
    
    # Should return all lines
    assert content == file_content
    mock_open.assert_called_once_with("test.py", "r", encoding="utf-8")


@patch('builtins.open')
def test_extract_from_file_line_range(mock_open):
    """Test extracting content from a specific line range"""
    file_content = "line 1\nline 2\nline 3\nline 4\nline 5"
    mock_open.return_value = io.StringIO(file_content)
    
    content = extract_from_file("test.py:2-4")
    
    # Should return only lines 2-4
    assert content == "line 2\nline 3\nline 4"
    mock_open.assert_called_once_with("test.py", "r", encoding="utf-8")


@patch('builtins.open')
def test_extract_from_file_single_line(mock_open):
    """Test extracting a single line from a file"""
    file_content = "line 1\nline 2\nline 3\nline 4\nline 5"
    mock_open.return_value = io.StringIO(file_content)
    
    content = extract_from_file("test.py:3")
    
    # Should return only line 3
    assert content == "line 3"
    mock_open.assert_called_once_with("test.py", "r", encoding="utf-8")


@patch('builtins.open')
def test_extract_from_file_invalid_range(mock_open):
    """Test extracting with an invalid line range"""
    file_content = "line 1\nline 2\nline 3\nline 4\nline 5"
    mock_open.return_value = io.StringIO(file_content)
    
    # Test with range outside file bounds
    content = extract_from_file("test.py:10-20")
    
    # Should return empty string for out-of-bounds
    assert content == ""
    mock_open.assert_called_once_with("test.py", "r", encoding="utf-8")


@patch('builtins.open')
def test_extract_from_file_invalid_format(mock_open):
    """Test extracting with an invalid line format"""
    # Test with invalid format
    with pytest.raises(ValueError):
        extract_from_file("test.py:invalid")
    
    # Ensure open wasn't called
    mock_open.assert_not_called()


def test_add_snippet_logic_with_code_string(mock_add_or_replace):
    """Test adding a snippet from a code string"""
    # Set up the mock to return a snippet ID
    mock_add_or_replace.return_value = "snippet123"
    
    # Call the function with a code string
    result = add_snippet_logic(
        code="def test_function():\n    return 'Hello, World!'",
        lang="python",
        description="Test function",
        custom_id=None,
        file_path=None
    )
    
    # Verify the result
    assert result == "snippet123"
    
    # Verify add_or_replace was called with correct arguments
    mock_add_or_replace.assert_called_once()
    args = mock_add_or_replace.call_args[0]
    
    # First arg should be the ID (None for auto-generation)
    assert args[0] is None
    
    # Second arg should be the code
    assert "def test_function()" in args[1]
    
    # Third arg should be the metadata
    metadata = args[2]
    assert metadata["type"] == "snippet"
    assert metadata["language"] == "python"
    assert metadata["description"] == "Test function"
    assert "code" in metadata
    assert "timestamp" in metadata


def test_add_snippet_logic_with_custom_id(mock_add_or_replace):
    """Test adding a snippet with a custom ID"""
    # Set up the mock to return the custom ID
    mock_add_or_replace.return_value = "custom_snippet_id"
    
    # Call the function with a custom ID
    result = add_snippet_logic(
        code="console.log('Hello');",
        lang="javascript",
        description="Logging example",
        custom_id="custom_snippet_id",
        file_path=None
    )
    
    # Verify the result
    assert result == "custom_snippet_id"
    
    # Verify add_or_replace was called with the custom ID
    mock_add_or_replace.assert_called_once()
    assert mock_add_or_replace.call_args[0][0] == "custom_snippet_id"


@patch('scripts.add_snippet.extract_from_file')
def test_add_snippet_logic_from_file(mock_extract, mock_add_or_replace):
    """Test adding a snippet from a file"""
    # Set up mock_extract to return some code
    mock_extract.return_value = "function hello() {\n  console.log('world');\n}"
    
    # Set up mock_add_or_replace to return a snippet ID
    mock_add_or_replace.return_value = "snippet456"
    
    # Call the function with a file path
    result = add_snippet_logic(
        code=None,
        lang=None,  # Should be auto-detected
        description="Hello function",
        custom_id=None,
        file_path="script.js:1-3"
    )
    
    # Verify the result
    assert result == "snippet456"
    
    # Verify extract_from_file was called
    mock_extract.assert_called_once_with("script.js:1-3")
    
    # Verify add_or_replace was called with correct arguments
    mock_add_or_replace.assert_called_once()
    metadata = mock_add_or_replace.call_args[0][2]
    assert metadata["language"] == "javascript"  # Should be auto-detected from code
    assert metadata["description"] == "Hello function"
    assert "script.js:1-3" in metadata["source_file"]  # Should include source file info


@patch('scripts.add_snippet.extract_from_file')
def test_add_snippet_logic_from_file_with_lang_override(mock_extract, mock_add_or_replace):
    """Test adding a snippet from a file with language override"""
    # Set up mock_extract to return some code
    mock_extract.return_value = "SELECT * FROM users;"
    
    # Set up mock_add_or_replace to return a snippet ID
    mock_add_or_replace.return_value = "snippet789"
    
    # Call the function with a file path and explicit language
    result = add_snippet_logic(
        code=None,
        lang="sql",  # Explicitly set, should override auto-detection
        description="User query",
        custom_id=None,
        file_path="query.txt:1"  # File has no recognizable extension
    )
    
    # Verify the result
    assert result == "snippet789"
    
    # Verify extract_from_file was called
    mock_extract.assert_called_once_with("query.txt:1")
    
    # Verify add_or_replace was called with the correct language
    mock_add_or_replace.assert_called_once()
    metadata = mock_add_or_replace.call_args[0][2]
    assert metadata["language"] == "sql"  # Should use the explicit language override


def test_add_snippet_logic_no_code_or_file(mock_add_or_replace):
    """Test error handling when neither code nor file_path is provided"""
    # Call the function with neither code nor file_path
    with pytest.raises(ValueError) as excinfo:
        add_snippet_logic(
            code=None,
            lang="python",
            description="This should fail",
            custom_id=None,
            file_path=None
        )
    
    # Verify the error message
    assert "Either code or file_path must be provided" in str(excinfo.value)
    
    # Verify add_or_replace was not called
    mock_add_or_replace.assert_not_called()


@patch('scripts.add_snippet.extract_from_file')
def test_add_snippet_logic_empty_file(mock_extract, mock_add_or_replace):
    """Test error handling when the file is empty"""
    # Set up mock_extract to return empty string
    mock_extract.return_value = ""
    
    # Call the function with a file path
    with pytest.raises(ValueError) as excinfo:
        add_snippet_logic(
            code=None,
            lang=None,
            description="Empty file",
            custom_id=None,
            file_path="empty.py"
        )
    
    # Verify the error message
    assert "No code content found" in str(excinfo.value)
    
    # Verify extract_from_file was called
    mock_extract.assert_called_once_with("empty.py")
    
    # Verify add_or_replace was not called
    mock_add_or_replace.assert_not_called() 