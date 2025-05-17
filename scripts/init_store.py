#!/usr/bin/env python
"""
Initializes the vector store (.cursor/vecstore) if it doesn't exist.
"""
import logging
import sys
from memory_utils import _ensure_store # underscore implies protected, but used here for init

# ───────────────────────────────────────── Logging Setup ────
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def main():
    try:
        _ensure_store()
        print("✅ vecstore initialized/verified (.cursor/vecstore)")
    except Exception as e:
        logging.critical(f"Failed to initialize vector store: {e}", exc_info=True)
        print(f"❌ Error initializing vector store. Check logs.")
        sys.exit(1)

if __name__ == "__main__":
    main()