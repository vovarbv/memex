#!/usr/bin/env python
"""
Tests for the migration script that fixes old FAISS ID-keyed metadata format.
"""

import pytest
import json
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock

from ..scripts.migrate_faiss_keyed_metadata import (
    identify_incorrectly_keyed_items, 
    migrate_metadata_keys,
    create_backup
)


class TestMigrateFaissKeyedMetadata:
    """Tests for the FAISS keyed metadata migration functionality"""
    
    @pytest.fixture
    def old_format_metadata(self):
        """Sample metadata in old format (keyed by FAISS IDs)"""
        return {
            "_custom_to_faiss_id_map_": {
                "note_123": 101,
                "task_456": 102,
                "snippet_789": 103
            },
            "_faiss_id_to_custom_id_map_": {
                101: "note_123",
                102: "task_456", 
                103: "snippet_789"
            },
            # Old format: metadata stored under FAISS ID keys
            "101": {
                "id": "note_123",
                "text": "This is a note",
                "type": "note",
                "timestamp": "2024-01-01T00:00:00"
            },
            "102": {
                "id": "task_456",
                "text": "Complete the project",
                "type": "task",
                "status": "in_progress"
            },
            "103": {
                "id": "snippet_789",
                "text": "def hello(): print('world')",
                "type": "snippet",
                "language": "python"
            }
        }
    
    @pytest.fixture
    def correct_format_metadata(self):
        """Sample metadata in correct format (keyed by custom IDs)"""
        return {
            "_custom_to_faiss_id_map_": {
                "note_123": 101,
                "task_456": 102,
                "snippet_789": 103
            },
            "_faiss_id_to_custom_id_map_": {
                101: "note_123",
                102: "task_456", 
                103: "snippet_789"
            },
            # Correct format: metadata stored under custom ID keys
            "note_123": {
                "id": "note_123",
                "text": "This is a note",
                "type": "note",
                "timestamp": "2024-01-01T00:00:00"
            },
            "task_456": {
                "id": "task_456",
                "text": "Complete the project",
                "type": "task",
                "status": "in_progress"
            },
            "snippet_789": {
                "id": "snippet_789",
                "text": "def hello(): print('world')",
                "type": "snippet",
                "language": "python"
            }
        }
    
    @pytest.fixture
    def mixed_format_metadata(self):
        """Sample metadata with mixed old and new format"""
        return {
            "_custom_to_faiss_id_map_": {
                "note_correct": 101,
                "task_old": 102,
                "snippet_old": 103
            },
            # One item correctly keyed by custom ID
            "note_correct": {
                "id": "note_correct",
                "text": "This note is correctly keyed",
                "type": "note"
            },
            # Two items incorrectly keyed by FAISS ID
            "102": {
                "id": "task_old",
                "text": "This task is incorrectly keyed",
                "type": "task"
            },
            "103": {
                "id": "snippet_old", 
                "text": "print('incorrectly keyed')",
                "type": "snippet"
            }
        }
    
    def test_identify_incorrectly_keyed_items_old_format(self, old_format_metadata):
        """Test identification of incorrectly keyed items in old format"""
        incorrectly_keyed = identify_incorrectly_keyed_items(old_format_metadata)
        
        # All 3 items should be identified as incorrectly keyed
        assert len(incorrectly_keyed) == 3
        
        # Verify all custom IDs are found
        custom_ids = {item['custom_id'] for item in incorrectly_keyed}
        assert custom_ids == {"note_123", "task_456", "snippet_789"}
        
        # Verify FAISS ID mappings
        faiss_ids = {item['faiss_id'] for item in incorrectly_keyed}
        assert faiss_ids == {"101", "102", "103"}
        
        # Verify item types are preserved
        item_types = {item['item_type'] for item in incorrectly_keyed}
        assert item_types == {"note", "task", "snippet"}
    
    def test_identify_incorrectly_keyed_items_correct_format(self, correct_format_metadata):
        """Test that correctly formatted metadata is not flagged"""
        incorrectly_keyed = identify_incorrectly_keyed_items(correct_format_metadata)
        
        # No items should be flagged as incorrectly keyed
        assert len(incorrectly_keyed) == 0
    
    def test_identify_incorrectly_keyed_items_mixed_format(self, mixed_format_metadata):
        """Test identification in mixed format metadata"""
        incorrectly_keyed = identify_incorrectly_keyed_items(mixed_format_metadata)
        
        # Only 2 items should be identified as incorrectly keyed
        assert len(incorrectly_keyed) == 2
        
        custom_ids = {item['custom_id'] for item in incorrectly_keyed}
        assert custom_ids == {"task_old", "snippet_old"}
    
    def test_migrate_metadata_keys_dry_run(self, old_format_metadata):
        """Test migration in dry run mode"""
        original_meta = old_format_metadata.copy()
        
        stats = migrate_metadata_keys(old_format_metadata, dry_run=True)
        
        # Metadata should be unchanged in dry run
        assert old_format_metadata == original_meta
        
        # Stats should report what would be migrated
        assert stats['items_migrated'] == 3
        assert len(stats['errors']) == 0
    
    def test_migrate_metadata_keys_actual_migration(self, old_format_metadata):
        """Test actual migration of metadata keys"""
        stats = migrate_metadata_keys(old_format_metadata, dry_run=False)
        
        # Verify migration stats
        assert stats['items_migrated'] == 3
        assert len(stats['errors']) == 0
        
        # Verify old FAISS ID keys are gone
        assert "101" not in old_format_metadata
        assert "102" not in old_format_metadata
        assert "103" not in old_format_metadata
        
        # Verify new custom ID keys exist
        assert "note_123" in old_format_metadata
        assert "task_456" in old_format_metadata
        assert "snippet_789" in old_format_metadata
        
        # Verify metadata content is preserved
        assert old_format_metadata["note_123"]["text"] == "This is a note"
        assert old_format_metadata["task_456"]["type"] == "task"
        assert old_format_metadata["snippet_789"]["language"] == "python"
        
        # Verify ID fields are correct
        assert old_format_metadata["note_123"]["id"] == "note_123"
        assert old_format_metadata["task_456"]["id"] == "task_456"
        assert old_format_metadata["snippet_789"]["id"] == "snippet_789"
        
        # Verify mapping tables are preserved
        assert old_format_metadata["_custom_to_faiss_id_map_"]["note_123"] == 101
    
    def test_migrate_metadata_keys_mixed_format(self, mixed_format_metadata):
        """Test migration of mixed format metadata"""
        stats = migrate_metadata_keys(mixed_format_metadata, dry_run=False)
        
        # Only 2 items should be migrated
        assert stats['items_migrated'] == 2
        assert len(stats['errors']) == 0
        
        # Correctly keyed item should remain unchanged
        assert "note_correct" in mixed_format_metadata
        assert mixed_format_metadata["note_correct"]["text"] == "This note is correctly keyed"
        
        # Incorrectly keyed items should be migrated
        assert "102" not in mixed_format_metadata
        assert "103" not in mixed_format_metadata
        assert "task_old" in mixed_format_metadata
        assert "snippet_old" in mixed_format_metadata
    
    def test_create_backup(self):
        """Test backup file creation"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a test metadata file
            original_file = Path(temp_dir) / "metadata.json"
            test_data = {"test": "data"}
            
            with open(original_file, 'w') as f:
                json.dump(test_data, f)
            
            # Create backup
            backup_path = create_backup(original_file)
            
            # Verify backup exists and has correct content
            assert backup_path.exists()
            assert backup_path.suffix.startswith(".bak_")
            
            with open(backup_path, 'r') as f:
                backup_data = json.load(f)
            
            assert backup_data == test_data
    
    def test_empty_metadata(self):
        """Test handling of empty metadata"""
        empty_meta = {}
        
        incorrectly_keyed = identify_incorrectly_keyed_items(empty_meta)
        assert len(incorrectly_keyed) == 0
        
        stats = migrate_metadata_keys(empty_meta, dry_run=False)
        assert stats['items_migrated'] == 0
        assert len(stats['errors']) == 0
    
    def test_metadata_without_mapping(self):
        """Test handling of metadata without ID mapping"""
        meta_no_map = {
            "some_item": {
                "id": "some_item",
                "text": "No mapping for this item",
                "type": "note"
            }
        }
        
        incorrectly_keyed = identify_incorrectly_keyed_items(meta_no_map)
        assert len(incorrectly_keyed) == 0
        
        stats = migrate_metadata_keys(meta_no_map, dry_run=False)
        assert stats['items_migrated'] == 0
        assert len(stats['errors']) == 0