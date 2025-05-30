#!/usr/bin/env python
"""
Migration script for fixing metadata.json files that use the old (FAISS ID-keyed) format.

This script identifies items in metadata.json where the metadata is stored under FAISS ID keys
instead of custom ID keys, then re-keys them to use the correct custom ID format.

The main symptom this fixes is when the Memory tab in the UI shows no items despite having data.
"""

import json
import logging
import argparse
import shutil
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Set

# Set up relative imports
import sys
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

try:
    from scripts.memory_utils import load_cfg, get_meta_path, load_index
except ImportError:
    from memex.scripts.memory_utils import load_cfg, get_meta_path, load_index


def identify_incorrectly_keyed_items(meta: Dict[str, Any]) -> List[Dict[str, str]]:
    """
    Identify items that are keyed by FAISS ID instead of custom ID.
    
    Args:
        meta: The metadata dictionary
        
    Returns:
        List of dictionaries with 'custom_id', 'faiss_id', 'expected_key', 'found_key'
    """
    incorrectly_keyed = []
    custom_to_faiss_map = meta.get("_custom_to_faiss_id_map_", {})
    
    for custom_id, faiss_id in custom_to_faiss_map.items():
        faiss_id_str = str(faiss_id)
        
        # Check if metadata exists under FAISS ID key but not under custom ID key
        if faiss_id_str in meta and custom_id not in meta:
            # Additional verification: ensure it's actual item metadata (not system data)
            item_meta = meta[faiss_id_str]
            if isinstance(item_meta, dict) and not faiss_id_str.startswith("_"):
                incorrectly_keyed.append({
                    'custom_id': custom_id,
                    'faiss_id': faiss_id_str,
                    'expected_key': custom_id,
                    'found_key': faiss_id_str,
                    'item_type': item_meta.get('type', 'unknown')
                })
    
    return incorrectly_keyed


def migrate_metadata_keys(meta: Dict[str, Any], dry_run: bool = False) -> Dict[str, Any]:
    """
    Migrate metadata from FAISS ID keys to custom ID keys.
    
    Args:
        meta: The metadata dictionary to migrate
        dry_run: If True, don't modify the dictionary, just return what would be changed
        
    Returns:
        Dictionary with migration statistics
    """
    stats = {
        'items_migrated': 0,
        'items_verified': 0,
        'errors': []
    }
    
    incorrectly_keyed = identify_incorrectly_keyed_items(meta)
    
    for item in incorrectly_keyed:
        custom_id = item['custom_id']
        faiss_id_str = item['faiss_id']
        item_type = item['item_type']
        
        try:
            if not dry_run:
                # Copy metadata from FAISS ID key to custom ID key
                meta[custom_id] = meta[faiss_id_str].copy()
                
                # Ensure the 'id' field in metadata matches the custom_id
                if 'id' in meta[custom_id]:
                    meta[custom_id]['id'] = custom_id
                
                # Remove the old FAISS ID key
                del meta[faiss_id_str]
                
                # Verify the migration
                if custom_id in meta and faiss_id_str not in meta:
                    stats['items_migrated'] += 1
                    logging.info(f"Migrated {item_type} '{custom_id}' from key '{faiss_id_str}' to '{custom_id}'")
                else:
                    stats['errors'].append(f"Migration verification failed for '{custom_id}'")
            else:
                stats['items_migrated'] += 1
                logging.info(f"Would migrate {item_type} '{custom_id}' from key '{faiss_id_str}' to '{custom_id}'")
                
        except Exception as e:
            error_msg = f"Error migrating '{custom_id}': {str(e)}"
            stats['errors'].append(error_msg)
            logging.error(error_msg)
    
    return stats


def create_backup(meta_path: Path) -> Path:
    """
    Create a backup of the metadata file.
    
    Args:
        meta_path: Path to the metadata.json file
        
    Returns:
        Path to the backup file
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = meta_path.with_suffix(f".bak_{timestamp}")
    
    shutil.copy2(meta_path, backup_path)
    logging.info(f"Created backup: {backup_path}")
    
    return backup_path


def main():
    """Main migration function."""
    parser = argparse.ArgumentParser(
        description="Migrate metadata.json from old FAISS ID-keyed format to custom ID-keyed format"
    )
    parser.add_argument(
        "--dry-run", 
        action="store_true", 
        help="Show what would be changed without making actual changes"
    )
    parser.add_argument(
        "--verbose", 
        action="store_true",
        help="Enable verbose logging"
    )
    parser.add_argument(
        "--no-backup",
        action="store_true", 
        help="Skip creating backup (not recommended)"
    )
    
    args = parser.parse_args()
    
    # Set up logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    try:
        # Load configuration and paths
        cfg = load_cfg()
        meta_path = get_meta_path(cfg)
        
        if not meta_path.exists():
            logging.error(f"Metadata file not found: {meta_path}")
            return 1
        
        logging.info(f"Loading metadata from: {meta_path}")
        
        # Load current metadata
        with open(meta_path, 'r', encoding='utf-8') as f:
            meta = json.load(f)
        
        # Identify items that need migration
        incorrectly_keyed = identify_incorrectly_keyed_items(meta)
        
        if not incorrectly_keyed:
            logging.info("No incorrectly keyed metadata found. Migration not needed.")
            return 0
        
        # Report what will be migrated
        logging.info(f"Found {len(incorrectly_keyed)} items with incorrect keying:")
        for item in incorrectly_keyed:
            logging.info(f"  {item['item_type']} '{item['custom_id']}' (key: {item['found_key']} -> {item['expected_key']})")
        
        if args.dry_run:
            logging.info("\n=== DRY RUN MODE - No changes will be made ===")
            stats = migrate_metadata_keys(meta, dry_run=True)
            logging.info(f"Would migrate {stats['items_migrated']} items")
            if stats['errors']:
                logging.warning(f"Would encounter {len(stats['errors'])} errors:")
                for error in stats['errors']:
                    logging.warning(f"  {error}")
            return 0
        
        # Create backup unless explicitly disabled
        if not args.no_backup:
            backup_path = create_backup(meta_path)
            logging.info(f"Original metadata backed up to: {backup_path}")
        
        # Perform migration
        logging.info("Starting migration...")
        stats = migrate_metadata_keys(meta, dry_run=False)
        
        # Save migrated metadata
        with open(meta_path, 'w', encoding='utf-8') as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)
        
        # Report results
        logging.info(f"Migration completed successfully!")
        logging.info(f"Items migrated: {stats['items_migrated']}")
        
        if stats['errors']:
            logging.warning(f"Errors encountered: {len(stats['errors'])}")
            for error in stats['errors']:
                logging.warning(f"  {error}")
        
        # Recommend next steps
        logging.info("\nRecommended next steps:")
        logging.info("1. Run 'python scripts/check_store_health.py' to verify the migration")
        logging.info("2. Test the Memory tab in the UI to ensure items are now visible")
        logging.info("3. If everything works correctly, you can delete the backup file")
        
        return 0
        
    except Exception as e:
        logging.error(f"Migration failed: {str(e)}")
        if args.verbose:
            import traceback
            logging.error(traceback.format_exc())
        return 1


if __name__ == "__main__":
    exit(main())