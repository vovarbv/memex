#!/usr/bin/env python
"""Check which files were indexed and verify exclusion patterns are working."""
import sys
import os
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt="%Y-%m-%d %H:%M:%S"
)

def check_indexed_files():
    """Check which files are indexed and verify exclusion patterns."""
    # Import with proper error handling for different execution contexts
    try:
        # When run as a module within the package
        from .memory_utils import load_cfg, load_index, ROOT
        from .index_codebase import find_files_to_index
        try:
            from .thread_safe_store import VectorStoreMetadataReadError
        except ImportError:
            VectorStoreMetadataReadError = Exception
    except ImportError:
        try:
            # When run as a script directly
            from memory_utils import load_cfg, load_index, ROOT
            from index_codebase import find_files_to_index
            VectorStoreMetadataReadError = Exception
        except ImportError:
            # Last resort: absolute import
            from memex.scripts.memory_utils import load_cfg, load_index, ROOT
            from memex.scripts.index_codebase import find_files_to_index
            VectorStoreMetadataReadError = Exception

    # First, let's see what files the indexer found
    cfg = load_cfg()
    files_to_index = find_files_to_index(cfg, ROOT)

    print(f'Files found by indexer: {len(files_to_index)}')
    print('\nSample of files to be indexed:')
    for f in sorted(files_to_index)[:10]:
        print(f'  {f}')

    # Check if any problematic files are included
    problematic = []
    for f in files_to_index:
        path_str = str(f).replace('\\', '/')
        if 'memex/' in path_str or '.idea/' in path_str or '.cursor/vecstore/' in path_str:
            problematic.append(f)

    if problematic:
        print(f'\n❌ Found {len(problematic)} files that should be excluded:')
        for f in problematic[:10]:
            print(f'  {f}')
    else:
        print('\n✅ No problematic files found in the indexing list!')

    # Now check what's actually in the vector store
    print('\n' + '='*60)
    print('Checking vector store contents...')

    # load_index returns a tuple (index, meta)
    index, meta = load_index()

    # Get all code chunks
    code_chunks = []
    if index is not None and meta is not None:
        # Get the reverse map from the metadata
        faiss_to_custom_map = meta.get("_faiss_id_to_custom_id_map_", {})
        
        for faiss_id in range(index.ntotal):
            try:
                # Get custom ID from the map
                custom_id = faiss_to_custom_map.get(faiss_id)
                if custom_id:
                    # Get metadata for this custom ID
                    item_meta = meta.get(custom_id)
                    if item_meta and item_meta.get('type') == 'code':
                        file_path = item_meta.get('metadata', {}).get('file')
                        if file_path:
                            code_chunks.append(file_path)
            except Exception:
                pass

    # Count unique files
    unique_files = set(code_chunks)
    print(f'\nTotal indexed files: {len(unique_files)}')
    print(f'Total code chunks: {len(code_chunks)}')

    # Check for problematic files in vector store
    problematic_patterns = [
        'memex/',
        '.idea/',
        '.cursor/vecstore/',
        'venv/',
        '__pycache__/'
    ]

    print('\nChecking for files that should be excluded:')
    found_problems = False
    for file in sorted(unique_files):
        for pattern in problematic_patterns:
            if pattern in file:
                print(f'  ❌ {file} (should be excluded by {pattern})')
                found_problems = True
                break

    if not found_problems:
        print('  ✅ No excluded files found in the vector store!')
    else:
        print(f'\nFound {len(unique_files)} files in the vector store')

def main(argv=None):
    """Main entry point for the script."""
    try:
        check_indexed_files()
        return 0
    except Exception as e:
        logging.error(f"Error checking indexed files: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())