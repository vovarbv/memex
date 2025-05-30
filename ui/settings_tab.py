import gradio as gr
import logging
import os
import pathlib

# Import the shared utility functions
from .shared_utils import try_import_with_prefix, import_memory_utils
from .file_browser_utils import (
    create_file_browser_component, 
    convert_selections_to_patterns,
    sync_patterns_with_toml,
    parse_current_patterns,
    match_patterns_to_paths
)

def create_settings_tab(ts, cfg, data_integrity_error=None):
    """Creates the Settings tab UI with essential system settings.
    
    Args:
        ts: TaskStore instance
        cfg: Configuration dictionary
        data_integrity_error: Data integrity error message, if any
        
    Returns:
        dict: A dictionary containing references to the refresh function and components
    """
    # Import required functions
    try:
        # Get memory_utils module and constants
        memory_utils = import_memory_utils()
        CFG_PATH = memory_utils.CFG_PATH
        ROOT = memory_utils.ROOT
        check_vector_store_integrity = memory_utils.check_vector_store_integrity
        
        # Get MDC generation function
        gen_memory_mdc_module = try_import_with_prefix("gen_memory_mdc", ["scripts.", ".scripts.", "memex.scripts."])
        generate_mdc_logic = gen_memory_mdc_module.make if gen_memory_mdc_module and hasattr(gen_memory_mdc_module, 'make') else None
        
        # Get indexing function
        index_codebase_module = try_import_with_prefix("index_codebase", ["scripts.", ".scripts.", "memex.scripts."])
        index_codebase_logic = index_codebase_module.main if index_codebase_module and hasattr(index_codebase_module, 'main') else None
        
        # Try to import TOML libraries for validation
        try:
            import tomli
            import tomli_w
            has_tomli = True
        except ImportError:
            logging.warning("tomli/tomli_w not available for TOML validation")
            has_tomli = False
    except Exception as e:
        logging.error(f"Error importing settings tab dependencies: {e}")
        CFG_PATH = None
        ROOT = None
        generate_mdc_logic = None
        check_vector_store_integrity = None
        has_tomli = False
    
    # Tab content starts here
    gr.Markdown("## System Settings")
    
    # Core system configuration section
    gr.Markdown("### Core Configuration")
    
    with gr.Accordion("System Information", open=True):
        # Show paths and system info
        paths_info = gr.Markdown()
        
        # Memory usage stats
        memory_usage = gr.Markdown()
        
        # System status
        system_status = gr.Markdown()
    
    # Memory.toml Section
    gr.Markdown("### Configuration File (memory.toml)")
    
    # Use Code component with TOML syntax
    memory_toml_display = gr.Code(language="python", label="Current memory.toml Content (Read-Only)", lines=15)
    memory_toml_edit = gr.Code(language="python", label="Edit memory.toml Content", lines=20, interactive=True)
    
    with gr.Row():
        load_toml_button = gr.Button("Load")
        validate_toml_button = gr.Button("Validate")
        save_toml_button = gr.Button("Save Changes")
    
    toml_status = gr.Markdown("")
    
    # Interactive File Selection Section
    gr.Markdown("### 📁 Interactive File Selection for Indexing")
    gr.Markdown("Use the file browser below to select files and folders for FAISS indexing. Your selections will be converted to glob patterns and **only update the include section** of memory.toml (exclude patterns are preserved).")
    
    with gr.Accordion("File Browser", open=True):
        # Create file browser component
        file_browser, selected_paths_state, browser_status = create_file_browser_component(str(ROOT.parent))
        
        # Pattern preview
        gr.Markdown("#### Generated Patterns Preview")
        patterns_preview = gr.Code(
            language="yaml",
            label="Include/Exclude Patterns",
            lines=10,
            interactive=False
        )
        
        with gr.Row():
            select_all_btn = gr.Button("✅ Select All", variant="secondary")
            deselect_all_btn = gr.Button("❌ Deselect All", variant="secondary")
            load_existing_btn = gr.Button("📥 Load Existing", variant="secondary")
            
        with gr.Row():
            apply_selections_btn = gr.Button("💾 Apply to memory.toml", variant="primary")
            index_selected_btn = gr.Button("🔍 Index Selected Files", variant="primary")
            clear_selections_btn = gr.Button("🗑️ Clear Selections")
            
        with gr.Row():
            reindex_selected_btn = gr.Button("🔄 Rebuild Index from Selection", variant="secondary")
            reindex_all_btn = gr.Button("🔄 Rebuild Complete Index", variant="secondary")
            
        selection_status = gr.Markdown("")
    
    # Data Management Section
    gr.Markdown("### Data Management")
    
    with gr.Row():
        backup_button = gr.Button("📦 Backup Data", variant="secondary")
        delete_store_btn = gr.Button("🗑️ Delete Vector Store", variant="stop")
        
    delete_confirmation = gr.Markdown("")
    
    gr.Markdown("💡 **Note**: Backup creates a copy of your vector store and configuration. Delete permanently removes all indexed data (tasks, snippets, notes, and code chunks).")
    
    data_management_status = gr.Markdown("")
    
    # Core function: Backup/Restore
    def backup_data():
        try:
            timestamp = memory_utils.get_timestamp() if hasattr(memory_utils, 'get_timestamp') else ""
            backup_dir = ROOT / "backups" / f"backup_{timestamp}"
            
            # Create backup directory
            backup_dir.mkdir(parents=True, exist_ok=True)
            
            # List of files to backup (simplified for core functionality)
            files_to_backup = [
                CFG_PATH,  # memory.toml
                ROOT / cfg.get("system", {}).get("tasks_file_relative_to_memex_root", "docs/TASKS.yaml"),
                ROOT / cfg.get("system", {}).get("snippets_file_relative_to_memex_root", "docs/SNIPPETS.yaml"),
                ROOT / cfg.get("system", {}).get("notes_file_relative_to_memex_root", "docs/NOTES.yaml")
            ]
            
            # Backup vector store
            vector_store_dir = ROOT / cfg.get("system", {}).get("vector_store_dir", "vector_store")
            if vector_store_dir.exists():
                import shutil
                shutil.copytree(vector_store_dir, backup_dir / "vector_store", dirs_exist_ok=True)
            
            # Copy individual files
            for file_path in files_to_backup:
                if file_path and file_path.exists():
                    import shutil
                    shutil.copy2(file_path, backup_dir / file_path.name)
            
            return f"✅ Backup created at: {backup_dir}"
        except Exception as e:
            logging.error(f"Backup error: {e}")
            return f"❌ Backup failed: {str(e)}"
    
    # Core function: Load memory.toml
    def load_memory_toml():
        try:
            if not CFG_PATH or not CFG_PATH.exists():
                return "", "", f"❌ Configuration file not found at: {CFG_PATH or 'Unknown path'}"
            
            content = CFG_PATH.read_text(encoding="utf-8")
            return content, content, f"✅ Loaded configuration from: {CFG_PATH}"
        except Exception as e:
            return "", "", f"❌ Error loading configuration: {str(e)}"
    
    # Core function: Validate TOML
    def validate_toml(toml_content):
        if not has_tomli:
            return "⚠️ TOML validation library not available. Install with `pip install tomli tomli_w`."
        
        try:
            # Parse the TOML to verify it's valid
            tomli.loads(toml_content)
            return "✅ TOML format is valid."
        except Exception as e:
            return f"❌ Invalid TOML format: {str(e)}"
    
    # Core function: Save memory.toml
    def save_memory_toml(toml_content):
        try:
            if not CFG_PATH:
                gr.Error("Configuration path not available")
                return memory_toml_display.value, f"❌ Configuration path not available"
            
            # Validate TOML content
            if has_tomli:
                try:
                    # Parse the TOML to verify it's valid
                    tomli.loads(toml_content)
                except Exception as e:
                    gr.Error(f"Invalid TOML format: {str(e)}")
                    return memory_toml_display.value, f"❌ Invalid TOML format: {str(e)}"
            
            # Save to file
            if not CFG_PATH.parent.exists():
                CFG_PATH.parent.mkdir(parents=True, exist_ok=True)
            
            CFG_PATH.write_text(toml_content, encoding="utf-8")
            gr.Info(f"Configuration saved to {CFG_PATH}")
            return toml_content, f"✅ Configuration saved to: {CFG_PATH}"
        except Exception as e:
            gr.Error(f"Error saving configuration: {str(e)}")
            return memory_toml_display.value, f"❌ Error saving configuration: {str(e)}"
    
    # Function to handle file browser selection changes
    def handle_selection_change(selections):
        """Handle file browser selection changes."""
        try:
            if not selections:
                return selections, "# No selections made\ninclude = []\nexclude = []", "", []
            
            # Update pattern preview
            preview, status = update_pattern_preview(selections)
            
            return selections, preview, status, selections
            
        except Exception as e:
            logging.error(f"Error handling selection change: {e}")
            return selections, "", f"❌ Error: {str(e)}", selections
    
    # Function to update pattern preview
    def update_pattern_preview(selections):
        """Update the pattern preview based on file browser selections."""
        try:
            if not selections:
                return "# No selections made\ninclude = []\nexclude = []", ""
                    
            # Convert to patterns (selections are already absolute paths from FileExplorer)
            include_patterns, exclude_patterns = convert_selections_to_patterns(
                selections, str(ROOT)
            )
            
            # Format as TOML-like preview (note: exclude patterns will be preserved from memory.toml)
            preview = "[files]\ninclude = [\n"
            for pattern in include_patterns:
                preview += f'    "{pattern}",\n'
            preview += "]\n# exclude patterns will be preserved from existing memory.toml"
            
            return preview, f"✅ Generated {len(include_patterns)} include patterns from {len(selections)} selections"
            
        except Exception as e:
            logging.error(f"Error updating pattern preview: {e}")
            return "", f"❌ Error: {str(e)}"
    
    # Function to apply selections to memory.toml (PRESERVE exclude section)
    def apply_selections_to_toml(selections, current_toml):
        """Apply file browser selections to memory.toml while preserving exclude patterns."""
        try:
            if not selections:
                return current_toml, current_toml, "⚠️ No selections to apply"
                    
            # Convert to patterns (selections are already absolute paths)
            include_patterns, _ = convert_selections_to_patterns(
                selections, str(ROOT)
            )
            
            # Parse current TOML to preserve exclude section
            if has_tomli:
                try:
                    import tomli_w
                    current_config = tomli.loads(current_toml)
                    
                    # Update only the include patterns, preserve existing exclude
                    if 'files' not in current_config:
                        current_config['files'] = {}
                    
                    current_config['files']['include'] = include_patterns
                    # Keep existing exclude patterns unchanged
                    
                    # Convert back to TOML string
                    updated_toml = tomli_w.dumps(current_config)
                    
                except Exception as e:
                    logging.error(f"Error parsing TOML: {e}")
                    return current_toml, current_toml, f"❌ Error parsing TOML: {str(e)}"
            else:
                # Fallback: manual string replacement (less reliable)
                lines = current_toml.split('\n')
                new_lines = []
                in_include_section = False
                bracket_count = 0
                
                for line in lines:
                    stripped = line.strip()
                    if stripped.startswith('include = ['):
                        in_include_section = True
                        bracket_count = line.count('[') - line.count(']')
                        new_lines.append('include = [')
                        for pattern in include_patterns:
                            new_lines.append(f'    "{pattern}",')
                        if bracket_count <= 0:
                            new_lines.append(']')
                            in_include_section = False
                    elif in_include_section:
                        bracket_count += line.count('[') - line.count(']')
                        if bracket_count <= 0:
                            new_lines.append(']')
                            in_include_section = False
                        # Skip old include pattern lines
                    else:
                        new_lines.append(line)
                
                updated_toml = '\n'.join(new_lines)
            
            # Also update the file
            if CFG_PATH and updated_toml != current_toml:
                CFG_PATH.write_text(updated_toml, encoding="utf-8")
                gr.Info("✅ Configuration saved to memory.toml")
                
            return updated_toml, updated_toml, f"✅ Applied {len(include_patterns)} include patterns (exclude patterns preserved)"
            
        except Exception as e:
            logging.error(f"Error applying selections: {e}")
            return current_toml, current_toml, f"❌ Error: {str(e)}"
    
    # Function to select all files
    def select_all_files():
        """Select all relevant project files (excluding virtual environments, dependencies, etc.)."""
        try:
            all_files = []
            root_parent = ROOT.parent
            
            # Define comprehensive skip patterns - much more thorough
            skip_dirs = {
                'memex',                # Our memex directory
                '.git',                 # Git repository
                '__pycache__',          # Python cache
                '.venv', 'venv',        # Virtual environments
                'node_modules',         # Node.js dependencies
                '.env', 'env',          # Environment variables
                'site-packages',        # Python packages
                '.pip', 'pip',          # Pip cache and packages
                'dist', 'build',        # Distribution/build files
                '.tox', '.pytest_cache', '.mypy_cache',  # Test/lint caches
                '.coverage', 'htmlcov', # Coverage files
                '.idea', '.vscode',     # IDE files
                'library', 'lib', 'libs',  # Library directories
                'vendor', '_vendor',    # Vendor dependencies
                'packages',             # Package directories
                'scripts',              # Windows venv scripts
                'include',              # Python include files
                'share',                # Shared files
                'pyvenv.cfg',           # Virtual env config
                'bin',                  # Unix binaries
                'man',                  # Manual pages
            }
            
            # Path patterns that indicate virtual environments or dependencies
            venv_patterns = [
                'venvs/',               # Virtual environments directory
                '/venv/',               # Virtual environment
                '/.venv/',              # Hidden virtual environment  
                'site-packages/',       # Python packages
                '/lib/python',          # Python library path
                '/scripts/',            # Windows venv scripts
                '/include/',            # Include files
                '/share/',              # Shared files
                'pip/_internal/',       # Pip internals
                'pip/_vendor/',         # Pip vendor packages
                'dist-info/',           # Package distribution info
                'egg-info/',            # Python egg info
                '__pycache__/',         # Python cache
                '.pyc',                 # Python bytecode
                '.pyo',                 # Python optimized
                '/bin/',                # Binary files
                'activate',             # Virtual env activation scripts
                'deactivate',           # Virtual env deactivation scripts
            ]
            
            # Traverse the parent directory
            for root, dirs, files in os.walk(root_parent):
                root_path = pathlib.Path(root)
                
                try:
                    rel_path = root_path.relative_to(root_parent)
                except ValueError:
                    # Path is not relative to root_parent, skip
                    continue
                
                # Convert path to string for pattern matching
                path_str = str(rel_path).replace('\\', '/').lower()
                full_path_str = str(root_path).replace('\\', '/').lower()
                
                # Skip if any part of the path contains skip patterns
                should_skip = False
                
                # Check each path component
                for part in rel_path.parts:
                    part_lower = part.lower()
                    if (part_lower in skip_dirs or 
                        part_lower.startswith('.') and part != '.cursor' or
                        'python' in part_lower and any(v in part_lower for v in ['3.', '2.', 'env']) or
                        part_lower.endswith('.egg') or
                        part_lower.endswith('.dist-info')):
                        should_skip = True
                        break
                
                # Check for virtual environment patterns in the full path
                if not should_skip:
                    for pattern in venv_patterns:
                        if pattern in path_str or pattern in full_path_str:
                            should_skip = True
                            break
                
                # Special check for paths that contain tilde (home directory references)
                if '~' in str(root_path):
                    should_skip = True
                
                # Skip .cursor/vecstore and .cursor/rules but allow other .cursor files
                if '.cursor' in rel_path.parts:
                    if any(part in rel_path.parts for part in ['vecstore', 'rules']):
                        should_skip = True
                
                if should_skip:
                    # Also remove these directories from further traversal
                    dirs[:] = []
                    continue
                    
                # Add files with relevant extensions
                for file in files:
                    file_path = root_path / file
                    file_lower = file.lower()
                    
                    # Check file extension
                    if file_path.suffix.lower() in {'.py', '.md', '.js', '.ts', '.txt', '.json', '.yaml', '.yml', '.toml', '.cfg', '.ini', '.sh', '.bat', '.html', '.css', '.dart'}:
                        # Additional file-level filters
                        if (not any(skip in file_lower for skip in ['site-packages', 'dist-info', '__pycache__', '.pyc', '.pyo']) and
                            not file_lower.startswith('activate') and
                            not file_lower.startswith('deactivate') and
                            not file_lower.endswith('.egg')):
                            all_files.append(str(file_path))
            
            # Remove any remaining problematic paths that might have slipped through
            cleaned_files = []
            for file_path in all_files:
                file_str = file_path.lower().replace('\\', '/')
                if not any(bad in file_str for bad in [
                    'site-packages', 'venvs/', '/lib/python', 'pip/_internal', 
                    'pip/_vendor', 'dist-info', '__pycache__', '~/'
                ]):
                    cleaned_files.append(file_path)
            
            # Limit to reasonable number for UI performance
            if len(cleaned_files) > 300:
                cleaned_files = cleaned_files[:300]
                status = f"⚠️ Selected first 300 relevant files (found {len(cleaned_files)}+ total)"
            else:
                status = f"✅ Selected {len(cleaned_files)} relevant project files"
                
            logging.info(f"[settings_tab] select_all_files: Selected {len(cleaned_files)} files after filtering")
            
            return cleaned_files, status, cleaned_files
            
        except Exception as e:
            logging.error(f"Error selecting all files: {e}")
            return [], f"❌ Error: {str(e)}", []
    
    # Function to deselect all files
    def deselect_all_files():
        """Deselect all files."""
        return [], "✅ All files deselected", []
    
    # Function to clear selections
    def clear_all_selections():
        """Clear all file browser selections."""
        return [], "", "✅ Selections cleared", []
    
    # Function to index selected files
    def index_selected_files(selections):
        """Index the selected files directly to FAISS store."""
        try:
            if not selections:
                return "⚠️ No files selected for indexing"
            
            if not index_codebase_logic:
                return "❌ Indexing functionality not available"
            
            # Temporarily update memory.toml with selected patterns for indexing
            include_patterns, _ = convert_selections_to_patterns(selections, str(ROOT))
            
            if not include_patterns:
                return "⚠️ No valid patterns generated from selections"
            
            # Create a temporary config or update current one
            if has_tomli:
                try:
                    import tomli_w
                    current_toml = CFG_PATH.read_text(encoding="utf-8") if CFG_PATH else ""
                    current_config = tomli.loads(current_toml) if current_toml else {}
                    
                    # Backup original include patterns
                    original_include = current_config.get('files', {}).get('include', [])
                    
                    # Set selected patterns for indexing
                    if 'files' not in current_config:
                        current_config['files'] = {}
                    current_config['files']['include'] = include_patterns
                    
                    # Write temporary config
                    temp_toml = tomli_w.dumps(current_config)
                    if CFG_PATH:
                        CFG_PATH.write_text(temp_toml, encoding="utf-8")
                    
                    # Run indexing
                    result = index_codebase_logic([])  # No args means index based on config
                    
                    # Restore original config
                    current_config['files']['include'] = original_include
                    restored_toml = tomli_w.dumps(current_config)
                    if CFG_PATH:
                        CFG_PATH.write_text(restored_toml, encoding="utf-8")
                    
                    return f"✅ Successfully indexed {len(selections)} selected files ({len(include_patterns)} patterns)"
                    
                except Exception as e:
                    logging.error(f"Error during indexing: {e}")
                    return f"❌ Indexing failed: {str(e)}"
            else:
                return "❌ TOML libraries required for indexing. Install with: pip install tomli tomli_w"
                
        except Exception as e:
            logging.error(f"Error indexing selected files: {e}")
            return f"❌ Error: {str(e)}"
    
    def reindex_selected_files(selections):
        """Rebuild the index using only the selected files (removes all existing code chunks first)."""
        try:
            if not selections:
                return "⚠️ No files selected for reindexing"
            
            if not index_codebase_logic:
                return "❌ Indexing functionality not available"
            
            # Temporarily update memory.toml with selected patterns for indexing
            include_patterns, _ = convert_selections_to_patterns(selections, str(ROOT))
            
            if not include_patterns:
                return "⚠️ No valid patterns generated from selections"
            
            # Create a temporary config with reindex flag
            if has_tomli:
                try:
                    import tomli_w
                    current_toml = CFG_PATH.read_text(encoding="utf-8") if CFG_PATH else ""
                    current_config = tomli.loads(current_toml) if current_toml else {}
                    
                    # Backup original include patterns
                    original_include = current_config.get('files', {}).get('include', [])
                    
                    # Set selected patterns for indexing
                    if 'files' not in current_config:
                        current_config['files'] = {}
                    current_config['files']['include'] = include_patterns
                    
                    # Write temporary config
                    temp_toml = tomli_w.dumps(current_config)
                    if CFG_PATH:
                        CFG_PATH.write_text(temp_toml, encoding="utf-8")
                    
                    # Run indexing with reindex flag
                    result = index_codebase_logic(["--reindex"])  # Add reindex flag
                    
                    # Restore original config
                    current_config['files']['include'] = original_include
                    restored_toml = tomli_w.dumps(current_config)
                    if CFG_PATH:
                        CFG_PATH.write_text(restored_toml, encoding="utf-8")
                    
                    return f"✅ Successfully rebuilt index from {len(selections)} selected files\\n🔄 All existing code chunks were removed and replaced"
                    
                except Exception as e:
                    logging.error(f"Error during reindexing: {e}")
                    return f"❌ Reindexing failed: {str(e)}"
            else:
                return "❌ TOML libraries required for reindexing. Install with: pip install tomli tomli_w"
                
        except Exception as e:
            logging.error(f"Error reindexing selected files: {e}")
            return f"❌ Error: {str(e)}"
    
    def reindex_all_files():
        """Rebuild the complete index based on current memory.toml patterns."""
        try:
            if not index_codebase_logic:
                return "❌ Indexing functionality not available"
            
            # Run indexing with reindex flag using current config
            result = index_codebase_logic(["--reindex"])
            
            return "✅ Successfully rebuilt complete index\\n🔄 All existing code chunks were removed and replaced with current configuration"
                
        except Exception as e:
            logging.error(f"Error rebuilding complete index: {e}")
            return f"❌ Complete reindex failed: {str(e)}"
    
    def delete_vector_store():
        """Delete the entire vector store after confirmation."""
        try:
            # Get vector store paths
            vec_dir = memory_utils.get_vec_dir() if hasattr(memory_utils, 'get_vec_dir') else None
            
            if not vec_dir or not vec_dir.exists():
                return "⚠️ Vector store directory not found or already deleted"
            
            import shutil
            shutil.rmtree(vec_dir)
            
            return f"✅ Vector store deleted successfully\\n📂 Removed: {vec_dir}"
                
        except Exception as e:
            logging.error(f"Error deleting vector store: {e}")
            return f"❌ Failed to delete vector store: {str(e)}"
    
    # Function to load existing patterns from memory.toml
    def load_existing_patterns(toml_content):
        """Load existing patterns from memory.toml and select matching items."""
        try:
            # Parse current patterns
            include_patterns, exclude_patterns = parse_current_patterns(toml_content)
            
            if not include_patterns:
                return [], "⚠️ No existing patterns found in memory.toml"
                
            # Match patterns to actual file paths
            matched_paths = match_patterns_to_paths(include_patterns, str(ROOT))
            
            return matched_paths, f"✅ Loaded {len(matched_paths)} files from {len(include_patterns)} patterns"
            
        except Exception as e:
            logging.error(f"Error loading existing patterns: {e}")
            return [], f"❌ Error: {str(e)}"
    
    # Function to check system status and update UI
    def update_system_info():
        try:
            # Generate paths info
            paths_text = "**System Paths:**\n"
            paths_text += f"- Root Directory: `{ROOT}`\n"
            paths_text += f"- Configuration File: `{CFG_PATH}`\n"
            
            # Memory usage
            # Vector store is in the parent directory (host project root)
            host_root = ROOT.parent
            vector_store_dir = host_root / ".cursor" / "vecstore"
            memory_text = "**Memory Usage:**\n"
            
            # Calculate directory sizes
            if vector_store_dir.exists():
                vector_store_size = sum(f.stat().st_size for f in vector_store_dir.glob('**/*') if f.is_file())
                memory_text += f"- Vector Store: {vector_store_size / (1024*1024):.2f} MB\n"
            else:
                memory_text += "- Vector Store: Not found\n"
            
            # System status check
            status_text = "**System Status:**\n"
            if check_vector_store_integrity:
                store_health = check_vector_store_integrity()
                status = store_health.get("status", "unknown")
                status_emoji = "✅" if status == "ok" else "⚠️" if status == "warning" else "❌"
                status_text += f"{status_emoji} Vector Store: {status.upper()}\n"
            else:
                status_text += "⚠️ Vector Store health check not available\n"
            
            return paths_text, memory_text, status_text
        except Exception as e:
            logging.error(f"Error updating system info: {e}")
            return "Error retrieving system paths", "Error retrieving memory usage", f"❌ Error: {str(e)}"
    
    # Refresh function for the entire tab
    def refresh_settings():
        try:
            # Update system info
            paths_info_text, memory_usage_text, system_status_text = update_system_info()
            
            # Load memory.toml
            toml_display, toml_edit, toml_status_text = load_memory_toml()
            
            # Clear file browser selections on refresh
            cleared_browser = []
            cleared_preview = ""
            
            # Return all updates
            return (paths_info_text, memory_usage_text, system_status_text, 
                   toml_display, toml_edit, toml_status_text, "",
                   cleared_browser, cleared_preview, "")
        except Exception as e:
            logging.error(f"Error refreshing settings tab: {e}")
            return ("Error refreshing", "Error refreshing", "Error refreshing", 
                   "", "", "❌ Error refreshing settings", "",
                   [], "", "")
    
    # Connect buttons to functions
    load_toml_button.click(
        load_memory_toml,
        outputs=[memory_toml_display, memory_toml_edit, toml_status]
    )
    
    validate_toml_button.click(
        validate_toml,
        inputs=[memory_toml_edit],
        outputs=[toml_status]
    )
    
    save_toml_button.click(
        save_memory_toml,
        inputs=[memory_toml_edit],
        outputs=[memory_toml_display, toml_status]
    )
    
    backup_button.click(
        backup_data,
        outputs=[data_management_status]
    )
    
    # Connect file browser interactions
    file_browser.change(
        handle_selection_change,
        inputs=[file_browser],
        outputs=[file_browser, patterns_preview, browser_status, selected_paths_state]
    )
    
    apply_selections_btn.click(
        apply_selections_to_toml,
        inputs=[selected_paths_state, memory_toml_edit],
        outputs=[memory_toml_display, memory_toml_edit, selection_status]
    )
    
    clear_selections_btn.click(
        clear_all_selections,
        outputs=[file_browser, patterns_preview, selection_status, selected_paths_state]
    )
    
    load_existing_btn.click(
        load_existing_patterns,
        inputs=[memory_toml_display],
        outputs=[file_browser, selection_status]
    ).then(
        handle_selection_change,
        inputs=[file_browser],
        outputs=[file_browser, patterns_preview, browser_status, selected_paths_state]
    )
    
    # Connect new buttons
    select_all_btn.click(
        select_all_files,
        outputs=[file_browser, selection_status, selected_paths_state]
    ).then(
        handle_selection_change,
        inputs=[file_browser],
        outputs=[file_browser, patterns_preview, browser_status, selected_paths_state]
    )
    
    deselect_all_btn.click(
        deselect_all_files,
        outputs=[file_browser, selection_status, selected_paths_state]
    )
    
    index_selected_btn.click(
        index_selected_files,
        inputs=[selected_paths_state],
        outputs=[selection_status]
    )
    
    reindex_selected_btn.click(
        reindex_selected_files,
        inputs=[selected_paths_state],
        outputs=[selection_status]
    )
    
    reindex_all_btn.click(
        reindex_all_files,
        outputs=[selection_status]
    )
    
    # Delete store with confirmation
    def handle_delete_store():
        """Handle delete store with a confirmation step."""
        return "⚠️ **Are you sure?** This will permanently delete ALL data (tasks, snippets, notes, code chunks).\\n\\n🔴 **Click 'Delete Vector Store' again to confirm.**"
    
    def confirm_delete_store():
        """Actually delete the store after confirmation."""
        return delete_vector_store()
    
    # Track if user has been warned
    delete_warned = gr.State(False)
    
    def delete_store_handler(warned):
        if not warned:
            return handle_delete_store(), True
        else:
            return confirm_delete_store(), False
    
    delete_store_btn.click(
        delete_store_handler,
        inputs=[delete_warned],
        outputs=[delete_confirmation, delete_warned]
    )
    
    # Initial load of system information
    paths_info.value, memory_usage.value, system_status.value = update_system_info()
    
    # Initial load of memory.toml
    memory_toml_display.value, memory_toml_edit.value, toml_status.value = load_memory_toml()
    
    # Return references
    return {
        "refresh": refresh_settings,
        "components": {
            "paths_info": paths_info,
            "memory_usage": memory_usage,
            "system_status": system_status,
            "memory_toml_display": memory_toml_display,
            "memory_toml_edit": memory_toml_edit,
            "toml_status": toml_status,
            "data_management_status": data_management_status,
            "file_browser": file_browser,
            "patterns_preview": patterns_preview,
            "browser_status": browser_status,
            "selection_status": selection_status,
            "selected_paths_state": selected_paths_state,
            "delete_confirmation": delete_confirmation,
            "reindex_selected_btn": reindex_selected_btn,
            "reindex_all_btn": reindex_all_btn,
            "delete_store_btn": delete_store_btn
        }
    }