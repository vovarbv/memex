#!/usr/bin/env python
"""
Сканирует проект и генерирует/обновляет memory.toml (особенно секцию files.include).
Создает пустой docs/TASKS.yaml и docs/PREFERENCES.yaml если их нет.
"""
import os
import pathlib
import collections
import logging
import sys
import fnmatch
import tomli # For reading existing toml
import tomli_w # For writing toml

# ───────────────────────────────────────── Logging Setup ────
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# ───────────────────────────────────────── Constants ────
ROOT = pathlib.Path(__file__).resolve().parents[1]
CFG_PATH = ROOT / "memory.toml"
TASKS_YAML_PATH = ROOT / "docs" / "TASKS.yaml" # Default, but actual path from config
PREFERENCES_YAML_PATH = ROOT / "docs" / "PREFERENCES.yaml" # Default

# Common patterns to exclude
COMMON_EXCLUDE_PATTERNS = [
    "**/__pycache__/**",
    "**/node_modules/**",
    "**/.git/**",
    "**/build/**",
    "**/.venv/**",
    "**/.vscode/**",
    "**/.idea/**",
    "**/.cursor/**", # Exclude the .cursor directory itself
    "**/dist/**",
    "**/*.egg-info/**",
]

# For directories, we extract just the directory name part for direct comparison
# Note: Some patterns like "**/.git/**" match both directories and files
DIR_EXCLUDE_PATTERNS = set(
    pattern.strip("*").split("/")[-2] 
    for pattern in COMMON_EXCLUDE_PATTERNS
    if "/" in pattern and not pattern.endswith("/*")
)

# Default config structure if memory.toml doesn't exist or is minimal
DEFAULT_BOOTSTRAP_CFG_STRUCTURE = {
    "files": {"include": ["src/**/*.*"], "exclude": COMMON_EXCLUDE_PATTERNS},
    "prompt": {"max_tokens": 10_000, "top_k_tasks": 5, "top_k_context_items": 5},
    "tasks": {"file": "docs/TASKS.yaml"},
    "preferences": {"file": "docs/PREFERENCES.yaml"},
}

def should_exclude_dir(dir_path):
    """
    Check if a directory should be excluded based on exclusion patterns.
    This is used to prune directories early during os.walk() traversal.
    """
    # Get the relative path from ROOT for pattern matching
    rel_path = os.path.relpath(dir_path, ROOT)
    
    # Skip hidden directories
    dir_name = os.path.basename(dir_path)
    if dir_name.startswith('.') and dir_name != '.':
        return True
    
    # Check if any common directory pattern matches
    if os.path.basename(dir_path) in DIR_EXCLUDE_PATTERNS:
        return True
    
    # Check each pattern against this directory path
    for pattern in COMMON_EXCLUDE_PATTERNS:
        # Convert the glob pattern to be relative from ROOT
        if fnmatch.fnmatch(rel_path, pattern.replace("**/", "").replace("/**", "")):
            return True
    
    return False

def should_exclude_file(file_path):
    """
    Check if a file should be excluded based on exclusion patterns.
    """
    # Get the relative path from ROOT for pattern matching
    rel_path = os.path.relpath(file_path, ROOT)
    
    # Skip hidden files
    file_name = os.path.basename(file_path)
    if file_name.startswith('.'):
        return True
    
    # Check each pattern against this file path
    for pattern in COMMON_EXCLUDE_PATTERNS:
        if fnmatch.fnmatch(rel_path, pattern):
            return True
    
    return False

def main():
    # 1. Scan project for common file types to suggest for `files.include`
    stats = collections.Counter()
    
    logging.info(f"Scanning project root: {ROOT}")
    
    scanned_files_count = 0
    excluded_files_count = 0
    excluded_dirs_count = 0
    
    # Use os.walk with topdown=True to allow modifying dirs list in-place
    for root_dir, dirs, files in os.walk(str(ROOT), topdown=True):
        # Skip excluded directories - modify dirs in-place to skip traversal
        # Use slice assignment to modify the dirs list in-place
        i = 0
        while i < len(dirs):
            dir_path = os.path.join(root_dir, dirs[i])
            if should_exclude_dir(dir_path):
                excluded_dirs_count += 1
                dirs.pop(i)  # Remove this directory from traversal
            else:
                i += 1
        
        # Process files
        for file_name in files:
            scanned_files_count += 1
            file_path = os.path.join(root_dir, file_name)
            
            try:
                if should_exclude_file(file_path):
                    excluded_files_count += 1
                    continue
                
                # Get file extension and update stats
                if os.path.isfile(file_path):
                    _, ext = os.path.splitext(file_path)
                    ext = ext.lstrip('.').lower()
                    if ext:
                        stats[ext] += 1
            except Exception as e:
                logging.warning(f"Could not process path {file_path}: {e}")
    
    logging.info(f"Total files scanned: {scanned_files_count}. Files excluded: {excluded_files_count}. Directories excluded: {excluded_dirs_count}")
    logging.info(f"File extension counts: {stats}")

    suggested_includes = []
    # Prioritize common code extensions if found
    priority_code_extensions = {"py", "js", "ts", "tsx", "java", "go", "rb", "php", "cs", "c", "cpp", "h", "hpp", "swift", "kt", "rs", "scala", "md"}

    for ext, count in stats.most_common(): # Get all found extensions
        if ext in priority_code_extensions:
            suggested_includes.append(f"**/*.{ext}")

    # If no priority code extensions found, take top 3 generic ones, avoiding binary/uncommon ones
    if not suggested_includes:
        generic_extensions = [ext for ext, count in stats.most_common(5) if ext not in {"exe", "dll", "so", "o", "a", "lock", "log"}] # Add more non-textual extensions
        for ext in generic_extensions[:3]:
             suggested_includes.append(f"**/*.{ext}")

    if not suggested_includes: # Fallback if still nothing
        suggested_includes = ["src/**/*.*", "docs/**/*.md"] # A very generic default
        logging.warning("No common file types detected or too few files. Using generic include patterns.")

    logging.info(f"Suggested include patterns: {suggested_includes}")

    # 2. Prepare new/updated config
    # Start with default structure
    current_cfg_data = {}
    if CFG_PATH.exists():
        try:
            with CFG_PATH.open("rb") as f:
                current_cfg_data = tomli.load(f)
            logging.info(f"Loaded existing configuration from {CFG_PATH}.")
        except Exception as e:
            logging.error(f"Failed to load existing {CFG_PATH}: {e}. Will create a new one.")
            current_cfg_data = {} # Reset if malformed

    # Create the config to be written
    # Start with a deep copy of the default structure to ensure all keys are present
    final_cfg = {
        k: v.copy() if isinstance(v, dict) else v
        for k,v in DEFAULT_BOOTSTRAP_CFG_STRUCTURE.items()
    }

    # Merge existing config over defaults, so user's custom sections are preserved
    for key, value in current_cfg_data.items():
        if key in final_cfg and isinstance(final_cfg[key], dict) and isinstance(value, dict):
            final_cfg[key].update(value)
        else:
            final_cfg[key] = value

    # Specifically update/set the files section based on scan & defaults
    final_cfg["files"]["include"] = suggested_includes
    final_cfg["files"]["exclude"] = DEFAULT_BOOTSTRAP_CFG_STRUCTURE["files"]["exclude"] # Always reset excludes to common list

    # 3. Write memory.toml
    try:
        CFG_PATH.write_text(tomli_w.dumps(final_cfg, multiline_strings=True), encoding="utf-8")
        print(f"✅ memory.toml {'updated' if current_cfg_data else 'generated'} at {CFG_PATH}")
    except Exception as e:
        logging.critical(f"Failed to write {CFG_PATH}: {e}")
        print(f"❌ Error writing {CFG_PATH}. Check logs.")
        sys.exit(1)

    # 4. Ensure TASKS.yaml and PREFERENCES.yaml exist
    # Paths for these files should ideally come from the `final_cfg` just written.
    tasks_file_rel_path = final_cfg.get("tasks", {}).get("file", "docs/TASKS.yaml")
    prefs_file_rel_path = final_cfg.get("preferences", {}).get("file", "docs/PREFERENCES.yaml")

    actual_tasks_path = ROOT / tasks_file_rel_path
    actual_prefs_path = ROOT / prefs_file_rel_path

    for doc_path, content_if_new in [
        (actual_tasks_path, "[]\n# Add your tasks here in YAML format\n# - id: 1\n#   title: \"My First Task\"\n#   status: \"todo\"\n#   progress: 0\n#   plan:\n#     - \"Step 1\"\n#     - \"Step 2\"\n#   done_steps: []  # Steps that have been completed\n"),
        (actual_prefs_path, "# Add your project preferences here in YAML format\n# example_preference: \"value\"\n")
    ]:
        try:
            doc_path.parent.mkdir(parents=True, exist_ok=True)
            if not doc_path.exists():
                doc_path.write_text(content_if_new, encoding="utf-8")
                print(f"✅ Empty {doc_path.name} created at {doc_path}")
            else:
                logging.info(f"{doc_path.name} already exists at {doc_path}, not overwritten.")
        except Exception as e:
            logging.error(f"Failed to create or check {doc_path.name}: {e}")
            print(f"⚠️ Could not ensure {doc_path.name} exists. Check logs.")

    print("Bootstrap complete. Please review memory.toml for accuracy.")

if __name__ == "__main__":
    main()