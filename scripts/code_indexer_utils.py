"""
Utilities for chunking code files for indexing in the vector store.
"""
import pathlib
import re
import hashlib
import tokenize
import io
import logging
from typing import List, Dict, Tuple, Optional, Any

try:
    # Try direct import
    from memex.scripts.memory_utils import generate_chunk_id
except ImportError:
    try:
        # Try relative import
        from .memory_utils import generate_chunk_id
    except ImportError:
        # Fall back to direct path
        from memory_utils import generate_chunk_id


def _calculate_content_hash(content: str) -> str:
    """Calculate a hash of the content for deduplication."""
    return hashlib.md5(content.encode()).hexdigest()[:8]


def chunk_python_file(file_path: str, min_lines: int = 5, max_lines: int = 100) -> List[Dict[str, Any]]:
    """
    Chunk a Python file into semantically meaningful chunks (functions, classes, etc.).
    
    Args:
        file_path: Path to the Python file
        min_lines: Minimum number of lines for a chunk
        max_lines: Maximum number of lines for a chunk
        
    Returns:
        List of dictionaries with chunk metadata: {
            id: str,
            type: "code_chunk",
            source_file: str,
            language: "python",
            start_line: int,
            end_line: int,
            name: str (function/class name if available),
            content: str
        }
    """
    try:
        path = pathlib.Path(file_path)
        if not path.exists():
            logging.error(f"File not found: {file_path}")
            return []
            
        with open(path, 'r', encoding='utf-8') as f:
            file_content = f.read()
        
        chunks = []
        
        # Use tokenize to find functions and classes
        # This is more robust than regex for Python
        tokens = list(tokenize.tokenize(io.BytesIO(file_content.encode('utf-8')).readline))
        
        # First pass - collect all function/class definitions
        definitions = []
        for i, token in enumerate(tokens):
            if token.type == tokenize.NAME and token.string in ('def', 'class'):
                if i + 2 < len(tokens) and tokens[i+1].type == tokenize.NAME:
                    # Found a function or class definition
                    name = tokens[i+1].string
                    start_line = token.start[0]
                    
                    # Find the end by tracking indentation
                    indentation = 0  # Will be set to the actual indentation
                    end_line = start_line
                    
                    # Scan ahead to find the end of the block
                    found_end = False
                    for j in range(i+1, len(tokens)):
                        if tokens[j].type == tokenize.INDENT:
                            indentation += 1
                        elif tokens[j].type == tokenize.DEDENT:
                            indentation -= 1
                            if indentation <= 0:
                                end_line = tokens[j].start[0]
                                found_end = True
                                break
                        else:
                            end_line = tokens[j].start[0]
                    
                    if not found_end:
                        end_line = tokens[-1].start[0]  # End of file
                    
                    # Create a definition record
                    def_type = "function" if token.string == "def" else "class"
                    definitions.append({
                        "type": def_type,
                        "name": name,
                        "start_line": start_line,
                        "end_line": end_line
                    })
        
        # If no definitions were found or file is short, create a single chunk
        file_lines = file_content.split('\n')
        if not definitions or len(file_lines) <= max_lines:
            content = file_content
            chunk_id = generate_chunk_id(
                str(path),
                1,
                len(file_lines),
                _calculate_content_hash(content)
            )
            chunks.append({
                "id": chunk_id,
                "type": "code_chunk",
                "source_file": str(path),
                "language": "python",
                "start_line": 1,
                "end_line": len(file_lines),
                "name": path.name,
                "content": content
            })
            return chunks
        
        # Process each definition
        for defn in definitions:
            # Skip if it's too small
            if defn["end_line"] - defn["start_line"] < min_lines:
                continue
                
            # Split if it's too large
            if defn["end_line"] - defn["start_line"] > max_lines:
                # TODO: Implement smarter splitting of large functions/classes
                # For now, we'll just take chunks of max_lines
                start = defn["start_line"]
                while start < defn["end_line"]:
                    end = min(start + max_lines, defn["end_line"])
                    
                    chunk_lines = file_lines[start-1:end]
                    content = '\n'.join(chunk_lines)
                    
                    chunk_id = generate_chunk_id(
                        str(path),
                        start,
                        end,
                        _calculate_content_hash(content)
                    )
                    
                    chunk_name = f"{defn['name']} (part {(start-defn['start_line'])//max_lines+1})"
                    
                    chunks.append({
                        "id": chunk_id,
                        "type": "code_chunk",
                        "source_file": str(path),
                        "language": "python",
                        "start_line": start,
                        "end_line": end,
                        "name": chunk_name,
                        "content": content
                    })
                    
                    start = end + 1
            else:
                # Use the definition as is
                chunk_lines = file_lines[defn["start_line"]-1:defn["end_line"]]
                content = '\n'.join(chunk_lines)
                
                chunk_id = generate_chunk_id(
                    str(path),
                    defn["start_line"],
                    defn["end_line"],
                    _calculate_content_hash(content)
                )
                
                chunks.append({
                    "id": chunk_id,
                    "type": "code_chunk",
                    "source_file": str(path),
                    "language": "python",
                    "start_line": defn["start_line"],
                    "end_line": defn["end_line"],
                    "name": defn["name"],
                    "content": content
                })
        
        # Process module-level code more intelligently
        # Sort definitions by start_line
        sorted_defns = sorted(definitions, key=lambda d: d["start_line"])
        
        # Helper function to analyze module-level code content
        def analyze_module_code(lines):
            """Analyze module-level code to determine its type and appropriate name."""
            content = '\n'.join(lines)
            non_empty_lines = [line for line in lines if line.strip()]
            
            if not non_empty_lines:
                return "empty", False
            
            # Check for imports
            import_lines = [line for line in non_empty_lines if line.strip().startswith(('import ', 'from '))]
            import_count = len(import_lines)
            
            # Check for constants (UPPER_CASE variables)
            constant_pattern = re.compile(r'^[A-Z_]+\s*=')
            constant_lines = [line for line in non_empty_lines if constant_pattern.match(line.strip())]
            constant_count = len(constant_lines)
            
            # Check for type annotations/aliases
            type_pattern = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*\s*:\s*[A-Za-z_]')
            has_type_annotations = any(type_pattern.match(line.strip()) for line in non_empty_lines)
            
            # Check for main block
            has_main = any('if __name__' in line and '__main__' in line for line in lines)
            
            # Check for decorators at module level
            has_decorators = any(line.strip().startswith('@') for line in non_empty_lines)
            
            # Check for docstrings
            first_non_empty = non_empty_lines[0].strip() if non_empty_lines else ""
            has_module_docstring = first_non_empty.startswith(('"""', "'''"))
            
            # Check for global variable initialization
            global_var_pattern = re.compile(r'^[a-z_][a-z0-9_]*\s*=')
            global_var_count = sum(1 for line in non_empty_lines if global_var_pattern.match(line.strip()))
            
            # Determine primary type and name
            total_lines = len(non_empty_lines)
            
            if has_main:
                return "main_execution", True
            elif has_module_docstring and total_lines <= 10:
                return "module_docstring", True
            elif import_count > 0 and import_count >= total_lines * 0.6:  # Mostly imports
                return "imports", True
            elif constant_count > 0 and constant_count >= total_lines * 0.4:  # Mostly constants
                return "constants_and_config", True
            elif has_type_annotations:
                return "type_definitions", True
            elif global_var_count >= total_lines * 0.5:  # Mostly global variables
                return "global_variables", True
            elif has_decorators:
                return "decorator_definitions", True
            else:
                # Try to be more specific based on content
                if import_count > 0 and constant_count > 0:
                    return "imports_and_config", True
                elif import_count > 0:
                    return "module_imports", False
                elif constant_count > 0:
                    return "module_constants", False
                else:
                    return "module_setup", False
        
        # Process module-level code sections
        module_sections = []
        
        # Check for content before the first definition
        if sorted_defns:
            first_def_start = sorted_defns[0]["start_line"]
            if first_def_start > 1:
                module_sections.append({
                    "start": 1,
                    "end": first_def_start - 1,
                    "after": None
                })
        
        # Check for gaps between definitions
        for i in range(len(sorted_defns)):
            current_def = sorted_defns[i]
            current_end = current_def["end_line"]
            
            if i < len(sorted_defns) - 1:
                next_start = sorted_defns[i+1]["start_line"]
                if next_start - current_end > 1:  # There's a gap
                    module_sections.append({
                        "start": current_end + 1,
                        "end": next_start - 1,
                        "after": current_def["name"]
                    })
            else:
                # Check for content after the last definition
                if current_end < len(file_lines):
                    module_sections.append({
                        "start": current_end + 1,
                        "end": len(file_lines),
                        "after": current_def["name"]
                    })
        
        # Process each module section intelligently
        for section in module_sections:
            section_lines = file_lines[section["start"]-1:section["end"]]
            
            # Skip empty sections
            if not any(line.strip() for line in section_lines):
                continue
            
            # For small sections, check if they should be merged with adjacent chunks
            if len(section_lines) < min_lines:
                # Check if it contains important patterns that warrant separate chunking
                important_patterns = [
                    'if __name__',
                    re.compile(r'^(def|class)\s+')  # Nested definitions
                ]
                
                has_critical_code = any(
                    any(
                        pattern.search(line) if hasattr(pattern, 'search') else pattern in line
                        for pattern in important_patterns
                    )
                    for line in section_lines
                )
                
                if has_critical_code:
                    # Keep as separate chunk despite being small
                    pass
                else:
                    # Skip for now, will be handled by merging logic
                    continue
            
            # Analyze the content
            section_type, is_primary = analyze_module_code(section_lines)
            
            # Determine the chunk name
            if section_type == "main_execution":
                chunk_name = "main_execution_block"
            elif section_type == "module_docstring":
                chunk_name = "module_documentation"
            elif section_type == "imports":
                chunk_name = "module_imports"
            elif section_type == "constants_and_config":
                chunk_name = "constants_and_configuration"
            elif section_type == "type_definitions":
                chunk_name = "type_definitions"
            elif section_type == "global_variables":
                chunk_name = "global_variables"
            elif section_type == "decorator_definitions":
                chunk_name = "decorator_definitions"
            elif section_type == "imports_and_config":
                chunk_name = "imports_and_configuration"
            elif section_type == "module_imports":
                chunk_name = "additional_imports"
            elif section_type == "module_constants":
                chunk_name = "additional_constants"
            elif section_type == "empty":
                continue  # Skip empty sections
            else:
                # For generic module setup, try to provide context
                if section["after"]:
                    chunk_name = f"module_code_after_{section['after']}"
                elif section["start"] == 1:
                    chunk_name = "module_header"
                else:
                    chunk_name = "module_code"
            
            # Create the chunk
            content = '\n'.join(section_lines)
            chunk_id = generate_chunk_id(
                str(path),
                section["start"],
                section["end"],
                _calculate_content_hash(content)
            )
            
            chunks.append({
                "id": chunk_id,
                "type": "code_chunk",
                "source_file": str(path),
                "language": "python",
                "start_line": section["start"],
                "end_line": section["end"],
                "name": chunk_name,
                "content": content,
                "metadata": {
                    "section_type": section_type,
                    "is_primary_type": is_primary
                }
            })
        
        # Post-process chunks to merge related sections
        merged_chunks = []
        i = 0
        while i < len(chunks):
            current_chunk = chunks[i]
            
            # Check if this is an import-related chunk that could be merged
            if i < len(chunks) - 1 and current_chunk.get("metadata", {}).get("section_type") in ["imports", "module_imports"]:
                next_chunk = chunks[i + 1]
                
                # Check if next chunk is also import-related and adjacent
                if (next_chunk.get("metadata", {}).get("section_type") in ["imports", "module_imports", "imports_and_config"] and
                    current_chunk["end_line"] + 1 >= next_chunk["start_line"] - 2):  # Allow for small gaps
                    
                    # Merge the chunks
                    merged_lines = file_lines[current_chunk["start_line"]-1:next_chunk["end_line"]]
                    merged_content = '\n'.join(merged_lines)
                    
                    merged_chunk = {
                        "id": generate_chunk_id(
                            str(path),
                            current_chunk["start_line"],
                            next_chunk["end_line"],
                            _calculate_content_hash(merged_content)
                        ),
                        "type": "code_chunk",
                        "source_file": str(path),
                        "language": "python",
                        "start_line": current_chunk["start_line"],
                        "end_line": next_chunk["end_line"],
                        "name": "module_imports_and_setup",
                        "content": merged_content,
                        "metadata": {
                            "section_type": "imports_and_setup",
                            "is_primary_type": True
                        }
                    }
                    merged_chunks.append(merged_chunk)
                    i += 2  # Skip the next chunk since we merged it
                    continue
            
            # No merging needed, keep the chunk as is
            merged_chunks.append(current_chunk)
            i += 1
        
        return merged_chunks
        
    except Exception as e:
        logging.error(f"Error chunking Python file {file_path}: {e}")
        return []


def chunk_markdown_file(file_path: str, min_lines: int = 5, max_lines: int = 100) -> List[Dict[str, Any]]:
    """
    Chunk a Markdown file into sections based on headings.
    
    Args:
        file_path: Path to the Markdown file
        min_lines: Minimum number of lines for a chunk
        max_lines: Maximum number of lines for a chunk
        
    Returns:
        List of dictionaries with chunk metadata
    """
    try:
        path = pathlib.Path(file_path)
        if not path.exists():
            logging.error(f"File not found: {file_path}")
            return []
            
        with open(path, 'r', encoding='utf-8') as f:
            file_content = f.read()
        
        chunks = []
        file_lines = file_content.split('\n')
        
        # If file is small enough, return it as a single chunk
        if len(file_lines) <= max_lines:
            chunk_id = generate_chunk_id(
                str(path),
                1,
                len(file_lines),
                _calculate_content_hash(file_content)
            )
            chunks.append({
                "id": chunk_id,
                "type": "code_chunk",
                "source_file": str(path),
                "language": "markdown",
                "start_line": 1,
                "end_line": len(file_lines),
                "name": path.name,
                "content": file_content
            })
            return chunks
        
        # Find all headings
        heading_pattern = re.compile(r'^(#{1,6})\s+(.+)$', re.MULTILINE)
        headings = []
        
        for i, line in enumerate(file_lines):
            match = heading_pattern.match(line)
            if match:
                level = len(match.group(1))
                title = match.group(2).strip()
                headings.append({
                    "level": level,
                    "title": title,
                    "line": i + 1
                })
        
        # If no headings found, split by size
        if not headings:
            start_line = 1
            while start_line <= len(file_lines):
                end_line = min(start_line + max_lines - 1, len(file_lines))
                
                chunk_lines = file_lines[start_line-1:end_line]
                content = '\n'.join(chunk_lines)
                
                chunk_id = generate_chunk_id(
                    str(path),
                    start_line,
                    end_line,
                    _calculate_content_hash(content)
                )
                
                chunks.append({
                    "id": chunk_id,
                    "type": "code_chunk",
                    "source_file": str(path),
                    "language": "markdown",
                    "start_line": start_line,
                    "end_line": end_line,
                    "name": f"{path.name} (part {(start_line-1)//max_lines+1})",
                    "content": content
                })
                
                start_line = end_line + 1
        else:
            # Process content before first heading if it's substantial
            if headings[0]["line"] > min_lines:
                start_line = 1
                end_line = headings[0]["line"] - 1
                
                chunk_lines = file_lines[start_line-1:end_line]
                content = '\n'.join(chunk_lines)
                
                chunk_id = generate_chunk_id(
                    str(path),
                    start_line,
                    end_line,
                    _calculate_content_hash(content)
                )
                
                chunks.append({
                    "id": chunk_id,
                    "type": "code_chunk",
                    "source_file": str(path),
                    "language": "markdown",
                    "start_line": start_line,
                    "end_line": end_line,
                    "name": "Introduction",
                    "content": content
                })
            
            # Process each section
            for i in range(len(headings)):
                start_line = headings[i]["line"]
                end_line = headings[i+1]["line"] - 1 if i < len(headings) - 1 else len(file_lines)
                
                # Skip if section is too small
                if end_line - start_line + 1 < min_lines:
                    continue
                
                # Split if section is too large
                if end_line - start_line + 1 > max_lines:
                    section_start = start_line
                    while section_start <= end_line:
                        section_end = min(section_start + max_lines - 1, end_line)
                        
                        chunk_lines = file_lines[section_start-1:section_end]
                        content = '\n'.join(chunk_lines)
                        
                        part_num = (section_start - start_line) // max_lines + 1
                        section_name = (
                            f"{headings[i]['title']} (part {part_num})" 
                            if part_num > 1 else headings[i]['title']
                        )
                        
                        chunk_id = generate_chunk_id(
                            str(path),
                            section_start,
                            section_end,
                            _calculate_content_hash(content)
                        )
                        
                        chunks.append({
                            "id": chunk_id,
                            "type": "code_chunk",
                            "source_file": str(path),
                            "language": "markdown",
                            "start_line": section_start,
                            "end_line": section_end,
                            "name": section_name,
                            "content": content
                        })
                        
                        section_start = section_end + 1
                else:
                    # Use section as is
                    chunk_lines = file_lines[start_line-1:end_line]
                    content = '\n'.join(chunk_lines)
                    
                    chunk_id = generate_chunk_id(
                        str(path),
                        start_line,
                        end_line,
                        _calculate_content_hash(content)
                    )
                    
                    chunks.append({
                        "id": chunk_id,
                        "type": "code_chunk",
                        "source_file": str(path),
                        "language": "markdown",
                        "start_line": start_line,
                        "end_line": end_line,
                        "name": headings[i]["title"],
                        "content": content
                    })
        
        return chunks
        
    except Exception as e:
        logging.error(f"Error chunking Markdown file {file_path}: {e}")
        return []


def chunk_text_file(file_path: str, min_lines: int = 5, max_lines: int = 100) -> List[Dict[str, Any]]:
    """
    Chunk a generic text file by paragraphs or fixed line count.
    
    Args:
        file_path: Path to the text file
        min_lines: Minimum number of lines for a chunk
        max_lines: Maximum number of lines for a chunk
        
    Returns:
        List of dictionaries with chunk metadata
    """
    try:
        path = pathlib.Path(file_path)
        if not path.exists():
            logging.error(f"File not found: {file_path}")
            return []
            
        with open(path, 'r', encoding='utf-8') as f:
            file_content = f.read()
        
        # Determine language based on file extension
        extension = path.suffix.lower()
        language_map = {
            '.js': 'javascript',
            '.ts': 'typescript',
            '.py': 'python',
            '.java': 'java',
            '.c': 'c',
            '.cpp': 'cpp',
            '.h': 'cpp',
            '.html': 'html',
            '.css': 'css',
            '.md': 'markdown',
            '.json': 'json',
            '.xml': 'xml',
            '.yaml': 'yaml',
            '.yml': 'yaml',
            '.sh': 'bash',
            '.bat': 'batch',
            '.ps1': 'powershell',
            '.sql': 'sql',
            '.rb': 'ruby',
            '.go': 'go',
            '.rs': 'rust',
            '.php': 'php'
        }
        language = language_map.get(extension, 'text')
        
        # For Python files, use the specialized chunker
        if language == 'python':
            return chunk_python_file(file_path, min_lines, max_lines)
            
        # For Markdown files, use the specialized chunker
        if language == 'markdown':
            return chunk_markdown_file(file_path, min_lines, max_lines)
            
        # Generic chunking by fixed line count
        chunks = []
        file_lines = file_content.split('\n')
        
        # If file is small enough, return it as a single chunk
        if len(file_lines) <= max_lines:
            chunk_id = generate_chunk_id(
                str(path),
                1,
                len(file_lines),
                _calculate_content_hash(file_content)
            )
            chunks.append({
                "id": chunk_id,
                "type": "code_chunk",
                "source_file": str(path),
                "language": language,
                "start_line": 1,
                "end_line": len(file_lines),
                "name": path.name,
                "content": file_content
            })
            return chunks
        
        # Chunk by fixed line count
        start_line = 1
        while start_line <= len(file_lines):
            end_line = min(start_line + max_lines - 1, len(file_lines))
            
            chunk_lines = file_lines[start_line-1:end_line]
            content = '\n'.join(chunk_lines)
            
            # Skip if too small (except for the last chunk)
            if end_line < len(file_lines) and end_line - start_line + 1 < min_lines:
                start_line = end_line + 1
                continue
                
            chunk_id = generate_chunk_id(
                str(path),
                start_line,
                end_line,
                _calculate_content_hash(content)
            )
            
            chunks.append({
                "id": chunk_id,
                "type": "code_chunk",
                "source_file": str(path),
                "language": language,
                "start_line": start_line,
                "end_line": end_line,
                "name": f"{path.name} (lines {start_line}-{end_line})",
                "content": content
            })
            
            start_line = end_line + 1
        
        return chunks
        
    except Exception as e:
        logging.error(f"Error chunking text file {file_path}: {e}")
        return []


def get_chunker_for_file(file_path: str) -> Optional[callable]:
    """
    Get the appropriate chunker function for a file based on its extension.
    
    Args:
        file_path: Path to the file
        
    Returns:
        Chunker function or None if no suitable chunker is found
    """
    path = pathlib.Path(file_path)
    extension = path.suffix.lower()
    
    if extension == '.py':
        return chunk_python_file
    elif extension == '.md':
        return chunk_markdown_file
    else:
        return chunk_text_file 