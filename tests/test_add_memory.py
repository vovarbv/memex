import pytest
from unittest.mock import patch, MagicMock
import datetime as dt
from datetime import timezone

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
        "note"  # item_type parameter
    )
    
    # Verify result
    assert result == "memory123"
    
    # Verify add_or_replace was called
    mock_add_or_replace.assert_called_once()
    
    # Check arguments
    args = mock_add_or_replace.call_args[0]
    # First arg is the ID (auto-generated UUID)
    assert len(args[0]) == 36  # UUID format
    # Second arg is the content text
    assert args[1] == "This is a test note"
    # Third arg is the metadata
    metadata = args[2]
    assert metadata["type"] == "note"
    assert metadata["text"] == "This is a test note"
    assert "timestamp" in metadata
    assert metadata["id"] == args[0]  # ID should match


def test_add_memory_item_logic_with_custom_id(mock_add_or_replace):
    """Test adding a memory item with a custom ID"""
    # Set up mock to return the custom ID
    custom_id = "custom_memory_id"
    mock_add_or_replace.return_value = custom_id
    
    # Call the function with a custom ID
    result = add_memory_item_logic(
        "Note with custom ID",
        "note",  # item_type
        custom_id=custom_id
    )
    
    # Verify result
    assert result == custom_id
    
    # Verify add_or_replace was called with the custom ID
    mock_add_or_replace.assert_called_once()
    assert mock_add_or_replace.call_args[0][0] == custom_id


def test_add_memory_item_logic_with_timestamp(mock_add_or_replace):
    """Test that timestamp is always auto-generated"""
    # Set up mock
    mock_add_or_replace.return_value = "memory_with_timestamp"
    
    # Call the function
    result = add_memory_item_logic(
        "Note with timestamp",
        "note"
    )
    
    # Verify result
    assert result == "memory_with_timestamp"
    
    # Verify timestamp was auto-generated (not custom)
    metadata = mock_add_or_replace.call_args[0][2]
    assert "timestamp" in metadata
    # Timestamp should be recent (within last minute)
    from datetime import datetime
    ts = datetime.fromisoformat(metadata["timestamp"])
    now = datetime.now(timezone.utc)
    assert (now - ts).total_seconds() < 60


def test_add_memory_item_logic_auto_timestamp(mock_add_or_replace):
    """Test that a timestamp is automatically added"""
    # Set up mock
    mock_add_or_replace.return_value = "memory_auto_timestamp"
    
    # Call the function
    result = add_memory_item_logic(
        "Note without timestamp",
        "fact"  # Different item_type
    )
    
    # Verify result
    assert result == "memory_auto_timestamp"
    
    # Verify a timestamp was added automatically
    metadata = mock_add_or_replace.call_args[0][2]
    assert "timestamp" in metadata
    
    # Basic validation of timestamp format
    timestamp = metadata["timestamp"]
    assert isinstance(timestamp, str)
    
    # Should be in ISO format
    assert "T" in timestamp  # ISO separator between date and time
    assert ":" in timestamp  # Time separator
    # Note: utcnow() doesn't include timezone, so no + or Z


def test_add_memory_item_logic_metadata_structure(mock_add_or_replace):
    """Test the metadata structure created by the function"""
    # Set up mock
    mock_add_or_replace.return_value = "memory_with_metadata"
    
    # Call the function with different item_type
    result = add_memory_item_logic(
        "Note with metadata",
        "reminder"  # Different item_type
    )
    
    # Verify result
    assert result == "memory_with_metadata"
    
    # Verify metadata structure
    saved_metadata = mock_add_or_replace.call_args[0][2]
    assert saved_metadata["type"] == "reminder"
    assert saved_metadata["text"] == "Note with metadata"
    assert "timestamp" in saved_metadata
    assert "id" in saved_metadata
    # Should only have these 4 fields
    assert len(saved_metadata) == 4


def test_add_memory_item_logic_error_handling(mock_add_or_replace):
    """Test error handling when add_or_replace fails"""
    # Set up mock to raise an exception
    mock_add_or_replace.side_effect = Exception("Vector store error")
    
    # Call the function - it should return None on error
    result = add_memory_item_logic("This should fail", "note")
    
    # Verify it returns None on error
    assert result is None
    
    # Verify add_or_replace was called
    mock_add_or_replace.assert_called_once()


def test_add_memory_item_logic_empty_content(mock_add_or_replace):
    """Test handling of empty content"""
    # Call the function with empty content
    result = add_memory_item_logic("", "note")
    
    # Should return None for empty content
    assert result is None
    
    # add_or_replace should not be called
    mock_add_or_replace.assert_not_called()
    
    # Reset the mock for the next test
    mock_add_or_replace.reset_mock()
    
    # Also test whitespace-only content
    result = add_memory_item_logic("   \n\t  ", "note")
    assert result is None
    mock_add_or_replace.assert_not_called()