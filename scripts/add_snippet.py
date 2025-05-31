#!/usr/bin/env python
"""
Saves a code snippet to memory.
Usage:
    python scripts/add_snippet.py "print('Hello, World!')" --lang py
    python scripts/add_snippet.py --from path/to/your/file.py:20-45
    python scripts/add_snippet.py --from path/to/your/file.txt # Whole file as snippet
"""
import re
import sys
import pathlib
import datetime as dt
import logging
import argparse
import uuid

from memory_utils import ROOT
from thread_safe_store import add_or_replace

# ───────────────────────────────────────── Logging Setup ────
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def load_from_file(spec: str) -> tuple[str, str | None, str | None]:
    """
    Loads snippet from file specification.
    Spec format: path/to/file.py[:start_line[-end_line]]
    Returns (content, file_path_str, language_or_None)
    """
    file_path_str = spec
    lang = None

    line_range_match = re.match(r"(.+?):(\d+)(?:-(\d+))?$", spec)

    if line_range_match:
        path_str, start_line_str, end_line_str = line_range_match.groups()
        path = pathlib.Path(path_str)
        start_line = int(start_line_str)
        end_line = int(end_line_str) if end_line_str else start_line
        file_path_str = path_str # Store original path string for metadata

        if not path.is_file():
            raise FileNotFoundError(f"File not found: {path}")

        try:
            lines = path.read_text(encoding="utf-8").splitlines()
            # Adjust for 0-based indexing and inclusive end_line
            snippet_lines = lines[start_line-1:end_line]
            text_content = "\n".join(snippet_lines)
            lang = path.suffix.lstrip(".") if path.suffix else None
            return text_content, file_path_str, lang
        except Exception as e:
            raise ValueError(f"Error reading lines from {path}: {e}")

    else: # Treat spec as just a file path for the whole file
        path = pathlib.Path(spec)
        if not path.is_file():
            raise FileNotFoundError(f"File not found: {path}")
        try:
            text_content = path.read_text(encoding="utf-8")
            lang = path.suffix.lstrip(".") if path.suffix else None
            return text_content, str(path), lang
        except Exception as e:
            raise ValueError(f"Error reading file {path}: {e}")

def add_snippet_logic(content: str, lang: str = "text", source_desc: str = "manual", 
                      custom_id: str | None = None, source_file_path: str | None = None) -> str | None:
    """
    Core logic for adding a snippet to memory.
    
    Args:
        content: The content of the snippet
        lang: Language of the snippet (default: "text")
        source_desc: Description of the source (default: "manual")
        custom_id: Optional custom ID (default: generated UUID)
        source_file_path: Optional path to source file
    
    Returns:
        The ID of the added snippet, or None if addition failed
    """
    try:
        if not content.strip():
            logging.error("Attempted to add empty snippet")
            return None
            
        final_lang = lang or "text"  # Default to "text"
        formatted_snippet_for_mdc = f"```{final_lang}\n{content}\n```"
        
        snippet_id = custom_id or str(uuid.uuid4())
        
        # If source_file_path is provided but source_desc is still "manual", use the file path
        if source_file_path and source_desc == "manual":
            source_desc = source_file_path
            
        meta = {
            "type": "snippet",
            "text": formatted_snippet_for_mdc,  # This is what gen_memory_mdc will use
            "raw_content": content,  # Store raw content separately if needed
            "language": final_lang,
            "source": source_desc,
            "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(),
            "id": snippet_id  # Store the ID also in metadata for easier lookup
        }
        
        # The text for embedding could be just content, or include more context
        embedding_text = f"Code snippet ({final_lang}):\n{content}"
        
        returned_id = add_or_replace(snippet_id, embedding_text, meta)
        
        if returned_id:
            logging.info(f"Snippet stored with ID: {returned_id}")
            return returned_id
        else:
            logging.error("Failed to store snippet")
            return None
            
    except Exception as e:
        logging.critical(f"An unexpected error occurred while adding snippet: {e}", exc_info=True)
        return None


def main():
    parser = argparse.ArgumentParser(description="Adds a code snippet to the memory.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("snippet_text", nargs="?", help="The text of the snippet.")
    group.add_argument("--from", dest="from_spec", metavar="FILE[:START[-END]]",
                       help="Load snippet from a file or a specific line range (e.g., src/app.py:20-45).")

    parser.add_argument("--lang", help="Language of the snippet (e.g., 'py', 'js'). Auto-detected if --from is used with common extensions.")
    parser.add_argument("--source", help="Optional source description (e.g., 'manual', 'IDE selection').")
    parser.add_argument("--id", help="Optional custom ID for the snippet (default: UUID).")

    args = parser.parse_args()

    snippet_content: str
    source_file: str | None = None
    detected_lang: str | None = None

    try:
        if args.from_spec:
            snippet_content, source_file, detected_lang = load_from_file(args.from_spec)
            if not args.source and source_file:
                args.source = source_file # Use file path as source if not provided
        elif args.snippet_text:
            snippet_content = args.snippet_text
        else:
            # Should not happen due to mutually_exclusive_group being required
            parser.error("Either snippet_text or --from must be provided.")
            return # For linters

        final_lang = args.lang or detected_lang or "text" # Default to "text"
        
        returned_id = add_snippet_logic(
            content=snippet_content, 
            lang=final_lang, 
            source_desc=args.source or ("manual" if args.snippet_text else "file import"),
            custom_id=args.id,
            source_file_path=source_file
        )

        if returned_id:
            print(f"✅ Snippet stored with ID: {returned_id}")
            if source_file:
                print(f"   Source: {source_file}")
            print(f"   Language: {final_lang}")
        else:
            print("❌ Failed to store snippet. Check logs.")
            sys.exit(1)

    except FileNotFoundError as e:
        logging.error(f"Error: {e}")
        print(f"❌ Error: {e}")
        sys.exit(1)
    except ValueError as e:
        logging.error(f"Error: {e}")
        print(f"❌ Error: {e}")
        sys.exit(1)
    except Exception as e:
        logging.critical(f"An unexpected error occurred: {e}", exc_info=True)
        print(f"❌ An unexpected error occurred. Check logs for details.")
        sys.exit(1)

if __name__ == "__main__":
    main()