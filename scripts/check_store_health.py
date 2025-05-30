#!/usr/bin/env python
"""
Checks the health and integrity of the vector store by verifying
synchronization between the FAISS index and metadata.json.

This utility helps diagnose issues if search behavior is unexpected
or if data corruption is suspected.
"""
import sys
import json
import logging
import argparse
from memory_utils import check_vector_store_integrity, get_index_path, get_meta_path
from thread_safe_store import load_index

# ───────────────────────────────────────── Logging Setup ────
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def main(args=None):
    """Main entry point for the CLI script."""
    parser = argparse.ArgumentParser(
        description="Check the integrity of the vector store (FAISS index and metadata)."
    )
    parser.add_argument("--verbose", "-v", action="store_true", 
                        help="Detailed output with full issue details")
    parser.add_argument("--json", "-j", action="store_true", 
                        help="Output results in JSON format")
    parser.add_argument("--quiet", "-q", action="store_true", 
                        help="Suppress informational output, only show errors/warnings")
    
    parsed_args = parser.parse_args(args)
    
    # Print basic info about vector store
    if not parsed_args.quiet:
        index_path = get_index_path()
        meta_path = get_meta_path()
        print(f"Vector store locations:")
        print(f"FAISS index: {index_path}")
        print(f"Metadata file: {meta_path}")
        print("Checking vector store integrity...")
    
    # Run the integrity check
    results = check_vector_store_integrity()
    
    # Output in JSON format if requested
    if parsed_args.json:
        print(json.dumps(results, indent=2))
        # Return non-zero exit code if there are issues
        return 0 if results.get('status') == 'ok' else 1
    
    # Print human-readable report
    status = results.get('status', 'unknown')
    summary = results.get('summary', {})
    issues = results.get('issues', [])
    
    # Status line
    status_emoji = "✅" if status == 'ok' else "⚠️" if status == 'warning' else "❌"
    print(f"\n{status_emoji} Vector Store Status: {status.upper()}")
    
    # Summary section
    print("\nSummary:")
    print(f"- FAISS index size: {summary.get('faiss_index_size', 'N/A')} vectors")
    print(f"- Mapped vectors: {summary.get('mapped_vectors_count', 'N/A')} entries")
    print(f"- Missing metadata entries: {summary.get('missing_metadata_entries', 0)}")
    print(f"- Orphaned metadata entries: {summary.get('orphaned_metadata_entries', 0)}")
    print(f"- Missing vectors in FAISS: {summary.get('missing_vectors', 0)}")
    print(f"- Orphaned vectors: {summary.get('orphaned_vectors', 0)}")
    
    # Issues section
    if issues:
        print("\nIssues Found:")
        for i, issue in enumerate(issues, 1):
            print(f"{i}. {issue}")
    else:
        print("\nNo issues found.")
    
    # Detailed section (if verbose)
    if parsed_args.verbose and status != 'ok':
        details = results.get('details', {})
        print("\nDetailed diagnostics:")
        
        if details.get('missing_metadata'):
            print("\nEntries in ID map missing metadata:")
            for entry in details['missing_metadata']:
                print(f"- custom_id: {entry.get('custom_id')}, faiss_id: {entry.get('faiss_id')}")
        
        if details.get('orphaned_metadata'):
            print("\nOrphaned metadata entries (not referenced in ID map):")
            for entry in details['orphaned_metadata']:
                print(f"- faiss_id: {entry.get('faiss_id')}")
                # Optionally print metadata type/info
                meta_entry = entry.get('metadata', {})
                print(f"  Type: {meta_entry.get('type', 'unknown')}")
        
        if details.get('missing_vectors'):
            print("\nVectors missing from FAISS index:")
            for entry in details['missing_vectors']:
                print(f"- custom_id: {entry.get('custom_id')}, faiss_id: {entry.get('faiss_id')}")
        
        if details.get('reconstruction_errors'):
            print("\nReconstruction errors:")
            for entry in details['reconstruction_errors']:
                print(f"- custom_id: {entry.get('custom_id')}, faiss_id: {entry.get('faiss_id')}")
                print(f"  Error: {entry.get('error')}")
    
    # Add suggestions if issues found
    if status != 'ok':
        print("\nSuggested actions:")
        if summary.get('missing_metadata_entries', 0) > 0:
            print("- Metadata entries are missing: Consider rebuilding the vector store or repairing the metadata.json file.")
        
        if summary.get('missing_vectors', 0) > 0:
            print("- Vectors are missing from FAISS: Consider rebuilding the vector store.")
        
        if summary.get('orphaned_metadata_entries', 0) > 0:
            print("- Orphaned metadata: These may be removed with a store cleanup utility.")
        
        if summary.get('orphaned_vectors', 0) > 0:
            print("- Orphaned vectors: Consider rebuilding the vector store to reclaim space.")
    
    # Return non-zero exit code for warning/error status
    return 0 if status == 'ok' else 1

if __name__ == "__main__":
    sys.exit(main()) 