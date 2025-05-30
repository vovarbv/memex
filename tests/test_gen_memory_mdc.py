import pytest
from unittest.mock import patch, MagicMock, mock_open
import os
import json

from scripts.gen_memory_mdc import make, load_tasks, _formulate_query_from_active_tasks


@pytest.fixture
def mock_tasks():
    """Returns mock task data for testing"""
    return [
        {
            "id": 1,
            "title": "Implement user authentication",
            "status": "in_progress",
            "progress": 60,
            "plan": ["Create login form", "Set up API routes", "Add token validation"],
            "done_steps": ["Create login form", "Set up API routes"],
            "notes": ["Use JWT for tokens", "Remember to handle token expiration"]
        },
        {
            "id": 2,
            "title": "Design database schema",
            "status": "todo",
            "progress": 0,
            "plan": ["Define user table", "Define product table", "Create relationships"],
            "done_steps": [],
            "notes": []
        },
        {
            "id": 3,
            "title": "Write documentation",
            "status": "done",
            "progress": 100,
            "plan": ["Document API", "Create README"],
            "done_steps": ["Document API", "Create README"],
            "notes": ["Published on GitHub"]
        }
    ]


@pytest.fixture
def mock_preferences():
    """Returns mock preferences data for testing"""
    return {
        "coding_style": "PEP 8 with a max line length of 100 characters",
        "primary_language": "Python 3.11",
        "database_type": "PostgreSQL",
        "testing_framework": "pytest"
    }


@pytest.fixture
def mock_search_results():
    """Returns mock search results for testing"""
    return [
        ({
            "id": "snippet1",
            "type": "snippet",
            "language": "python",
            "code": "def authenticate_user(username, password):\n    # Check credentials\n    return generate_token(user_id)",
            "description": "User authentication function"
        }, 0.85),
        ({
            "id": "snippet2",
            "type": "snippet",
            "language": "javascript",
            "code": "function validateToken(token) {\n  // Verify JWT token\n  return decodedToken;\n}",
            "description": "Token validation"
        }, 0.75),
        ({
            "id": "note1",
            "type": "note",
            "content": "API endpoints should follow RESTful conventions",
            "note_type": "insight"
        }, 0.65)
    ]


@pytest.fixture
def mock_code_chunks_results():
    """Returns mock code chunk search results for testing"""
    return [
        ({
            "id": "scripts/auth.py:function:validate_token",
            "type": "code_chunk",
            "source_file": "scripts/auth.py",
            "language": "python",
            "start_line": 42,
            "end_line": 78,
            "name": "validate_token",
            "content": "def validate_token(token):\n    \"\"\"Validate JWT token and return user ID.\"\"\"\n    try:\n        payload = jwt.decode(token)\n        return payload['user_id']\n    except Exception as e:\n        raise AuthError(str(e))"
        }, 0.92),
        ({
            "id": "scripts/db.py:function:get_user_by_id",
            "type": "code_chunk",
            "source_file": "scripts/db.py",
            "language": "python", 
            "start_line": 15,
            "end_line": 25,
            "name": "get_user_by_id",
            "content": "def get_user_by_id(user_id):\n    \"\"\"Retrieve user from database by ID.\"\"\"\n    return db.query(User).filter(User.id == user_id).first()"
        }, 0.87)
    ]


@patch('scripts.gen_memory_mdc.load_preferences')
@patch('scripts.gen_memory_mdc.search')
@patch('scripts.gen_memory_mdc.load_tasks')
@patch('scripts.gen_memory_mdc.load_cfg')
def test_make_basic_functionality(mock_load_cfg, mock_load_tasks, mock_search, 
                                 mock_load_preferences, mock_tasks, mock_preferences,
                                 mock_search_results, tmp_path):
    """Tests the basic functionality of the make function"""
    # Configure mocks
    mock_load_cfg.return_value = {
        "prompt": {
            "max_tokens": 1000,
            "top_k_tasks": 2,
            "top_k_snippets": 2
        },
        "system": {
            "cursor_output_dir_relative_to_memex_root": ".."
        }
    }
    mock_load_tasks.return_value = mock_tasks
    mock_load_preferences.return_value = mock_preferences
    mock_search.return_value = mock_search_results
    
    # Create temporary output directory
    mdc_dir = tmp_path / ".cursor" / "rules"
    mdc_dir.mkdir(parents=True, exist_ok=True)
    mdc_path = mdc_dir / "memory.mdc"
    
    # Mock ROOT and os.makedirs to use our temp directory
    with patch('scripts.gen_memory_mdc.ROOT', tmp_path), \
         patch('os.makedirs', return_value=None), \
         patch('builtins.open', mock_open()) as mock_file:
        
        # Call the function
        result = make()
        
        # Verify the function returned True
        assert result is True
        
        # Verify file operations
        mock_file.assert_called_once()
        # Verify the file content was written
        file_handle = mock_file()
        # Extract the content that was written
        content = ''.join([call.args[0] for call in file_handle.write.call_args_list])
        
        # Check if critical components are in the generated content
        assert "Implement user authentication" in content
        assert "Design database schema" in content  # Should include top 2 tasks
        assert "Write documentation" not in content  # Should exclude task with id=3
        assert "PEP 8" in content  # From preferences
        assert "User authentication function" in content  # From snippet1
        assert "Token validation" in content  # From snippet2
        assert "API endpoints" in content  # From note1


@patch('scripts.gen_memory_mdc.load_preferences')
@patch('scripts.gen_memory_mdc.search')
@patch('scripts.gen_memory_mdc.load_tasks')
@patch('scripts.gen_memory_mdc.load_cfg')
@patch('scripts.gen_memory_mdc.num_tokens_from_string')
def test_make_token_limiting(mock_num_tokens, mock_load_cfg, mock_load_tasks, 
                            mock_search, mock_load_preferences, mock_tasks, 
                            mock_preferences, mock_search_results, tmp_path):
    """Tests that the make function correctly limits tokens"""
    # Configure mocks
    mock_load_cfg.return_value = {
        "prompt": {
            "max_tokens": 500,  # Small token limit
            "top_k_tasks": 2,
            "top_k_snippets": 2
        },
        "system": {
            "cursor_output_dir_relative_to_memex_root": ".."
        }
    }
    mock_load_tasks.return_value = mock_tasks
    mock_load_preferences.return_value = mock_preferences
    mock_search.return_value = mock_search_results
    
    # Make token count exceed the limit after preferences but before tasks/snippets
    def token_counter(text):
        if "PEP 8" in text:  # Preferences section
            return 300
        elif "Implement user authentication" in text:  # First task
            return 150
        elif "validateToken" in text:  # A snippet
            return 100
        return 50  # Default for shorter texts
    
    mock_num_tokens.side_effect = token_counter
    
    # Create temporary output directory and mock file operations
    mdc_dir = tmp_path / ".cursor" / "rules"
    mdc_dir.mkdir(parents=True, exist_ok=True)
    
    with patch('scripts.gen_memory_mdc.ROOT', tmp_path), \
         patch('os.makedirs', return_value=None), \
         patch('builtins.open', mock_open()) as mock_file:
        
        # Call the function
        result = make()
        
        # Verify the function returned True
        assert result is True
        
        # Extract the content
        file_handle = mock_file()
        content = ''.join([call.args[0] for call in file_handle.write.call_args_list])
        
        # Check token limiting behavior
        assert "PEP 8" in content  # Preferences should be included
        assert "Implement user authentication" in content  # First task should be included
        assert "Design database schema" not in content  # Second task should be excluded due to token limit
        assert "validateToken" not in content  # Snippets should be excluded due to token limit


@patch('builtins.open')
def test_load_tasks_valid_file(mock_open, sample_tasks_path):
    """Tests loading tasks from a valid file"""
    # Read actual content from the fixture
    with open(sample_tasks_path, 'r') as f:
        fixture_content = f.read()
    
    # Configure mock to return this content
    mock_open.return_value.__enter__.return_value.read.return_value = fixture_content
    
    # Call function with mocked file path
    with patch('scripts.gen_memory_mdc.Path.exists', return_value=True):
        tasks = load_tasks("mocked_path")
    
    # Verify tasks were loaded
    assert len(tasks) == 3
    assert tasks[0]["title"] == "Sample Task 1"


@patch('builtins.open')
def test_load_tasks_file_not_found(mock_open):
    """Tests behavior when tasks file doesn't exist"""
    # Configure Path.exists to return False
    with patch('scripts.gen_memory_mdc.Path.exists', return_value=False):
        tasks = load_tasks("nonexistent_path")
    
    # Should return empty list
    assert tasks == []
    # Verify open was not called
    mock_open.assert_not_called()


@patch('builtins.open')
def test_load_tasks_malformed_yaml(mock_open):
    """Tests behavior with malformed YAML"""
    # Configure mock to return invalid YAML
    mock_open.return_value.__enter__.return_value.read.return_value = "- this: is not valid: yaml"
    
    # Call function with mocked file path
    with patch('scripts.gen_memory_mdc.Path.exists', return_value=True):
        tasks = load_tasks("mocked_path")
    
    # Should return empty list on YAML error
    assert tasks == []


def test_formulate_query_from_active_tasks():
    """Tests that task-based query formulation works correctly"""
    # Create test active tasks
    active_tasks = [
        {
            "id": 1,
            "title": "Implement user authentication",
            "plan": ["Create login form", "Set up API routes", "Add token validation"],
            "done_steps": ["Create login form"]
        },
        {
            "id": 2,
            "title": "Refactor database code",
            "plan": ["Create ORM models", "Optimize queries", "Add migrations"],
            "done_steps": []
        }
    ]
    
    # Generate query
    query = _formulate_query_from_active_tasks(active_tasks)
    
    # Verify query contains task titles and pending steps
    assert "Implement user authentication" in query
    assert "Refactor database code" in query
    assert "Set up API routes" in query  # Pending step from first task
    assert "Add token validation" in query  # Pending step from first task
    assert "Create login form" not in query  # Completed step should be excluded
    assert "Create ORM models" in query  # Pending step from second task
    
    # Test limiting behavior
    query_limited = _formulate_query_from_active_tasks(active_tasks, max_tasks=1, max_plan_items=1)
    # Should only contain first task and its first pending step
    assert "Implement user authentication" in query_limited
    assert "Set up API routes" in query_limited
    assert "Add token validation" not in query_limited  # Should be excluded by max_plan_items
    assert "Refactor database code" not in query_limited  # Should be excluded by max_tasks
    
    # Test empty input
    assert _formulate_query_from_active_tasks([]) == ""


@patch('scripts.gen_memory_mdc.TaskStore')
@patch('scripts.gen_memory_mdc.search')
@patch('scripts.gen_memory_mdc.load_preferences')
@patch('scripts.gen_memory_mdc.load_cfg')
def test_task_driven_context_retrieval(mock_load_cfg, mock_load_preferences, mock_search, 
                                    mock_task_store, mock_tasks, mock_code_chunks_results, tmp_path):
    """Tests that task-driven context retrieval works correctly when no focus is provided"""
    # Configure mocks
    mock_load_cfg.return_value = {
        "prompt": {
            "max_tokens": 10000,
            "top_k_tasks": 2,
            "top_k_context_items": 2
        },
        "system": {
            "cursor_output_dir_relative_to_memex_root": ".."
        }
    }
    mock_load_preferences.return_value = {}
    
    # Configure TaskStore
    task_store_instance = MagicMock()
    task_store_instance.get_all_tasks_as_dicts.return_value = mock_tasks
    mock_task_store.return_value = task_store_instance
    
    # Configure search to return code chunks for task-driven context
    mock_search.return_value = mock_code_chunks_results
    
    # Create temporary output directory
    mdc_dir = tmp_path / ".cursor" / "rules"
    mdc_dir.mkdir(parents=True, exist_ok=True)
    
    with patch('scripts.gen_memory_mdc.ROOT', tmp_path), \
         patch('os.makedirs', return_value=None), \
         patch('builtins.open', mock_open()) as mock_file:
        
        # Call the function without a focus
        result = make(focus=None)
        
        # Verify the function returned True
        assert result is True
        
        # Verify search was called with a query derived from tasks
        # At least one of the search calls should be for task-derived context
        task_driven_call = False
        for call in mock_search.call_args_list:
            args, kwargs = call
            if "Implement user authentication" in args[0] and "Add token validation" in args[0]:
                task_driven_call = True
                break
        assert task_driven_call, "Search was not called with task-derived query"
        
        # Extract the content
        file_handle = mock_file()
        content = ''.join([call.args[0] for call in file_handle.write.call_args_list])
        
        # Check that task-derived context section is included
        assert "Task-Relevant Context" in content
        # Check that code chunks are included
        assert "validate_token" in content
        assert "get_user_by_id" in content


@patch('scripts.gen_memory_mdc.TaskStore')
@patch('scripts.gen_memory_mdc.search')
@patch('scripts.gen_memory_mdc.load_preferences')
@patch('scripts.gen_memory_mdc.load_cfg')
def test_focus_overrides_task_driven_context(mock_load_cfg, mock_load_preferences, mock_search, 
                                          mock_task_store, mock_tasks, mock_search_results, tmp_path):
    """Tests that focus query overrides task-driven context when provided"""
    # Configure mocks
    mock_load_cfg.return_value = {
        "prompt": {
            "max_tokens": 10000,
            "top_k_tasks": 2,
            "top_k_context_items": 2
        },
        "system": {
            "cursor_output_dir_relative_to_memex_root": ".."
        }
    }
    mock_load_preferences.return_value = {}
    
    # Configure TaskStore
    task_store_instance = MagicMock()
    task_store_instance.get_all_tasks_as_dicts.return_value = mock_tasks
    mock_task_store.return_value = task_store_instance
    
    # Configure search to return snippets for focus-based context
    mock_search.return_value = mock_search_results
    
    # Create temporary output directory
    mdc_dir = tmp_path / ".cursor" / "rules"
    mdc_dir.mkdir(parents=True, exist_ok=True)
    
    with patch('scripts.gen_memory_mdc.ROOT', tmp_path), \
         patch('os.makedirs', return_value=None), \
         patch('builtins.open', mock_open()) as mock_file:
        
        # Call the function with a focus
        result = make(focus="authentication")
        
        # Verify the function returned True
        assert result is True
        
        # Verify search was called with the focus query
        mock_search.assert_any_call("authentication", top_k=2, pred=mock_search.call_args[0][2])
        
        # Extract the content
        file_handle = mock_file()
        content = ''.join([call.args[0] for call in file_handle.write.call_args_list])
        
        # Check that focus-based context section is included
        assert "Focus Context for: authentication" in content
        # Ensure task-driven context is not present when focus is provided
        assert "Task-Relevant Context" not in content
        # Check that focus-relevant snippets are included
        assert "User authentication function" in content
        assert "Token validation" in content 