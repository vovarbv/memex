import pytest
from unittest.mock import patch, MagicMock
import datetime as dt

from scripts.add_memory import add_memory_item_logic


@pytest.fixture
def mock_add_or_replace():
    with patch('scripts.add_memory.add_or_replace') as mock:
        yield mock


def test_add_memory_item_logic_basic(mock_add_or_replace):
    """Test adding a basic memory item"""
    # Set up mock to return a custom ID
    mock_add_or_replace.return_value = "memory123"
    
    # Call the function with basic content
    result = add_memory_item_logic(
        "This is a test note",
        {"type": "note", "note_type": "insight"}
    )
    
    # Verify result
    assert result == "memory123"
    
    # Verify add_or_replace was called
    mock_add_or_replace.assert_called_once()
    
    # Check arguments
    args = mock_add_or_replace.call_args[0]
    # First arg is the ID (None for auto-generation)
    assert args[0] is None
    # Second arg is the content text
    assert args[1] == "This is a test note"
    # Third arg is the metadata
    metadata = args[2]
    assert metadata["type"] == "note"
    assert metadata["note_type"] == "insight"
    assert "timestamp" in metadata


def test_add_memory_item_logic_with_custom_id(mock_add_or_replace):
    """Test adding a memory item with a custom ID"""
    # Set up mock to return the custom ID
    custom_id = "custom_memory_id"
    mock_add_or_replace.return_value = custom_id
    
    # Call the function with a custom ID
    result = add_memory_item_logic(
        "Note with custom ID",
        {"type": "note", "note_type": "reference"},
        custom_id=custom_id
    )
    
    # Verify result
    assert result == custom_id
    
    # Verify add_or_replace was called with the custom ID
    mock_add_or_replace.assert_called_once()
    assert mock_add_or_replace.call_args[0][0] == custom_id


def test_add_memory_item_logic_with_timestamp(mock_add_or_replace):
    """Test adding a memory item with a pre-defined timestamp"""
    # Set up mock
    mock_add_or_replace.return_value = "memory_with_timestamp"
    
    # Define a specific timestamp
    timestamp = "2023-01-01T12:00:00Z"
    
    # Call the function with metadata including a timestamp
    result = add_memory_item_logic(
        "Note with timestamp",
        {"type": "note", "note_type": "journal", "timestamp": timestamp}
    )
    
    # Verify result
    assert result == "memory_with_timestamp"
    
    # Verify timestamp was preserved in metadata
    metadata = mock_add_or_replace.call_args[0][2]
    assert metadata["timestamp"] == timestamp


def test_add_memory_item_logic_auto_timestamp(mock_add_or_replace):
    """Test that a timestamp is automatically added if not provided"""
    # Set up mock
    mock_add_or_replace.return_value = "memory_auto_timestamp"
    
    # Call the function without a timestamp in metadata
    result = add_memory_item_logic(
        "Note without timestamp",
        {"type": "note", "note_type": "other"}
    )
    
    # Verify result
    assert result == "memory_auto_timestamp"
    
    # Verify a timestamp was added automatically
    metadata = mock_add_or_replace.call_args[0][2]
    assert "timestamp" in metadata
    
    # Basic validation of timestamp format
    timestamp = metadata["timestamp"]
    assert isinstance(timestamp, str)
    
    # Should be in ISO format with timezone
    assert "T" in timestamp  # ISO separator between date and time
    assert ":" in timestamp  # Time separator
    assert "+" in timestamp or "Z" in timestamp  # Timezone indicator


def test_add_memory_item_logic_metadata_preserved(mock_add_or_replace):
    """Test that additional metadata fields are preserved"""
    # Set up mock
    mock_add_or_replace.return_value = "memory_with_extra_metadata"
    
    # Create metadata with extra fields
    metadata = {
        "type": "note", 
        "note_type": "insight",
        "priority": "high",
        "tags": ["important", "follow-up"],
        "related_task_id": 42,
        "author": "test_user"
    }
    
    # Call the function with extra metadata
    result = add_memory_item_logic("Note with extra metadata", metadata)
    
    # Verify result
    assert result == "memory_with_extra_metadata"
    
    # Verify all metadata fields were preserved
    saved_metadata = mock_add_or_replace.call_args[0][2]
    assert saved_metadata["type"] == "note"
    assert saved_metadata["note_type"] == "insight"
    assert saved_metadata["priority"] == "high"
    assert saved_metadata["tags"] == ["important", "follow-up"]
    assert saved_metadata["related_task_id"] == 42
    assert saved_metadata["author"] == "test_user"
    assert "timestamp" in saved_metadata  # Auto-added


def test_add_memory_item_logic_error_handling(mock_add_or_replace):
    """Test error handling when add_or_replace fails"""
    # Set up mock to raise an exception
    mock_add_or_replace.side_effect = Exception("Vector store error")
    
    # Call the function
    with pytest.raises(Exception) as excinfo:
        add_memory_item_logic("This should fail", {"type": "note"})
    
    # Verify the error was passed through
    assert "Vector store error" in str(excinfo.value)
    
    # Verify add_or_replace was called
    mock_add_or_replace.assert_called_once() 