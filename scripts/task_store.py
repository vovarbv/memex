#!/usr/bin/env python
"""
Manages loading and saving tasks from/to a YAML file.
"""
import yaml
import time
import pathlib
import logging
import typing as _t
from dataclasses import dataclass, field
from datetime import datetime, timezone

# Import memory_utils functions
try:
    from memex.scripts.memory_utils import load_cfg, get_tasks_file_path
except ImportError:
    try:
        from .memory_utils import load_cfg, get_tasks_file_path
    except ImportError:
        from memory_utils import load_cfg, get_tasks_file_path

# ───────────────────────────────────────── Error Classes ────
class DuplicateTaskIDError(ValueError):
    """Raised when duplicate task IDs are detected during task loading."""
    pass

# ───────────────────────────────────────── Task Class Definition ────
@dataclass
class Task:
    """
    Represents a single task with its metadata.
    """
    id: _t.Optional[int]
    title: str
    status: str = "todo"
    progress: int = 0
    plan: _t.List[str] = field(default_factory=list)
    done_steps: _t.List[str] = field(default_factory=list)
    notes: _t.Union[str, _t.List[str]] = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    priority: str = "medium"
    tags: _t.List[str] = field(default_factory=list)
    
    def update_timestamps(self, update_created=False):
        """Update the timestamps on the task."""
        now = datetime.now(timezone.utc).isoformat()
        if update_created:
            self.created_at = now
        self.updated_at = now
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "title": self.title,
            "status": self.status,
            "progress": self.progress,
            "plan": self.plan,
            "done_steps": self.done_steps,
            "notes": self.notes,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "priority": self.priority,
            "tags": self.tags
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Task':
        """Create a Task object from a dictionary."""
        # Ensure all fields are present with defaults
        task_data = {
            "id": data.get("id"),
            "title": data.get("title", ""),
            "status": data.get("status", "todo"),
            "progress": data.get("progress", 0),
            "plan": data.get("plan", []),
            "done_steps": data.get("done_steps", []),
            "notes": data.get("notes", ""),
            "created_at": data.get("created_at", datetime.now(timezone.utc).isoformat()),
            "updated_at": data.get("updated_at", datetime.now(timezone.utc).isoformat()),
            "priority": data.get("priority", "medium"),
            "tags": data.get("tags", [])
        }
        return cls(**task_data)

# ───────────────────────────────────────── Task Store Class ────
class TaskStore:
    """
    Manages a collection of tasks in a YAML file.
    """
    def __init__(self, file_path=None):
        """Initialize the task store with the given path or from config."""
        self.tasks = []
        self.next_id = 1
        self.cfg = load_cfg()
        
        if file_path is None:
            self.file_path = get_tasks_file_path(self.cfg)
        else:
            self.file_path = pathlib.Path(file_path)
        
        # Load tasks from file if it exists
        self.load_tasks()
    
    def load_tasks(self):
        """Load tasks from the YAML file."""
        try:
            if self.file_path.exists():
                with open(self.file_path, 'r', encoding='utf-8') as f:
                    data = yaml.safe_load(f)
                    if data is None:
                        # Empty file
                        self.tasks = []
                        self.next_id = 1
                        return
                    
                    if "tasks" in data and isinstance(data["tasks"], list):
                        # Check for duplicate IDs before converting to Task objects
                        task_ids = [t.get('id') for t in data["tasks"] if t.get('id') is not None]
                        duplicate_ids = set([tid for tid in task_ids if task_ids.count(tid) > 1])
                        
                        if duplicate_ids:
                            error_msg = f"Duplicate task IDs found in {self.file_path}: {', '.join(map(str, duplicate_ids))}"
                            logging.error(error_msg)
                            raise DuplicateTaskIDError(error_msg)
                        
                        self.tasks = [Task.from_dict(t) for t in data["tasks"]]
                        # Set the next ID to be one more than the highest ID
                        if self.tasks:
                            existing_ids = [t.id for t in self.tasks if t.id is not None]
                            self.next_id = max(existing_ids) + 1 if existing_ids else 1
                    else:
                        logging.warning(f"Invalid task data format in {self.file_path}. Expected 'tasks' list.")
                        self.tasks = []
            else:
                logging.info(f"Tasks file {self.file_path} does not exist. Starting with empty task list.")
                self.tasks = []
                self.next_id = 1
                # Create the parent directories if they don't exist
                self.file_path.parent.mkdir(parents=True, exist_ok=True)
                # Create an empty tasks file
                self.save_tasks()
        except DuplicateTaskIDError:
            # Re-raise this specific exception to be caught by the caller
            raise
        except (OSError, PermissionError) as e:
            logging.error(f"File access error loading tasks from {self.file_path}: {e}")
            self.tasks = []
            self.next_id = 1
        except yaml.YAMLError as e:
            logging.error(f"YAML parsing error in {self.file_path}: {e}")
            self.tasks = []
            self.next_id = 1
        except Exception as e:
            logging.error(f"Unexpected error loading tasks from {self.file_path}: {e}")
            self.tasks = []
            self.next_id = 1
    
    def save_tasks(self):
        """Save tasks to the YAML file."""
        try:
            # Create parent directories if they don't exist
            self.file_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(self.file_path, 'w', encoding='utf-8') as f:
                yaml.dump({"tasks": [t.to_dict() for t in self.tasks]}, f, sort_keys=False, allow_unicode=True)
            logging.info(f"Saved {len(self.tasks)} tasks to {self.file_path}")
        except (OSError, PermissionError) as e:
            logging.error(f"File access error saving tasks to {self.file_path}: {e}")
            raise
        except yaml.YAMLError as e:
            logging.error(f"YAML encoding error saving tasks to {self.file_path}: {e}")
            raise
        except Exception as e:
            logging.error(f"Unexpected error saving tasks to {self.file_path}: {e}")
            raise
    
    def get_all_tasks(self) -> _t.List[Task]:
        """Get all tasks."""
        return self.tasks
    
    def get_all_tasks_as_dicts(self) -> _t.List[dict]:
        """Get all tasks as dictionaries."""
        return [t.to_dict() for t in self.tasks]
    
    def get_task_by_id(self, task_id: int) -> _t.Optional[Task]:
        """Get a task by its ID."""
        for task in self.tasks:
            if task.id == task_id:
                return task
        return None
    
    def add_task(self, task: Task) -> Task:
        """Add a new task and assign an ID if needed."""
        if task.id is None:
            task.id = self.next_id
            self.next_id += 1
        task.update_timestamps(update_created=True)
        self.tasks.append(task)
        self.save_tasks()
        return task
    
    def update_task(self, task: Task) -> bool:
        """Update an existing task."""
        if task.id is None:
            return False
        
        for i, t in enumerate(self.tasks):
            if t.id == task.id:
                task.update_timestamps()
                self.tasks[i] = task
                self.save_tasks()
                return True
        
        return False
    
    def delete_task(self, task_id: int) -> bool:
        """Delete a task by its ID."""
        for i, task in enumerate(self.tasks):
            if task.id == task_id:
                del self.tasks[i]
                self.save_tasks()
                return True
        return False
    
    def complete_step(self, task_id: int, step_text: str) -> bool:
        """Mark a step as completed in a task."""
        task = self.get_task_by_id(task_id)
        if task is None:
            logging.warning(f"Task ID {task_id} not found when trying to complete step: {step_text}")
            return False
        
        # Check if the step is in the plan
        if step_text not in task.plan:
            logging.warning(f"Step '{step_text}' not in plan for task {task_id}")
            return False
        
        # Add to done_steps if not already done
        if step_text not in task.done_steps:
            task.done_steps.append(step_text)
            
            # Update progress
            if task.plan:
                task.progress = int((len(task.done_steps) / len(task.plan)) * 100)
                
                # If all steps are done, mark the task as done
                if len(task.done_steps) == len(task.plan):
                    task.status = "done"
            
            # Update timestamps and save
            task.update_timestamps()
            self.save_tasks()
            return True
        
        return False

