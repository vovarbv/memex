#!/usr/bin/env python
"""
Сохраняет произвольный текст (заметка/факт) в память.
"""
import sys
import datetime as dt
import uuid
import logging
import argparse

from memory_utils import add_or_replace

# ───────────────────────────────────────── Logging Setup ────
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def main():
    parser = argparse.ArgumentParser(description="Saves arbitrary text (note/fact) to memory.")
    parser.add_argument("text_content", help="The text to save.")
    parser.add_argument("--id", help="Optional custom ID for this memory item (default: UUID).")
    parser.add_argument("--type", default="note", help="Type of memory item (e.g., 'note', 'fact', 'reminder').")

    args = parser.parse_args()

    if not args.text_content.strip():
        print("Error: Text content cannot be empty.")
        logging.error("Attempted to add empty memory item.")
        sys.exit(1)

    # Use provided ID or generate a UUID. This will be a string.
    memory_id = args.id if args.id else str(uuid.uuid4())

    # The text to be embedded can be just the content or more descriptive
    embedding_text = args.text_content

    meta = {
        "type": args.type,
        "text": args.text_content, # The original text for display or mdc
        "timestamp": dt.datetime.utcnow().isoformat(),
        "id": memory_id # Store the ID in metadata as well
    }

    try:
        # add_or_replace can handle string IDs for metadata and FAISS ID generation
        returned_id = add_or_replace(memory_id, embedding_text, meta)
        if returned_id:
            print(f"✅ Memory item added/updated with ID: {returned_id}")
        else:
            print(f"❌ Failed to add memory item. Check logs.")
            sys.exit(1)
    except Exception as e:
        logging.critical(f"An unexpected error occurred while adding memory: {e}", exc_info=True)
        print(f"❌ An unexpected error occurred. Check logs for details.")
        sys.exit(1)


if __name__ == "__main__":
    main()