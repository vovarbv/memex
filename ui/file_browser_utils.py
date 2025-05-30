import os
import pathlib
import logging
from typing import List, Dict, Tuple, Optional
import gradio as gr

# Note: get_directory_tree is no longer needed with FileExplorer component
# The FileExplorer handles directory traversal internally

def convert_selections_to_patterns(selections: List[str], root_path: str) -> Tuple[List[str], List[str]]:
    """Convert selected paths to glob patterns for include/exclude.
    
    Args:
        selections: List of selected file/folder paths (absolute paths from FileExplorer)
        root_path: Root path of the memex directory
        
    Returns:
        Tuple of (include_patterns, exclude_patterns)
    """
    include_patterns = []
    exclude_patterns = []
    
    try:
        memex_root = pathlib.Path(root_path)
        processed_dirs = set()  # Track processed directories to avoid duplicates
        
        for selection in selections:
            if not selection:  # Skip empty selections
                continue
                
            path = pathlib.Path(selection)
            
            # Calculate relative path from memex directory
            try:
                # If the path is within memex, skip it (we don't want to index memex itself)
                if memex_root in path.parents or path == memex_root:
                    continue
                    
                # For paths outside memex (in host project)
                relative = path.relative_to(memex_root.parent)
                relative_str = str(relative).replace('\\', '/')
                
                if path.is_dir():
                    # For directories, create recursive pattern
                    pattern = f"../{relative_str}/**/*"
                    
                    # Check if we already processed a parent directory
                    skip = False
                    for processed_dir in processed_dirs:
                        if relative_str.startswith(processed_dir):
                            skip = True
                            break
                    
                    if not skip and pattern not in include_patterns:
                        include_patterns.append(pattern)
                        processed_dirs.add(relative_str)
                        
                else:
                    # For individual files, check if parent directory is already included
                    parent_included = False
                    parent_str = str(relative.parent).replace('\\', '/')
                    
                    for processed_dir in processed_dirs:
                        if parent_str.startswith(processed_dir):
                            parent_included = True
                            break
                    
                    if not parent_included:
                        # Add specific file pattern
                        pattern = f"../{relative_str}"
                        if pattern not in include_patterns:
                            include_patterns.append(pattern)
                    
            except ValueError:
                # Path is not relative to memex parent, skip it
                logging.warning(f"Skipping path outside project scope: {selection}")
                
    except Exception as e:
        logging.error(f"Error converting selections to patterns: {e}")
        
    return include_patterns, exclude_patterns

def create_file_browser_component(root_path: str) -> Tuple[gr.FileExplorer, gr.State, gr.Markdown]:
    """Create the file browser UI component using FileExplorer.
    
    Args:
        root_path: Root directory for browsing
        
    Returns:
        Tuple of (file_explorer, selected_paths_state, status_text)
    """
    # Create UI components
    with gr.Column():
        gr.Markdown("### 📁 File Browser")
        gr.Markdown("**Select files and folders to include in FAISS indexing:**")
        gr.Markdown("*💡 Tip: Click on folders to expand them. Use Ctrl/Cmd+Click for multiple selections*")
        
        # Create the FileExplorer component
        file_browser = gr.FileExplorer(
            glob="**/*",
            value=[],
            file_count="multiple",
            root_dir=root_path,
            ignore_glob="**/{.git,__pycache__,.venv,venv,node_modules,.cursor,vecstore}/**",
            label="Project Files & Folders",
            interactive=True,
            height=400
        )
        
        # State to track selected paths
        selected_paths_state = gr.State(value=[])
        
        browser_status = gr.Markdown("")
        
    return file_browser, selected_paths_state, browser_status

def sync_patterns_with_toml(include_patterns: List[str], exclude_patterns: List[str], 
                           current_toml_content: str) -> str:
    """Sync the selected patterns with the TOML content.
    
    Args:
        include_patterns: List of include patterns
        exclude_patterns: List of exclude patterns  
        current_toml_content: Current TOML file content
        
    Returns:
        Updated TOML content
    """
    try:
        import tomli
        import tomli_w
        
        # Parse current TOML
        config = tomli.loads(current_toml_content)
        
        # Update the files section
        if 'files' not in config:
            config['files'] = {}
            
        config['files']['include'] = include_patterns
        config['files']['exclude'] = exclude_patterns
        
        # Convert back to TOML string
        updated_toml = tomli_w.dumps(config)
        
        return updated_toml
        
    except ImportError:
        logging.error("tomli/tomli_w not available for TOML manipulation")
        return current_toml_content
    except Exception as e:
        logging.error(f"Error syncing patterns with TOML: {e}")
        return current_toml_content

def parse_current_patterns(toml_content: str) -> Tuple[List[str], List[str]]:
    """Parse current include/exclude patterns from TOML content.
    
    Args:
        toml_content: TOML file content
        
    Returns:
        Tuple of (include_patterns, exclude_patterns)
    """
    try:
        import tomli
        
        config = tomli.loads(toml_content)
        include = config.get('files', {}).get('include', [])
        exclude = config.get('files', {}).get('exclude', [])
        
        return include, exclude
        
    except Exception as e:
        logging.error(f"Error parsing patterns from TOML: {e}")
        return [], []

# Note: get_all_children_labels and apply_cascade_selection are no longer needed
# FileExplorer handles directory selection internally - selecting a directory
# automatically includes all its contents when generating patterns

def match_patterns_to_paths(patterns: List[str], root_path: str) -> List[str]:
    """Convert glob patterns to actual file paths for FileExplorer.
    
    Args:
        patterns: List of glob patterns from memory.toml
        root_path: Root path of memex directory
        
    Returns:
        List of absolute file paths that match the patterns
    """
    import fnmatch
    import glob
    
    matched_paths = []
    memex_root = pathlib.Path(root_path)
    host_root = memex_root.parent
    
    try:
        for pattern in patterns:
            # Convert relative pattern to absolute path pattern
            if pattern.startswith('../'):
                # Pattern is relative to host project
                abs_pattern = str(host_root / pattern[3:])
            else:
                # Pattern is relative to memex
                abs_pattern = str(memex_root / pattern)
            
            # Use pathlib glob to find matching files
            if '*' in abs_pattern or '?' in abs_pattern:
                # It's a glob pattern
                base_path = pathlib.Path(abs_pattern.split('*')[0].rstrip('/'))
                if base_path.exists():
                    pattern_suffix = abs_pattern[len(str(base_path)):].lstrip('/')
                    matches = [str(p) for p in base_path.glob(pattern_suffix)]
                else:
                    matches = []
            else:
                # It's a direct path
                matches = [abs_pattern] if os.path.exists(abs_pattern) else []
            
            # Add all matches
            for match in matches:
                if match not in matched_paths:
                    matched_paths.append(match)
                    
            # For directory patterns ending with /**/*, also add the directory itself
            if pattern.endswith('/**/*'):
                dir_pattern = abs_pattern[:-6]  # Remove /**/* suffix
                if os.path.exists(dir_pattern) and os.path.isdir(dir_pattern):
                    if dir_pattern not in matched_paths:
                        matched_paths.append(dir_pattern)
                        
    except Exception as e:
        logging.error(f"Error matching patterns to paths: {e}")
        
    return matched_paths