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
from .memory_utils import ROOT, load_cfg # For TASKS_PATH from config

# Load config to get tasks file path
# Global TASKS_PATH and TASK_ID_COUNTER_FILE for module-level functions
_TASKS_PATH_STR_DEFAULT = "docs/TASKS.yaml"
_TASKS_PATH_CONFIG_KEY = "tasks.file"

_module_cfg = load_cfg()
_tasks_file_path_str = _module_cfg.get("tasks", {}).get("file", _TASKS_PATH_STR_DEFAULT)
TASKS_PATH_GLOBAL = ROOT / _tasks_file_path_str
TASK_ID_COUNTER_FILE_GLOBAL = TASKS_PATH_GLOBAL.parent / ".task_id_counter"


@dataclass
class Task:
    title: str  # Non-default arguments first
    id: _t.Optional[int] = None # Then default arguments
    status: str = "todo" # todo, in_progress, done, blocked, deferred
    progress: int = 0 # 0-100
    plan: _t.List[str] = field(default_factory=list)
    done_steps: _t.List[str] = field(default_factory=list)
    notes: _t.List[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict:
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
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Task":
        return cls(
            id=data.get("id"),
            title=data.get("title", "Untitled Task"),
            status=data.get("status", "todo"),
            progress=data.get("progress", 0),
            plan=data.get("plan", []),
            done_steps=data.get("done_steps", []),
            notes=data.get("notes", []),
            created_at=data.get("created_at", datetime.now(timezone.utc).isoformat()),
            updated_at=data.get("updated_at", datetime.now(timezone.utc).isoformat()),
        )

class TaskStore:
    def __init__(self, tasks_file_path: _t.Union[str, pathlib.Path, None] = None):
        if tasks_file_path:
            self.tasks_path = pathlib.Path(tasks_file_path)
        else:
            self.tasks_path = TASKS_PATH_GLOBAL
        
        # Determine counter file path relative to the current tasks_path
        self.task_id_counter_file = self.tasks_path.parent / ".task_id_counter"
        self.tasks: _t.List[Task] = self._load()

    def _load(self) -> _t.List[Task]:
        if not self.tasks_path.exists():
            return []
        try:
            tasks_text = self.tasks_path.read_text(encoding="utf-8")
            if not tasks_text.strip(): return []
            loaded_data = yaml.safe_load(tasks_text)
            if loaded_data is None: return []
            if not isinstance(loaded_data, list):
                logging.error(f"Tasks file {self.tasks_path} corrupt. Expected list.")
                return []
            return [Task.from_dict(task_data) for task_data in loaded_data if isinstance(task_data, dict) and "id" in task_data]
        except Exception as e:
            logging.error(f"Error loading tasks from {self.tasks_path}: {e}")
            return []

    def _save(self):
        try:
            self.tasks_path.parent.mkdir(parents=True, exist_ok=True)
            tasks_to_save = [task.to_dict() for task in self.tasks]
            self.tasks_path.write_text(
                yaml.safe_dump(tasks_to_save, allow_unicode=True, sort_keys=False, indent=2),
                encoding="utf-8"
            )
        except Exception as e:
            logging.error(f"Error saving tasks to {self.tasks_path}: {e}")

    def _get_next_id(self) -> int:
        try:
            current_counter = 0
            if self.task_id_counter_file.exists():
                try:
                    current_counter = int(self.task_id_counter_file.read_text().strip())
                except (ValueError, IOError): current_counter = 0
            next_counter = current_counter + 1
            self.task_id_counter_file.parent.mkdir(parents=True, exist_ok=True)
            self.task_id_counter_file.write_text(str(next_counter))
            return next_counter
        except Exception:
            if not self.tasks:
                return 1
            return max(task.id for task in self.tasks) + 1 if self.tasks else 1

    def add_task(self, task: Task):
        if task.id is None:
             task.id = self._get_next_id()
        task.updated_at = datetime.now(timezone.utc).isoformat()
        if task.created_at is None:
             task.created_at = datetime.now(timezone.utc).isoformat()
        self.tasks.append(task)
        self._save()

    def get_task_by_id(self, task_id: int) -> _t.Optional[Task]:
        return next((task for task in self.tasks if task.id == task_id), None)

    def update_task(self, updated_task: Task):
        for i, task in enumerate(self.tasks):
            if task.id == updated_task.id:
                updated_task.updated_at = datetime.now(timezone.utc).isoformat()
                self.tasks[i] = updated_task
                self._save()
                return
        logging.warning(f"Task with ID {updated_task.id} not found for update.")

    def complete_step(self, task_id: int, step_description: str):
        task = self.get_task_by_id(task_id)
        if task:
            if step_description in task.plan and step_description not in task.done_steps:
                task.done_steps.append(step_description)
                if task.plan: # Avoid division by zero
                    task.progress = int((len(task.done_steps) / len(task.plan)) * 100)
                if task.progress == 100:
                    task.status = "done"
                task.updated_at = datetime.now(timezone.utc).isoformat()
                self.update_task(task) # This will call _save()
            else:
                logging.warning(f"Step '{step_description}' not in plan or already done for task {task_id}.")
        else:
            logging.warning(f"Task with ID {task_id} not found for completing step.")

# Keep original functions for now, perhaps for scripts that use them directly
# Or decide if they should be removed/made private to TaskStore

def load_tasks() -> list[dict]:
    """Loads tasks from the YAML file specified in the configuration."""
    if not TASKS_PATH_GLOBAL.exists():
        logging.info(f"Tasks file {TASKS_PATH_GLOBAL} not found. Returning empty list of tasks.")
        return []
    try:
        tasks_text = TASKS_PATH_GLOBAL.read_text(encoding="utf-8")
        if not tasks_text.strip(): return []
        loaded_data = yaml.safe_load(tasks_text)
        if loaded_data is None: return []
        if not isinstance(loaded_data, list):
            logging.error(f"Tasks file {TASKS_PATH_GLOBAL} does not contain a list. Type: {type(loaded_data)}.")
            return []
        valid_tasks = []
        for task_dict in loaded_data:
            if isinstance(task_dict, dict) and "id" in task_dict and "title" in task_dict:
                valid_tasks.append(task_dict)
            else:
                logging.warning(f"Skipping invalid task entry in {TASKS_PATH_GLOBAL}: {task_dict}")
        return valid_tasks
    except Exception as e:
        logging.error(f"Error loading tasks from {TASKS_PATH_GLOBAL}: {e}")
        return []

def save_tasks(tasks: list[dict]):
    """Saves the list of tasks to the YAML file specified in the configuration."""
    try:
        TASKS_PATH_GLOBAL.parent.mkdir(parents=True, exist_ok=True)
        if not isinstance(tasks, list) or not all(isinstance(t, dict) for t in tasks):
            logging.error("Attempted to save tasks in an invalid format.")
            raise ValueError("Tasks must be a list of dictionaries.")
        TASKS_PATH_GLOBAL.write_text(
            yaml.safe_dump(tasks, allow_unicode=True, sort_keys=False, indent=2),
            encoding="utf-8"
        )
    except Exception as e:
        logging.error(f"Error saving tasks to {TASKS_PATH_GLOBAL}: {e}")

def next_id(tasks: list[dict]) -> int:
    try:
        current_counter = 0
        if TASK_ID_COUNTER_FILE_GLOBAL.exists():
            try: current_counter = int(TASK_ID_COUNTER_FILE_GLOBAL.read_text().strip())
            except (ValueError, IOError): current_counter = 0
        next_val = current_counter + 1
        TASK_ID_COUNTER_FILE_GLOBAL.parent.mkdir(parents=True, exist_ok=True)
        TASK_ID_COUNTER_FILE_GLOBAL.write_text(str(next_val))
        return next_val
    except Exception as e:
        logging.error(f"Error with task ID counter file: {e}. Falling back.")
        if not tasks: return 1
        try: return max(int(t["id"]) for t in tasks if "id" in t) + 1
        except (ValueError, TypeError): return len(tasks) + 1

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    print(f"Using tasks file: {TASKS_PATH_GLOBAL}")
    if not TASKS_PATH_GLOBAL.exists():
        TASKS_PATH_GLOBAL.parent.mkdir(parents=True, exist_ok=True)
        TASKS_PATH_GLOBAL.write_text(yaml.safe_dump([], allow_unicode=True), encoding="utf-8")
    
    # Test with TaskStore
    store = TaskStore()
    print(f"Loaded {len(store.tasks)} tasks via TaskStore.")
    
    new_task_obj = Task(id=None, title="Test Task from TaskStore class")
    store.add_task(new_task_obj)
    print(f"Added task: {new_task_obj.title} with ID {new_task_obj.id}")

    retrieved_task = store.get_task_by_id(new_task_obj.id)
    if retrieved_task:
        print(f"Retrieved task: {retrieved_task.title}, Status: {retrieved_task.status}")
        store.complete_step(retrieved_task.id, "Define class structure") # Example step

    # Original functional test
    # current_tasks_dicts = load_tasks()
    # print(f"Loaded {len(current_tasks_dicts)} tasks using load_tasks().")
    # new_task_id_val = next_id(current_tasks_dicts)
    # print(f"Next available task ID (functional): {new_task_id_val}")