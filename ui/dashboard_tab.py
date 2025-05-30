"""
Streamlined Dashboard Tab - Quick overview and system status.
This tab provides essential system information and quick actions.
"""

import gradio as gr
import logging
import os
import psutil
from typing import Dict, Any, Optional
from pathlib import Path

# Import shared utilities
from .shared_utils import (
    try_import_with_prefix, 
    import_memory_utils,
    format_error_message,
    format_success_message
)

def create_dashboard_tab(ts, cfg, data_integrity_error=None):
    """
    Creates a streamlined Dashboard tab with essential information only.
    
    Args:
        ts: TaskStore instance or None if there was an error
        cfg: Configuration dictionary
        data_integrity_error: Error message or None
    
    Returns:
        dict: References to components and refresh function
    """
    
    # Import required functions
    try:
        memory_utils = import_memory_utils()
        search = memory_utils.search
        count_items = memory_utils.count_items
        check_vector_store_integrity = memory_utils.check_vector_store_integrity
        ROOT = memory_utils.ROOT if hasattr(memory_utils, 'ROOT') else None
        
        # Get MDC generation function
        gen_memory_mdc_module = try_import_with_prefix("gen_memory_mdc", ["scripts.", ".scripts.", "memex.scripts."])
        generate_mdc_logic = gen_memory_mdc_module.make if gen_memory_mdc_module and hasattr(gen_memory_mdc_module, 'make') else None
        
    except Exception as e:
        logging.error(f"Error importing dashboard dependencies: {e}")
        memory_utils = None
        search = None
        count_items = None
        check_vector_store_integrity = None
        generate_mdc_logic = None
        ROOT = None
    
    # Dashboard header
    gr.Markdown("## 📊 System Dashboard")
    
    # Quick Actions at top
    with gr.Group():
        gr.Markdown("### ⚡ Quick Actions")
        with gr.Row():
            generate_mdc_button = gr.Button("🚀 Generate Memory Context", variant="primary", scale=2)
            refresh_button = gr.Button("🔄 Refresh", scale=1)
        
        action_status = gr.Markdown("")
    
    # System Status
    with gr.Row():
        # Left column - Key metrics
        with gr.Column(scale=1):
            gr.Markdown("### 📈 Key Metrics")
            key_metrics = gr.Markdown("Loading metrics...")
            
            gr.Markdown("### 🎯 Active Focus")
            active_focus = gr.Markdown("Loading active tasks...")
        
        # Right column - System health
        with gr.Column(scale=1):
            gr.Markdown("### 💚 System Health")
            system_health = gr.Markdown("Loading system status...")
            
            gr.Markdown("### 📍 Paths")
            system_paths = gr.Markdown("Loading paths...")
    
    # Helper functions
    def get_key_metrics():
        """Get essential metrics only."""
        try:
            metrics = []
            
            # Task metrics
            if ts and hasattr(ts, 'tasks'):
                total_tasks = len(ts.tasks)
                active_tasks = sum(1 for t in ts.tasks if hasattr(t, 'status') and t.status in ['in_progress', 'todo'])
                metrics.append(f"**Tasks**: {active_tasks} active / {total_tasks} total")
            
            # Memory items
            if count_items:
                try:
                    total_items = count_items()
                    metrics.append(f"**Memory Items**: {total_items:,}")
                except:
                    metrics.append("**Memory Items**: N/A")
            
            # Storage usage
            if ROOT:
                vecstore_path = ROOT.parent / ".cursor" / "vecstore"
                if vecstore_path.exists():
                    size_mb = sum(f.stat().st_size for f in vecstore_path.rglob('*') if f.is_file()) / (1024 * 1024)
                    metrics.append(f"**Vector Store**: {size_mb:.1f} MB")
            
            return "\n".join(metrics) if metrics else "No metrics available"
            
        except Exception as e:
            logging.error(f"Error getting metrics: {e}")
            return f"Error loading metrics: {str(e)}"
    
    def get_active_focus():
        """Get current active tasks."""
        try:
            if not ts or not hasattr(ts, 'tasks'):
                return "No tasks available"
            
            active_tasks = []
            for task in ts.tasks:
                if hasattr(task, 'status') and task.status == 'in_progress':
                    title = getattr(task, 'title', 'Untitled')
                    task_id = getattr(task, 'id', '?')
                    progress = getattr(task, 'progress', 0)
                    priority = getattr(task, 'priority', 'medium')
                    
                    emoji = {'high': '🔴', 'medium': '🟡', 'low': '🟢'}.get(priority, '⚪')
                    active_tasks.append(f"{emoji} **#{task_id}**: {title} ({progress}%)")
            
            if active_tasks:
                return "\n".join(active_tasks[:5])  # Show max 5
            else:
                return "No active tasks. Start a task from the Tasks tab."
                
        except Exception as e:
            logging.error(f"Error getting active tasks: {e}")
            return "Error loading active tasks"
    
    def get_system_health():
        """Get system health status."""
        try:
            health_items = []
            
            # Vector store status
            if check_vector_store_integrity:
                try:
                    integrity = check_vector_store_integrity()
                    if integrity.get('status') == 'healthy':
                        health_items.append("✅ **Vector Store**: Healthy")
                    else:
                        issues = len(integrity.get('issues', []))
                        health_items.append(f"⚠️ **Vector Store**: {issues} issues")
                except:
                    health_items.append("❌ **Vector Store**: Error")
            
            # Memory usage
            try:
                memory = psutil.virtual_memory()
                health_items.append(f"💾 **Memory**: {memory.percent:.1f}% used")
            except:
                pass
            
            # Data integrity
            if data_integrity_error:
                health_items.append(f"❌ **Data**: {data_integrity_error}")
            else:
                health_items.append("✅ **Data**: No issues")
            
            return "\n".join(health_items) if health_items else "Status unavailable"
            
        except Exception as e:
            logging.error(f"Error getting system health: {e}")
            return "Error checking system health"
    
    def get_system_paths():
        """Get key system paths."""
        try:
            paths = []
            
            if ROOT:
                paths.append(f"**Root**: `{ROOT}`")
                
                # Config file
                config_path = ROOT / "memory.toml"
                if config_path.exists():
                    paths.append(f"**Config**: `memory.toml` ✓")
                else:
                    paths.append(f"**Config**: `memory.toml` ✗")
                
                # Tasks file
                tasks_file = cfg.get("system", {}).get("tasks_file_relative_to_memex_root", "docs/TASKS.yaml")
                tasks_path = ROOT / tasks_file
                if tasks_path.exists():
                    paths.append(f"**Tasks**: `{tasks_file}` ✓")
                else:
                    paths.append(f"**Tasks**: `{tasks_file}` ✗")
            
            return "\n".join(paths) if paths else "Path information unavailable"
            
        except Exception as e:
            logging.error(f"Error getting paths: {e}")
            return "Error loading paths"
    
    def refresh_dashboard():
        """Refresh all dashboard components."""
        return (
            get_key_metrics(),
            get_active_focus(),
            get_system_health(),
            get_system_paths(),
            ""  # Clear action status
        )
    
    def generate_mdc():
        """Generate memory.mdc file."""
        if not generate_mdc_logic:
            return format_error_message("MDC generation not available")
        
        try:
            result = generate_mdc_logic()
            # Handle both 2-tuple and 3-tuple returns
            if len(result) == 3:
                success, message, _ = result
            else:
                success, message = result
            
            if success:
                return format_success_message(message)
            else:
                return format_error_message(message)
        except Exception as e:
            logging.error(f"Error generating MDC: {e}")
            return format_error_message(f"Failed to generate MDC: {str(e)}")
    
    # Connect event handlers
    refresh_button.click(
        refresh_dashboard,
        outputs=[key_metrics, active_focus, system_health, system_paths, action_status]
    )
    
    generate_mdc_button.click(
        generate_mdc,
        outputs=[action_status]
    ).then(
        refresh_dashboard,
        outputs=[key_metrics, active_focus, system_health, system_paths, action_status]
    )
    
    # Initial load
    try:
        key_metrics.value = get_key_metrics()
        active_focus.value = get_active_focus()
        system_health.value = get_system_health()
        system_paths.value = get_system_paths()
    except Exception as e:
        logging.error(f"Error loading initial dashboard data: {e}")
    
    # Return references
    return {
        "refresh": refresh_dashboard,
        "components": {
            "key_metrics": key_metrics,
            "active_focus": active_focus,
            "system_health": system_health,
            "system_paths": system_paths,
            "action_status": action_status
        }
    }