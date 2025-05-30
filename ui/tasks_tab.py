"""
Enhanced Tasks Tab - Zero-friction task management with quick-switcher and improved UX.
This tab provides streamlined task management with keyboard shortcuts and one-click actions.
"""

import gradio as gr
import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import json

# Import shared utilities and required functions
from .shared_utils import (
    try_import_with_prefix, 
    import_memory_utils,
    import_task_store_module,
    format_error_message,
    format_success_message,
    format_warning_message
)

def create_tasks_tab(ts, cfg, data_integrity_error=None):
    """
    Creates the enhanced Tasks tab UI with quick-switcher and improved functionality.
    
    Args:
        ts: TaskStore instance
        cfg: Configuration dictionary
        data_integrity_error: Data integrity error message, if any
        
    Returns:
        dict: References to components and refresh function
    """
    
    # Import required functions
    try:
        # Task management functions
        task_store_module = import_task_store_module()
        
        # Import task CLI functions for backend logic
        tasks_module = try_import_with_prefix("tasks", ["scripts.", ".scripts.", "memex.scripts."])
        if tasks_module:
            create_task_logic = getattr(tasks_module, 'create_task_logic', None)
            start_task_logic = getattr(tasks_module, 'start_task_logic', None)
            done_task_logic = getattr(tasks_module, 'done_task_logic', None)
            edit_task_logic = getattr(tasks_module, 'edit_task_logic', None)
        else:
            create_task_logic = None
            start_task_logic = None
            done_task_logic = None
            edit_task_logic = None
            
    except Exception as e:
        logging.error(f"Error importing tasks tab dependencies: {e}")
        create_task_logic = None
        start_task_logic = None
        done_task_logic = None
        edit_task_logic = None
    
    # Handle data integrity error
    if data_integrity_error:
        gr.Markdown(f"⚠️ **Error loading tasks**: {data_integrity_error}")
        tasks_display = gr.Markdown("Cannot load tasks due to data integrity error.")
        
        return {
            "refresh": lambda: None,
            "components": {
                "display": tasks_display
            }
        }
    
    # Header with quick actions
    with gr.Row():
        with gr.Column(scale=3):
            gr.Markdown("## 📋 Task Management")
        with gr.Column(scale=1):
            quick_stats = gr.Markdown("Loading stats...")
    
    # Task Quick-Switcher (Ctrl+K style)
    with gr.Group():
        gr.Markdown("### ⚡ Quick Task Switcher")
        with gr.Row():
            task_switcher = gr.Dropdown(
                label="",
                choices=[],
                value=None,
                interactive=True,
                scale=3,
                info="Quick switch between tasks (Ctrl+K to focus)"
            )
            switch_button = gr.Button("▶️ Switch", variant="primary", scale=1)
            new_task_button = gr.Button("➕ New", variant="secondary", scale=1)
    
    # Main content area with two columns
    with gr.Row():
        # Left column - Task list and filters
        with gr.Column(scale=1):
            gr.Markdown("### 📊 Task Overview")
            
            # Smart filters
            with gr.Group():
                with gr.Row():
                    status_filter = gr.Radio(
                        choices=["active", "all", "todo", "in_progress", "done", "blocked"],
                        value="active",
                        label="Status Filter",
                        elem_id="status-filter"
                    )
                
                with gr.Row():
                    priority_filter = gr.Dropdown(
                        choices=["all", "high", "medium", "low"],
                        value="all",
                        label="Priority"
                    )
                    
                    sort_by = gr.Dropdown(
                        choices=["smart", "priority", "progress", "recent", "alpha"],
                        value="smart",
                        label="Sort By"
                    )
            
            # Task list with rich display
            task_list_display = gr.HTML(value="<p>Loading tasks...</p>")
            
            # Info about task management
            with gr.Row():
                gr.Markdown("💡 Use the task details section to manage individual tasks")
        
        # Right column - Task details and actions
        with gr.Column(scale=2):
            # Current task details
            with gr.Group():
                gr.Markdown("### 🎯 Task Details")
                current_task_id = gr.State(value=None)
                task_details_display = gr.Markdown("Select a task to view details...")
                
                # Quick actions for selected task
                with gr.Row():
                    start_task_btn = gr.Button("▶️ Start", variant="primary")
                    done_task_btn = gr.Button("✅ Done", variant="secondary")
                    edit_task_btn = gr.Button("✏️ Edit")
                    delete_task_btn = gr.Button("🗑️ Delete", variant="stop")
            
            # Task creation/editing form
            with gr.Group():
                gr.Markdown("### ✏️ Create/Edit Task")
                
                # Smart task input
                with gr.Tab("Quick Create"):
                    quick_task_input = gr.Textbox(
                        label="Quick Task",
                        placeholder="e.g., 'Fix login bug @high #backend due:tomorrow'",
                        lines=2,
                        info="Use natural language with @priority, #tags, due:date"
                    )
                    quick_create_btn = gr.Button("Create Task", variant="primary")
                
                with gr.Tab("Detailed Form"):
                    task_id_edit = gr.State(value=None)
                    
                    task_title = gr.Textbox(
                        label="Title",
                        placeholder="Clear, actionable task title"
                    )
                    
                    task_description = gr.Textbox(
                        label="Description",
                        placeholder="Detailed description and context",
                        lines=3
                    )
                    
                    with gr.Row():
                        task_status = gr.Dropdown(
                            choices=["todo", "in_progress", "done", "blocked"],
                            label="Status",
                            value="todo"
                        )
                        
                        task_priority = gr.Dropdown(
                            choices=["high", "medium", "low"],
                            label="Priority",
                            value="medium"
                        )
                        
                        task_progress = gr.Slider(
                            minimum=0,
                            maximum=100,
                            value=0,
                            step=5,
                            label="Progress %"
                        )
                    
                    task_plan = gr.Textbox(
                        label="Action Plan",
                        placeholder="1. First step\n2. Second step\n3. Third step",
                        lines=4
                    )
                    
                    task_notes = gr.Textbox(
                        label="Notes",
                        placeholder="Additional notes, blockers, or context",
                        lines=3
                    )
                    
                    with gr.Row():
                        save_task_btn = gr.Button("💾 Save Task", variant="primary")
                        cancel_edit_btn = gr.Button("Cancel")
                        form_status = gr.Markdown("")
    
    # Task templates section
    with gr.Accordion("📑 Task Templates", open=False):
        gr.Markdown("### Quick Templates")
        template_buttons = []
        templates = [
            ("🐛 Bug Fix", "bug", {"priority": "high", "prefix": "Fix: "}),
            ("✨ Feature", "feature", {"priority": "medium", "prefix": "Implement: "}),
            ("📝 Documentation", "docs", {"priority": "low", "prefix": "Document: "}),
            ("🧪 Testing", "test", {"priority": "medium", "prefix": "Test: "}),
            ("♻️ Refactor", "refactor", {"priority": "low", "prefix": "Refactor: "})
        ]
        
        with gr.Row():
            for label, template_type, template_data in templates:
                btn = gr.Button(label, scale=1)
                template_buttons.append((btn, template_type, template_data))
    
    # Hidden state for selected tasks
    selected_task_ids = gr.State(value=[])
    
    # Helper functions
    def get_task_stats(tasks):
        """Calculate quick statistics for tasks."""
        if not tasks:
            return "No tasks"
        
        stats = {
            'total': len(tasks),
            'in_progress': sum(1 for t in tasks if hasattr(t, 'status') and t.status == 'in_progress'),
            'todo': sum(1 for t in tasks if hasattr(t, 'status') and t.status == 'todo'),
            'done': sum(1 for t in tasks if hasattr(t, 'status') and t.status == 'done'),
            'high': sum(1 for t in tasks if hasattr(t, 'priority') and t.priority == 'high')
        }
        
        return f"**Total**: {stats['total']} | **Active**: {stats['in_progress']} | **High Priority**: {stats['high']}"
    
    def get_task_choices(tasks):
        """Generate task choices for quick switcher."""
        choices = []
        for task in tasks:
            if hasattr(task, 'id') and hasattr(task, 'title'):
                status = getattr(task, 'status', 'unknown')
                priority = getattr(task, 'priority', 'medium')
                emoji = {
                    'in_progress': '🔄',
                    'todo': '📝',
                    'done': '✅',
                    'blocked': '🚫'
                }.get(status, '❓')
                
                priority_emoji = {'high': '🔴', 'medium': '🟡', 'low': '🟢'}.get(priority, '')
                
                label = f"{emoji} {priority_emoji} {task.title} (#{task.id})"
                choices.append((label, str(task.id)))
        
        return choices
    
    def format_task_list(tasks, status_filter="active", priority_filter="all", sort_by="smart"):
        """Format tasks as rich HTML display."""
        if not tasks:
            return "<p>No tasks found. Create your first task!</p>"
        
        # Filter tasks
        filtered_tasks = []
        for task in tasks:
            # Status filter
            if status_filter == "active":
                if not hasattr(task, 'status') or task.status not in ['todo', 'in_progress']:
                    continue
            elif status_filter != "all":
                if not hasattr(task, 'status') or task.status != status_filter:
                    continue
            
            # Priority filter
            if priority_filter != "all":
                if not hasattr(task, 'priority') or task.priority != priority_filter:
                    continue
            
            filtered_tasks.append(task)
        
        # Sort tasks
        if sort_by == "smart":
            # Smart sort: in_progress first, then by priority, then by progress
            def smart_key(task):
                status_order = {'in_progress': 0, 'todo': 1, 'blocked': 2, 'done': 3}
                priority_order = {'high': 0, 'medium': 1, 'low': 2}
                status = getattr(task, 'status', 'todo')
                priority = getattr(task, 'priority', 'medium')
                progress = getattr(task, 'progress', 0)
                
                return (
                    status_order.get(status, 4),
                    priority_order.get(priority, 3),
                    -progress  # Higher progress first
                )
            filtered_tasks.sort(key=smart_key)
        elif sort_by == "priority":
            priority_order = {'high': 0, 'medium': 1, 'low': 2}
            filtered_tasks.sort(key=lambda t: priority_order.get(getattr(t, 'priority', 'medium'), 3))
        elif sort_by == "progress":
            filtered_tasks.sort(key=lambda t: -getattr(t, 'progress', 0))
        elif sort_by == "recent":
            filtered_tasks.sort(key=lambda t: getattr(t, 'id', 0), reverse=True)
        elif sort_by == "alpha":
            filtered_tasks.sort(key=lambda t: getattr(t, 'title', '').lower())
        
        # Format as HTML
        html_parts = []
        for task in filtered_tasks:
            task_id = getattr(task, 'id', 'unknown')
            title = getattr(task, 'title', 'Untitled')
            status = getattr(task, 'status', 'unknown')
            priority = getattr(task, 'priority', 'medium')
            progress = getattr(task, 'progress', 0)
            description = getattr(task, 'description', '')
            
            # Status styling
            status_styles = {
                'in_progress': ('🔄', '#2196f3'),
                'todo': ('📝', '#ff9800'),
                'done': ('✅', '#4caf50'),
                'blocked': ('🚫', '#f44336')
            }
            status_emoji, status_color = status_styles.get(status, ('❓', '#9e9e9e'))
            
            # Priority styling
            priority_styles = {
                'high': ('🔴', '#ff5252'),
                'medium': ('🟡', '#ffc107'),
                'low': ('🟢', '#4caf50')
            }
            priority_emoji, priority_color = priority_styles.get(priority, ('⚪', '#9e9e9e'))
            
            # Progress bar
            progress_bar = f"""
            <div style="background: #e0e0e0; border-radius: 4px; height: 8px; margin: 5px 0;">
                <div style="background: {status_color}; width: {progress}%; height: 100%; border-radius: 4px;"></div>
            </div>
            """
            
            html_parts.append(f"""
            <div style="border: 1px solid #ddd; border-radius: 8px; padding: 15px; margin: 10px 0; background: #f9f9f9; cursor: pointer;" 
                 onclick="selectTask('{task_id}')">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <h4 style="margin: 0; color: #333;">
                        {status_emoji} #{task_id}: {title}
                    </h4>
                    <div style="display: flex; gap: 10px; align-items: center;">
                        <span style="font-size: 20px;">{priority_emoji}</span>
                        <span style="background: {status_color}; color: white; padding: 2px 8px; border-radius: 12px; font-size: 12px;">
                            {status}
                        </span>
                    </div>
                </div>
                {f'<p style="color: #666; margin: 5px 0; font-size: 14px;">{description[:100]}...</p>' if description else ''}
                {progress_bar}
                <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 5px;">
                    <span style="font-size: 12px; color: #666;">Progress: {progress}%</span>
                    <input type="checkbox" style="transform: scale(1.2);" onclick="toggleTaskSelection(event, '{task_id}')">
                </div>
            </div>
            """)
        
        if not html_parts:
            return "<p>No tasks match the current filters.</p>"
        
        # Add JavaScript for interaction
        js_script = """
        <script>
        function selectTask(taskId) {
            // This will be handled by Gradio event
            console.log('Selected task:', taskId);
        }
        
        function toggleTaskSelection(event, taskId) {
            event.stopPropagation();
            // This will be handled by Gradio event
            console.log('Toggle selection:', taskId);
        }
        </script>
        """
        
        return js_script + "\n".join(html_parts)
    
    def format_task_details(task_id):
        """Format detailed view of a single task."""
        if not ts or not task_id:
            return "No task selected"
        
        task = None
        for t in ts.tasks:
            if hasattr(t, 'id') and str(t.id) == str(task_id):
                task = t
                break
        
        if not task:
            return f"Task #{task_id} not found"
        
        # Format task details with rich markdown
        details = f"# Task #{task.id}: {getattr(task, 'title', 'Untitled')}\n\n"
        
        # Status and priority badges
        status = getattr(task, 'status', 'unknown')
        priority = getattr(task, 'priority', 'medium')
        progress = getattr(task, 'progress', 0)
        
        status_emoji = {
            'in_progress': '🔄',
            'todo': '📝',
            'done': '✅',
            'blocked': '🚫'
        }.get(status, '❓')
        
        priority_emoji = {
            'high': '🔴',
            'medium': '🟡',
            'low': '🟢'
        }.get(priority, '⚪')
        
        details += f"**Status**: {status_emoji} {status} | **Priority**: {priority_emoji} {priority} | **Progress**: {progress}%\n\n"
        
        # Description
        if hasattr(task, 'description') and task.description:
            details += f"## Description\n{task.description}\n\n"
        
        # Action plan
        if hasattr(task, 'plan') and task.plan:
            details += "## Action Plan\n"
            for i, step in enumerate(task.plan, 1):
                # Check if step is completed (simple heuristic)
                if progress > (i / len(task.plan) * 100):
                    details += f"- [x] {step}\n"
                else:
                    details += f"- [ ] {step}\n"
            details += "\n"
        
        # Notes
        if hasattr(task, 'notes') and task.notes:
            details += "## Notes\n"
            if isinstance(task.notes, list):
                for note in task.notes:
                    details += f"- {note}\n"
            else:
                details += f"{task.notes}\n"
            details += "\n"
        
        # Metadata
        details += "## Metadata\n"
        details += f"- **Created**: {getattr(task, 'created_at', 'Unknown')}\n"
        details += f"- **Updated**: {getattr(task, 'updated_at', 'Unknown')}\n"
        if hasattr(task, 'tags') and task.tags:
            details += f"- **Tags**: {', '.join(task.tags)}\n"
        
        return details
    
    def parse_quick_task(input_text):
        """Parse natural language task input."""
        import re
        
        # Extract components
        priority_match = re.search(r'@(high|medium|low)', input_text, re.IGNORECASE)
        priority = priority_match.group(1).lower() if priority_match else 'medium'
        
        tags_matches = re.findall(r'#(\w+)', input_text)
        tags = tags_matches if tags_matches else []
        
        due_match = re.search(r'due:(\S+)', input_text)
        due_date = due_match.group(1) if due_match else None
        
        # Clean title
        title = input_text
        title = re.sub(r'@(high|medium|low)', '', title, flags=re.IGNORECASE)
        title = re.sub(r'#\w+', '', title)
        title = re.sub(r'due:\S+', '', title)
        title = ' '.join(title.split())  # Clean up whitespace
        
        return {
            'title': title,
            'priority': priority,
            'tags': tags,
            'due_date': due_date
        }
    
    # Event handlers
    def on_quick_create(input_text):
        """Handle quick task creation."""
        if not input_text.strip():
            return format_warning_message("Please enter a task description")
        
        if not create_task_logic:
            return format_error_message("Task creation not available")
        
        try:
            # Parse the input
            parsed = parse_quick_task(input_text)
            
            # Create the task
            success, message = create_task_logic(
                title=parsed['title'],
                priority=parsed['priority'],
                status='todo'
            )
            
            if success:
                # Clear input and refresh
                return format_success_message(message), ""
            else:
                return format_error_message(message), input_text
                
        except Exception as e:
            logging.error(f"Error creating quick task: {e}")
            return format_error_message(f"Failed to create task: {str(e)}"), input_text
    
    def on_task_switch(task_id):
        """Handle task switching."""
        if not task_id or not start_task_logic:
            return format_warning_message("Select a task to switch to"), None
        
        try:
            success, message = start_task_logic(task_id)
            if success:
                return format_success_message(f"Switched to task #{task_id}"), task_id
            else:
                return format_error_message(message), None
        except Exception as e:
            return format_error_message(f"Failed to switch task: {str(e)}"), None
    
    def refresh_all():
        """Refresh all task displays."""
        if not ts:
            return (
                "No tasks available",
                [],
                "<p>No tasks available</p>",
                "No task selected",
                ""
            )
        
        try:
            # Get fresh tasks
            ts.load_tasks()  # Reload from file
            
            # Update all displays
            stats = get_task_stats(ts.tasks)
            choices = get_task_choices(ts.tasks)
            task_list_html = format_task_list(ts.tasks)
            
            return (
                stats,
                choices,
                task_list_html,
                "Select a task to view details...",
                ""
            )
        except Exception as e:
            logging.error(f"Error refreshing tasks: {e}")
            return (
                "Error loading tasks",
                [],
                "<p>Error loading tasks</p>",
                f"Error: {str(e)}",
                ""
            )
    
    def on_filter_change(status_filter, priority_filter, sort_by):
        """Handle filter changes."""
        if not ts:
            return "<p>No tasks available</p>"
        
        return format_task_list(ts.tasks, status_filter, priority_filter, sort_by)
    
    def on_task_select(task_list_html):
        """Extract selected task from HTML interaction."""
        # This is a placeholder - in real implementation, we'd use JavaScript callbacks
        # For now, we'll handle task selection through the quick switcher
        return task_list_html
    
    def load_task_for_edit(task_id):
        """Load task data into edit form."""
        if not ts or not task_id:
            return (
                None, "", "", "todo", "medium", 0, "", ""
            )
        
        task = None
        for t in ts.tasks:
            if hasattr(t, 'id') and str(t.id) == str(task_id):
                task = t
                break
        
        if not task:
            return (
                None, "", "", "todo", "medium", 0, "", ""
            )
        
        return (
            task_id,
            getattr(task, 'title', ''),
            getattr(task, 'description', ''),
            getattr(task, 'status', 'todo'),
            getattr(task, 'priority', 'medium'),
            getattr(task, 'progress', 0),
            '\n'.join(getattr(task, 'plan', [])),
            '\n'.join(getattr(task, 'notes', [])) if isinstance(getattr(task, 'notes', []), list) else getattr(task, 'notes', '')
        )
    
    def on_save_task(task_id, title, description, status, priority, progress, plan, notes):
        """Save task (create or update)."""
        if not title.strip():
            return format_warning_message("Task title is required"), task_id
        
        try:
            plan_list = [line.strip() for line in plan.split('\n') if line.strip()]
            notes_list = [line.strip() for line in notes.split('\n') if line.strip()]
            
            if task_id and edit_task_logic:
                # Update existing task
                success, message = edit_task_logic(
                    task_id=task_id,
                    title=title,
                    description=description,
                    status=status,
                    priority=priority,
                    progress=progress,
                    plan=plan_list,
                    notes=notes_list
                )
            elif create_task_logic:
                # Create new task
                success, message = create_task_logic(
                    title=title,
                    description=description,
                    status=status,
                    priority=priority,
                    progress=progress,
                    plan=plan_list,
                    notes=notes_list
                )
            else:
                success, message = False, "Task operations not available"
            
            if success:
                # Clear form on success for new tasks
                if not task_id:
                    return (
                        format_success_message(message),
                        None,  # Clear task_id
                        "",    # Clear title
                        "",    # Clear description
                        "todo",
                        "medium",
                        0,
                        "",
                        ""
                    )
                else:
                    return format_success_message(message), task_id
            else:
                return format_error_message(message), task_id
                
        except Exception as e:
            logging.error(f"Error saving task: {e}")
            return format_error_message(f"Failed to save task: {str(e)}"), task_id
    
    def apply_template(template_type, template_data):
        """Apply a task template."""
        prefix = template_data.get('prefix', '')
        priority = template_data.get('priority', 'medium')
        
        templates = {
            'bug': {
                'title': f"{prefix}",
                'description': "Bug description:\n\nSteps to reproduce:\n1. \n2. \n\nExpected behavior:\n\nActual behavior:",
                'plan': "1. Reproduce the issue\n2. Identify root cause\n3. Implement fix\n4. Add tests\n5. Verify fix"
            },
            'feature': {
                'title': f"{prefix}",
                'description': "Feature description:\n\nUser story:\nAs a [user type], I want [goal] so that [reason]",
                'plan': "1. Design solution\n2. Implement core functionality\n3. Add tests\n4. Update documentation\n5. Get review"
            },
            'docs': {
                'title': f"{prefix}",
                'description': "Documentation needed for:",
                'plan': "1. Research topic\n2. Write draft\n3. Add examples\n4. Review and edit\n5. Publish"
            },
            'test': {
                'title': f"{prefix}",
                'description': "Testing requirements:",
                'plan': "1. Identify test cases\n2. Write unit tests\n3. Write integration tests\n4. Run test suite\n5. Document results"
            },
            'refactor': {
                'title': f"{prefix}",
                'description': "Refactoring goals:\n\nCurrent issues:\n\nProposed improvements:",
                'plan': "1. Analyze current code\n2. Plan refactoring\n3. Create tests\n4. Refactor incrementally\n5. Verify behavior"
            }
        }
        
        template = templates.get(template_type, {})
        
        return (
            None,  # task_id (new task)
            template.get('title', ''),
            template.get('description', ''),
            'todo',
            priority,
            0,
            template.get('plan', ''),
            ''  # notes
        )
    
    # Connect event handlers
    
    # Quick task creation
    quick_create_btn.click(
        on_quick_create,
        inputs=[quick_task_input],
        outputs=[form_status, quick_task_input]
    ).then(
        refresh_all,
        outputs=[quick_stats, task_switcher, task_list_display, task_details_display, form_status]
    )
    
    # Task switching
    switch_button.click(
        on_task_switch,
        inputs=[task_switcher],
        outputs=[form_status, current_task_id]
    ).then(
        lambda task_id: format_task_details(task_id) if task_id else "No task selected",
        inputs=[current_task_id],
        outputs=[task_details_display]
    )
    
    task_switcher.change(
        lambda task_id: (task_id, format_task_details(task_id) if task_id else "No task selected"),
        inputs=[task_switcher],
        outputs=[current_task_id, task_details_display]
    )
    
    # Filter changes
    for filter_component in [status_filter, priority_filter, sort_by]:
        filter_component.change(
            on_filter_change,
            inputs=[status_filter, priority_filter, sort_by],
            outputs=[task_list_display]
        )
    
    # Task action handlers
    def handle_start_task(task_id):
        if not task_id:
            return format_warning_message("No task selected")
        if not start_task_logic:
            return format_error_message("Task operations not available")
        try:
            success, message = start_task_logic(task_id)
            return format_success_message(message) if success else format_error_message(message)
        except Exception as e:
            return format_error_message(f"Failed to start task: {str(e)}")
    
    def handle_done_task(task_id):
        if not task_id:
            return format_warning_message("No task selected")
        if not done_task_logic:
            return format_error_message("Task operations not available")
        try:
            success, message = done_task_logic(task_id)
            return format_success_message(message) if success else format_error_message(message)
        except Exception as e:
            return format_error_message(f"Failed to complete task: {str(e)}")
    
    def handle_delete_task(task_id):
        if not task_id:
            return format_warning_message("No task selected")
        
        try:
            # Get the task to get its title for the success message
            task = ts.get_task_by_id(task_id)
            if not task:
                return format_error_message(f"Task with ID {task_id} not found")
            
            task_title = task.title
            
            # Delete from task store
            if ts.delete_task(task_id):
                # Delete from vector store
                task_id_str = str(task_id)
                try:
                    # Import delete_vector from memory_utils
                    memory_utils = import_memory_utils()
                    if memory_utils and hasattr(memory_utils, 'delete_vector'):
                        memory_utils.delete_vector(task_id_str)
                        return format_success_message(f"Successfully deleted task #{task_id}: {task_title}")
                    else:
                        # If delete_vector is not available, still consider it a success
                        logging.warning("delete_vector not available in memory_utils")
                        return format_success_message(f"Task #{task_id} deleted from task store")
                except Exception as e:
                    logging.error(f"Task deleted from local store but not from vector store: {e}")
                    return format_success_message(f"Task #{task_id} deleted from task store (vector store deletion failed)")
            else:
                return format_error_message(f"Failed to delete task #{task_id} from task store")
        except Exception as e:
            return format_error_message(f"Failed to delete task: {str(e)}")
    
    # Task actions
    start_task_btn.click(
        handle_start_task,
        inputs=[current_task_id],
        outputs=[form_status]
    ).then(
        refresh_all,
        outputs=[quick_stats, task_switcher, task_list_display, task_details_display, form_status]
    )
    
    done_task_btn.click(
        handle_done_task,
        inputs=[current_task_id],
        outputs=[form_status]
    ).then(
        refresh_all,
        outputs=[quick_stats, task_switcher, task_list_display, task_details_display, form_status]
    )
    
    edit_task_btn.click(
        load_task_for_edit,
        inputs=[current_task_id],
        outputs=[task_id_edit, task_title, task_description, task_status, task_priority, task_progress, task_plan, task_notes]
    )
    
    delete_task_btn.click(
        handle_delete_task,
        inputs=[current_task_id],
        outputs=[form_status]
    ).then(
        refresh_all,
        outputs=[quick_stats, task_switcher, task_list_display, task_details_display, form_status]
    )
    
    # Form submission
    save_task_btn.click(
        on_save_task,
        inputs=[task_id_edit, task_title, task_description, task_status, task_priority, task_progress, task_plan, task_notes],
        outputs=[form_status, task_id_edit]
    ).then(
        refresh_all,
        outputs=[quick_stats, task_switcher, task_list_display, task_details_display, form_status]
    )
    
    cancel_edit_btn.click(
        lambda: (None, "", "", "todo", "medium", 0, "", "", ""),
        outputs=[task_id_edit, task_title, task_description, task_status, task_priority, task_progress, task_plan, task_notes, form_status]
    )
    
    # Note: new_task_button removed as tasks are created via forms
    
    # Template buttons
    for btn, template_type, template_data in template_buttons:
        btn.click(
            lambda tt=template_type, td=template_data: apply_template(tt, td),
            outputs=[task_id_edit, task_title, task_description, task_status, task_priority, task_progress, task_plan, task_notes]
        )
    
    # Initial load
    try:
        if ts and hasattr(ts, 'tasks'):
            quick_stats.value = get_task_stats(ts.tasks)
            task_switcher.choices = get_task_choices(ts.tasks)
            task_list_display.value = format_task_list(ts.tasks)
            
            # Select first in-progress task if any
            for task in ts.tasks:
                if hasattr(task, 'status') and task.status == 'in_progress':
                    task_switcher.value = str(task.id)
                    current_task_id.value = str(task.id)
                    task_details_display.value = format_task_details(str(task.id))
                    break
    except Exception as e:
        logging.error(f"Error loading initial task data: {e}")
    
    # Return references
    return {
        "refresh": refresh_all,
        "components": {
            "task_switcher": task_switcher,
            "task_list": task_list_display,
            "task_details": task_details_display,
            "quick_stats": quick_stats,
            "form_status": form_status
        }
    }