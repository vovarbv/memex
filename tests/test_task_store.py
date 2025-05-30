import pytest
import yaml
import tempfile
from pathlib import Path

from ..scripts.task_store import TaskStore, Task, DuplicateTaskIDError

# Test loading from a valid tasks file
def test_load_tasks_valid_file(sample_tasks_path):
    task_store = TaskStore(sample_tasks_path)
    assert len(task_store.tasks) == 3
    assert task_store.tasks[0].title == "Sample Task 1"
    assert task_store.tasks[1].id == 2
    assert task_store.tasks[2].status == "done"

# Test loading from an empty tasks file
def test_load_tasks_empty_file(empty_tasks_path):
    task_store = TaskStore(empty_tasks_path)
    assert len(task_store.tasks) == 0

# Test loading from a malformed tasks file (expecting an error)
def test_load_tasks_malformed_file(malformed_tasks_path, caplog):
    # TaskStore._load() should catch YAMLError and return an empty list, logging an error.
    task_store = TaskStore(malformed_tasks_path)
    assert len(task_store.tasks) == 0
    assert "Error loading tasks" in caplog.text
    assert str(malformed_tasks_path) in caplog.text # Ensure the path is in the log

# Test loading from a file with only comments
def test_load_tasks_comments_only_file(comments_only_tasks_path):
    task_store = TaskStore(comments_only_tasks_path)
    assert len(task_store.tasks) == 0

# Test adding a new task
def test_add_task(temp_task_file):
    task_store = TaskStore(temp_task_file)
    assert len(task_store.tasks) == 0
    new_task = Task(id=None, title="New Unique Task", plan=["Step A", "Step B"])
    task_store.add_task(new_task)
    assert len(task_store.tasks) == 1
    assert task_store.tasks[0].title == "New Unique Task"
    assert task_store.tasks[0].id is not None # ID should be assigned

# Test getting a task by ID
def test_get_task_by_id(sample_tasks_path):
    task_store = TaskStore(sample_tasks_path)
    task = task_store.get_task_by_id(2)
    assert task is not None
    assert task.title == "Sample Task 2"
    task_none = task_store.get_task_by_id(99)
    assert task_none is None

# Test updating an existing task
def test_update_task(sample_tasks_path, temp_task_file):
    # Copy sample tasks to a temporary file to avoid modifying fixtures
    with open(sample_tasks_path, 'r') as f_in, open(temp_task_file, 'w') as f_out:
        f_out.write(f_in.read())

    task_store = TaskStore(temp_task_file)
    task_to_update = task_store.get_task_by_id(1)
    assert task_to_update is not None
    task_to_update.status = "in_progress"
    task_to_update.progress = 75
    task_store.update_task(task_to_update)

    # Re-load to verify persistence
    updated_task_store = TaskStore(temp_task_file)
    updated_task = updated_task_store.get_task_by_id(1)
    assert updated_task is not None
    assert updated_task.status == "in_progress"
    assert updated_task.progress == 75

# Test completing a step in a task
def test_complete_step(sample_tasks_path, temp_task_file):
    with open(sample_tasks_path, 'r') as f_in, open(temp_task_file, 'w') as f_out:
        f_out.write(f_in.read())
    
    task_store = TaskStore(temp_task_file)
    task = task_store.get_task_by_id(1) # Task 1 has ["Step 1", "Step 2"]
    assert task.progress == 0
    assert "Step 1" not in task.done_steps

    task_store.complete_step(1, "Step 1")
    updated_task = task_store.get_task_by_id(1)
    assert "Step 1" in updated_task.done_steps
    assert updated_task.progress == 50 # 1 out of 2 steps done

    task_store.complete_step(1, "Step 2")
    updated_task_2 = task_store.get_task_by_id(1)
    assert "Step 2" in updated_task_2.done_steps
    assert updated_task_2.progress == 100
    assert updated_task_2.status == "done" # Assuming status updates automatically

# Test completing a non-existent step
def test_complete_non_existent_step(sample_tasks_path, temp_task_file):
    with open(sample_tasks_path, 'r') as f_in, open(temp_task_file, 'w') as f_out:
        f_out.write(f_in.read())
    
    task_store = TaskStore(temp_task_file)
    task_store.complete_step(1, "Non Existent Step") # Should not fail, but log a warning
    updated_task = task_store.get_task_by_id(1)
    assert "Non Existent Step" not in updated_task.done_steps
    assert updated_task.progress == 0 # Progress should not change

# Test duplicate task IDs
def test_duplicate_task_ids(tmp_path):
    """Test that loading tasks with duplicate IDs raises DuplicateTaskIDError."""
    tasks_file = tmp_path / "duplicate_tasks.yaml"
    duplicate_data = {
        "tasks": [
            {"id": 1, "title": "Task 1", "status": "todo"},
            {"id": 2, "title": "Task 2", "status": "todo"},
            {"id": 1, "title": "Duplicate Task", "status": "todo"}  # Duplicate ID
        ]
    }
    
    with open(tasks_file, 'w') as f:
        yaml.dump(duplicate_data, f)
    
    with pytest.raises(DuplicateTaskIDError) as excinfo:
        TaskStore(tasks_file)
    
    assert "1" in str(excinfo.value)  # Should mention the duplicate ID

# Test next_id calculation edge cases
def test_next_id_calculation(tmp_path):
    """Test next_id calculation with various ID configurations."""
    # Test with gap in IDs
    tasks_file = tmp_path / "gap_tasks.yaml"
    gap_data = {
        "tasks": [
            {"id": 1, "title": "Task 1", "status": "todo"},
            {"id": 3, "title": "Task 3", "status": "todo"},
            {"id": 7, "title": "Task 7", "status": "todo"}
        ]
    }
    
    with open(tasks_file, 'w') as f:
        yaml.dump(gap_data, f)
    
    task_store = TaskStore(tasks_file)
    assert task_store.next_id == 8  # Should be max_id + 1
    
    # Add a new task and verify ID assignment
    new_task = Task(id=None, title="New Task")
    task_store.add_task(new_task)
    assert task_store.tasks[-1].id == 8

# Test empty and non-existent TASKS.yaml
def test_non_existent_tasks_file(tmp_path):
    """Test behavior with non-existent TASKS.yaml file."""
    non_existent_file = tmp_path / "non_existent.yaml"
    
    # Should create empty store and file
    task_store = TaskStore(non_existent_file)
    assert len(task_store.tasks) == 0
    assert task_store.next_id == 1
    assert non_existent_file.exists()  # File should be created
    
    # Add a task to verify functionality
    new_task = Task(id=None, title="First Task")
    task_store.add_task(new_task)
    assert task_store.tasks[0].id == 1

# Test edge cases for task ID types
def test_task_id_type_handling(tmp_path):
    """Test handling of different ID types (string, float, etc.)."""
    tasks_file = tmp_path / "mixed_id_tasks.yaml"
    
    # Create tasks with string IDs (common in manual editing)
    mixed_data = {
        "tasks": [
            {"id": "1", "title": "String ID Task", "status": "todo"},
            {"id": 2.0, "title": "Float ID Task", "status": "todo"},
            {"id": 3, "title": "Int ID Task", "status": "todo"}
        ]
    }
    
    with open(tasks_file, 'w') as f:
        yaml.dump(mixed_data, f)
    
    task_store = TaskStore(tasks_file)
    
    # All IDs should be converted to integers
    assert all(isinstance(task.id, int) for task in task_store.tasks)
    assert task_store.tasks[0].id == 1
    assert task_store.tasks[1].id == 2
    assert task_store.tasks[2].id == 3
    assert task_store.next_id == 4

# Test deleting a task
def test_delete_task(sample_tasks_path, temp_task_file):
    """Test deleting tasks and ID reassignment."""
    with open(sample_tasks_path, 'r') as f_in, open(temp_task_file, 'w') as f_out:
        f_out.write(f_in.read())
    
    task_store = TaskStore(temp_task_file)
    initial_count = len(task_store.tasks)
    
    # Delete a task
    task_store.delete_task(2)
    assert len(task_store.tasks) == initial_count - 1
    assert task_store.get_task_by_id(2) is None
    
    # Verify next_id is still correct
    max_id = max(task.id for task in task_store.tasks)
    assert task_store.next_id == max_id + 1

# Test task serialization edge cases
def test_task_serialization_edge_cases():
    """Test Task.to_dict() and Task.from_dict() with edge cases."""
    # Task with all fields
    full_task = Task(
        id=1,
        title="Full Task",
        status="in_progress",
        progress=50,
        plan=["Step 1", "Step 2"],
        done_steps=["Step 1"],
        notes=["Note 1", "Note 2"],
        priority="high",
        tags=["urgent", "backend"]
    )
    
    task_dict = full_task.to_dict()
    reconstructed = Task.from_dict(task_dict)
    
    assert reconstructed.id == full_task.id
    assert reconstructed.title == full_task.title
    assert reconstructed.priority == full_task.priority
    assert reconstructed.tags == full_task.tags
    assert reconstructed.done_steps == full_task.done_steps
    
    # Task with minimal fields
    minimal_task = Task(id=2, title="Minimal Task")
    minimal_dict = minimal_task.to_dict()
    
    assert minimal_dict["id"] == 2
    assert minimal_dict["title"] == "Minimal Task"
    assert minimal_dict["status"] == "todo"
    assert minimal_dict["progress"] == 0
    assert minimal_dict["plan"] == []
    assert minimal_dict["notes"] == []

# Test concurrent modifications (simulated)
def test_save_tasks_error_handling(tmp_path, monkeypatch):
    """Test error handling during save_tasks."""
    tasks_file = tmp_path / "tasks.yaml"
    task_store = TaskStore(tasks_file)
    
    # Add a task
    task_store.add_task(Task(id=None, title="Test Task"))
    
    # Make the file read-only to simulate permission error
    tasks_file.chmod(0o444)
    
    # save_tasks should raise due to our changes in task_store.py
    with pytest.raises(PermissionError):
        task_store.save_tasks()
    
    # Restore permissions
    tasks_file.chmod(0o644) 