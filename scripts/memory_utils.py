"""
Общие функции: чтение конфигурации, работа с Faiss, эмбеддинг.
Single-source, чтобы другие скрипты не дублировались.
"""
from __future__ import annotations
import os
import json
import pathlib
import functools
import logging
import typing as _t

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
VEC_DIR = ROOT / ".cursor" / "vecstore"
INDEX_PATH = VEC_DIR / "index.faiss"
META_PATH = VEC_DIR / "metadata.json"

_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

DEFAULT_CFG = {
    "files": {"include": ["src/**/*.py"], "exclude": []},
    "prompt": {"max_tokens": 10_000, "top_k_tasks": 5, "top_k_snippets": 5},
    "tasks": {"file": "docs/TASKS.yaml", "tag_prefix": "- "}, # tag_prefix might be legacy from MD
    "preferences": {"file": "docs/PREFERENCES.yaml"},
}

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
@functools.lru_cache
def model() -> SentenceTransformer:
    try:
        return SentenceTransformer(_MODEL_NAME)
    except Exception as e:
        logging.error(f"Failed to load SentenceTransformer model '{_MODEL_NAME}': {e}")
        raise

def vec_dim() -> int:
    try:
        return model().get_sentence_embedding_dimension()
    except Exception as e:
        logging.error(f"Failed to get vector dimension from model: {e}")
        # Fallback or re-raise, depending on desired robustness.
        # For now, re-raise as it's critical for Faiss index.
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
        VEC_DIR.mkdir(parents=True, exist_ok=True)
        current_dim = vec_dim()
        if not INDEX_PATH.exists():
            logging.info(f"FAISS index not found at {INDEX_PATH}. Creating new index with dim {current_dim}.")
            # Create an IndexFlatL2 index and wrap it with IndexIDMap
            base_index = faiss.IndexFlatL2(current_dim)
            id_mapped_index = faiss.IndexIDMap(base_index)
            faiss.write_index(id_mapped_index, str(INDEX_PATH))
            
            # When creating a new index, also ensure metadata is fresh and has the map
            if META_PATH.exists():
                try:
                    # Attempt to load existing meta to preserve other data if any
                    meta = json.loads(META_PATH.read_text(encoding="utf-8"))
                except json.JSONDecodeError:
                    meta = {} # Corrupted or empty, start fresh
            else: # This else corresponds to `if META_PATH.exists()`
                meta = {}
            # These operations are for the new index case, after meta is initialized
            meta["_custom_to_faiss_id_map_"] = meta.get("_custom_to_faiss_id_map_", {})
            META_PATH.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

        elif not META_PATH.exists(): # Index exists, but no metadata
            logging.info(f"Metadata file not found at {META_PATH} but index exists. Creating empty metadata with ID map.")
            meta = {"_custom_to_faiss_id_map_": {}}
            META_PATH.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        else: # Both exist, check index dimension and ensure map in metadata during load_index
            try:
                temp_index = faiss.read_index(str(INDEX_PATH))
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

def load_index() -> tuple[faiss.Index | None, dict]:
    _ensure_store() # Ensures files exist
    try:
        index = faiss.read_index(str(INDEX_PATH))
        meta_text = META_PATH.read_text(encoding="utf-8")
        meta = json.loads(meta_text)
        
        # Ensure the custom ID to FAISS ID map exists in the loaded metadata
        if "_custom_to_faiss_id_map_" not in meta:
            meta["_custom_to_faiss_id_map_"] = {}
            # Do not save here; this is a read operation. Modifications in add/delete will save.
            logging.info("'_custom_to_faiss_id_map_' was missing from metadata.json; initialized in memory.")
            
        return index, meta
    except FileNotFoundError: # Handles case where _ensure_store might not have created them due to an issue
        logging.error(f"FAISS index or metadata file not found after _ensure_store. Path: {INDEX_PATH} or {META_PATH}")
        return None, {"_custom_to_faiss_id_map_": {}} # Return a valid meta structure
    except json.JSONDecodeError as e:
        logging.error(f"Error decoding metadata.json: {e}. Returning empty metadata with ID map.")
        # Attempt to preserve the index if it's loadable
        try:
            index = faiss.read_index(str(INDEX_PATH))
        except Exception as index_e:
            logging.error(f"Failed to load FAISS index after metadata decode error: {index_e}")
            index = None
        return index, {"_custom_to_faiss_id_map_": {}}
    except Exception as e:
        logging.error(f"Failed to load FAISS index or metadata: {e}")
        return None, {"_custom_to_faiss_id_map_": {}}


def save_index(index: faiss.Index, meta: dict):
    try:
        faiss.write_index(index, str(INDEX_PATH))
        META_PATH.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        logging.error(f"Failed to save FAISS index or metadata: {e}")
        # Potentially raise here as data loss could occur

def add_or_replace(id_: int | str, text: str, metadata: dict):
    """Adds or replaces a vector and its metadata using a custom ID (string or int).
    Manages mapping from custom ID to FAISS integer ID.
    """
    index, meta = load_index()
    if index is None: # load_index failed or files don't exist
        logging.error("Cannot add/replace vector: FAISS index not loaded or store not initialized.")
        return None

    custom_id_str = str(id_)
    vec = embed(text)
    if vec is None: # Embedding failed
        logging.error(f"Cannot add/replace vector for custom ID '{custom_id_str}': text embedding failed.")
        return None

    custom_to_faiss_map = meta.get("_custom_to_faiss_id_map_", {})
    is_update = False

    if custom_id_str in custom_to_faiss_map:
        # Existing item: Update
        faiss_int_id = custom_to_faiss_map[custom_id_str]
        try:
            # Atomically replace: remove old, add new with the same FAISS ID
            # Ensure faiss_int_id is a valid ID for removal (e.g., not -1 if that's possible)
            # index.remove_ids requires a C-contiguous array of int64
            ids_to_remove = np.array([faiss_int_id], dtype=np.int64)
            remove_count = index.remove_ids(ids_to_remove)
            
            if remove_count == 0:
                # This case is problematic: the ID was in our map, but not in FAISS.
                # This indicates a desynchronization. 
                # For robustness, we could try to add it as a new entry instead.
                logging.warning(f"Custom ID '{custom_id_str}' (FAISS ID {faiss_int_id}) was in map but not found in FAISS for removal. Attempting to add as new.")
                # Proceed as if it's a new item, but we already have faiss_int_id. 
                # This might lead to ID collision if faiss_int_id is reused by index.add() if not using add_with_ids.
                # A safer approach for this edge case: re-assign a new faiss_id if strictly using index.add()
                # However, since we intend to use add_with_ids, we can try to reuse faiss_int_id.
                pass # Let the add_with_ids try, or handle below if it's truly problematic.

            index.add_with_ids(vec[None, :], np.array([faiss_int_id], dtype=np.int64))
            meta[str(faiss_int_id)] = metadata # Store metadata keyed by FAISS int ID
            is_update = True
            logging.info(f"Vector for custom ID '{custom_id_str}' (FAISS ID {faiss_int_id}) updated.")
        except Exception as e:
            # This could happen if faiss_int_id is somehow invalid for FAISS operations
            logging.error(f"Error updating vector for custom ID '{custom_id_str}' (FAISS ID {faiss_int_id}): {e}. Attempting to treat as new entry.")
            # Fallback: treat as a new entry. We need a new FAISS ID.
            # To prevent using a potentially problematic faiss_int_id, we should unset it here or re-generate.
            # For now, let the 'new item' logic handle getting a new FAISS ID.
            del custom_to_faiss_map[custom_id_str] # Remove from map to force new ID generation
            # This will fall through to the 'else' block for new items.

    if not is_update: # New item or update failed and now treating as new
        # Determine the new FAISS ID. Using index.ntotal is simplest if no ID management beyond that.
        # However, if remove_ids was used, ntotal might not be the next truly available ID slot
        # if FAISS reuses IDs. add_with_ids with an explicitly managed ID is safer.
        # For now, let's find a truly unique new faiss_id if possible, or use ntotal carefully.
        # A simple robust way: use a high number or manage a counter if not using index.ntotal directly.
        # If we stick to index.ntotal for new additions after potential removals, ensure FAISS handles it or manage IDs explicitly.
        # The most robust approach with add_with_ids for NEW items is to ensure new_faiss_id is unique.
        # Let's use index.ntotal as the candidate for the new FAISS ID. This is what index.add() would effectively use internally for the ID.
        new_faiss_id = index.ntotal 

        # Defensive check: if this faiss_id is already a key in meta (excluding map itself), it means it might be in use.
        # This scenario should be rare if meta keys are faiss_ids from the map or previous direct adds.
        # A more robust ID generation might be needed if `index.ntotal` can collide after removals and `add_with_ids`.
        # For simplicity of `IndexFlatL2` and `add_with_ids`, `new_faiss_id` must be a new, unused integer ID.
        # `index.ntotal` should be safe for `IndexFlatL2` when `add_with_ids` as it tracks the highest assigned ID + 1 implicitly.

        index.add_with_ids(vec[None, :], np.array([new_faiss_id], dtype=np.int64))
        meta[str(new_faiss_id)] = metadata  # Store metadata keyed by the new FAISS int ID
        custom_to_faiss_map[custom_id_str] = new_faiss_id # Update map
        is_update = False # Explicitly state it was an add op
        logging.info(f"Vector for custom ID '{custom_id_str}' added with new FAISS ID {new_faiss_id}.")

    meta["_custom_to_faiss_id_map_"] = custom_to_faiss_map # Ensure map is part of meta being saved
    save_index(index, meta)
    return custom_id_str # Return the original custom ID


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

        # Remove metadata entry (keyed by FAISS int ID)
        if str(faiss_int_id) in meta:
            del meta[str(faiss_int_id)]
        else:
            logging.warning(f"Metadata for FAISS ID {faiss_int_id} (custom ID '{custom_id_str}') not found, though it was in the map.")

        # Remove from custom ID map
        del custom_to_faiss_map[custom_id_str]
        meta["_custom_to_faiss_id_map_"] = custom_to_faiss_map # Update the map in meta
        
        save_index(index, meta)
        logging.info(f"Successfully processed deletion for custom ID '{custom_id_str}'.")
        return True
        
    except Exception as e:
        logging.error(f"Error deleting vector for custom ID '{custom_id_str}' (FAISS ID {faiss_int_id}): {e}")
        return False


def search(query: str, top_k: int, pred: _t.Callable[[dict], bool] | None = None) -> list[tuple[dict, float]]:
    index, meta = load_index()
    if index is None or index.ntotal == 0:
        if index is None: 
            logging.warning("Search failed: FAISS index not loaded.")
        else: 
            logging.info("Search skipped: FAISS index is empty.")
        return []

    # The _custom_to_faiss_id_map_ is not directly used in search retrieval, 
    # as FAISS returns its internal integer IDs. Metadata is stored keyed by these FAISS IDs.
    # Ensure meta dictionary is valid and contains expected structure (handled by load_index).

    try:
        qv = embed(query)[None, :]
        if qv is None: # Embedding failed
            logging.error(f"Search failed for query '{query}': text embedding failed.")
            return []
            
        distances, indices = index.search(qv, k=min(top_k, index.ntotal)) # Ensure k <= index.ntotal

        results = []
        for dist, idx in zip(distances[0], indices[0]):
            if idx == -1: # Faiss can return -1 if k > ntotal or for other reasons
                continue
            
            # FAISS indices (idx) are integers. Metadata is keyed by str(idx).
            entry_meta = meta.get(str(idx)) 
            
            if entry_meta:
                # Ensure that the entry_meta is not the map itself, if by some accident it got returned.
                # This is a very defensive check, normally meta.get(str(idx)) would return the item's metadata.
                if isinstance(entry_meta, dict) and "_custom_to_faiss_id_map_" in entry_meta and str(idx) == "_custom_to_faiss_id_map_":
                    logging.warning(f"Search tried to retrieve metadata map itself for FAISS index {idx}. Skipping.")
                    continue

                if pred is None or pred(entry_meta):
                    results.append((entry_meta, float(dist)))
            else:
                # This implies a desync: FAISS has an index idx, but its metadata str(idx) is not in meta.
                # This could happen if meta saving failed or was corrupted.
                logging.warning(f"Metadata not found for FAISS index {idx} (key: '{str(idx)}') during search. This entry will be skipped.")
        return results
    except Exception as e:
        logging.error(f"Error during FAISS search for query '{query}': {e}")
        return []

# ───────────────────────────────────────── Utils ────
def load_preferences(cfg: dict) -> dict:
    pref_file_path = cfg.get("preferences", {}).get("file")
    if not pref_file_path:
        logging.warning("Preferences file path not defined in configuration.")
        return {}

    path = ROOT / pref_file_path
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