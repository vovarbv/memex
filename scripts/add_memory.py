#!/usr/bin/env python
"""
Saves arbitrary text (note/fact) to memory.
"""
import sys
import datetime as dt
import uuid
import logging
import argparse

from thread_safe_store import add_or_replace

# ───────────────────────────────────────── Logging Setup ────
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def add_memory_item_logic(text_content: str, item_type: str = "note", custom_id: str | None = None) -> str | None:
    """
    Core logic for adding a memory item (note, fact, etc.)
    
    Args:
        text_content: The text to save
        item_type: Type of memory item (default: "note")
        custom_id: Optional custom ID (default: generated UUID)
    
    Returns:
        The ID of the added item, or None if addition failed
    """
    if not text_content.strip():
        logging.error("Attempted to add empty memory item.")
        return None

    # Use provided ID or generate a UUID
    memory_id = custom_id if custom_id else str(uuid.uuid4())

    # The text to be embedded
    embedding_text = text_content

    meta = {
        "type": item_type,
        "text": text_content,  # The original text for display or mdc
        "timestamp": dt.datetime.utcnow().isoformat(),
        "id": memory_id  # Store the ID in metadata as well
    }

    try:
        # add_or_replace can handle string IDs for metadata and FAISS ID generation
        returned_id = add_or_replace(memory_id, embedding_text, meta)
        if returned_id:
            logging.info(f"Memory item added/updated with ID: {returned_id}")
            return returned_id
        else:
            logging.error("Failed to add memory item.")
            return None
    except Exception as e:
        logging.critical(f"An unexpected error occurred while adding memory: {e}", exc_info=True)
        return None

def main():
    parser = argparse.ArgumentParser(description="Saves arbitrary text (note/fact) to memory.")
    parser.add_argument("text_content", help="The text to save.")
    parser.add_argument("--id", help="Optional custom ID for this memory item (default: UUID).")
    parser.add_argument("--type", default="note", help="Type of memory item (e.g., 'note', 'fact', 'reminder').")

    args = parser.parse_args()

    returned_id = add_memory_item_logic(args.text_content, args.type, args.id)
    
    if returned_id:
        print(f"✅ Memory item added/updated with ID: {returned_id}")
    else:
        print(f"❌ Failed to add memory item. Check logs.")
        sys.exit(1)

if __name__ == "__main__":
    main()