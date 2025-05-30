import pytest
from unittest.mock import patch, MagicMock
import datetime as dt

from scripts.tasks import (
    create_task_logic,
    start_task_logic,
    bump_task_logic,
    delete_task_logic,
    list_tasks_logic,
    add_note_to_task_logic,
    complete_step_logic,
    sync_task_vector,
    delete_task_vector
)
from scripts.task_store import Task, TaskStore


# ────────────────────────── Helper Function Tests ──────────────────────────

@pytest.fixture
def mock_add_or_replace():
    with patch('scripts.tasks.add_or_replace') as mock:
        yield mock

@pytest.fixture
def mock_delete_vector():
    with patch('scripts.tasks.delete_vector') as mock:
        yield mock


def test_sync_task_vector(mock_add_or_replace):
    # Create sample task dict
    task = {
        "id": 1,
        "title": "Test Task",
        "status": "todo",
        "progress": 0,
        "plan": ["Step 1", "Step 2"],
        "done_steps": [],
        "notes": "This is a note"
    }
    
    # Call the function
    sync_task_vector(task)
    
    # Verify add_or_replace was called with correct arguments
    mock_add_or_replace.assert_called_once()
    # First argument should be task ID
    assert mock_add_or_replace.call_args[0][0] == 1
    # Second argument should be text containing title and status
    assert "Test Task" in mock_add_or_replace.call_args[0][1]
    assert "todo" in mock_add_or_replace.call_args[0][1]
    # Third argument should be task metadata with type
    assert mock_add_or_replace.call_args[0][2]["type"] == "task"


def test_delete_task_vector(mock_delete_vector):
    # Set up the mock to return True (successful deletion)
    mock_delete_vector.return_value = True
    
    # Call the function
    delete_task_vector(1)
    
    # Verify delete_vector was called with correct task ID
    mock_delete_vector.assert_called_once_with(1)


# ────────────────────────── Logic Function Tests ──────────────────────────

@pytest.fixture
def mock_task_store():
    mock = MagicMock(spec=TaskStore)
    return mock


def test_create_task_logic(mock_task_store, mock_add_or_replace):
    # Call create_task_logic
    task_dict = create_task_logic(
        "New Test Task",
        "Step 1;Step 2;Step 3",
        "todo",
        mock_task_store
    )
    
    # Verify task store's add_task was called
    mock_task_store.add_task.assert_called_once()
    
    # Verify task properties
    assert task_dict["title"] == "New Test Task"
    assert task_dict["status"] == "todo"
    assert task_dict["progress"] == 0
    assert len(task_dict["plan"]) == 3
    assert "Step 1" in task_dict["plan"]
    assert "Step 2" in task_dict["plan"]
    assert "Step 3" in task_dict["plan"]
    assert task_dict["done_steps"] == []
    assert "created_at" in task_dict
    assert "updated_at" in task_dict
    
    # Verify vector sync was called
    mock_add_or_replace.assert_called_once()


def test_create_task_done_status(mock_task_store, mock_add_or_replace):
    # Call create_task_logic with done status
    task_dict = create_task_logic(
        "Completed Task",
        "Step 1;Step 2",
        "done",
        mock_task_store
    )
    
    # Verify task is marked as done with 100% progress
    assert task_dict["status"] == "done"
    assert task_dict["progress"] == 100
    assert task_dict["done_steps"] == ["Step 1", "Step 2"]


def test_start_task_logic_not_found(mock_task_store):
    # Set up mock to return None (task not found)
    mock_task_store.get_task_by_id.return_value = None
    
    # Call the function
    result, message = start_task_logic(1, mock_task_store)
    
    # Verify result
    assert result is None
    assert message == "TASK_NOT_FOUND"
    assert not mock_task_store.update_task.called


def test_start_task_logic_already_started(mock_task_store, mock_add_or_replace):
    # Create a task that's already in progress
    task = Task(id=1, title="Already Started", status="in_progress")
    task_dict = task.to_dict()
    
    # Set up mock to return this task
    mock_task_store.get_task_by_id.return_value = task
    
    # Call the function
    result, message = start_task_logic(1, mock_task_store)
    
    # Verify result
    assert result == task_dict
    assert message == "ALREADY_STARTED"
    assert not mock_task_store.update_task.called


def test_start_task_logic_success(mock_task_store, mock_add_or_replace):
    # Create a task that's not started
    task = Task(id=1, title="Task to Start", status="todo")
    
    # Set up mock to return this task
    mock_task_store.get_task_by_id.return_value = task
    
    # Call the function
    result, message = start_task_logic(1, mock_task_store)
    
    # Verify result
    assert result is not None
    assert message == "STARTED_NOW"
    assert result["status"] == "in_progress"
    
    # Verify task was updated
    mock_task_store.update_task.assert_called_once()
    
    # Verify vector sync was called
    mock_add_or_replace.assert_called_once()


def test_bump_task_logic_not_found(mock_task_store):
    # Set up mock to return None (task not found)
    mock_task_store.get_task_by_id.return_value = None
    
    # Call the function
    result, message = bump_task_logic(1, 25, mock_task_store)
    
    # Verify result
    assert result is None
    assert message == "TASK_NOT_FOUND"
    assert not mock_task_store.update_task.called


def test_bump_task_logic_no_change(mock_task_store, mock_add_or_replace):
    # Create a task with specific progress
    task = Task(id=1, title="Unchanged Task", status="in_progress", progress=50)
    task_dict = task.to_dict()
    
    # Set up mock to return this task
    mock_task_store.get_task_by_id.return_value = task
    
    # Call the function with delta=0
    result, message = bump_task_logic(1, 0, mock_task_store)
    
    # Verify result
    assert result == task_dict
    assert message == "NO_CHANGE_PROGRESS"
    assert not mock_task_store.update_task.called
    assert not mock_add_or_replace.called


def test_bump_task_logic_increase_progress(mock_task_store, mock_add_or_replace):
    # Create a task with starting progress
    task = Task(id=1, title="Progressing Task", status="in_progress", progress=25)
    
    # Set up mock to return this task
    mock_task_store.get_task_by_id.return_value = task
    
    # Call the function
    result, message = bump_task_logic(1, 25, mock_task_store)
    
    # Verify result
    assert result is not None
    assert message == "PROGRESS_CHANGED"
    assert result["progress"] == 50
    assert result["status"] == "in_progress"
    
    # Verify task was updated
    mock_task_store.update_task.assert_called_once()
    
    # Verify vector sync was called
    mock_add_or_replace.assert_called_once()


def test_bump_task_logic_complete_task(mock_task_store, mock_add_or_replace):
    # Create a task with progress near completion
    task = Task(id=1, title="Almost Done Task", status="in_progress", progress=90)
    
    # Set up mock to return this task
    mock_task_store.get_task_by_id.return_value = task
    
    # Call the function
    result, message = bump_task_logic(1, 15, mock_task_store)
    
    # Verify result
    assert result is not None
    assert message == "PROGRESS_CHANGED"
    assert result["progress"] == 100
    assert result["status"] == "done"
    
    # Verify task was updated
    mock_task_store.update_task.assert_called_once()
    
    # Verify vector sync was called
    mock_add_or_replace.assert_called_once()


def test_delete_task_logic(mock_task_store, mock_delete_vector):
    # Set up mock to return a task
    task = Task(id=1, title="Task to Delete")
    mock_task_store.get_task_by_id.return_value = task
    
    # Set up delete_vector to succeed
    mock_delete_vector.return_value = True
    
    # Call the function
    result = delete_task_logic(1, mock_task_store)
    
    # Verify result
    assert result is True
    
    # Verify task was deleted
    mock_task_store.delete_task.assert_called_once_with(1)
    
    # Verify vector was deleted
    mock_delete_vector.assert_called_once_with(1)


def test_delete_task_logic_not_found(mock_task_store, mock_delete_vector):
    # Set up mock to return None (task not found)
    mock_task_store.get_task_by_id.return_value = None
    
    # Call the function
    result = delete_task_logic(1, mock_task_store)
    
    # Verify result
    assert result is False
    
    # Verify no deletion attempted
    assert not mock_task_store.delete_task.called
    assert not mock_delete_vector.called


def test_list_tasks_logic_all(mock_task_store):
    # Create sample task list
    tasks = [
        Task(id=1, title="Task 1", status="todo"),
        Task(id=2, title="Task 2", status="in_progress"),
        Task(id=3, title="Task 3", status="done")
    ]
    
    # Convert to dicts
    task_dicts = [t.to_dict() for t in tasks]
    
    # Set up mock to return these tasks
    mock_task_store.get_all_tasks_as_dicts.return_value = task_dicts
    
    # Call the function with no filter
    result = list_tasks_logic(None, mock_task_store)
    
    # Verify all tasks are returned
    assert len(result) == 3
    # Verify get_all_tasks_as_dicts was called
    mock_task_store.get_all_tasks_as_dicts.assert_called_once()


def test_list_tasks_logic_with_filter(mock_task_store):
    # Create sample task list
    tasks = [
        Task(id=1, title="Task 1", status="todo"),
        Task(id=2, title="Task 2", status="in_progress"),
        Task(id=3, title="Task 3", status="done")
    ]
    
    # Convert to dicts
    task_dicts = [t.to_dict() for t in tasks]
    
    # Set up mock to return a filtered list
    filtered_tasks = [t for t in task_dicts if t["status"] == "in_progress"]
    mock_task_store.get_tasks_by_status.return_value = filtered_tasks
    
    # Call the function with a filter
    result = list_tasks_logic("in_progress", mock_task_store)
    
    # Verify filtered tasks are returned
    assert len(result) == 1
    assert result[0]["title"] == "Task 2"
    # Verify get_tasks_by_status was called
    mock_task_store.get_tasks_by_status.assert_called_once_with("in_progress")


def test_add_note_to_task_logic(mock_task_store, mock_add_or_replace):
    # Create a task
    task = Task(id=1, title="Task with Notes", notes=[])
    
    # Set up mock to return this task
    mock_task_store.get_task_by_id.return_value = task
    
    # Call the function
    result = add_note_to_task_logic(1, "This is a test note", mock_task_store)
    
    # Verify result
    assert result is not None
    assert "This is a test note" in result["notes"]
    
    # Verify task was updated
    mock_task_store.update_task.assert_called_once()
    
    # Verify vector sync was called
    mock_add_or_replace.assert_called_once()


def test_add_note_to_task_logic_not_found(mock_task_store, mock_add_or_replace):
    # Set up mock to return None (task not found)
    mock_task_store.get_task_by_id.return_value = None
    
    # Call the function
    result = add_note_to_task_logic(1, "This is a test note", mock_task_store)
    
    # Verify result
    assert result is None
    
    # Verify no updates were made
    assert not mock_task_store.update_task.called
    assert not mock_add_or_replace.called


def test_complete_step_logic_task_not_found(mock_task_store):
    # Set up mock to return None (task not found)
    mock_task_store.get_task_by_id.return_value = None
    
    # Call the function
    result, message = complete_step_logic(1, 0, False, mock_task_store)
    
    # Verify result
    assert result is None
    assert message == "TASK_NOT_FOUND"


def test_complete_step_logic_step_not_in_plan(mock_task_store, mock_add_or_replace):
    # Create a task with plan steps
    task = Task(id=1, title="Task with Plan", plan=["Step 1", "Step 2"], done_steps=[])
    
    # Set up mock to return this task
    mock_task_store.get_task_by_id.return_value = task
    
    # Call the function with invalid step index
    result, message = complete_step_logic(1, 5, False, mock_task_store)  # There's no Step 6
    
    # Verify result
    assert result is not None
    assert message == "STEP_INDEX_OUT_OF_RANGE"
    assert result["done_steps"] == []
    assert not mock_task_store.update_task.called
    assert not mock_add_or_replace.called


def test_complete_step_logic_complete_first_step(mock_task_store, mock_add_or_replace):
    # Create a task with plan steps
    task = Task(id=1, title="Task with Plan", plan=["Step 1", "Step 2"], done_steps=[])
    
    # Set up mock to return this task
    mock_task_store.get_task_by_id.return_value = task
    
    # Call the function to complete the first step
    result, message = complete_step_logic(1, 0, False, mock_task_store)  # Complete Step 1
    
    # Verify result
    assert result is not None
    assert message == "STEP_COMPLETED"
    assert "Step 1" in result["done_steps"]
    assert result["progress"] == 50  # 1 of 2 steps = 50%
    
    # Verify task was updated
    mock_task_store.update_task.assert_called_once()
    
    # Verify vector sync was called
    mock_add_or_replace.assert_called_once()


def test_complete_step_logic_complete_all_steps(mock_task_store, mock_add_or_replace):
    # Create a task with one step already done
    task = Task(id=1, title="Task with Plan", plan=["Step 1", "Step 2"], 
                done_steps=["Step 1"], progress=50, status="in_progress")
    
    # Set up mock to return this task
    mock_task_store.get_task_by_id.return_value = task
    
    # Call the function to complete the second step
    result, message = complete_step_logic(1, 1, False, mock_task_store)  # Complete Step 2
    
    # Verify result
    assert result is not None
    assert message == "STEP_COMPLETED"
    assert "Step 1" in result["done_steps"]
    assert "Step 2" in result["done_steps"]
    assert result["progress"] == 100  # All steps done
    assert result["status"] == "done"  # Task should be marked done
    
    # Verify task was updated
    mock_task_store.update_task.assert_called_once()
    
    # Verify vector sync was called
    mock_add_or_replace.assert_called_once()


def test_complete_step_logic_unmark_step(mock_task_store, mock_add_or_replace):
    # Create a task with completed steps
    task = Task(id=1, title="Task with Plan", plan=["Step 1", "Step 2"], 
                done_steps=["Step 1", "Step 2"], progress=100, status="done")
    
    # Set up mock to return this task
    mock_task_store.get_task_by_id.return_value = task
    
    # Call the function to unmark a step
    result, message = complete_step_logic(1, 0, True, mock_task_store)  # Unmark Step 1
    
    # Verify result
    assert result is not None
    assert message == "STEP_UNMARKED"
    assert "Step 1" not in result["done_steps"]
    assert "Step 2" in result["done_steps"]
    assert result["progress"] == 50  # 1 of 2 steps = 50%
    assert result["status"] == "in_progress"  # Task should not be done
    
    # Verify task was updated
    mock_task_store.update_task.assert_called_once()
    
    # Verify vector sync was called
    mock_add_or_replace.assert_called_once() 