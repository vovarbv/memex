"""
Common functions: reading configuration, working with Faiss, embedding.
Single-source to avoid duplication in other scripts.
"""
from __future__ import annotations
import os
import json
import pathlib
import functools
import logging
import typing as _t
import threading
import time

import numpy as np
import faiss
from sentence_transformers import SentenceTransformer
import tomli
import yaml

# ───────────────────────────────────────── Logging Setup ────
# Basic logging for library functions, application scripts can set their own handlers/format.
# logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(module)s - %(message)s')
# Decided to let executable scripts set their own basicConfig.

# ───────────────────────────────────────── Constants & Config ────
ROOT = pathlib.Path(__file__).resolve().parents[1]
CFG_PATH = ROOT / "memory.toml"

# These paths will be dynamically constructed based on the configuration
# They are initially set to default values
_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

DEFAULT_CFG = {
    "files": {
        "include": ["src/**/*.py"], 
        "exclude": [
            # Virtual environments
            "venv/**/*", ".venv/**/*", "env/**/*", ".env/**/*", "virtualenv/**/*",
            # Python caches
            "__pycache__/**/*", "**/__pycache__/**/*",
            ".pytest_cache/**/*", "**/.pytest_cache/**/*",
            # Package directories
            "site-packages/**/*", "Lib/site-packages/**/*", "lib/python*/site-packages/**/*",
            # Node modules
            "node_modules/**/*", "**/node_modules/**/*",
            # Vendor directories
            "vendor/**/*", "vendors/**/*",
            # IDE directories
            ".idea/**/*", ".vscode/**/*", ".cursor/**/*",
            # Build artifacts
            "build/**/*", "dist/**/*", "target/**/*", "out/**/*", "bin/**/*",
            "**/*.egg-info/**/*",
            # Version control
            ".git/**/*",
            # Temporary files
            "tmp/**/*", "temp/**/*", "logs/**/*",
            "**/*.log", "**/*.tmp",
            # OS-specific files
            ".DS_Store", "**/Thumbs.db", "desktop.ini",
            # Common large data directories
            "data/**/*", "datasets/**/*", "models/**/*",
            # Coverage reports
            "htmlcov/**/*", ".coverage", "coverage.xml",
            # Jupyter checkpoints
            ".ipynb_checkpoints/**/*", "**/.ipynb_checkpoints/**/*"
        ]
    },
    "prompt": {"max_tokens": 10_000, "top_k_tasks": 5, "top_k_snippets": 5},
    "tasks": {"file": "docs/TASKS.yaml", "tag_prefix": "- "}, # tag_prefix might be legacy from MD
    "preferences": {"file": "docs/PREFERENCES.yaml"},
    "system": {
        # Path to the .cursor directory, relative to memex root.
        # Default ".." means .cursor will be in parent of memex_root.
        "cursor_output_dir_relative_to_memex_root": "..",
        # Path to TASKS.yaml, relative to memex root.
        "tasks_file_relative_to_memex_root": "docs/TASKS.yaml",
        # Path to PREFERENCES.yaml, relative to memex root.
        "preferences_file_relative_to_memex_root": "docs/PREFERENCES.yaml"
    }
}

DEFAULT_BOOTSTRAP_CFG_STRUCTURE = DEFAULT_CFG.copy()

def get_cursor_output_base_path(cfg: Optional[Dict[str, Any]] = None) -> Path:
    """Get the base path for .cursor directory based on configuration.
    
    Args:
        cfg: Optional configuration dictionary. If None, loads from memory.toml.
        
    Returns:
        Path to the base directory where .cursor will be created.
    """
    if cfg is None:
        cfg = load_cfg()
    cursor_rel_path = cfg.get("system", {}).get("cursor_output_dir_relative_to_memex_root", "..")
    return ROOT / cursor_rel_path

def get_vec_dir(cfg: Optional[Dict[str, Any]] = None) -> Path:
    """Get the vector store directory path based on configuration.
    
    Args:
        cfg: Optional configuration dictionary. If None, loads from memory.toml.
        
    Returns:
        Path to the vector store directory (.cursor/vecstore).
    """
    cursor_base = get_cursor_output_base_path(cfg)
    return cursor_base / ".cursor" / "vecstore"

def get_index_path(cfg: Optional[Dict[str, Any]] = None) -> Path:
    """Get the FAISS index file path based on configuration.
    
    Args:
        cfg: Optional configuration dictionary. If None, loads from memory.toml.
        
    Returns:
        Path to the FAISS index file (index.faiss).
    """
    return get_vec_dir(cfg) / "index.faiss"

def get_meta_path(cfg: Optional[Dict[str, Any]] = None) -> Path:
    """Get the metadata file path based on configuration.
    
    Args:
        cfg: Optional configuration dictionary. If None, loads from memory.toml.
        
    Returns:
        Path to the metadata JSON file.
    """
    return get_vec_dir(cfg) / "metadata.json"

def get_tasks_file_path(cfg=None):
    """Get the path to the tasks file."""
    if cfg is None:
        cfg = load_cfg()
    
    # First try the new path in system section
    tasks_file_rel_path = cfg.get("system", {}).get(
        "tasks_file_relative_to_memex_root",
        # Fall back to legacy path in tasks section
        cfg.get("tasks", {}).get("file", "docs/TASKS.yaml")
    )
    
    # Return the absolute path
    return ROOT / tasks_file_rel_path

def load_cfg() -> dict:
    if not CFG_PATH.exists():
        logging.warning(f"Config file {CFG_PATH} not found, using default configuration.")
        return DEFAULT_CFG
    try:
        with CFG_PATH.open("rb") as f:
            return tomli.load(f)
    except tomli.TOMLDecodeError as e:
        logging.error(f"Error parsing {CFG_PATH}: {e}. Using default configuration.")
        return DEFAULT_CFG
    except IOError as e:
        logging.error(f"Error reading {CFG_PATH}: {e}. Using default configuration.")
        return DEFAULT_CFG

# ───────────────────────────────────────── Vector Store ────
# ───────────────────────────────────────── IndexManager ────

# Import the memory-bounded IndexManager with proper error handling
try:
    # Try relative import first (when imported as part of package)
    from .memory_bounded_index_manager import MemoryBoundedIndexManager as IndexManager
    logging.info("Using MemoryBoundedIndexManager for FAISS index management")
except ImportError:
    try:
        # Try absolute import (when script is run directly)
        from memory_bounded_index_manager import MemoryBoundedIndexManager as IndexManager
        logging.info("Using MemoryBoundedIndexManager for FAISS index management")
    except ImportError as e:
        logging.error(f"Failed to import MemoryBoundedIndexManager: {e}")
        logging.error("Falling back to basic IndexManager implementation")
    
    # Minimal fallback implementation to prevent complete failure
    class IndexManager:
        """Basic fallback IndexManager without memory bounds"""
        _instance = None
        _lock = threading.RLock()
        
        def __new__(cls):
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialize()
                return cls._instance
        
        def _initialize(self):
            """Initialize the basic index manager"""
            self.index = None
            self.meta = None
            self.last_load_time = 0
            self.load_count = 0
            self.hit_count = 0
            
        def get_index_and_meta(self, force_reload=False):
            """Get the FAISS index and metadata"""
            with self._lock:
                if self.index is None or self.meta is None or force_reload:
                    self.load_count += 1
                    self.index, self.meta = _load_index_internal()
                    self.last_load_time = time.time()
                    logging.info(f"FAISS index loaded (fallback mode, count: {self.load_count})")
                else:
                    self.hit_count += 1
                return self.index, self.meta
                
        def invalidate(self):
            """Invalidate the cached index and metadata"""
            self.index = None
            self.meta = None
            logging.info("FAISS index cache invalidated (fallback mode)")
            
        def get_stats(self):
            """Get basic statistics"""
            return {
                "load_count": self.load_count,
                "hit_count": self.hit_count,
                "loaded": self.index is not None and self.meta is not None,
                "last_load_time": self.last_load_time,
                "mode": "fallback"
            }

# Create a global instance for the module
_index_manager = IndexManager()

@functools.lru_cache
def model() -> SentenceTransformer:
    try:
        return SentenceTransformer(_MODEL_NAME)
    except (OSError, ImportError, RuntimeError) as e:
        logging.error(f"Failed to load SentenceTransformer model '{_MODEL_NAME}': {e}")
        raise
    except Exception as e:
        logging.error(f"Unexpected error loading SentenceTransformer model '{_MODEL_NAME}': {e}")
        raise

def vec_dim() -> int:
    try:
        return model().get_sentence_embedding_dimension()
    except (AttributeError, RuntimeError) as e:
        logging.error(f"Failed to get vector dimension from model: {e}")
        raise
    except Exception as e:
        logging.error(f"Unexpected error getting vector dimension from model: {e}")
        raise

def embed(text: str) -> np.ndarray:
    try:
        return model().encode(text, normalize_embeddings=True).astype("float32")
    except Exception as e:
        logging.error(f"Failed to embed text: {e}")
        # Return a zero vector of appropriate dimension or raise error
        # Returning zero vector might lead to silent failures in search
        raise # Or return np.zeros(vec_dim(), dtype="float32") if that's preferred

def _ensure_store():
    try:
        cfg = load_cfg()
        vec_dir = get_vec_dir(cfg)
        index_path = get_index_path(cfg)
        meta_path = get_meta_path(cfg)
        
        vec_dir.mkdir(parents=True, exist_ok=True)
        current_dim = vec_dim()
        if not index_path.exists():
            logging.info(f"FAISS index not found at {index_path}. Creating new index with dim {current_dim}.")
            # Create an IndexFlatL2 index and wrap it with IndexIDMap
            base_index = faiss.IndexFlatL2(current_dim)
            id_mapped_index = faiss.IndexIDMap(base_index)
            faiss.write_index(id_mapped_index, str(index_path))
            
            # When creating a new index, also ensure metadata is fresh and has the map
            if meta_path.exists():
                try:
                    # Attempt to load existing meta to preserve other data if any
                    meta = json.loads(meta_path.read_text(encoding="utf-8"))
                except json.JSONDecodeError:
                    meta = {} # Corrupted or empty, start fresh
            else: # This else corresponds to `if META_PATH.exists()`
                meta = {}
            # These operations are for the new index case, after meta is initialized
            meta["_custom_to_faiss_id_map_"] = meta.get("_custom_to_faiss_id_map_", {})
            meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

        elif not meta_path.exists(): # Index exists, but no metadata
            logging.info(f"Metadata file not found at {meta_path} but index exists. Creating empty metadata with ID map.")
            meta = {"_custom_to_faiss_id_map_": {}}
            meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        else: # Both exist, check index dimension and ensure map in metadata during load_index
            try:
                temp_index = faiss.read_index(str(index_path))
                if temp_index.d != current_dim:
                    logging.warning(
                        f"Existing FAISS index dimension ({temp_index.d}) "
                        f"differs from model dimension ({current_dim}). "
                        f"Consider re-initializing the store if model changed."
                    )
            except Exception as e:
                logging.warning(f"Could not verify dimension of existing FAISS index: {e}")
            # Ensure map exists in metadata - this will be handled by load_index robustly

    except Exception as e:
        logging.error(f"Failed to ensure vector store directories/files: {e}")
        raise

def _load_index_internal() -> tuple[faiss.Index | None, dict]:
    """Internal function that actually loads the index from disk.
    This is used by the IndexManager and should not be called directly."""
    _ensure_store() # Ensures files exist
    try:
        cfg = load_cfg()
        index_path = get_index_path(cfg)
        meta_path = get_meta_path(cfg)
        
        index = faiss.read_index(str(index_path))
        meta_text = meta_path.read_text(encoding="utf-8")
        meta = json.loads(meta_text)
        
        # Ensure the custom ID to FAISS ID map exists in the loaded metadata
        if "_custom_to_faiss_id_map_" not in meta:
            meta["_custom_to_faiss_id_map_"] = {}
            logging.info("'_custom_to_faiss_id_map_' was missing from metadata.json; initialized in memory.")
        
        # X.2.2: Ensure FAISS IDs in the custom_to_faiss_map are integers
        # And rebuild the _faiss_id_to_custom_id_map_ (reverse map)
        # This ensures the reverse map is always correct in memory after loading.
        custom_to_faiss_map_loaded = meta.get("_custom_to_faiss_id_map_", {})
        faiss_id_to_custom_id_map_rebuilt = {}
        for custom_id, faiss_id_val in custom_to_faiss_map_loaded.items():
            try:
                # Ensure faiss_id_val is a valid integer for the key of the reverse map
                faiss_id_int_key = int(faiss_id_val)
                faiss_id_to_custom_id_map_rebuilt[faiss_id_int_key] = custom_id
            except (ValueError, TypeError):
                logging.warning(f"Skipping invalid FAISS ID '{faiss_id_val}' for custom ID '{custom_id}' during reverse map construction in load_index.")
        
        # Store the rebuilt reverse map in meta
        meta["_faiss_id_to_custom_id_map_"] = faiss_id_to_custom_id_map_rebuilt
        logging.info(f"Rebuilt '_faiss_id_to_custom_id_map_' in memory with {len(faiss_id_to_custom_id_map_rebuilt)} entries.")

        return index, meta
    except FileNotFoundError: # Handles case where _ensure_store might not have created them due to an issue
        logging.error(f"FAISS index or metadata file not found after _ensure_store. Path: {get_index_path()} or {get_meta_path()}")
        return None, {"_custom_to_faiss_id_map_": {}} # Return a valid meta structure
    except json.JSONDecodeError as e:
        logging.error(f"Error decoding metadata.json: {e}. Returning empty metadata with ID map.")
        # Attempt to preserve the index if it's loadable
        try:
            index = faiss.read_index(str(get_index_path()))
        except Exception as index_e:
            logging.error(f"Failed to load FAISS index after metadata decode error: {index_e}")
            index = None
        return index, {"_custom_to_faiss_id_map_": {}}
    except Exception as e:
        logging.error(f"Failed to load FAISS index or metadata: {e}")
        return None, {"_custom_to_faiss_id_map_": {}}

def load_index(force_reload=False) -> tuple[faiss.Index | None, dict]:
    """Load the FAISS index and metadata.
    
    This function now uses the IndexManager to cache the index and prevent
    unnecessary rebuilding of the FAISS ID to custom ID map.
    
    Args:
        force_reload: If True, force reloading the index even if cached
        
    Returns:
        Tuple of (index, meta)
    """
    return _index_manager.get_index_and_meta(force_reload=force_reload)


def save_index(index: faiss.Index, meta: dict):
    """Save FAISS index and metadata to disk.
    
    This function also invalidates the IndexManager cache to ensure
    the next load_index call gets the freshest data.
    
    Args:
        index: FAISS index to save
        meta: Metadata dictionary to save
        
    Returns:
        bool: True if save was successful, False otherwise
    """
    try:
        cfg = load_cfg()
        index_path = get_index_path(cfg)
        meta_path = get_meta_path(cfg)
        
        # Ensure vector store directory exists
        vec_dir = get_vec_dir(cfg)
        vec_dir.mkdir(parents=True, exist_ok=True)
        
        # Write FAISS index
        faiss.write_index(index, str(index_path))
        
        # X.2.3: BEGIN SANITIZATION FOR JSON SERIALIZATION
        # Sanitize _custom_to_faiss_id_map_ to ensure FAISS IDs are Python int
        sanitized_custom_to_faiss_map = {
            custom_id: int(f_id)
            for custom_id, f_id in meta.get("_custom_to_faiss_id_map_", {}).items()
        }
        meta["_custom_to_faiss_id_map_"] = sanitized_custom_to_faiss_map

        # Rebuild _faiss_id_to_custom_id_map_ from the sanitized map
        # This ensures its keys are also Python int - will be rebuilt on load, so no need to save
        sanitized_faiss_to_custom_map = {
            int(f_id): custom_id
            for custom_id, f_id in sanitized_custom_to_faiss_map.items()
        }
        meta["_faiss_id_to_custom_id_map_"] = sanitized_faiss_to_custom_map
        # END SANITIZATION

        # Write metadata
        meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        
        # Invalidate the cache in IndexManager to ensure fresh data on next load
        _index_manager.invalidate()
        
        return True
    except Exception as e:
        logging.error(f"Failed to save FAISS index or metadata: {e}")
        return False

def get_index_manager_stats() -> dict:
    """Get statistics about the IndexManager for debugging"""
    return _index_manager.get_stats()

def check_vector_store_integrity() -> dict:
    """
    Verifies the integrity of the vector store by checking synchronization between
    FAISS index and metadata.json.
    
    This function performs comprehensive checks to identify:
    1. Missing vectors: Custom IDs mapped to FAISS IDs that don't exist in the index
    2. Orphaned metadata: Metadata entries without corresponding FAISS ID mappings
    3. Missing metadata: FAISS IDs mapped to custom IDs that don't have metadata entries
    
    For IndexIDMap indices, a sampling approach is used to efficiently check for missing vectors
    by testing a representative sample of IDs rather than every ID.
    
    Returns:
        dict: A summary of the integrity check with these keys:
            - 'status': 'ok' | 'warning' | 'error'
            - 'issues': List of human-readable issue descriptions
            - 'summary': Dict with counts of items checked and issues found
            - 'details': Detailed information about specific problematic entries
            - 'recommendations': List of suggested fixes based on detected issues
    """
    result = {
        'status': 'ok',  # Default to 'ok', will be updated if issues found
        'issues': [],    # List of issue descriptions
        'summary': {     # Summary counts
            'mapped_vectors_count': 0,
            'faiss_index_size': 0,
            'metadata_entries': 0,
            'missing_metadata_entries': 0,
            'orphaned_metadata_entries': 0,
            'missing_vectors': 0,
            'orphaned_vectors': 0,
        },
        'details': {     # Detailed issue information
            'missing_metadata': [],
            'orphaned_metadata': [],
            'missing_vectors': [],
            'reconstruction_errors': []
        },
        'recommendations': [] # Suggested fixes based on detected issues
    }
    
    try:
        # Load the index and metadata
        index, meta = load_index()
        
        if index is None:
            result['status'] = 'error'
            result['issues'].append("CRITICAL: FAISS index could not be loaded.")
            result['recommendations'].append(
                "The FAISS index file may be corrupted or missing. Check that the file exists at the expected path "
                "and has proper permissions. If the file exists but is corrupted, you may need to recreate the index."
            )
            # Ensure summary still exists and has default keys if an unexpected error occurred early
            if 'summary' not in result or not isinstance(result['summary'], dict):
                result['summary'] = {
                    'mapped_vectors_count': 0, 'faiss_index_size': 0, 'metadata_entries': 0,
                    'missing_metadata_entries': 0, 'orphaned_metadata_entries': 0,
                    'missing_vectors': 0, 'orphaned_vectors': 0,
                }
            else: # Ensure all default keys are present if summary dict exists
                default_summary_keys = {
                    'mapped_vectors_count': 0, 'faiss_index_size': 0, 'metadata_entries': 0,
                    'missing_metadata_entries': 0, 'orphaned_metadata_entries': 0,
                    'missing_vectors': 0, 'orphaned_vectors': 0,
                }
                for k, v_default in default_summary_keys.items():
                    result['summary'].setdefault(k, v_default)
            return result # Cannot proceed if index is None
            
        # Check for dimension mismatch between the index and the current model
        try:
            current_dim = vec_dim()
            if index.d != current_dim:
                result['status'] = 'error'
                result['issues'].append(
                    f"DIMENSION MISMATCH: The FAISS index dimension ({index.d}) differs from "
                    f"the current model dimension ({current_dim}). This will cause embedding failures."
                )
                result['recommendations'].append(
                    "The embedding model has changed since the index was created. You need to rebuild "
                    "the vector store with the current model to ensure compatibility."
                )
                result['summary']['dimension_mismatch'] = True
        except Exception as e:
            logging.warning(f"Could not verify dimension compatibility: {e}")
            result['details']['dimension_check_error'] = str(e)

        custom_to_faiss_map = meta.get("_custom_to_faiss_id_map_", {})
        # Ensure FAISS IDs in map are integers for comparison; they should be from sanitization on save
        # but good for robustness during check if loaded from an older/unsanitized state.
        custom_to_faiss_map = {k: int(v) for k, v in custom_to_faiss_map.items()}

        faiss_ids_in_map = set(custom_to_faiss_map.values())
        custom_ids_in_map = set(custom_to_faiss_map.keys())
        
        result['summary']['mapped_vectors_count'] = len(custom_to_faiss_map)
        result['summary']['faiss_index_size'] = index.ntotal
        
        # Check metadata entries (excluding the map itself)
        metadata_item_keys = {k for k in meta.keys() if k not in ["_custom_to_faiss_id_map_", "_faiss_id_to_custom_id_map_"]}
        result['summary']['metadata_entries'] = len(metadata_item_keys)

        # 1. Check for FAISS IDs in map that are not in the actual FAISS index (Missing Vectors)
        #    This requires testing if the ID actually exists in the index
        if index.ntotal > 0:
            try:
                # Approach for checking if FAISS IDs are actually in the index
                if isinstance(index, faiss.IndexIDMap):
                    # For IndexIDMap, we need to verify if mapped FAISS IDs actually exist in the index
                    # We'll implement a more accurate approach using search and sample testing
                    
                    # Get all FAISS IDs from the map
                    faiss_ids_to_check = list(faiss_ids_in_map)
                    missing_vectors_count = 0
                    verified_ids = set()
                    
                    # APPROACH 1: Sampling-based check
                    # Test a sample of IDs to determine if they exist
                    # This is more efficient than testing all IDs if there are many
                    sample_size = min(100, len(faiss_ids_to_check))  # Limit sample size
                    
                    if sample_size > 0:
                        # Get sample IDs
                        import random
                        sample_ids = random.sample(faiss_ids_to_check, sample_size)
                        
                        for faiss_id in sample_ids:
                            # Get the custom ID for better error reporting
                            custom_id = next((cid for cid, fid in custom_to_faiss_map.items() if int(fid) == faiss_id), None)
                            
                            # Try to verify if the ID exists using search with a dummy vector
                            # This is more reliable than reconstruct which requires sequential IDs
                            try:
                                # Create a dummy query vector with the same dimension as the index
                                dummy_vector = np.zeros((1, index.d), dtype="float32")
                                
                                # Search with the dummy vector and k=index.ntotal to get all vectors
                                # This is inefficient but more reliable than reconstruct for IndexIDMap
                                distances, found_ids = index.search(dummy_vector, index.ntotal)
                                
                                # Convert all found IDs to Python ints for comparison
                                found_ids_set = set(int(id) for id in found_ids[0] if id != -1)
                                
                                # Check if our ID is among the found IDs
                                if int(faiss_id) not in found_ids_set:
                                    missing_vectors_count += 1
                                    result['details']['missing_vectors'].append({
                                        'custom_id': custom_id,
                                        'faiss_id': int(faiss_id),
                                        'found_by': 'search_sampling'
                                    })
                                else:
                                    verified_ids.add(int(faiss_id))
                            except Exception as e:
                                logging.warning(f"Error checking FAISS ID {faiss_id} existence: {e}")
                        
                        # Calculate estimated missing percentage based on the sample
                        if sample_size > 0:
                            missing_pct = (missing_vectors_count / sample_size) * 100
                            
                            # Update the overall missing vectors count with an estimate
                            if missing_pct > 0:
                                # Estimate total missing vectors based on sample percentage
                                estimated_missing = int((missing_pct / 100) * len(faiss_ids_to_check))
                                result['summary']['missing_vectors'] = estimated_missing
                                result['issues'].append(
                                    f"Estimated {estimated_missing} vectors ({missing_pct:.1f}%) are missing from the FAISS index "
                                    f"based on sampling {sample_size} of {len(faiss_ids_to_check)} mapped IDs."
                                )
                                # If significant percentage is missing, mark as error
                                if missing_pct > 10:  # If more than 10% are missing, it's an error
                                    result['status'] = 'error'
                    
                    # APPROACH 2: Direct existence check for each metadata entry
                    # This approach checks each metadata entry's mapped FAISS ID
                    # to determine if it's actually present in the index
                    
                    # For each metadata entry, check if its FAISS ID exists
                    for custom_id in metadata_item_keys:
                        if custom_id in custom_to_faiss_map:
                            faiss_id = int(custom_to_faiss_map[custom_id])
                            
                            # Skip IDs we already verified in the sampling phase
                            if faiss_id in verified_ids:
                                continue
                                
                            # Try direct methods to check if ID exists
                            exists = False
                            
                            # Method 1: Try to reconstruct the vector (may fail if ID is non-sequential)
                            try:
                                # For IndexIDMap, reconstruct() takes *internal* idx, not external ID
                                # So this approach has limitations for IndexIDMap
                                vector = index.reconstruct(faiss_id)
                                exists = True
                            except RuntimeError:
                                # This error is expected if the ID doesn't exist
                                # But it could also occur if the ID is valid but not sequential
                                pass
                            except Exception as e:
                                logging.debug(f"Error during vector reconstruction for ID {faiss_id}: {e}")
                            
                            # If we couldn't verify existence, mark as potentially missing
                            if not exists and faiss_id not in verified_ids:
                                result['details']['missing_vectors'].append({
                                    'custom_id': custom_id,
                                    'faiss_id': faiss_id,
                                    'found_by': 'direct_check'
                                })
                                result['summary']['missing_vectors'] += 1
                                result['issues'].append(
                                    f"Custom ID '{custom_id}' is mapped to FAISS ID {faiss_id} which may not exist in the index."
                                )
                                if result['status'] != 'error':
                                    result['status'] = 'warning'
                
                else: # Not an IndexIDMap (e.g., IndexFlatL2 directly)
                    # For standard indices, IDs are implicitly 0 to ntotal-1
                    present_faiss_ids_in_index = set(range(index.ntotal))
                    
                    for custom_id in metadata_item_keys:
                        if custom_id not in custom_ids_in_map:
                            result['status'] = 'warning'
                            result['issues'].append(f"Metadata for '{custom_id}' exists but no FAISS ID mapping.")
                            result['summary']['orphaned_metadata_entries'] += 1
                            result['details']['orphaned_metadata'].append(custom_id)
                        else:
                            # Has mapping, check if corresponding vector is in FAISS
                            faiss_id = custom_to_faiss_map[custom_id]
                            if faiss_id not in present_faiss_ids_in_index: # For non-IndexIDMap
                                result['status'] = 'error' # Critical if mapped but not in index
                                result['issues'].append(f"Vector for '{custom_id}' (FAISS ID {faiss_id}) is mapped but missing from FAISS index.")
                                result['summary']['missing_vectors'] += 1
                                result['details']['missing_vectors'].append(custom_id)
                
                # Check for FAISS IDs in the map that are out of bounds for index.ntotal
                # This applies more directly if we weren't using IndexIDMap, or if index.ntotal is the source of truth for max ID.
                # With IndexIDMap, an ID could be large but valid if index.ntotal is small (e.g. after deletions).
                # However, if a mapped ID is >= index.ntotal, it *could* indicate an issue if ntotal is supposed to reflect the count of unique IDs.
                # This is less reliable for IndexIDMap.

            except Exception as e:
                result['status'] = 'error'
                result['issues'].append(f"Error during FAISS index analysis: {str(e)}")
                result['details']['reconstruction_errors'].append(str(e))
        
        # 2. Check for metadata entries that are not in the custom_to_faiss_map (Orphaned Metadata)
        for custom_id in metadata_item_keys:
            if custom_id not in custom_ids_in_map:
                # This was partially covered above, but ensure it's caught if the FAISS analysis part was skipped/failed
                if "Metadata for '{custom_id}' exists but no FAISS ID mapping." not in result['issues']:
                    result['status'] = 'warning'
                    result['issues'].append(f"Metadata for '{custom_id}' exists but no FAISS ID mapping.")
                    result['summary']['orphaned_metadata_entries'] += 1
                    result['details']['orphaned_metadata'].append(custom_id)

        # 3. Check for custom_ids in the map that do not have corresponding metadata entries (Missing Metadata / Orphaned Map Entry)
        for custom_id in custom_ids_in_map:
            if custom_id not in metadata_item_keys:
                # Check if metadata might exist under the FAISS ID key (old data format)
                faiss_id_for_custom_entry = custom_to_faiss_map.get(custom_id)
                if faiss_id_for_custom_entry is not None and str(faiss_id_for_custom_entry) in metadata_item_keys:
                    result['status'] = 'error'  # This is a critical data format error
                    result['issues'].append(
                        f"CRITICAL MISMATCH: Metadata for custom ID '{custom_id}' is keyed by its FAISS ID '{str(faiss_id_for_custom_entry)}' instead of its custom ID. "
                        "This indicates an old data format. Run migration script or re-index."
                    )
                    result['details'].setdefault('incorrectly_keyed_metadata', []).append({
                        'custom_id': custom_id,
                        'expected_key': custom_id,
                        'found_key': str(faiss_id_for_custom_entry)
                    })
                    result['summary'].setdefault('incorrectly_keyed_items_count', 0)
                    result['summary']['incorrectly_keyed_items_count'] += 1
                else:
                    # Original "Missing Metadata" issue
                    result['status'] = 'warning'
                    result['issues'].append(f"FAISS ID mapping for '{custom_id}' exists but no metadata entry found under custom ID or FAISS ID key.")
                    result['summary']['missing_metadata_entries'] += 1
                    result['details']['missing_metadata'].append(custom_id)
        
        # Update status based on issues found and generate appropriate recommendations
        if result['summary']['missing_vectors'] > 0:
            result['status'] = 'error'
            percentage_missing = (result['summary']['missing_vectors'] / result['summary']['mapped_vectors_count']) * 100 if result['summary']['mapped_vectors_count'] > 0 else 0
            
            # Add detailed message about missing vectors
            result['issues'].append(
                f"Found {result['summary']['missing_vectors']} missing vectors ({percentage_missing:.1f}% of mapped vectors). "
                f"These are entries in the metadata with FAISS ID mappings, but the vectors don't exist in the FAISS index."
            )
            
            # Add appropriate recommendations
            if percentage_missing > 50:
                result['recommendations'].append(
                    "CRITICAL: Most vectors are missing from the FAISS index. Consider rebuilding the entire vector store "
                    "by using the rebuild_vector_store() function or manually re-indexing all content."
                )
            else:
                result['recommendations'].append(
                    "Some vectors are missing from the FAISS index. To fix this, you can either:\n"
                    "1. Re-add the specific missing entries using their original content\n"
                    "2. Remove the orphaned mappings and metadata using delete_vector() for each missing custom ID\n"
                    "3. For a complete fix, rebuild the entire vector store"
                )
        
        if result['summary']['orphaned_vectors'] > 0:
            result['status'] = 'error'
            result['issues'].append(
                f"Found {result['summary']['orphaned_vectors']} orphaned vectors in the FAISS index that aren't mapped to any custom ID. "
                f"These vectors waste space and can't be accessed through normal search operations."
            )
            result['recommendations'].append(
                "To fix orphaned vectors, you should rebuild the FAISS index from the metadata "
                "by creating a new index and re-adding all vectors that have proper metadata entries."
            )
            
        if result['summary']['missing_metadata_entries'] > 0:
            if result['status'] != 'error': # Don't downgrade from error to warning
                result['status'] = 'warning'
            result['issues'].append(
                f"Found {result['summary']['missing_metadata_entries']} custom IDs in the mapping that don't have corresponding metadata entries. "
                f"These mappings point to custom IDs with no stored metadata."
            )
            result['recommendations'].append(
                "To fix missing metadata entries, either:\n"
                "1. Remove the orphaned mappings using a custom script\n"
                "2. If the metadata exists elsewhere, restore it to the vector store"
            )
            
        if result['summary']['orphaned_metadata_entries'] > 0:
            if result['status'] != 'error': # Don't downgrade from error to warning
                result['status'] = 'warning'
            result['issues'].append(
                f"Found {result['summary']['orphaned_metadata_entries']} metadata entries without corresponding FAISS ID mappings. "
                f"These entries exist in metadata but aren't mapped to vectors in the FAISS index."
            )
            result['recommendations'].append(
                "To fix orphaned metadata entries, either:\n"
                "1. Re-add the vectors for these entries if the original content is available\n"
                "2. Remove the orphaned metadata entries to clean up the store"
            )
        
        # A specific check for complete index/metadata mismatch
        if result['summary']['faiss_index_size'] > 0 and \
           result['summary']['mapped_vectors_count'] > 0 and \
           result['summary']['missing_vectors'] == result['summary']['mapped_vectors_count'] and \
           result['summary']['mapped_vectors_count'] == result['summary']['faiss_index_size']: # Added this condition
            result['status'] = 'error'
            if "All mapped vectors appear to be missing from the FAISS index." not in result['issues']:
                result['issues'].append(
                    "CRITICAL: All mapped vectors appear to be missing from the FAISS index. "
                    "This indicates a severe ID mismatch or index corruption."
                )
            result['recommendations'].append(
                "CRITICAL ISSUE: The FAISS index and metadata are completely out of sync. "
                "The most reliable fix is to completely rebuild the vector store from original content sources."
            )
        
        # Ensure all default summary keys are present if not updated
        default_summary_keys = {
            'mapped_vectors_count': 0, 'faiss_index_size': 0, 'metadata_entries': 0,
            'missing_metadata_entries': 0, 'orphaned_metadata_entries': 0,
            'missing_vectors': 0, 'orphaned_vectors': 0,
        }
        for k, v_default in default_summary_keys.items():
            result['summary'].setdefault(k, v_default)
    
    except Exception as e:
        result['status'] = 'error'
        error_message = f"Error during integrity check: {str(e)}"
        result['issues'].append(f"CRITICAL: {error_message}")
        result['recommendations'].append(
            "An unexpected error occurred during the integrity check. This could indicate a more serious issue "
            "with the vector store files or FAISS library. Consider running in debug mode for more information."
        )
        
        # Add detailed error info to help with debugging
        import traceback
        result['details']['error_traceback'] = traceback.format_exc()
        
        # Ensure summary still exists and has default keys if an unexpected error occurred
        if 'summary' not in result or not isinstance(result['summary'], dict):
            result['summary'] = {
                'mapped_vectors_count': 0,
                'faiss_index_size': 0,
                'metadata_entries': 0,
                'missing_metadata_entries': 0,
                'orphaned_metadata_entries': 0,
                'missing_vectors': 0,
                'orphaned_vectors': 0,
                'check_failed': True,
                'error_message': error_message
            }
        else: # Ensure all default keys are present if summary dict exists
            default_summary_keys = {
                'mapped_vectors_count': 0, 'faiss_index_size': 0, 'metadata_entries': 0,
                'missing_metadata_entries': 0, 'orphaned_metadata_entries': 0,
                'missing_vectors': 0, 'orphaned_vectors': 0, 'check_failed': True,
                'error_message': error_message
            }
            for k, v_default in default_summary_keys.items():
                result['summary'].setdefault(k, v_default)
        
        # Log the error for server-side diagnostics
        logging.error(f"Vector store integrity check failed with error: {str(e)}", exc_info=True)
    
    return result

def add_or_replace(id_: int | str, text: str, metadata: dict):
    """Adds or replaces a vector and its metadata."""
    index, meta = load_index()
    if index is None:
        logging.error("Cannot add/replace vector: FAISS index not loaded.")
        return None

    # Ensure metadata has the custom_id field
    metadata["id"] = str(id_) # Store custom ID also in the metadata item itself
    custom_id_str = str(id_)  # Use string form for map keys

    # Validate we have a proper custom ID
    if custom_id_str is None or custom_id_str.lower() == "none" or not custom_id_str.strip():
        logging.error(f"Cannot add/replace vector with invalid custom ID: {custom_id_str}")
        return None

    embedding = embed(text)
    vector = np.array([embedding], dtype="float32")

    custom_to_faiss_map = meta.get("_custom_to_faiss_id_map_", {})
    # Ensure FAISS IDs in map are integers for processing
    custom_to_faiss_map = {k: int(v) for k, v in custom_to_faiss_map.items()}
    
    faiss_id_to_update = None
    is_update = False

    if custom_id_str in custom_to_faiss_map:
        faiss_id_to_update = custom_to_faiss_map[custom_id_str]
        try:
            # Ensure faiss_id_to_update is a Python int before creating numpy array
            index.remove_ids(np.array([int(faiss_id_to_update)], dtype=np.int64))
            is_update = True
            logging.info(f"Vector for custom ID '{custom_id_str}' (FAISS ID {faiss_id_to_update}) removed for update.")
        except RuntimeError as e: # pragma: no cover
            logging.warning(f"Failed to remove FAISS ID {faiss_id_to_update} for '{custom_id_str}' during update (may not exist in index): {e}. Will try to add as new.")
            # Invalidate faiss_id_to_update so a new one is generated
            faiss_id_to_update = None 
            is_update = False # Treat as new addition if removal failed
            # Remove from map if removal failed, to avoid re-using a potentially problematic ID
            if custom_id_str in custom_to_faiss_map:
                del custom_to_faiss_map[custom_id_str]


    if faiss_id_to_update is not None: #This means it's an update and old vector was removed
        new_faiss_id = int(faiss_id_to_update) # Reuse the same FAISS ID, ensure it's Python int
    else: # New item or update failed and now treating as new
        # Determine a new FAISS ID.
        # For IndexIDMap, we need an ID that is not currently in use.
        # A robust way is to find the maximum ID currently in the FAISS index (if possible) 
        # or in our map, and increment from there, ensuring it's not in use.
        
        # Get all FAISS IDs currently in the map.
        current_faiss_ids_in_map = set(custom_to_faiss_map.values())
        
        # Start searching for a new ID from 0 or max_id + 1
        # Max ID could be from map or from index.ntotal (as a hint of highest possible ID if map is sparse)
        # However, index.ntotal for IndexIDMap is just the count, not necessarily max ID.
        
        if not current_faiss_ids_in_map:
            # If map is empty, start checking from ID 0.
            # If index.ntotal is also 0, ID 0 is fine.
            # If index.ntotal > 0 but map is empty, it implies orphaned vectors.
            # We should still try to use low IDs if they are available in the FAISS index itself.
            next_potential_id = 0
        else:
            next_potential_id = max(current_faiss_ids_in_map) + 1

        # For IndexIDMap, we must ensure the ID is not already physically in the index.
        # The id_map component of IndexIDMap can check this.
        # Note: faiss.IndexIDMap does not directly expose a Pythonic way to iterate all present IDs
        # or check existence of a specific ID without searching/reconstructing.
        # The `index.id_map.size()` gives count of unique IDs ever added (if direct map access), not current.
        # `index.ntotal` is the current number of vectors.
        # The most reliable way with IndexIDMap is to pick a candidate ID and try to add.
        # FAISS itself might handle re-adding an ID if it supports it, or error.
        # add_with_ids should replace if the ID exists, but we already removed.
        # So, the chosen `next_potential_id` should be okay.
        # If we want truly unique, increment `next_potential_id` until `index.reconstruct(id)` fails or similar (complex).
        # The `max(map_ids) + 1` is generally a safe strategy for new IDs *managed by us*.
        new_faiss_id = int(next_potential_id)


    # Add to FAISS index with the chosen/new FAISS ID
    # Ensure the ID is np.int64 for add_with_ids
    index.add_with_ids(vector, np.array([new_faiss_id], dtype=np.int64))
    
    # Update mappings - ensure new_faiss_id is Python int for storage in JSON
    custom_to_faiss_map[custom_id_str] = int(new_faiss_id) 
    # meta["_faiss_id_to_custom_id_map_"] will be rebuilt by save_index from the sanitized custom_to_faiss_map
    meta["_custom_to_faiss_id_map_"] = custom_to_faiss_map
    
    # CRITICAL: Store the metadata using the custom_id_str as the key, not the FAISS ID
    meta[custom_id_str] = metadata
    
    if save_index(index, meta):
        if is_update:
            logging.info(f"Vector for custom ID '{custom_id_str}' (FAISS ID {new_faiss_id}) updated.")
        else:
            logging.info(f"Vector for custom ID '{custom_id_str}' added with new FAISS ID {new_faiss_id}.")
        return custom_id_str
    else: # pragma: no cover
        logging.error(f"Failed to save index/metadata after adding/replacing '{custom_id_str}'.")
        return None


def delete_vector(id_: int | str):
    """Deletes a vector and its metadata by custom ID."""
    index, meta = load_index()
    if index is None:
        logging.error("Cannot delete vector: FAISS index not loaded.")
        return False

    custom_id_str = str(id_)
    custom_to_faiss_map = meta.get("_custom_to_faiss_id_map_", {})

    if custom_id_str not in custom_to_faiss_map:
        logging.warning(f"Cannot delete custom ID '{custom_id_str}': not found in ID map.")
        return False

    faiss_int_id = custom_to_faiss_map[custom_id_str]

    try:
        ids_to_remove = np.array([faiss_int_id], dtype=np.int64)
        remove_count = index.remove_ids(ids_to_remove)

        if remove_count == 0:
            logging.warning(
                f"Custom ID '{custom_id_str}' (FAISS ID {faiss_int_id}) was in map, "
                f"but corresponding vector not found in FAISS index for removal. Metadata will still be cleaned up."
            )
        else:
            logging.info(f"Vector for FAISS ID {faiss_int_id} (custom ID '{custom_id_str}') removed from FAISS index.")

        # Remove metadata entry, which is keyed by custom_id_str
        if custom_id_str in meta:
            del meta[custom_id_str]
            logging.info(f"Metadata for custom ID '{custom_id_str}' removed from metadata store.")
        else:
            logging.warning(f"Metadata for custom ID '{custom_id_str}' not found, though it was in the map.")

        # Remove from custom ID map
        del custom_to_faiss_map[custom_id_str]
        meta["_custom_to_faiss_id_map_"] = custom_to_faiss_map # Update the map in meta
        
        # Also update the reverse map (_faiss_id_to_custom_id_map_)
        faiss_to_custom_map = meta.get("_faiss_id_to_custom_id_map_", {})
        if faiss_int_id in faiss_to_custom_map:
            del faiss_to_custom_map[faiss_int_id]
            meta["_faiss_id_to_custom_id_map_"] = faiss_to_custom_map
        
        save_index(index, meta)
        logging.info(f"Successfully processed deletion for custom ID '{custom_id_str}'.")
        return True
        
    except Exception as e:
        logging.error(f"Error deleting vector for custom ID '{custom_id_str}' (FAISS ID {faiss_int_id}): {e}")
        return False


def delete_vectors_by_filter(pred: _t.Callable[[dict], bool]):
    """
    Delete multiple vectors and their metadata based on a predicate function.
    
    Args:
        pred: Function that takes a metadata dict and returns True if the vector should be deleted
        
    Returns:
        Tuple of (success_count, failure_count, total_checked)
    """
    index, meta = load_index()
    if index is None:
        logging.error("Cannot delete vectors: FAISS index not loaded.")
        return 0, 0, 0
    
    custom_to_faiss_map = meta.get("_custom_to_faiss_id_map_", {})
    custom_ids_to_delete = []
    total_checked = 0
    
    # First, identify all vectors to delete
    for custom_id_str, faiss_int_id in custom_to_faiss_map.items():
        # Check if metadata exists for this custom ID
        if custom_id_str in meta and isinstance(meta[custom_id_str], dict):
            metadata = meta[custom_id_str]
            total_checked += 1
            
            if pred(metadata):
                custom_ids_to_delete.append(custom_id_str)
    
    # Then delete them
    success_count = 0
    failure_count = 0
    for custom_id_str in custom_ids_to_delete:
        if delete_vector(custom_id_str):
            success_count += 1
        else:
            failure_count += 1
    
    logging.info(f"Deleted {success_count} vectors based on filter predicate.")
    if failure_count > 0:
        logging.warning(f"Failed to delete {failure_count} vectors.")
    
    return success_count, failure_count, total_checked

def search(query: str, top_k: int = 5, pred: _t.Callable[[dict], bool] | None = None, offset: int = 0) -> list[tuple[dict, float]]:
    """Search for text in the vector store. 
    
    Args:
        query: Text to search for.
        top_k: Number of results to return.
        pred: Optional predicate to filter results.
        offset: Offset for pagination (not directly supported by FAISS search, handled post-search).
        
    Returns:
        List of tuples, where each tuple contains (metadata, score).
    """
    index, meta = load_index()
    if index is None:
        logging.error("Cannot search: FAISS index not loaded.")
        return []

    logging.info(f"[memory_utils.search] Received query: '{query}', top_k: {top_k}") # LOGGING

    custom_to_faiss_map = meta.get("_custom_to_faiss_id_map_", {})
    faiss_to_custom_map = meta.get("_faiss_id_to_custom_id_map_", {})
    
    # If no query, return all items matching predicate (if any), respecting top_k and offset
    if not query.strip():
        logging.info("[memory_utils.search] Empty query received. Returning items based on predicate.") # LOGGING
        all_items = []
        # Iterate over custom IDs stored in the map
        for custom_id_str, faiss_int_id in custom_to_faiss_map.items():
            # Metadata items are keyed by custom_id_str in the 'meta' dict itself (excluding internal maps)
            if custom_id_str in meta:
                metadata_item = meta[custom_id_str]
                if pred is None or pred(metadata_item):
                    all_items.append((metadata_item, 1.0)) # Score 1.0 for non-semantic matches
            else:
                # This case should ideally not happen if data is consistent
                logging.warning(f"[memory_utils.search] Orphaned custom_id '{custom_id_str}' in map, but no corresponding metadata entry.")
        
        # Sort by a default criteria if needed, e.g., 'updated_at' or 'id' if available in metadata
        # For now, no specific sorting for empty query, relies on dict iteration order (Python 3.7+)
        logging.info(f"[memory_utils.search] Empty query: Found {len(all_items)} items before offset/top_k.") # LOGGING
        # Apply offset and top_k
        return all_items[offset : offset + top_k]

    try:
        query_vector = embed(query)
    except Exception as e:
        logging.error(f"[memory_utils.search] Failed to embed query '{query}': {e}")
        return []

    # FAISS search returns distances (L2 squared) and labels (FAISS integer IDs)
    # Need to adjust k for search if offset is used, then slice later.
    # This is inefficient for large offsets but FAISS doesn't support offset directly.
    # For typical small top_k, it's acceptable.
    # If we expect large offsets frequently, a different strategy for pagination would be needed.
    # For now, assume offset is small or zero.
    search_k = top_k + offset 
    try:
        distances, faiss_ids = index.search(np.array([query_vector]), search_k)
    except Exception as e:
        logging.error(f"[memory_utils.search] FAISS index.search failed for query '{query}': {e}")
        return []

    results = []
    # Get the reverse map from FAISS ID to custom ID string
    # This should be already rebuilt during load_index
    
    logging.info(f"[memory_utils.search] FAISS raw search for '{query}' returned {len(faiss_ids[0])} results before filtering.") # LOGGING
    raw_results_count = 0

    for i, faiss_int_id in enumerate(faiss_ids[0]):
        raw_results_count += 1
        if faiss_int_id == -1:  # No more results or padding from FAISS
            continue

        # Convert numpy.int64 (or other int types from FAISS) to standard Python int for dict key lookup
        faiss_int_id_py = int(faiss_int_id)

        # Use the reverse map to get the custom ID
        custom_id_str = faiss_to_custom_map.get(faiss_int_id_py)
        if not custom_id_str:
            logging.warning(f"[memory_utils.search] FAISS ID {faiss_int_id_py} not found in faiss_to_custom_map. Skipping.")
            continue
            
        # Metadata items are keyed by custom_id_str in the 'meta' dict itself
        metadata_item = meta.get(custom_id_str)
        if not metadata_item:
            logging.warning(f"[memory_utils.search] Custom ID '{custom_id_str}' (from FAISS ID {faiss_int_id_py}) not found in metadata. Skipping.")
            continue
        
        # Predicate check
        predicate_passed = pred is None or pred(metadata_item)
        logging.debug(f"[memory_utils.search] Checking item: ID='{custom_id_str}', Type='{metadata_item.get('type')}'. Predicate passed: {predicate_passed}") # DEBUG LOGGING
        if predicate_passed:
            # Similarity score (1.0 - distance for normalized embeddings, or use raw distance)
            # Assuming normalized embeddings, higher score is better (closer to 1.0)
            # Max L2 distance for normalized vectors is 2, so (2 - dist) / 2 gives 0-1 score.
            # Or, if distances are small, 1 - dist is common. Let's use a simple positive score.
            # SentenceTransformer usually returns cosine similarity, not L2. 
            # If using index.search with IndexFlatL2, distances are L2. 
            # If model.encode normalizes, then L2 distance d^2 = 2 - 2*cos_sim.
            # So cos_sim = 1 - d^2/2. Higher is better.
            score = 1.0 - (distances[0][i] / 2.0) # Crude similarity from L2, higher is better
            results.append((metadata_item, score))
    
    logging.info(f"[memory_utils.search] Query '{query}': Processed {raw_results_count} raw FAISS results. Found {len(results)} items matching predicate before offset and top_k.") # LOGGING
    
    # Apply offset and then limit to top_k after predicate filtering and scoring
    # This ensures the predicate is applied first.
    final_results = results[offset : offset + top_k]
    logging.info(f"[memory_utils.search] Query '{query}': Returning {len(final_results)} final results after offset and top_k.") # LOGGING
    return final_results

def count_items(pred: _t.Callable[[dict], bool] | None = None) -> int:
    """
    Count the number of items in the vector store, optionally filtered by a predicate.
    
    Args:
        pred: Optional predicate to filter items by metadata.
        
    Returns:
        Count of items matching the predicate.
    """
    try:
        _, meta = load_index()
        if not meta:
            logging.error("Failed to load metadata for counting items.")
            return 0
        
        # Count items that match the predicate and are actual items (not the ID map)
        count = 0
        for key, value in meta.items():
            if key != "_custom_to_faiss_id_map_" and isinstance(value, dict):
                if not pred or pred(value):
                    count += 1
        
        return count
    except Exception as e:
        logging.error(f"Error counting items: {e}")
        return 0

# ───────────────────────────────────────── Utils ────
def load_preferences(cfg: dict, memex_root: pathlib.Path = None) -> dict:
    if memex_root is None:
        memex_root = ROOT
    
    pref_file_rel_path = cfg.get("system", {}).get("preferences_file_relative_to_memex_root", 
                                                  cfg.get("preferences", {}).get("file", "docs/PREFERENCES.yaml"))
    
    if not pref_file_rel_path:
        logging.warning("Preferences file path not defined in configuration.")
        return {}

    path = memex_root / pref_file_rel_path
    if not path.exists():
        logging.info(f"Preferences file {path} not found. Returning empty preferences.")
        return {}
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as e:
        logging.error(f"Error parsing preferences file {path}: {e}. Returning empty preferences.")
        return {}
    except IOError as e:
        logging.error(f"Error reading preferences file {path}: {e}. Returning empty preferences.")
        return {}

def index_code_chunk(chunk_id: str, content: str, metadata: dict) -> str:
    """
    Index a code chunk in the vector store.
    
    Args:
        chunk_id: Unique identifier for the code chunk
        content: Content of the code chunk to embed
        metadata: Metadata for the code chunk (should include source_file, language, start_line, end_line)
        
    Returns:
        The chunk_id if successfully indexed, None otherwise
    """
    try:
        # Ensure required metadata fields
        required_fields = ["source_file", "language", "start_line", "end_line"]
        for field in required_fields:
            if field not in metadata:
                logging.error(f"Missing required metadata field '{field}' for code chunk.")
                return None
        
        # Ensure the metadata has the correct type
        metadata["type"] = "code_chunk"
        
        # Create a rich description for embedding
        language = metadata.get("language", "unknown")
        source_file = metadata.get("source_file", "unknown")
        name = metadata.get("name", "")
        
        if name:
            embedding_description = f"{language} function '{name}' from {source_file}:\n{content}"
        else:
            embedding_description = f"{language} code from {source_file}:\n{content}"
        
        # Store the raw content in metadata
        metadata["content"] = content
        
        # Add to vector store
        return add_or_replace(chunk_id, embedding_description, metadata)
    
    except Exception as e:
        logging.error(f"Failed to index code chunk '{chunk_id}': {e}")
        return None

def delete_code_chunks():
    """
    Delete all code chunks from the vector store.
    
    Returns:
        Tuple of (success_count, failure_count, total_checked)
    """
    return delete_vectors_by_filter(lambda meta: meta.get("type") == "code_chunk")

def generate_chunk_id(source_file: str, start_line: int, end_line: int, content_hash: str = None) -> str:
    """
    Generate a deterministic ID for a code chunk based on file and line numbers.
    
    Args:
        source_file: Path to the source file
        start_line: Starting line number
        end_line: Ending line number
        content_hash: Optional hash of content to ensure uniqueness
        
    Returns:
        A string ID for the chunk
    """
    import hashlib
    
    # Normalize the source file path
    normalized_path = str(pathlib.Path(source_file)).replace("\\", "/")
    
    # Create a base ID from file and line numbers
    base_id = f"{normalized_path}:{start_line}-{end_line}"
    
    # If content hash is provided, append it
    if content_hash:
        return f"{base_id}:{content_hash}"
    
    # Otherwise, hash the base ID itself for a shorter ID
    return f"chunk_{hashlib.md5(base_id.encode()).hexdigest()[:12]}"

# ───────────────────────────────────────── Memory Management Functions ────
# Provide direct access to memory management functions
def get_index_cache_stats() -> dict:
    """Get cache statistics for the index manager."""
    return _index_manager.get_stats()

def set_index_cache_limits(max_memory_mb: int = None, ttl_seconds: int = None):
    """Set memory and TTL limits for the index cache."""
    if hasattr(_index_manager, 'set_limits'):
        _index_manager.set_limits(max_memory_mb, ttl_seconds)
    else:
        logging.warning("Cache limit configuration not available in fallback mode")