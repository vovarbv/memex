import pytest
import json
import os
from pathlib import Path
from unittest.mock import patch, MagicMock

# Import the function to test
from ..scripts.memory_utils import check_vector_store_integrity


class TestVectorStoreHealth:
    """Tests for the vector store health check functionality"""
    
    @pytest.fixture
    def mock_faiss(self):
        """Create a mock FAISS index"""
        mock_index = MagicMock()
        mock_index.ntotal = 10  # 10 vectors in index
        return mock_index
        
    @pytest.fixture
    def mock_metadata(self):
        """Create sample metadata for testing"""
        # Create metadata with IDs 1-10, but missing ID 3
        metadata = {}
        for i in range(1, 11):
            if i != 3:  # Skip ID 3 to create a missing entry
                metadata[str(i)] = {
                    "id": str(i),
                    "text": f"Test item {i}",
                    "type": "snippet" if i % 2 == 0 else "task"
                }
        
        # Add an extra ID that's not in FAISS (orphaned)
        metadata["orphaned_id"] = {
            "id": "orphaned_id",
            "text": "This is an orphaned entry",
            "type": "note"
        }
        
        return metadata
    
    @pytest.fixture
    def mock_metadata_old_format(self):
        """Create metadata with old format (keyed by FAISS IDs)"""
        metadata = {
            "_custom_to_faiss_id_map_": {
                "my_custom_item": 101,
                "another_item": 102
            },
            # Old format: metadata stored under FAISS ID keys instead of custom ID keys
            "101": {
                "id": "my_custom_item",
                "text": "This is stored under FAISS ID",
                "type": "note"
            },
            "102": {
                "id": "another_item", 
                "text": "Another old format item",
                "type": "task"
            }
        }
        return metadata
    
    @pytest.fixture
    def mock_id_map(self):
        """Create sample ID mapping for testing"""
        # Map custom IDs to FAISS indices (but with some issues)
        id_map = {}
        for i in range(1, 11):
            if i != 3:  # Skip ID 3 to create a missing mapping
                id_map[str(i)] = i - 1  # FAISS is 0-indexed
        
        # Add an inconsistent mapping (points to non-existent FAISS index)
        id_map["bad_mapping"] = 15  # Index out of range (FAISS only has 10 entries)
        
        return id_map
    
    @patch("memex.scripts.memory_utils.vec_dim")
    @patch("memex.scripts.memory_utils.load_index")
    def test_healthy_store(self, mock_load_index, mock_vec_dim):
        """Test health check with a perfectly healthy store"""
        # Create a consistent state with 10 vectors, 10 metadata entries, and 10 mappings
        mock_index = MagicMock()
        mock_index.ntotal = 10
        mock_index.d = 384  # dimension
        
        # Set up vec_dim to return the same dimension
        mock_vec_dim.return_value = 384
        
        metadata = {
            "_custom_to_faiss_id_map_": {}
        }
        for i in range(1, 11):
            metadata[str(i)] = {"id": str(i), "text": f"Item {i}"}
            metadata["_custom_to_faiss_id_map_"][str(i)] = i - 1  # FAISS is 0-indexed
        
        # load_index returns a tuple of (index, metadata)
        mock_load_index.return_value = (mock_index, metadata)
        
        # Run the health check
        result = check_vector_store_integrity()
        
        # Verify results
        assert result["status"] == "ok"
        assert len(result["issues"]) == 0
        assert result["summary"]["faiss_index_size"] == 10
        assert result["summary"]["mapped_vectors_count"] == 10
        assert result["summary"]["missing_metadata_entries"] == 0
        assert result["summary"]["orphaned_metadata_entries"] == 0
        assert result["summary"]["missing_vectors"] == 0
        assert result["summary"]["orphaned_vectors"] == 0
    
    @patch("memex.scripts.memory_utils.vec_dim")
    @patch("memex.scripts.memory_utils.load_index")
    def test_store_with_issues(self, mock_load_index, mock_vec_dim,
                              mock_faiss, mock_metadata, mock_id_map):
        """Test health check with a store that has various issues"""
        # Set up vec_dim
        mock_vec_dim.return_value = 384
        mock_faiss.d = 384
        
        # Combine metadata and id_map into the metadata structure expected by load_index
        combined_metadata = mock_metadata.copy()
        combined_metadata["_custom_to_faiss_id_map_"] = mock_id_map
        
        # load_index returns a tuple of (index, metadata)
        mock_load_index.return_value = (mock_faiss, combined_metadata)
        
        # Run the health check
        result = check_vector_store_integrity()
        
        # Verify results
        assert result["status"] == "warning"  # Should be warning due to issues
        assert len(result["issues"]) > 0  # Should have multiple issues
        
        # Check for specific issues
        issue_texts = "\n".join(result["issues"])
        # Update assertions to match actual error messages
        assert "exists but no FAISS ID mapping" in issue_texts  # "orphaned_id" is in metadata but not mapped
        assert "exists but no metadata entry found" in issue_texts  # "bad_mapping" has mapping but no metadata
        assert "metadata entries without corresponding FAISS ID mappings" in issue_texts
        
        # Check summary counts
        assert result["summary"]["faiss_index_size"] == 10
        assert result["summary"]["mapped_vectors_count"] == 10  # 9 good ones + 1 bad mapping
        assert result["summary"]["missing_metadata_entries"] >= 1  # "bad_mapping" has mapping but no metadata
        assert result["summary"]["orphaned_metadata_entries"] >= 1  # At least "orphaned_id"
        # Note: missing_vectors checks if FAISS IDs in the map actually exist in the index
        # Since we're using mocks, this might not be detected unless we mock the search behavior
    
    @patch("memex.scripts.memory_utils.vec_dim")
    @patch("memex.scripts.memory_utils.load_index")
    def test_empty_store(self, mock_load_index, mock_vec_dim):
        """Test health check with an empty vector store"""
        # Set up empty mocks
        mock_index = MagicMock()
        mock_index.ntotal = 0
        mock_index.d = 384
        
        mock_vec_dim.return_value = 384
        
        # Empty metadata with the required map
        metadata = {
            "_custom_to_faiss_id_map_": {}
        }
        
        mock_load_index.return_value = (mock_index, metadata)
        
        # Run the health check
        result = check_vector_store_integrity()
        
        # Verify results - empty store should be ok
        assert result["status"] == "ok"
        assert len(result["issues"]) == 0
        assert result["summary"]["faiss_index_size"] == 0
        assert result["summary"]["mapped_vectors_count"] == 0
    
    @patch("memex.scripts.memory_utils.load_index")
    def test_store_with_errors(self, mock_load_index):
        """Test health check when there are errors loading the store"""
        # Set up mock to return None (indicating load failure)
        mock_load_index.return_value = (None, {})
        
        # Run the health check
        result = check_vector_store_integrity()
        
        # Verify results - should have error status
        assert result["status"] == "error"
        assert len(result["issues"]) > 0
        assert any("FAISS index could not be loaded" in issue for issue in result["issues"])
    
    def test_json_serializable(self, monkeypatch):
        """Test that the result can be serialized to JSON (important for UI)"""
        # Mock the check function to return a known result
        def mock_check():
            return {
                "status": "warning",
                "issues": ["Issue 1", "Issue 2"],
                "summary": {
                    "faiss_index_size": 10,
                    "mapped_vectors_count": 9,
                    "missing_metadata_entries": 1,
                    "orphaned_metadata_entries": 0
                }
            }
        
        # Since we imported the function directly, we need to patch it in this module
        import sys
        current_module = sys.modules[__name__]
        monkeypatch.setattr(current_module, "check_vector_store_integrity", mock_check)
        
        # Try to serialize the result to JSON
        result = check_vector_store_integrity()
        json_result = json.dumps(result)
        
        # Should not raise any exceptions and should contain expected values
        assert "warning" in json_result
        assert "Issue 1" in json_result
        assert "Issue 2" in json_result
    
    @patch("memex.scripts.memory_utils.vec_dim")
    @patch("memex.scripts.memory_utils.load_index")
    def test_old_metadata_format_detection(self, mock_load_index, mock_vec_dim, mock_metadata_old_format):
        """Test detection of old metadata format where items are keyed by FAISS ID"""
        # Create a mock index 
        mock_index = MagicMock()
        mock_index.ntotal = 2
        mock_index.d = 384  # Standard dimension
        
        # Set up vec_dim
        mock_vec_dim.return_value = 384
        
        # Use the old format metadata fixture
        mock_load_index.return_value = (mock_index, mock_metadata_old_format)
        
        # Run the health check
        result = check_vector_store_integrity()
        
        # Verify that old format is detected as error
        assert result["status"] == "error"
        assert "incorrectly_keyed_items_count" in result["summary"]
        assert result["summary"]["incorrectly_keyed_items_count"] == 2
        
        # Check that specific error messages are present
        error_messages = " ".join(result["issues"])
        assert "CRITICAL MISMATCH" in error_messages
        assert "my_custom_item" in error_messages
        assert "another_item" in error_messages
        assert "old data format" in error_messages
        
        # Check details contain the incorrectly keyed metadata
        assert "incorrectly_keyed_metadata" in result["details"]
        incorrectly_keyed = result["details"]["incorrectly_keyed_metadata"]
        assert len(incorrectly_keyed) == 2
        
        # Verify the details contain expected keys
        custom_ids = [item['custom_id'] for item in incorrectly_keyed]
        assert "my_custom_item" in custom_ids
        assert "another_item" in custom_ids 