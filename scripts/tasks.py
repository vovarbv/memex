#!/usr/bin/env python
"""
CLI-менеджер задач: add / start / bump / done / delete / list / note.
Задачи хранятся в YAML и синхронизируются с векторной базой FAISS.
"""
import argparse
import datetime as dt
import logging
import sys
import textwrap

from memory_utils import add_or_replace, delete_vector, load_cfg, ROOT
# task_store functions will be used directly
import task_store


# ───────────────────────────────────────── Logging Setup ────
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


# ───────────────────────────────────────── Helper Functions ────
def find_task(tasks: list[dict], task_id: int) -> dict | None:
    """Finds a task by its ID."""
    for task in tasks:
        if task.get("id") == task_id:
            return task
    return None

def sync_task_vector(task: dict):
    """Synchronizes a single task with the FAISS vector store."""
    try:
        # Create a more structured text for better embedding
        title_part = f"TASK {task.get('id', 'N/A')} | {task.get('title', 'No Title')}"
        status_part = f"status {task.get('status', 'unknown')} | progress {task.get('progress', 0)}%"
        
        # Format plan steps more clearly as pending and done
        plan = task.get("plan", [])
        done_steps = task.get("done_steps", [])
        pending_steps = [s for s in plan if s not in done_steps]
        
        pending_steps_str = '; '.join(pending_steps) if pending_steps else "None"
        done_steps_str = '; '.join(done_steps) if done_steps else "None"
        plan_part = f"Pending steps: {pending_steps_str} | Completed steps: {done_steps_str}"
        
        # Build the full text
        text = f"{title_part} | {status_part} | {plan_part}"
        
        # Include the last note if available
        if task.get("notes"):
            # Include only the last note for brevity in vector, or summarize
            last_note = task["notes"].strip().splitlines()[-1] if task["notes"].strip() else ""
            text += f" | last_note: {last_note[:100]}" # Truncate last note
        
        # Add origin if available
        if task.get("origin"):
            text += f" | source: {task.get('origin')}"

        add_or_replace(task["id"], text, {**task, "type": "task"})
        logging.info(f"Task #{task['id']} synced with vector store.")
    except Exception as e:
        logging.error(f"Failed to sync task #{task.get('id')} with vector store: {e}")

def delete_task_vector(task_id: int):
    """Deletes a task's vector from FAISS."""
    try:
        if delete_vector(task_id):
            logging.info(f"Vector for task #{task_id} deleted from vector store.")
        else:
            logging.warning(f"Vector for task #{task_id} might not have been deleted or was not found.")
    except Exception as e:
        logging.error(f"Failed to delete vector for task #{task_id}: {e}")

# ───────────────────────────────────────── CLI Commands ────
def cmd_add(args):
    tasks = task_store.load_tasks()
    new_id = task_store.next_id(tasks)

    plan_steps = []
    if args.plan:
        plan_steps = [p.strip() for p in args.plan.split(";") if p.strip()]

    task = {
        "id": new_id,
        "title": args.title,
        "status": "todo",  # or args.status if you add that
        "progress": 0,
        "plan": plan_steps,
        "done_steps": [],
        "notes": "", # Initialize notes
        "created_at": dt.datetime.now().isoformat(),
        "updated_at": dt.datetime.now().isoformat(),
        "origin": "CLI:add",  # Track where the task was created
    }
    tasks.append(task)
    task_store.save_tasks(tasks)
    sync_task_vector(task)
    print(f"✅ Added task #{new_id}: \"{args.title}\"")

def cmd_start(args):
    tasks = task_store.load_tasks()
    task_id = int(args.id)
    task = find_task(tasks, task_id)
    if task:
        if task["status"] == "in_progress":
            print(f"ℹ️ Task #{task_id} is already in progress.")
            return
        if task["status"] == "done":
            print(f"ℹ️ Task #{task_id} is already done. Re-opening.") # Or prevent
        task["status"] = "in_progress"
        task["updated_at"] = dt.datetime.now().isoformat()
        task["origin"] = "CLI:start"  # Track the origin
        task_store.save_tasks(tasks)
        sync_task_vector(task)
        print(f"🚀 Task #{task_id} started: \"{task['title']}\"")
    else:
        print(f"❌ Error: Task with ID {task_id} not found.")
        sys.exit(1)

def cmd_bump(args):
    tasks = task_store.load_tasks()
    task_id = int(args.id)
    delta = int(args.delta)
    task = find_task(tasks, task_id)
    if task:
        new_progress = min(100, max(0, task.get("progress", 0) + delta))
        task["progress"] = new_progress
        if new_progress == 100 and task["status"] != "done":
            task["status"] = "done"
            print(f"🎉 Task #{task_id} marked as done (progress reached 100%).")
        elif new_progress < 100 and task["status"] == "done":
            task["status"] = "in_progress" # Re-opened if progress reduced from 100
        elif task["status"] == "todo" and new_progress > 0:
             task["status"] = "in_progress"

        task["updated_at"] = dt.datetime.now().isoformat()
        task["origin"] = f"CLI:bump_{delta}"  # Track the origin with the delta value
        task_store.save_tasks(tasks)
        sync_task_vector(task)
        print(f"📊 Task #{task_id} progress bumped by {delta}% to {new_progress}%. Status: {task['status']}.")
    else:
        print(f"❌ Error: Task with ID {task_id} not found.")
        sys.exit(1)

def cmd_done(args):
    tasks = task_store.load_tasks()
    task_id = int(args.id)
    task = find_task(tasks, task_id)
    if task:
        if task["status"] == "done":
            print(f"ℹ️ Task #{task_id} is already marked as done.")
            return
        task["status"] = "done"
        task["progress"] = 100
        # Mark all plan steps as done
        task["done_steps"] = list(task.get("plan", []))
        task["updated_at"] = dt.datetime.now().isoformat()
        task["origin"] = "CLI:done"  # Track the command that marked it done
        task_store.save_tasks(tasks)
        sync_task_vector(task)
        print(f"✅ Task #{task_id} marked as done: \"{task['title']}\"")
    else:
        print(f"❌ Error: Task with ID {task_id} not found.")
        sys.exit(1)

def cmd_delete(args):
    tasks = task_store.load_tasks()
    task_id = int(args.id)
    task_to_delete = find_task(tasks, task_id)

    if task_to_delete:
        # Before deleting, update the task with origin for tracking in logs
        task_to_delete["origin"] = "CLI:delete"
        task_to_delete["updated_at"] = dt.datetime.now().isoformat()
        
        # Log the deletion action - could be useful for audit or undo functionality
        logging.info(f"Deleting task #{task_id} '{task_to_delete['title']}'. Last origin: {task_to_delete.get('origin')}")
        
        # Perform the deletion
        tasks = [t for t in tasks if t.get("id") != task_id]
        task_store.save_tasks(tasks)
        delete_task_vector(task_id) # Delete from FAISS
        print(f"🗑️ Task #{task_id} \"{task_to_delete['title']}\" deleted.")
    else:
        print(f"❌ Error: Task with ID {task_id} not found for deletion.")
        sys.exit(1)

def cmd_note(args):
    tasks = task_store.load_tasks()
    task_id = int(args.id)
    task = find_task(tasks, task_id)
    if task:
        current_notes = task.get("notes", "")
        timestamp = dt.datetime.now().strftime('%Y-%m-%d %H:%M')
        new_note_line = f"{timestamp}: {args.note_text}"
        task["notes"] = f"{current_notes}\n{new_note_line}".strip()
        task["updated_at"] = dt.datetime.now().isoformat()
        task["origin"] = "CLI:note"  # Track the origin of the note
        task_store.save_tasks(tasks)
        sync_task_vector(task) # Notes content changed, so sync
        print(f"📝 Note added to task #{task_id}.")
    else:
        print(f"❌ Error: Task with ID {task_id} not found.")
        sys.exit(1)

def cmd_list(args):
    tasks = task_store.load_tasks()

    if not tasks:
        print("No tasks found.")
        return

    filtered_tasks = tasks
    if args.status:
        statuses = [s.strip().lower() for s in args.status.split(',')]
        filtered_tasks = [t for t in filtered_tasks if t.get("status", "").lower() in statuses]

    if not filtered_tasks and args.status:
        print(f"No tasks found with status(es): {args.status}")
        return
    elif not filtered_tasks:
        print("No tasks match the criteria.") # Should be caught by the first 'if not tasks'
        return


    print(f"{'ID':<4} | {'Title':<40} | {'Status':<12} | {'Progress':>8} | {'Plan Steps':<15} | Last Update")
    print("-" * 100)
    for task in sorted(filtered_tasks, key=lambda t: t.get("id", 0)):
        title = task.get('title', 'N/A')
        title_short = textwrap.shorten(title, width=38, placeholder="...")
        status = task.get('status', 'N/A')
        progress = f"{task.get('progress', 0)}%"

        plan = task.get('plan', [])
        done_steps = task.get('done_steps', [])
        plan_summary = f"{len(done_steps)}/{len(plan)}" if plan else "0/0"

        updated_at_iso = task.get("updated_at", task.get("created_at", ""))
        updated_at_str = ""
        if updated_at_iso:
            try:
                updated_at_dt = dt.datetime.fromisoformat(updated_at_iso)
                updated_at_str = updated_at_dt.strftime('%Y-%m-%d %H:%M')
            except ValueError:
                updated_at_str = updated_at_iso # Show raw if not parsable

        print(f"{task.get('id', ''):<4} | {title_short:<40} | {status:<12} | {progress:>8} | {plan_summary:<15} | {updated_at_str}")

        if args.details: # Show more details if requested
            if plan:
                print("    Plan:")
                for i, step in enumerate(plan):
                    # Improved status indicator with index numbers for easier reference
                    mark = "✅" if step in done_steps else ("🔄" if status == "in_progress" else "⏳")
                    print(f"      {i+1}. [{mark}] {step}")
                
                # Add a summary of completion percentage
                if done_steps:
                    completion_percent = (len(done_steps) / len(plan)) * 100
                    print(f"    Plan completion: {completion_percent:.1f}%")
            
            if task.get("notes"):
                print("    Recent Notes:")
                for note_line in task["notes"].strip().splitlines()[-3:]: # Show last 3 notes
                    print(f"      - {textwrap.shorten(note_line, width=80, placeholder='...')}")
            
            # Show task origin if available
            if task.get("origin"):
                print(f"    Origin: {task['origin']}")
                
            print("-" * 100)

def cmd_complete_step(args):
    """Mark or unmark a specific plan step as completed."""
    tasks = task_store.load_tasks()
    task_id = int(args.id)
    task = find_task(tasks, task_id)
    
    if not task:
        print(f"❌ Error: Task with ID {task_id} not found.")
        sys.exit(1)
    
    # Ensure the plan exists
    plan = task.get("plan", [])
    if not plan:
        print(f"❌ Error: Task #{task_id} has no plan steps to mark as complete.")
        sys.exit(1)
    
    # Validate step_index is within range
    try:
        step_index = int(args.step_index)
        if step_index < 1 or step_index > len(plan):
            print(f"❌ Error: Step index {step_index} is out of range. Task has {len(plan)} steps.")
            sys.exit(1)
    except ValueError:
        print(f"❌ Error: Step index must be a number.")
        sys.exit(1)
    
    # Get the step text at the specified index (0-based for arrays, but 1-based for user)
    step_text = plan[step_index - 1]
    
    # Initialize done_steps if it doesn't exist
    if "done_steps" not in task:
        task["done_steps"] = []
    
    # Mark or unmark the step
    if args.unmark:
        if step_text in task["done_steps"]:
            task["done_steps"].remove(step_text)
            print(f"↩️ Unmarked step #{step_index} as incomplete: \"{step_text}\"")
        else:
            print(f"ℹ️ Step #{step_index} is already marked as incomplete.")
            return
    else:
        if step_text not in task["done_steps"]:
            task["done_steps"].append(step_text)
            print(f"✓ Marked step #{step_index} as complete: \"{step_text}\"")
        else:
            print(f"ℹ️ Step #{step_index} is already marked as complete.")
            return
    
    # Recalculate progress based on completed steps
    if plan:
        task["progress"] = int((len(task["done_steps"]) / len(plan)) * 100)
    else:
        task["progress"] = 0
    
    # Update status based on progress
    if task["progress"] >= 100:
        task["status"] = "done"
    elif task["progress"] > 0:
        if task["status"] == "todo":
            task["status"] = "in_progress"
        # If status was already "done" but progress < 100 after unmarking a step:
        elif task["status"] == "done":
            task["status"] = "in_progress"
    
    # Update timestamp and origin
    task["updated_at"] = dt.datetime.now().isoformat()
    task["origin"] = f"CLI:{'unmark_step' if args.unmark else 'complete_step'}"
    
    # Save changes and sync to vector store
    task_store.save_tasks(tasks)
    sync_task_vector(task)
    
    print(f"📊 Task #{task_id} progress updated to {task['progress']}%. Status: {task['status']}.")

# ───────────────────────────────────────── Argument Parser ────
def build_parser():
    parser = argparse.ArgumentParser(description="CLI Task Manager for Project Memory.")
    subparsers = parser.add_subparsers(dest="command", title="Commands", required=True)

    # Add command
    p_add = subparsers.add_parser("add", help="Add a new task.")
    p_add.add_argument("title", help="Title of the task.")
    p_add.add_argument("--plan", help="Semicolon-separated list of plan steps (e.g., \"Step1;Step2\").", default="")
    p_add.set_defaults(func=cmd_add)

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

# ───────────────────────────────────────── Main Execution ────
if __name__ == "__main__":
    parser = build_parser()
    args = parser.parse_args()

    # Basic check for config and store initialization
    try:
        cfg_test = load_cfg()
        # You might want to call _ensure_store() from memory_utils here if commands
        # don't always trigger it via load_index indirectly.
        # However, most task operations will call sync_task_vector -> add_or_replace -> load_index -> _ensure_store.
    except Exception as e:
        logging.critical(f"Failed to initialize basic configuration or vector store. Aborting. Error: {e}")
        sys.exit(1)

    if hasattr(args, 'func'):
        try:
            args.func(args)
        except Exception as e:
            logging.error(f"An error occurred while executing command '{args.command}': {e}", exc_info=True)
            print(f"❌ An unexpected error occurred. Check logs for details.")
            sys.exit(1)
    else:
        parser.print_help() # Should not happen if subparsers are required