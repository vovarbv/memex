#!/usr/bin/env python
"""
Searches the memory (FAISS vector store) for a given query.
"""
import sys
import argparse
import logging
import textwrap

from memory_utils import search, load_cfg

# ───────────────────────────────────────── Logging Setup ────
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def main():
    parser = argparse.ArgumentParser(description="Search the project memory.")
    parser.add_argument("query", nargs="?", default="project memory context",
                        help="The search query (default: 'project memory context').")
    parser.add_argument("-k", "--top_k", type=int, default=5,
                        help="Number of top results to return (default: 5).")
    # Example of adding a filter based on metadata type
    parser.add_argument("--type", help="Filter results by type (e.g., 'task', 'snippet', 'note').")

    args = parser.parse_args()

    # Load config to potentially get default search parameters if needed in future
    try:
        cfg = load_cfg()
    except Exception as e:
        logging.error(f"Could not load configuration, using defaults for search: {e}")
        # cfg = {} # Or use memory_utils.DEFAULT_CFG

    print(f"Searching for: \"{args.query}\" (top {args.top_k})")

    predicate = None
    if args.type:
        def type_predicate(meta_item):
            return meta_item.get("type") == args.type
        predicate = type_predicate
        print(f"Filtering by type: {args.type}")

    try:
        results = search(args.query, top_k=args.top_k, pred=predicate)
    except Exception as e:
        logging.critical(f"Search operation failed: {e}", exc_info=True)
        print(f"❌ Search failed. Check logs for details.")
        sys.exit(1)

    if not results:
        print("No results found.")
        return

    print("\nSearch Results:")
    print("=" * 30)
    for i, (meta, dist) in enumerate(results):
        item_type = meta.get('type', 'unknown')
        item_id = meta.get('id', 'N/A')

        display_text = ""
        if item_type == "task":
            display_text = f"Task #{meta.get('id','?')}: {meta.get('title', 'No Title')} (Status: {meta.get('status','?')}, Progress: {meta.get('progress',0)}%)"
        elif item_type == "snippet":
            # 'text' in snippet meta is pre-formatted with ```
            # For console display, maybe show raw_content or a summary
            raw_content = meta.get('raw_content', meta.get('text', ''))
            display_text = f"Snippet (lang: {meta.get('language','?')}, source: {meta.get('source','N/A')}):\n"
            display_text += textwrap.indent(textwrap.shorten(raw_content, width=100, placeholder="... (truncated) ..."), "  ")
        elif item_type == "note":
            display_text = f"Note (ID: {item_id}): {textwrap.shorten(meta.get('text', ''), width=100, placeholder='...')}"
        else: # Generic display
            display_text = meta.get('text', meta.get('title', f"Item ID {item_id} of type {item_type}"))
            display_text = textwrap.shorten(display_text, width=100, placeholder="...")

        print(f"{i+1}. Distance: {dist:.4f} | Type: {item_type}")
        print(f"   {display_text}")
        print("-" * 30)

if __name__ == "__main__":
    main()