#!/usr/bin/env python
"""
Index codebase files into the vector store for semantic search.

This script indexes code, markdown, and other text files according to patterns
in memory.toml. It chunks files into semantically meaningful pieces and stores
them in the FAISS vector store for retrieval.
"""
import os
import sys
import pathlib
import fnmatch
import logging
import argparse
from typing import List, Dict, Any, Optional, Set

# Use proper package imports
try:
    # When run as a module within the package
    from .memory_utils import load_cfg, index_code_chunk, delete_code_chunks, ROOT
    from .code_indexer_utils import get_chunker_for_file
except ImportError:
    # When run as a script directly
    try:
        from memory_utils import load_cfg, index_code_chunk, delete_code_chunks, ROOT
        from code_indexer_utils import get_chunker_for_file
    except ImportError:
        # Last resort: absolute import
        try:
            from memex.scripts.memory_utils import load_cfg, index_code_chunk, delete_code_chunks, ROOT
            from memex.scripts.code_indexer_utils import get_chunker_for_file
        except ImportError as e:
            logging.error(f"Failed to import required modules: {e}")
            sys.exit(1)

# ───────────────────────────────────────── Logging Setup ────
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt="%Y-%m-%d %H:%M:%S"
)

def _matches_pattern(path: str, pattern: str) -> bool:
    """
    Check if a file path matches a glob pattern, properly handling ** wildcards.
    
    Args:
        path: File path to check (relative to root)
        pattern: Glob pattern that may contain ** wildcards
        
    Returns:
        True if the path matches the pattern
    """
    import re
    
    # Normalize paths for comparison
    path = path.replace('\\', '/')
    pattern = pattern.replace('\\', '/')
    
    # Debug logging for specific patterns
    debug_patterns = ['memex/**/*', '.idea/**/*', '.cursor/vecstore/**/*']
    if pattern in debug_patterns and any(p in path for p in ['memex/', '.idea/', '.cursor/']):
        logging.debug(f"Checking: path='{path}' against pattern='{pattern}'")
    
    # For exact match patterns (no wildcards)
    if '*' not in pattern:
        return path == pattern
    
    # Handle ** patterns
    if '**' in pattern:
        # For patterns like "dir/**/*" - check if path starts with "dir/"
        if pattern.endswith('/**/*'):
            prefix = pattern[:-5]  # Remove /**/*
            result = path.startswith(prefix + '/')
            if pattern in debug_patterns and any(p in path for p in ['memex/', '.idea/', '.cursor/']):
                logging.debug(f"  Prefix match: '{prefix}/' -> {result}")
            return result
        
        # For other ** patterns, convert to regex
        regex_pattern = re.escape(pattern)
        regex_pattern = regex_pattern.replace(r'\*\*', '.*')  # ** matches any path
        regex_pattern = regex_pattern.replace(r'\*', '[^/]*')  # * matches any filename part
        regex_pattern = '^' + regex_pattern + '$'
        
        result = bool(re.match(regex_pattern, path))
        if pattern in debug_patterns and any(p in path for p in ['memex/', '.idea/', '.cursor/']):
            logging.debug(f"  Regex: '{regex_pattern}' -> {result}")
        return result
    else:
        # For simple patterns without **, use fnmatch
        return fnmatch.fnmatch(path, pattern)

def find_files_to_index(cfg: Dict[str, Any], root_dir: pathlib.Path) -> List[pathlib.Path]:
    """
    Find files to index based on include and exclude patterns from config.
    
    Args:
        cfg: Configuration dictionary from memory.toml
        root_dir: Root directory to search from
        
    Returns:
        List of pathlib.Path objects for files to index
    """
    include_patterns = cfg.get("files", {}).get("include", ["**/*.py", "**/*.md"])
    exclude_patterns = cfg.get("files", {}).get("exclude", ["**/node_modules/**", "**/.git/**", "**/__pycache__/**"])
    
    # Ensure patterns are in a list
    if isinstance(include_patterns, str):
        include_patterns = [include_patterns]
    if isinstance(exclude_patterns, str):
        exclude_patterns = [exclude_patterns]
    
    # Resolve paths that start with "../" to be relative to root_dir's parent
    resolved_include_patterns = []
    for pattern in include_patterns:
        if pattern.startswith("../"):
            # Handle the "../" prefix by using the parent of root_dir
            # Remove "../" prefix and use it as a pattern from the parent directory
            resolved_pattern = pattern[3:]
            resolved_include_patterns.append(resolved_pattern)
        else:
            resolved_include_patterns.append(pattern)
    
    resolved_exclude_patterns = []
    for pattern in exclude_patterns:
        if pattern.startswith("../"):
            # Handle the "../" prefix by using the parent of root_dir
            # Remove "../" prefix and use it as a pattern from the parent directory
            resolved_pattern = pattern[3:]
            resolved_exclude_patterns.append(resolved_pattern)
        else:
            resolved_exclude_patterns.append(pattern)
    
    logging.info(f"Finding files with include patterns: {resolved_include_patterns}")
    logging.info(f"Excluding files with patterns: {resolved_exclude_patterns}")
    
    # If any pattern starts with '../', use the parent directory as the search root
    search_root = root_dir.parent if any(p.startswith("../") for p in include_patterns) else root_dir
    logging.info(f"Search root directory: {search_root}")
    
    all_files = []
    
    # Walk the directory tree
    for root, dirs, files in os.walk(search_root):
        rel_root = pathlib.Path(root).relative_to(search_root)
        
        # Skip directories that match exclude patterns
        dirs_to_remove = []
        for i, dir_name in enumerate(dirs):
            rel_dir_path = str(rel_root / dir_name)
            if any(_matches_pattern(rel_dir_path, pat) for pat in resolved_exclude_patterns):
                dirs_to_remove.append(i)
        
        # Remove excluded directories in reverse order to avoid index shifting
        for i in sorted(dirs_to_remove, reverse=True):
            del dirs[i]
        
        # Check each file against include and exclude patterns
        for file_name in files:
            rel_file_path = str(rel_root / file_name)
            
            # Debug: log problematic paths
            if any(p in rel_file_path for p in ['memex/', '.idea/', '.cursor/']):
                logging.debug(f"Processing file: {rel_file_path}")
            
            # Skip files that match exclude patterns
            if any(_matches_pattern(rel_file_path, pat) for pat in resolved_exclude_patterns):
                if any(p in rel_file_path for p in ['memex/', '.idea/', '.cursor/']):
                    logging.debug(f"  -> Excluded!")
                continue
            
            # Add files that match include patterns
            if any(_matches_pattern(rel_file_path, pat) for pat in resolved_include_patterns):
                all_files.append(search_root / rel_file_path)
                if any(p in rel_file_path for p in ['memex/', '.idea/', '.cursor/']):
                    logging.debug(f"  -> Included!")
    
    logging.info(f"Found {len(all_files)} files to index")
    return all_files

def index_file(file_path: pathlib.Path, cfg: Dict[str, Any]) -> int:
    """
    Index a single file by chunking it and adding to vector store.
    
    Args:
        file_path: Path to the file to index
        cfg: Configuration dictionary
        
    Returns:
        Number of chunks indexed
    """
    min_chunk_lines = cfg.get("files", {}).get("min_chunk_lines", 5)
    max_chunk_lines = cfg.get("files", {}).get("max_chunk_lines", 100)
    
    # Get the appropriate chunker for this file type
    chunker = get_chunker_for_file(str(file_path))
    if not chunker:
        logging.warning(f"No chunker available for file: {file_path}")
        return 0
    
    # Get chunks from the file
    chunks = chunker(str(file_path), min_lines=min_chunk_lines, max_lines=max_chunk_lines)
    
    if not chunks:
        logging.warning(f"No chunks generated for file: {file_path}")
        return 0
    
    # Index each chunk
    successful_chunks = 0
    for chunk in chunks:
        chunk_id = chunk.get("id")
        content = chunk.get("content", "")
        
        if not content or not chunk_id:
            logging.warning(f"Skipping invalid chunk from {file_path}: missing ID or content")
            continue
        
        result = index_code_chunk(chunk_id, content, chunk)
        if result:
            successful_chunks += 1
    
    logging.info(f"Indexed {successful_chunks}/{len(chunks)} chunks from {file_path}")
    return successful_chunks

def index_codebase(reindex: bool = False) -> int:
    """
    Index the entire codebase according to config patterns.
    
    Args:
        reindex: If True, delete all existing code chunks before indexing
        
    Returns:
        Total number of chunks indexed
    """
    cfg = load_cfg()
    
    if reindex:
        logging.info("Deleting existing code chunks...")
        success_count, failure_count, total_checked = delete_code_chunks()
        logging.info(f"Deleted {success_count} existing code chunks (failed: {failure_count}, checked: {total_checked})")
    
    # Find files to index
    files_to_index = find_files_to_index(cfg, ROOT)
    
    # Track indexed files and chunks
    total_chunks = 0
    indexed_files = 0
    skipped_files = 0
    
    # Process each file
    for file_path in files_to_index:
        try:
            chunks_added = index_file(file_path, cfg)
            total_chunks += chunks_added
            
            if chunks_added > 0:
                indexed_files += 1
            else:
                skipped_files += 1
        except Exception as e:
            logging.error(f"Error indexing file {file_path}: {e}")
            skipped_files += 1
    
    logging.info(f"Indexing complete: {indexed_files} files indexed, {skipped_files} files skipped, {total_chunks} total chunks")
    return total_chunks

def main(argv=None):
    """
    Main entry point for the script.
    
    Args:
        argv: Optional list of command-line arguments (for programmatic use)
    
    Returns:
        Integer status code or dictionary with results
    """
    parser = argparse.ArgumentParser(description="Index codebase files into vector store")
    parser.add_argument("--reindex", action="store_true", help="Delete existing code chunks before indexing")
    parser.add_argument("--file", help="Index a single file instead of the entire codebase")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    
    args = parser.parse_args(argv)
    
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    try:
        if args.file:
            file_path = pathlib.Path(args.file)
            if not file_path.exists():
                logging.error(f"File not found: {args.file}")
                return 1
            
            if args.reindex:
                logging.info("Deleting existing code chunks...")
                delete_code_chunks()
            
            cfg = load_cfg()
            chunks_added = index_file(file_path, cfg)
            logging.info(f"Added {chunks_added} chunks from {file_path}")
            
            # Return result as dictionary for UI integration
            return {
                "processed_files": 1,
                "added_chunks": chunks_added,
                "deleted_chunks": 0 if not args.reindex else 1,
                "failed_chunks": 0
            }
        else:
            total_chunks = index_codebase(reindex=args.reindex)
            
            # Return result as dictionary for UI integration
            return {
                "processed_files": 0,  # We don't track this currently
                "added_chunks": total_chunks,
                "deleted_chunks": 0 if not args.reindex else 1,
                "failed_chunks": 0
            }
    except Exception as e:
        logging.error(f"Error during indexing: {e}")
        return {"error": str(e)}

if __name__ == "__main__":
    sys.exit(main()) 