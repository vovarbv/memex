"""
Focus Tab - The command center for task-driven context generation.
This tab provides quick access to current task, live context preview,
and one-click actions for maximum productivity.
"""

import gradio as gr
import logging
from typing import Dict, List, Any, Optional, Tuple
import json
from datetime import datetime

# Import shared utilities and required functions
from .shared_utils import (
    try_import_with_prefix, 
    import_memory_utils,
    import_task_store_module,
    format_error_message,
    improve_code_chunk_visualization
)

def create_focus_tab(ts, cfg, data_integrity_error=None):
    """
    Creates the Focus tab UI - a streamlined command center for context generation.
    
    Args:
        ts: TaskStore instance
        cfg: Configuration dictionary
        data_integrity_error: Data integrity error message, if any
        
    Returns:
        dict: References to components and refresh function
    """
    
    # Import required functions
    try:
        # Task management
        task_store_module = import_task_store_module()
        
        # Memory utilities
        memory_utils = import_memory_utils()
        search = memory_utils.search
        
        # MDC generation
        gen_memory_mdc = try_import_with_prefix(
            "gen_memory_mdc", 
            ["scripts.", ".scripts.", "memex.scripts."]
        )
        if gen_memory_mdc and hasattr(gen_memory_mdc, 'generate_mdc_logic'):
            generate_mdc_logic = gen_memory_mdc.generate_mdc_logic
        else:
            generate_mdc_logic = None
            
    except Exception as e:
        logging.error(f"Error importing focus tab dependencies: {e}")
        search = None
        generate_mdc_logic = None
    
    # Header with current focus indicator
    gr.Markdown("## 🎯 Current Focus")
    
    if data_integrity_error:
        gr.Markdown(f"⚠️ **Data Issue**: {data_integrity_error}")
        gr.Markdown("Some features may be limited. Please check your TASKS.yaml file.")
    
    # Main layout with two columns
    with gr.Row():
        # Left column - Task control and actions
        with gr.Column(scale=1):
            # Current task selector
            gr.Markdown("### Active Task")
            
            # Get task choices for dropdown
            task_choices = []
            current_task_id = None
            
            if ts and hasattr(ts, 'tasks'):
                try:
                    # Get all in-progress and todo tasks
                    active_tasks = []
                    for task in ts.tasks:
                        if hasattr(task, 'status') and task.status in ['in_progress', 'todo']:
                            task_id = task.id if hasattr(task, 'id') else 'unknown'
                            title = task.title if hasattr(task, 'title') else 'Untitled'
                            status = task.status if hasattr(task, 'status') else 'unknown'
                            task_choices.append((f"{title} [{status}]", task_id))
                            if status == 'in_progress':
                                active_tasks.append(task_id)
                    
                    # Set current task to first in-progress task
                    if active_tasks:
                        current_task_id = active_tasks[0]
                    elif task_choices:
                        current_task_id = task_choices[0][1]
                        
                except Exception as e:
                    logging.error(f"Error loading tasks: {e}")
                    task_choices = [("No tasks available", None)]
            else:
                task_choices = [("No tasks available", None)]
            
            # Task selector dropdown
            task_selector = gr.Dropdown(
                choices=task_choices,
                value=current_task_id,
                label="Select Task",
                interactive=True
            )
            
            # Quick actions
            gr.Markdown("### Quick Actions")
            
            with gr.Row():
                generate_button = gr.Button("🚀 Generate MDC", variant="primary", scale=2)
                refresh_button = gr.Button("🔄 Refresh", scale=1)
            
            with gr.Row():
                switch_task_button = gr.Button("↔️ Switch Task", scale=1)
            
            # Action status
            action_status = gr.Markdown("")
            
            # Task details
            gr.Markdown("### Task Details")
            task_details = gr.Markdown("Select a task to see details...")
            
        # Right column - Context preview
        with gr.Column(scale=2):
            gr.Markdown("### 📄 Context Preview")
            gr.Markdown("*This is what will be included in your memory.mdc file*")
            
            # Context stats
            context_stats = gr.Markdown("Loading context statistics...")
            
            # Context preview with syntax highlighting - show full content
            context_preview = gr.Code(
                label="memory.mdc content (complete file)",
                language="markdown",
                lines=30,
                max_lines=None,  # Allow unlimited scrolling
                interactive=False
            )
            
            # Context effectiveness indicator
            with gr.Row():
                with gr.Column():
                    gr.Markdown("**Context Quality**")
                    quality_indicator = gr.Markdown("🟡 Checking quality...")
                with gr.Column():
                    gr.Markdown("**Estimated Tokens**")
                    token_count = gr.Markdown("Calculating...")
    
    # Activity feed at bottom
    gr.Markdown("### 📊 Recent Activity")
    activity_feed = gr.Markdown("Loading recent activity...")
    
    # Hidden state for current task
    current_task_state = gr.State(value=current_task_id)
    
    # Helper functions
    def get_task_details(task_id):
        """Get detailed information about a task."""
        if not ts or not task_id:
            return "No task selected"
        
        try:
            # Find the task
            task = None
            for t in ts.tasks:
                if hasattr(t, 'id') and str(t.id) == str(task_id):
                    task = t
                    break
            
            if not task:
                return f"Task {task_id} not found"
            
            # Format task details
            details = f"**{task.title if hasattr(task, 'title') else 'Untitled'}**\n\n"
            
            if hasattr(task, 'description') and task.description:
                details += f"*{task.description}*\n\n"
            
            if hasattr(task, 'status'):
                status_emoji = {
                    'todo': '📝',
                    'in_progress': '🔄',
                    'done': '✅',
                    'blocked': '🚫'
                }.get(task.status, '❓')
                details += f"**Status**: {status_emoji} {task.status}\n"
            
            if hasattr(task, 'priority'):
                priority_emoji = {
                    'high': '🔴',
                    'medium': '🟡',
                    'low': '🟢'
                }.get(task.priority, '⚪')
                details += f"**Priority**: {priority_emoji} {task.priority}\n"
            
            if hasattr(task, 'progress'):
                details += f"**Progress**: {task.progress}%\n"
            
            if hasattr(task, 'plan') and task.plan:
                details += f"\n**Plan**:\n"
                for i, step in enumerate(task.plan, 1):
                    details += f"{i}. {step}\n"
            
            return details
            
        except Exception as e:
            logging.error(f"Error getting task details: {e}")
            return f"Error loading task details: {str(e)}"
    
    def generate_context_preview(task_id):
        """Generate a preview of what will be in memory.mdc."""
        if not task_id:
            return "Context preview not available", "No statistics available"
        
        try:
            # First, try to read the actual MDC file if it exists
            from pathlib import Path
            cfg_module = try_import_with_prefix("memory_utils", ["scripts.", ".scripts.", "memex.scripts."])
            if cfg_module and hasattr(cfg_module, 'load_cfg'):
                try:
                    cfg = cfg_module.load_cfg()
                    # Get the parent directory (host project root)
                    host_root = Path(cfg_module.ROOT).parent
                    mdc_path = host_root / ".cursor" / "rules" / "memory.mdc"
                    
                    if mdc_path.exists():
                        # Read the actual MDC file
                        with open(mdc_path, 'r', encoding='utf-8') as f:
                            actual_mdc_content = f.read()
                        
                        # Calculate stats
                        line_count = actual_mdc_content.count('\n')
                        char_count = len(actual_mdc_content)
                        token_count = char_count // 4  # Rough estimate
                        
                        # Count different sections
                        chunk_count = actual_mdc_content.count('Code from')
                        snippet_count = actual_mdc_content.count('Snippet from')
                        note_count = actual_mdc_content.count('Note (ID:')
                        task_count = actual_mdc_content.count('### Task:')
                        
                        stats = f"""**File Statistics**
- Location: {mdc_path}
- Size: {char_count:,} characters
- Lines: {line_count:,}
- Estimated Tokens: ~{token_count:,}

**Content Summary**
- Tasks: {task_count}
- Code Chunks: {chunk_count}
- Snippets: {snippet_count}
- Notes: {note_count}

*Showing complete memory.mdc file*"""
                        
                        return actual_mdc_content, stats
                except Exception as e:
                    logging.debug(f"Could not read actual MDC file: {e}")
            
            # Fallback to preview generation if MDC doesn't exist
            gen_memory_mdc_preview = try_import_with_prefix(
                "gen_memory_mdc_preview",
                ["scripts.", ".scripts.", "memex.scripts."]
            )
            
            if not gen_memory_mdc_preview:
                return "# Context Preview\n\nGenerate MDC first to see preview", "Statistics unavailable"
            
            # Generate preview data
            preview_data = gen_memory_mdc_preview.preview_context(
                task_id=task_id,
                max_items=10
            )
            
            if preview_data.get('success'):
                preview_markdown = gen_memory_mdc_preview.format_preview_markdown(preview_data)
                stats_markdown = gen_memory_mdc_preview.format_preview_stats(preview_data)
                return preview_markdown, stats_markdown
            else:
                error_msg = preview_data.get('error', 'Unknown error')
                return f"# Preview Error\n\n{error_msg}", "Error generating statistics"
                
        except Exception as e:
            logging.error(f"Error generating preview: {e}")
            return f"# Preview Error\n\n{str(e)}", "Error generating statistics"
    
    def update_activity_feed():
        """Update the recent activity feed."""
        try:
            activities = []
            current_time = datetime.now().strftime('%H:%M')
            
            # Show current task status
            if ts and hasattr(ts, 'tasks'):
                in_progress_count = sum(1 for t in ts.tasks if hasattr(t, 'status') and t.status == 'in_progress')
                todo_count = sum(1 for t in ts.tasks if hasattr(t, 'status') and t.status == 'todo')
                done_count = sum(1 for t in ts.tasks if hasattr(t, 'status') and t.status == 'done')
                
                activities.append(f"📊 Tasks: {in_progress_count} active, {todo_count} pending, {done_count} done")
                activities.append(f"🔄 Last updated: {current_time}")
            
            return "\n".join(activities) if activities else "No activity to show"
        except Exception as e:
            return "Activity feed unavailable"
    
    # Event handlers
    def on_task_change(task_id):
        """Handle task selection change."""
        if not task_id:
            return (
                "No task selected",
                "Select a task to preview context",
                "No statistics available",
                task_id,
                "",
                "⚪ No task selected",
                "No tokens"
            )
        
        # Update task details
        details = get_task_details(task_id)
        
        # Generate preview
        preview, stats = generate_context_preview(task_id)
        
        # Extract token count and quality from stats
        quality = "🟡 Checking quality..."
        tokens = "Calculating..."
        
        if "Estimated Tokens" in stats:
            # Parse token count from stats
            import re
            token_match = re.search(r'Estimated Tokens.*?~([\d,]+)', stats)
            if token_match:
                token_num = int(token_match.group(1).replace(',', ''))
                tokens = f"~{token_num:,} tokens"
                
                # Update quality based on token count
                if token_num < 8000:
                    quality = "🟢 Good - Ready for generation"
                elif token_num < 12000:
                    quality = "🟡 Large - May need trimming"
                else:
                    quality = "🔴 Too Large - Reduce context"
        
        # Update activity
        activity = update_activity_feed()
        
        return details, preview, stats, task_id, activity, quality, tokens
    
    def on_generate_mdc(task_id):
        """Generate memory.mdc for the current task."""
        if not generate_mdc_logic or not task_id:
            gr.Warning("Please select a task first")
            return "❌ No task selected"
        
        try:
            success, message, _ = generate_mdc_logic(
                quiet=False,
                focus_task_id=task_id
            )
            
            if success:
                gr.Info(f"✅ {message}")
                return f"✅ {message}"
            else:
                gr.Warning(f"⚠️ {message}")
                return f"⚠️ {message}"
                
        except Exception as e:
            gr.Error(f"Error generating MDC: {str(e)}")
            return f"❌ Error: {str(e)}"
    
    def on_quick_capture():
        """Open quick capture dialog."""
        gr.Info("Use the Memory tab to capture new snippets and notes")
        return "📸 Use the Memory tab for capturing content"
    
    def on_switch_task(task_id):
        """Switch the task to in_progress status."""
        if not ts or not task_id:
            return "❌ No task selected", task_id
        
        try:
            # Find and update task
            for task in ts.tasks:
                if hasattr(task, 'id') and str(task.id) == str(task_id):
                    if hasattr(task, 'status'):
                        old_status = task.status
                        task.status = 'in_progress'
                        # Save changes
                        ts.save_tasks()
                        gr.Info(f"Switched task to in_progress: {task.title}")
                        return f"✅ Task switched to in_progress", task_id
            
            return "❌ Task not found", task_id
            
        except Exception as e:
            gr.Error(f"Error switching task: {str(e)}")
            return f"❌ Error: {str(e)}", task_id
    
    def refresh_focus():
        """Refresh all components in the focus tab."""
        task_id = current_task_state.value
        if task_id:
            details, preview, stats, _, activity, quality, tokens = on_task_change(task_id)
            return details, preview, stats, activity, "", quality, tokens
        else:
            return (
                "Select a task to see details...",
                "Select a task to preview context",
                "No statistics available",
                "No recent activity",
                "",
                "⚪ No task selected",
                "No tokens"
            )
    
    # Connect event handlers
    task_selector.change(
        on_task_change,
        inputs=[task_selector],
        outputs=[task_details, context_preview, context_stats, current_task_state, activity_feed, quality_indicator, token_count]
    )
    
    generate_button.click(
        on_generate_mdc,
        inputs=[current_task_state],
        outputs=[action_status]
    )
    
    refresh_button.click(
        refresh_focus,
        outputs=[task_details, context_preview, context_stats, activity_feed, action_status, quality_indicator, token_count]
    )
    
    
    switch_task_button.click(
        on_switch_task,
        inputs=[current_task_state],
        outputs=[action_status, current_task_state]
    ).then(
        refresh_focus,
        outputs=[task_details, context_preview, context_stats, activity_feed, action_status, quality_indicator, token_count]
    )
    
    # Initial load
    if current_task_id:
        # Get all initial values using the same logic as on_task_change
        details, preview, stats, _, activity, quality, tokens = on_task_change(current_task_id)
        task_details.value = details
        context_preview.value = preview
        context_stats.value = stats
        quality_indicator.value = quality
        token_count.value = tokens
        activity_feed.value = activity
    else:
        activity_feed.value = update_activity_feed()
    
    # Return references
    return {
        "refresh": refresh_focus,
        "components": {
            "task_selector": task_selector,
            "task_details": task_details,
            "context_preview": context_preview,
            "context_stats": context_stats,
            "activity_feed": activity_feed,
            "action_status": action_status
        }
    }