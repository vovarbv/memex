import pytest
from unittest.mock import patch, MagicMock, mock_open
import os
import json

from scripts.gen_memory_mdc import make, _formulate_query_from_active_tasks


def test_formulate_query_from_active_tasks():
    """Test query formulation from active tasks"""
    active_tasks = [
        {
            "id": 1,
            "title": "Implement user authentication",
            "status": "in_progress",
            "plan": ["Create login form", "Set up API routes", "Add token validation"],
            "done_steps": ["Create login form"],
            "notes": ["Use JWT for tokens"]
        },
        {
            "id": 2,
            "title": "Set up database schema",
            "status": "in_progress",
            "plan": ["Design tables", "Create migrations"],
            "done_steps": [],
            "notes": []
        }
    ]
    
    # Test with default parameters
    query = _formulate_query_from_active_tasks(active_tasks)
    
    # Verify query includes task information
    assert "user authentication" in query.lower()
    assert "database schema" in query.lower()
    
    # Test with limited tasks
    query = _formulate_query_from_active_tasks(active_tasks, max_tasks=1)
    assert "user authentication" in query.lower()
    # Second task should not be included
    assert "database schema" not in query.lower()


@patch('scripts.gen_memory_mdc.get_cursor_output_base_path')
@patch('scripts.gen_memory_mdc.TaskStore')
@patch('scripts.gen_memory_mdc.load_preferences')
@patch('scripts.gen_memory_mdc.load_cfg')
def test_make_function_success(mock_load_cfg, mock_load_preferences, 
                              mock_task_store_class, mock_get_cursor_path, tmp_path):
    """Test the make function completes successfully"""
    # Set up mocks
    mock_load_cfg.return_value = {
        "prompt": {
            "max_tokens": 1000,
            "top_k_tasks": 5,
            "top_k_context_items": 5
        }
    }
    
    mock_load_preferences.return_value = {
        "coding_style": "PEP 8",
        "language": "Python"
    }
    
    # Mock TaskStore instance
    mock_task_store = MagicMock()
    mock_task_store.get_all_tasks_as_dicts.return_value = [
        {"id": 1, "title": "Test Task", "status": "in_progress"}
    ]
    mock_task_store_class.return_value = mock_task_store
    
    # Mock cursor path - the function adds .cursor/rules to this
    mock_get_cursor_path.return_value = tmp_path
    
    # Run make function
    with patch('scripts.gen_memory_mdc.search') as mock_search:
        mock_search.return_value = []  # No search results
        
        success, message, path = make(quiet=True)
    
    # Verify success
    assert success is True
    assert "memory.mdc" in path
    assert (tmp_path / ".cursor" / "rules" / "memory.mdc").exists()


@patch('scripts.gen_memory_mdc.load_cfg')
def test_make_function_config_error(mock_load_cfg):
    """Test make function handles config loading errors"""
    mock_load_cfg.side_effect = Exception("Config error")
    
    success, message, path = make(quiet=True)
    
    assert success is False
    assert "Config error" in message
    assert path == ""


def test_formulate_query_empty_tasks():
    """Test query formulation with empty task list"""
    query = _formulate_query_from_active_tasks([])
    assert query == ""  # Should return empty string for no tasks


def test_formulate_query_with_notes():
    """Test that task notes are included in query"""
    tasks = [{
        "id": 1,
        "title": "Fix bug",
        "status": "in_progress",
        "notes": ["Check error handling", "Review logs"]
    }]
    
    query = _formulate_query_from_active_tasks(tasks)
    # Only the last note is included
    assert "Review logs" in query
    # First note should not be included
    assert "Check error handling" not in query