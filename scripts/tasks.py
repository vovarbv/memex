#!/usr/bin/env python
"""
CLI for managing tasks in YAML task store.

Usage examples:
  - Add a task: tasks.py add "Implement user login" --plan "Create UI;Backend logic;Tests"
  - List tasks: tasks.py list
  - Start a task: tasks.py start 3
  - Complete a task: tasks.py done 3
  - Delete a task: tasks.py delete 3
  - Add a note to a task: tasks.py note 3 "Found a bug in the login form submission"
"""
import sys
import os
import re
import argparse
import subprocess
import logging
import pathlib
import yaml
import importlib
import textwrap
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional, Union, Tuple

# Use proper package imports with multiple fallbacks
try:
    # When run as a module within the package
    from . import task_store
    from .memory_utils import load_cfg
    from .thread_safe_store import add_or_replace, delete_vector
except ImportError:
    try:
        # When run as a script directly from scripts directory
        import task_store
        from memory_utils import load_cfg
        from thread_safe_store import add_or_replace, delete_vector
    except ImportError:
        try:
            # When run from memex directory or as installed package
            from memex.scripts import task_store
            from memex.scripts.memory_utils import load_cfg
            from memex.scripts.thread_safe_store import add_or_replace, delete_vector
        except ImportError as e:
            logging.error(f"Failed to import required modules: {e}")
            logging.error("Try running from: memex/scripts/ directory OR memex/ directory OR install as package")
            sys.exit(1)

# ───────────────────────────────────────── Logging Setup ────
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# ───────────────────────────────────────── Free Text Parsing ────
def parse_free_text_task(text: str) -> Dict[str, Any]:
    """
    Parse a free-text task description into a structured task object.
    
    Advanced parsing capabilities:
    - Case-insensitive keywords with flexible whitespace
    - Multiple plan formats (semicolons, numbered list, newlines)
    - Status synonyms (wip -> in_progress, done -> completed)
    - Priority abbreviations (h -> high, m -> medium, l -> low)
    - Progress value cleaning (supports "25%" or "25")
    - Tag variations (space-separated, comma-separated, with/without #)
    - Multi-word tags with quotes
    - Comprehensive notes handling
    
    Args:
        text: Free-text task description
        
    Returns:
        Dictionary with parsed task fields
    """
    if not text or not text.strip():
        return {"title": "", "plan": [], "status": "todo", "progress": 0}
    
    # Normalize line endings and split by lines
    lines = text.replace("\r\n", "\n").split("\n")
    
    # Initialize result with defaults
    result = {
        "title": "",
        "plan": [],
        "status": "todo",
        "progress": 0,
        "priority": "medium",
        "tags": [],
        "notes": []
    }
    
    # C.1.3: Status synonyms mapping
    status_mapping = {
        "todo": "todo",
        "to-do": "todo",
        "backlog": "todo",
        "pending": "todo",
        "new": "todo",
        "in_progress": "in_progress",
        "in progress": "in_progress",
        "inprogress": "in_progress",
        "wip": "in_progress",
        "working": "in_progress",
        "started": "in_progress",
        "ongoing": "in_progress",
        "active": "in_progress",
        "done": "done",
        "complete": "done",
        "completed": "done",
        "finished": "done",
        "resolved": "done",
        "closed": "done"
    }
    
    # C.1.4: Priority mapping (with abbreviations)
    priority_mapping = {
        "h": "high",
        "high": "high",
        "important": "high",
        "critical": "high",
        "urgent": "high",
        "m": "medium",
        "med": "medium",
        "medium": "medium",
        "normal": "medium",
        "default": "medium",
        "l": "low",
        "low": "low",
        "minor": "low",
        "trivial": "low"
    }
    
    # First line is always the title unless it starts with a known key
    # C.1.1: Case-insensitive keyword detection
    first_line = lines[0].strip()
    if first_line and not re.match(r"^(plan|status|progress|priority|tags|notes):\s*", first_line, re.IGNORECASE):
        result["title"] = first_line
        lines = lines[1:]
    
    # Process lines looking for keys and their values
    current_key = None
    plan_as_list = [] # Store plan in order if using newline-separated format
    
    for line in lines:
        line = line.strip()
        if not line:
            current_key = None  # Reset on empty line
            continue
            
        # C.1.1: Case-insensitive keyword detection with flexible whitespace
        key_match = re.match(r"^(plan|status|progress|priority|tags|notes)\s*:\s*(.*)", line, re.IGNORECASE)
        if key_match:
            current_key = key_match.group(1).lower()
            value = key_match.group(2).strip()
            
            if current_key == "plan" and value:
                # C.1.2: Multiple plan formats
                if ";" in value:
                    # Semicolon-separated format: plan: step 1; step 2; step 3
                    result["plan"] = [step.strip() for step in value.split(";") if step.strip()]
                elif re.search(r'\d+\.\s', value):
                    # Numbered list style: plan: 1. step one 2. step two
                    # Extract text after numbers
                    steps = re.findall(r'\d+\.\s+([^0-9.]+?)(?=\s+\d+\.|$)', value + " ")
                    result["plan"] = [step.strip() for step in steps if step.strip()]
                else:
                    # Single line or beginning of a multi-line plan
                    plan_as_list = [value] if value else []
                    result["plan"] = plan_as_list
            elif current_key == "status":
                # C.1.3: Status synonyms
                status_value = value.lower().strip()
                result["status"] = status_mapping.get(status_value, status_value)
            elif current_key == "progress":
                # C.1.5: Progress value cleaning
                try:
                    # Handle different formats (25%, 25.5%, 25)
                    progress_value = value.replace("%", "").strip()
                    if progress_value:
                        # Handle decimal values
                        if "." in progress_value:
                            result["progress"] = int(float(progress_value))
                        else:
                            result["progress"] = int(progress_value)
                except ValueError:
                    logging.warning(f"Couldn't parse progress value: {value}")
            elif current_key == "priority":
                # C.1.4: Priority abbreviations
                priority_value = value.lower().strip()
                result["priority"] = priority_mapping.get(priority_value, priority_value)
            elif current_key == "tags" and value:
                # C.1.6: Tag variations
                tags = []
                
                # Handle quoted multi-word tags
                def extract_quoted_tags(text):
                    # Extract tags in quotes
                    quoted_tags = re.findall(r'"([^"]+)"', text)
                    # Remove quoted parts from text
                    remaining = re.sub(r'"[^"]+"', '', text)
                    return quoted_tags, remaining
                
                quoted_tags, remaining_text = extract_quoted_tags(value)
                tags.extend(quoted_tags)
                
                # Process remaining text for non-quoted tags
                if remaining_text:
                    # Check if comma-separated
                    if "," in remaining_text:
                        additional_tags = [t.strip() for t in remaining_text.split(",") if t.strip()]
                    else:
                        # Space-separated
                        additional_tags = [t.strip() for t in remaining_text.split() if t.strip()]
                    
                    # Clean tags (remove # if present)
                    for tag in additional_tags:
                        if tag.startswith("#"):
                            tags.append(tag[1:])
                        else:
                            tags.append(tag)
                
                result["tags"] = tags
            elif current_key == "notes" and value:
                result["notes"].append(value)
        elif current_key == "plan":
            # C.1.2: Support for newline-separated plan items
            plan_as_list.append(line)
            result["plan"] = plan_as_list
        elif current_key == "notes":
            # C.1.7: Multi-line notes handling
            result["notes"].append(line)
        else:
            # C.1.7: Text with no recognized keyword is treated as notes
            result["notes"].append(line)
    
    # If no title was found but we have notes, use the first note as title
    if not result["title"] and result["notes"]:
        result["title"] = result["notes"].pop(0)
    
    # If we only have one note, convert from list to string for backward compatibility
    if not result["notes"]:
        result["notes"] = ""
    
    return result

# ───────────────────────────────────────── Task Create/Sync Logic ────
def create_task_logic(title: str, plan_str: str, status: str, task_store_instance: task_store.TaskStore) -> dict:
    """
    Core logic for creating a new task.
    
    Args:
        title: Title of the task
        plan_str: Semicolon-separated plan steps
        status: Initial status (todo, in_progress, done)
        task_store_instance: TaskStore instance to use
    
    Returns:
        The created task dictionary
    """
    # Create plan steps list
    plan_steps = []
    if plan_str:
        plan_steps = [p.strip() for p in plan_str.split(";") if p.strip()]
    
    # Create new task object
    new_task = task_store.Task(
        id=None,  # Will be set by TaskStore
        title=title,
        status=status,
        progress=0 if status != "done" else 100,
        plan=plan_steps,
        done_steps=[] if status != "done" else plan_steps.copy(),
        notes=""
    )
    
    # Add task to store - This assigns an ID to new_task.id
    task_store_instance.add_task(new_task)
    
    # Now create a dictionary for syncing to FAISS
    # Critical: Create the dictionary AFTER the task has been added and assigned an ID
    task_dict_for_sync = new_task.to_dict()
    
    # Validate that the task has a proper ID before syncing
    if new_task.id is None or task_dict_for_sync.get("id") is None:
        logging.error("Task was not assigned a valid ID during creation. FAISS sync aborted.")
        return task_dict_for_sync
        
    # Sync to vector store
    sync_task_vector(task_dict_for_sync)
    
    return task_dict_for_sync

def create_task_from_free_text(text: str, task_store_instance: task_store.TaskStore) -> dict:
    """
    Create a new task from free-text input.
    
    Args:
        text: Free-text task description
        task_store_instance: TaskStore instance to use
        
    Returns:
        The created task dictionary
    """
    parsed = parse_free_text_task(text)
    
    # Create new task object
    new_task = task_store.Task(
        id=None,  # Will be set by TaskStore
        title=parsed.get("title", ""),
        status=parsed.get("status", "todo"),
        progress=parsed.get("progress", 0),
        plan=parsed.get("plan", []),
        done_steps=parsed.get("done_steps", []),
        notes=parsed.get("notes", ""),
        priority=parsed.get("priority", "medium"),
        tags=parsed.get("tags", [])
    )
    
    # Add task to store - This assigns an ID to new_task.id
    task_store_instance.add_task(new_task)
    
    # Now create a dictionary for syncing to FAISS
    # Critical: Create the dictionary AFTER the task has been added and assigned an ID
    task_dict_for_sync = new_task.to_dict()
    
    # Validate that the task has a proper ID before syncing
    if new_task.id is None or task_dict_for_sync.get("id") is None:
        logging.error("Task was not assigned a valid ID during creation. FAISS sync aborted.")
        return task_dict_for_sync
        
    # Sync to vector store
    sync_task_vector(task_dict_for_sync)
    
    return task_dict_for_sync

def sync_task_vector(task_dict: Dict[str, Any]) -> None:
    """
    Synchronize a task to the vector store.
    
    This function embeds the task and adds/updates its vector representation.
    
    Args:
        task_dict: Task dictionary to synchronize
    """
    # Use add_or_replace from memory_utils to add/update the task vector
    task_id = str(task_dict.get("id"))
    
    # Ensure we have a valid task ID
    if task_id is None or task_id.lower() == "none" or not task_id:
        logging.error(f"Cannot sync task with invalid ID: {task_id}")
        return
    
    # Format the task content for embedding
    title = task_dict.get("title", "")
    status = task_dict.get("status", "")
    plan = task_dict.get("plan", [])
    notes = task_dict.get("notes", "")
    
    # Create a rich text representation for embedding
    task_content = [f"Task: {title}"]
    task_content.append(f"Status: {status}")
    
    if plan:
        task_content.append("Plan:")
        for step in plan:
            task_content.append(f"- {step}")
    
    if notes:
        if isinstance(notes, list):
            task_content.append("Notes:")
            for note in notes:
                task_content.append(f"- {note}")
        else:
            task_content.append(f"Notes: {notes}")
    
    # Join all content with newlines
    embedding_text = "\n".join(task_content)
    
    # Create metadata
    metadata = {
        "id": task_id,
        "type": "task",
        "title": title,
        "status": status,
        "progress": task_dict.get("progress", 0),
        "content": embedding_text,
        "task_data": task_dict  # Store the complete task data for retrieval
    }
    
    # Add or replace in vector store
    add_or_replace(task_id, embedding_text, metadata)
    logging.info(f"Task #{task_id} '{title}' synced to vector store")

# ───────────────────────────────────────── CLI Commands ────

def cmd_add_task(args, ts):
    """
    Add a new task to the task store.
    
    Args:
        args: Parsed arguments
        ts: TaskStore instance
    """
    created_task = create_task_logic(
        args.title, 
        args.plan or "", 
        args.status,
        ts
    )
    print(f"✅ Added task #{created_task['id']}: {created_task['title']}")

def cmd_start(args, ts):
    """Start a task by marking it as in_progress."""
    task = ts.get_task_by_id(args.id)
    if not task:
        print(f"❌ Error: Task with ID {args.id} not found.")
        sys.exit(1)
    
    task.status = "in_progress"
    task.update_timestamps()
    ts.update_task(task)
    
    # Sync to vector store
    sync_task_vector(task.to_dict())
    
    print(f"▶️ Started task #{args.id}: {task.title}")

def cmd_bump(args, ts):
    """Update task progress by adding a delta value."""
    task = ts.get_task_by_id(args.id)
    if not task:
        print(f"❌ Error: Task with ID {args.id} not found.")
        sys.exit(1)
    
    old_progress = task.progress
    task.progress = max(0, min(100, old_progress + args.delta))
    
    if task.progress >= 100:
        task.status = "done"
    
    task.update_timestamps()
    ts.update_task(task)
    
    # Sync to vector store
    sync_task_vector(task.to_dict())
    
    print(f"📊 Updated task #{args.id} progress: {old_progress}% → {task.progress}%")
    if task.status == "done":
        print(f"✅ Task #{args.id} is now marked as done!")

def cmd_done(args, ts):
    """Mark a task as done with 100% progress."""
    task = ts.get_task_by_id(args.id)
    if not task:
        print(f"❌ Error: Task with ID {args.id} not found.")
        sys.exit(1)
    
    task.status = "done"
    task.progress = 100
    
    # Mark all plan steps as done
    if task.plan:
        task.done_steps = task.plan.copy()
    
    task.update_timestamps()
    ts.update_task(task)
    
    # Sync to vector store
    sync_task_vector(task.to_dict())
    
    print(f"✅ Completed task #{args.id}: {task.title}")

def cmd_delete(args, ts):
    """Delete a task."""
    task = ts.get_task_by_id(args.id)
    if not task:
        print(f"❌ Error: Task with ID {args.id} not found.")
        sys.exit(1)
    
    task_id = task.id
    task_title = task.title
    
    # Delete from task store
    if ts.delete_task(task_id):
        # Delete from vector store
        task_id_str = str(task_id)
        try:
            delete_vector(task_id_str)
            print(f"🗑️ Deleted task #{task_id}: {task_title}")
        except Exception as e:
            print(f"⚠️ Task deleted from local store but not from vector store: {e}")
    else:
        print(f"❌ Error: Failed to delete task #{task_id}.")

def cmd_note(args, ts):
    """Add a note to a task."""
    task = ts.get_task_by_id(args.id)
    if not task:
        print(f"❌ Error: Task with ID {args.id} not found.")
        sys.exit(1)
    
    # Add the note to the task
    note_text = args.note_text.strip()
    if not note_text:
        print("❌ Error: Note text cannot be empty.")
        sys.exit(1)
    
    # Handle notes as either a string or a list
    if isinstance(task.notes, list):
        task.notes.append(note_text)
    elif isinstance(task.notes, str):
        if task.notes:
            task.notes = [task.notes, note_text]
        else:
            task.notes = [note_text]
    else:
        task.notes = [note_text]
    
    task.update_timestamps()
    ts.update_task(task)
    
    # Sync to vector store
    sync_task_vector(task.to_dict())
    
    print(f"📝 Note added to task #{args.id}: {task.title}")

def cmd_list(args, ts):
    """List tasks, optionally filtered by status."""
    tasks = ts.get_all_tasks()
    
    # Filter by status if provided
    if args.status:
        statuses = [s.strip() for s in args.status.split(",")]
        filtered_tasks = [task for task in tasks if task.status in statuses]
    else:
        filtered_tasks = tasks

    if not filtered_tasks:
        if args.status:
            print(f"No tasks found with status(es): {args.status}")
        else:
            print("No tasks found.")
        return

    print(f"{'ID':<4} | {'Title':<40} | {'Status':<12} | {'Progress':>8} | {'Plan Steps':<15} | Last Update")
    print("-" * 100)
    
    for task in sorted(filtered_tasks, key=lambda t: t.id or 0):
        title = task.title or 'N/A'
        title_short = textwrap.shorten(title, width=38, placeholder="...")
        status = task.status or 'N/A'
        progress = f"{task.progress}%"

        plan = task.plan or []
        done_steps = task.done_steps or []
        plan_summary = f"{len(done_steps)}/{len(plan)}" if plan else "0/0"

        updated_at_iso = task.updated_at or ""
        updated_at_str = ""
        if updated_at_iso:
            try:
                updated_at_dt = datetime.fromisoformat(updated_at_iso)
                updated_at_str = updated_at_dt.strftime('%Y-%m-%d %H:%M')
            except ValueError:
                updated_at_str = updated_at_iso # Show raw if not parsable

        print(f"{task.id:<4} | {title_short:<40} | {status:<12} | {progress:>8} | {plan_summary:<15} | {updated_at_str}")

        if args.details: # Show more details if requested
            if plan:
                print("    Plan:")
                for i, step in enumerate(plan):
                    # Status indicator
                    mark = "✅" if step in done_steps else ("🔄" if status == "in_progress" else "⏳")
                    print(f"      {i+1}. [{mark}] {step}")
                
            if task.notes:
                print("    Notes:")
                if isinstance(task.notes, list):
                    for note in task.notes[-3:]:  # Show last 3 notes
                        print(f"      - {textwrap.shorten(note, width=80, placeholder='...')}")
                else:
                    print(f"      - {textwrap.shorten(task.notes, width=80, placeholder='...')}")
                    
            print("-" * 100)

def cmd_complete_step(args):
    task_store_instance = task_store.TaskStore()
    task_id = int(args.id)
    step_index = int(args.step_index)
    
    task_dict, message_code = complete_step_logic(task_id, step_index, args.unmark, task_store_instance)
    
    if not task_dict:
        if message_code == "TASK_NOT_FOUND":
            print(f"❌ Error: Task with ID {task_id} not found.")
        elif message_code == "INVALID_STEP":
            print(f"❌ Error: Invalid step index {step_index} for task #{task_id}.")
        sys.exit(1)
    
    plan = task_dict.get("plan", [])
    if not plan:
        print(f"❌ Error: Task #{task_id} has no plan steps to mark.")
        sys.exit(1)
    
    step_text = plan[step_index - 1] if step_index <= len(plan) else "Unknown step"
    
    if message_code == "ALREADY_UNMARKED":
        print(f"ℹ️ Step #{step_index} is already marked as incomplete: '{step_text}'")
    elif message_code == "ALREADY_MARKED":
        print(f"ℹ️ Step #{step_index} is already marked as complete: '{step_text}'")
    elif message_code == "STEP_UNMARKED":
        print(f"↩️ Unmarked step #{step_index} as incomplete: '{step_text}'")
    elif message_code == "STEP_MARKED":
        print(f"✓ Marked step #{step_index} as complete: '{step_text}'")
    
    print(f"📊 Task #{task_id} progress: {task_dict['progress']}%. Status: {task_dict['status']}.")

# ───────────────────────────────────────── Argument Parser ────
def build_parser():
    parser = argparse.ArgumentParser(description="CLI Task Manager for Project Memory.")
    subparsers = parser.add_subparsers(dest="command", title="Commands", required=True)

    # Add command
    p_add = subparsers.add_parser("add", help="Add a new task.")
    p_add.add_argument("title", help="Title of the task.")
    p_add.add_argument("--plan", help="Semicolon-separated list of plan steps (e.g., \"Step1;Step2\").", default="")
    p_add.add_argument("--status", help="Initial status for the task (e.g., 'todo', 'in_progress', 'done').", default="todo")
    p_add.set_defaults(func=cmd_add_task)

    # Start command
    p_start = subparsers.add_parser("start", help="Mark a task as 'in_progress'.")
    p_start.add_argument("id", help="ID of the task to start.")
    p_start.set_defaults(func=cmd_start)

    # Bump command
    p_bump = subparsers.add_parser("bump", help="Increase/decrease task progress by a delta.")
    p_bump.add_argument("id", help="ID of the task.")
    p_bump.add_argument("delta", type=int, help="Percentage points to add (can be negative).")
    p_bump.set_defaults(func=cmd_bump)

    # Done command
    p_done = subparsers.add_parser("done", help="Mark a task as 'done' (progress 100%).")
    p_done.add_argument("id", help="ID of the task to mark as done.")
    p_done.set_defaults(func=cmd_done)

    # Delete command
    p_delete = subparsers.add_parser("delete", help="Delete a task.")
    p_delete.add_argument("id", help="ID of the task to delete.")
    p_delete.add_argument("--force", "-f", action="store_true", help="Skip confirmation prompt.")
    p_delete.set_defaults(func=cmd_delete)

    # Note command
    p_note = subparsers.add_parser("note", help="Add a note to a task.")
    p_note.add_argument("id", help="ID of the task.")
    p_note.add_argument("note_text", help="Text of the note to add.")
    p_note.set_defaults(func=cmd_note)

    # Complete step command
    p_cs = subparsers.add_parser("complete_step", help="Mark/unmark a plan step as done/pending.")
    p_cs.add_argument("id", help="ID of the task.")
    p_cs.add_argument("step_index", type=int, help="1-based index of the plan step.")
    p_cs.add_argument("--unmark", action="store_true", help="Unmark step as done, set to pending.")
    p_cs.set_defaults(func=cmd_complete_step)

    # List command
    p_list = subparsers.add_parser("list", help="List tasks.")
    p_list.add_argument("--status", help="Filter by status (e.g., 'todo', 'in_progress', 'done', or comma-separated).", default=None)
    p_list.add_argument("--details", action="store_true", help="Show detailed plan and notes for listed tasks.")
    p_list.set_defaults(func=cmd_list)

    return parser

# ───────────────────────────────────────── Main Function ────

def main(args=None):
    """Main entry point for the script."""
    try:
        parser = argparse.ArgumentParser(description="Manage tasks")
        subparsers = parser.add_subparsers(dest="command", help="Sub-command to run")
        
        # Add task
        add_parser = subparsers.add_parser("add", help="Add a new task")
        add_parser.add_argument("title", help="Task title")
        add_parser.add_argument("--plan", help="Semicolon-separated plan steps")
        add_parser.add_argument("--status", default="todo", choices=["todo", "in_progress", "done", "blocked", "deferred"], help="Task status")
        add_parser.set_defaults(func=cmd_add_task)
        
        # List tasks
        list_parser = subparsers.add_parser("list", help="List tasks")
        list_parser.add_argument("--status", help="Filter by status")
        list_parser.add_argument("--details", action="store_true", help="Show detailed task information")
        list_parser.set_defaults(func=cmd_list)
        
        # Mark as in progress
        start_parser = subparsers.add_parser("start", help="Mark a task as in progress")
        start_parser.add_argument("id", type=int, help="Task ID")
        start_parser.set_defaults(func=cmd_start)
        
        # Mark as done
        done_parser = subparsers.add_parser("done", help="Mark a task as done")
        done_parser.add_argument("id", type=int, help="Task ID")
        done_parser.set_defaults(func=cmd_done)
        
        # Delete a task
        delete_parser = subparsers.add_parser("delete", help="Delete a task")
        delete_parser.add_argument("id", type=int, help="Task ID")
        delete_parser.set_defaults(func=cmd_delete)
        
        # Add a note to a task
        note_parser = subparsers.add_parser("note", help="Add a note to a task")
        note_parser.add_argument("id", type=int, help="Task ID")
        note_parser.add_argument("note_text", help="Note text")
        note_parser.set_defaults(func=cmd_note)
        
        # Update progress
        bump_parser = subparsers.add_parser("bump", help="Update task progress")
        bump_parser.add_argument("id", type=int, help="Task ID")
        bump_parser.add_argument("delta", type=int, help="Progress delta (0-100)")
        bump_parser.set_defaults(func=cmd_bump)
        
        parsed_args = parser.parse_args(args)
        
        if not parsed_args.command:
            parser.print_help()
            return
        
        # Create TaskStore instance once
        ts = task_store.TaskStore()
        
        # Call the appropriate function with the TaskStore instance
        if hasattr(parsed_args, 'func'):
            # Pass the TaskStore instance to all command functions
            parsed_args.func(parsed_args, ts)
        else:
            parser.print_help()
            
    except Exception as e:
        logging.error(f"An error occurred while executing command '{getattr(parsed_args, 'command', 'unknown')}': {e}")
        print(f"❌ An unexpected error occurred. Check logs for details.")
        return 1
    
    return 0

# ───────────────────────────────────────── Main Execution ────
if __name__ == "__main__":
    sys.exit(main())

def test_parse_free_text_task():
    """
    Test the free text task parser with various input formats.
    This can be run via the main CLI entrypoint with 'python -m memex.scripts.tasks test_parser'
    """
    test_cases = [
        # Basic cases
        {
            "name": "Title only",
            "input": "My Simple Task",
            "expected": {
                "title": "My Simple Task",
                "status": "todo",
                "plan": [],
                "notes": [],
                "priority": "medium",
                "tags": [],
                "progress": 0
            }
        },
        
        # Plan format variations
        {
            "name": "Plan with semicolons",
            "input": "Complex Task\nplan: Step 1; Step 2; Step 3",
            "expected": {
                "title": "Complex Task",
                "status": "todo", 
                "plan": ["Step 1", "Step 2", "Step 3"],
                "notes": [],
                "priority": "medium",
                "tags": [],
                "progress": 0
            }
        },
        {
            "name": "Plan with numbered list",
            "input": "Task With Numbered Plan\nplan: 1. First step 2. Second step 3. Third step",
            "expected": {
                "title": "Task With Numbered Plan",
                "status": "todo",
                "plan": ["First step", "Second step", "Third step"],
                "notes": [],
                "priority": "medium",
                "tags": [],
                "progress": 0
            }
        },
        {
            "name": "Plan with newlines",
            "input": "Task With Newline Plan\nplan:\nStep A\nStep B\nStep C",
            "expected": {
                "title": "Task With Newline Plan", 
                "status": "todo",
                "plan": ["Step A", "Step B", "Step C"],
                "notes": [],
                "priority": "medium",
                "tags": [],
                "progress": 0
            }
        },
        
        # Status variations
        {
            "name": "Status with whitespace",
            "input": "Task With Spaced Status\nstatus : In Progress",
            "expected": {
                "title": "Task With Spaced Status",
                "status": "in_progress",
                "plan": [],
                "notes": [],
                "priority": "medium",
                "tags": [],
                "progress": 0
            }
        },
        {
            "name": "Status case-insensitivity",
            "input": "Task With Uppercase Status\nSTATUS: in_progress",
            "expected": {
                "title": "Task With Uppercase Status",
                "status": "in_progress",
                "plan": [],
                "notes": [],
                "priority": "medium",
                "tags": [],
                "progress": 0
            }
        },
        {
            "name": "Status with synonyms",
            "input": "Task With Status Synonyms\nstatus: wip",
            "expected": {
                "title": "Task With Status Synonyms",
                "status": "in_progress",
                "plan": [],
                "notes": [],
                "priority": "medium",
                "tags": [],
                "progress": 0
            }
        },
        {
            "name": "Status with 'done' synonyms",
            "input": "Task With Status Synonyms\nstatus: completed",
            "expected": {
                "title": "Task With Status Synonyms",
                "status": "done",
                "plan": [],
                "notes": [],
                "priority": "medium",
                "tags": [],
                "progress": 0
            }
        },
        
        # Priority variations
        {
            "name": "Priority abbreviations - high",
            "input": "Task With Priority Abbreviation\npriority: h",
            "expected": {
                "title": "Task With Priority Abbreviation",
                "status": "todo",
                "plan": [],
                "notes": [],
                "priority": "high",
                "tags": [],
                "progress": 0
            }
        },
        {
            "name": "Priority abbreviations - medium",
            "input": "Task With Priority Abbreviation\npriority: m",
            "expected": {
                "title": "Task With Priority Abbreviation",
                "status": "todo",
                "plan": [],
                "notes": [],
                "priority": "medium",
                "tags": [],
                "progress": 0
            }
        },
        {
            "name": "Priority abbreviations - low",
            "input": "Task With Priority Abbreviation\npriority: l",
            "expected": {
                "title": "Task With Priority Abbreviation",
                "status": "todo",
                "plan": [],
                "notes": [],
                "priority": "low",
                "tags": [],
                "progress": 0
            }
        },
        {
            "name": "Priority with synonyms",
            "input": "Task With Priority Synonyms\npriority: critical",
            "expected": {
                "title": "Task With Priority Synonyms",
                "status": "todo",
                "plan": [],
                "notes": [],
                "priority": "high",
                "tags": [],
                "progress": 0
            }
        },
        
        # Progress variations
        {
            "name": "Progress with percent sign",
            "input": "Task With Progress\nprogress: 75%",
            "expected": {
                "title": "Task With Progress",
                "status": "todo",
                "plan": [],
                "notes": [],
                "priority": "medium",
                "tags": [],
                "progress": 75
            }
        },
        {
            "name": "Progress with decimal",
            "input": "Task With Decimal Progress\nprogress: 33.3",
            "expected": {
                "title": "Task With Decimal Progress",
                "status": "todo",
                "plan": [],
                "notes": [],
                "priority": "medium",
                "tags": [],
                "progress": 33
            }
        },
        {
            "name": "Progress with whitespace",
            "input": "Task With Progress Whitespace\nprogress : 50",
            "expected": {
                "title": "Task With Progress Whitespace",
                "status": "todo",
                "plan": [],
                "notes": [],
                "priority": "medium",
                "tags": [],
                "progress": 50
            }
        },
        
        # Tag variations
        {
            "name": "Tags with hashtags",
            "input": "Task With Hashtags\ntags: #frontend #api #testing",
            "expected": {
                "title": "Task With Hashtags",
                "status": "todo",
                "plan": [],
                "notes": [],
                "priority": "medium",
                "tags": ["frontend", "api", "testing"],
                "progress": 0
            }
        },
        {
            "name": "Tags with commas",
            "input": "Task With Comma Tags\ntags: frontend, api, testing",
            "expected": {
                "title": "Task With Comma Tags",
                "status": "todo",
                "plan": [],
                "notes": [],
                "priority": "medium",
                "tags": ["frontend", "api", "testing"],
                "progress": 0
            }
        },
        {
            "name": "Tags with quotes for multi-word tags",
            "input": 'Task With Quoted Tags\ntags: "user auth" api "error handling"',
            "expected": {
                "title": "Task With Quoted Tags",
                "status": "todo",
                "plan": [],
                "notes": [],
                "priority": "medium",
                "tags": ["user auth", "api", "error handling"],
                "progress": 0
            }
        },
        {
            "name": "Mixed tag formats",
            "input": 'Task With Mixed Tag Formats\ntags: #frontend, "api gateway", database',
            "expected": {
                "title": "Task With Mixed Tag Formats",
                "status": "todo",
                "plan": [],
                "notes": [],
                "priority": "medium",
                "tags": ["frontend", "api gateway", "database"],
                "progress": 0
            }
        },
        
        # Notes variations
        {
            "name": "Notes with keyword",
            "input": "Task With Notes\nnotes: This is a note\nWith multiple lines",
            "expected": {
                "title": "Task With Notes",
                "status": "todo",
                "plan": [],
                "notes": ["This is a note", "With multiple lines"],
                "priority": "medium",
                "tags": [],
                "progress": 0
            }
        },
        {
            "name": "Notes without keyword (implicit notes)",
            "input": "Task With Implicit Notes\nThis text should be treated as notes\nSpanning multiple lines",
            "expected": {
                "title": "Task With Implicit Notes",
                "status": "todo",
                "plan": [],
                "notes": ["This text should be treated as notes", "Spanning multiple lines"],
                "priority": "medium",
                "tags": [],
                "progress": 0
            }
        },
        
        # Combined complex examples
        {
            "name": "Complex task with multiple fields",
            "input": """Implement User Authentication
status: in_progress
priority: high
progress: 35%
plan:
1. Design API endpoints
2. Implement JWT tokens
3. Add password hashing
tags: #backend, security, "user management"
notes: Need to follow OWASP guidelines
Also need to check for rate limiting requirements""",
            "expected": {
                "title": "Implement User Authentication",
                "status": "in_progress",
                "plan": ["Design API endpoints", "Implement JWT tokens", "Add password hashing"],
                "notes": ["Need to follow OWASP guidelines", "Also need to check for rate limiting requirements"],
                "priority": "high",
                "tags": ["backend", "security", "user management"],
                "progress": 35
            }
        },
        {
            "name": "Task with flexible whitespace in keywords",
            "input": """Code Review UI Updates
status : in_progress
priority : h
progress : 25%""",
            "expected": {
                "title": "Code Review UI Updates",
                "status": "in_progress",
                "plan": [],
                "notes": [],
                "priority": "high",
                "tags": [],
                "progress": 25
            }
        }
    ]
    
    # Run the tests
    passed = 0
    failed = 0
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\nTest Case {i}: {test_case['name']}")
        print(f"Input:\n{test_case['input']}")
        
        # Parse the input
        result = parse_free_text_task(test_case['input'])
        
        # Check the result against expected values
        test_passed = True
        for key, expected_value in test_case['expected'].items():
            if key not in result:
                print(f"❌ Missing key: {key}")
                test_passed = False
                continue
                
            actual_value = result[key]
            if actual_value != expected_value:
                print(f"❌ Mismatch for '{key}':")
                print(f"  Expected: {expected_value}")
                print(f"  Got: {actual_value}")
                test_passed = False
        
        if test_passed:
            print("✅ PASSED")
            passed += 1
        else:
            print("❌ FAILED")
            failed += 1
            print("Actual result:")
            print(result)
    
    # Print summary
    print(f"\n=== Test Summary ===")
    print(f"Total tests: {len(test_cases)}")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    
    return passed, failed