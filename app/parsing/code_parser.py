# import os
# import re
# from typing import List, Dict, Any
# from app.parsing.chunk_utils import chunk_text
# from app.utils.logger import get_logger

# logger = get_logger(__name__)

# def parse_code_files(file_paths: List[str], repo_path: str) -> List[Dict[str, Any]]:
#     """
#     Reads code files and splits them into chunks.
#     Attaches metadata (file name, path, function/class name if possible).
#     """
#     all_chunks = []
    
#     for file_path in file_paths:
#         try:
#             with open(file_path, 'r', encoding='utf-8') as f:
#                 content = f.read()
#         except Exception as e:
#             logger.warning(f"Failed to read file {file_path}: {e}")
#             continue
            
#         if not content.strip():
#             continue

#         if len(content) > 50000:
#             logger.warning(f"Skipping large file: {file_path}")
#             continue

            
#         relative_path = os.path.relpath(file_path, repo_path)
#         file_name = os.path.basename(file_path)
        
#         # Simple heuristic to extract functions/classes for python
#         # A more robust approach would use Tree-sitter, but regex is simpler and meets "simple, readable implementations"
        
#         if file_path.endswith('.py'):
#             chunks = _parse_python_file(content, relative_path, file_name)
#             all_chunks.extend(chunks)
#         else:
#             # Fallback for other languages: fixed-size chunking
#             # raw_chunks = chunk_text(content, max_chunk_size=1500, overlap=300)
#             raw_chunks = chunk_text(content, max_chunk_size=500, overlap=50)
#             for i, text in enumerate(raw_chunks):
#                 all_chunks.append({
#                     "text": text,
#                     "metadata": {
#                         "file_name": file_name,
#                         "path": relative_path,
#                         "entity_name": f"chunk_{i}"
#                     }
#                 })
#     # Limit chunks to avoid memory issues
#     all_chunks = all_chunks[:50]

#     logger.info(f"Generated {len(all_chunks)} chunks from {len(file_paths)} files.")
#     return all_chunks

# def _parse_python_file(content: str, path: str, file_name: str) -> List[Dict[str, Any]]:
#     """
#     Simple parser for python files that tries to chunk by function/class.
#     """
#     # Split by def or class at the start of a line
#     pattern = re.compile(r'^(?=def |class )', re.MULTILINE)
#     parts = pattern.split(content)
    
#     chunks = []
    
#     # The first part might be module-level code/imports
#     if parts and parts[0].strip():
#         # Fallback to text chunking for large module level code
#         module_chunks = chunk_text(parts[0], max_chunk_size=1500)
#         for i, text in enumerate(module_chunks):
#             chunks.append({
#                 "text": text,
#                 "metadata": {
#                     "file_name": file_name,
#                     "path": path,
#                     "entity_name": "module_level"
#                 }
#             })
            
#     for part in parts[1:]:
#         if not part.strip():
#             continue
            
#         # Extract name
#         first_line = part.split('\\n')[0]
#         entity_name = "unknown"
#         match = re.match(r'(?:def|class)\s+([a-zA-Z0-9_]+)', first_line)
#         if match:
#             entity_name = match.group(1)
            
#         # If the function/class is too large, chunk it further
#         part_chunks = chunk_text(part, max_chunk_size=2000, overlap=200)
#         for i, text in enumerate(part_chunks):
#             name = entity_name if i == 0 else f"{entity_name}_part{i}"
#             chunks.append({
#                 "text": text,
#                 "metadata": {
#                     "file_name": file_name,
#                     "path": path,
#                     "entity_name": name
#                 }
#             })
            
#     return chunks


import os
from typing import List, Dict, Any
from app.utils.logger import get_logger

logger = get_logger(__name__)

def parse_code_files(file_paths: List[str], repo_path: str) -> List[Dict[str, Any]]:
    """
    Simplified parser: Treat each file as a single chunk.
    This avoids memory issues and ensures stability.
    """
    all_chunks = []

    # Limit number of files processed (safety)
    file_paths = file_paths[:3]

    for file_path in file_paths:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            logger.warning(f"Failed to read file {file_path}: {e}")
            continue

        if not content.strip():
            continue

        # HARD LIMIT content size (very important)
        content = content[:20000]

        relative_path = os.path.relpath(file_path, repo_path)
        file_name = os.path.basename(file_path)

        chunk = {
            "text": content,
            "metadata": {
                "file_name": file_name,
                "path": relative_path,
                "entity_name": "full_file"
            }
        }

        all_chunks.append(chunk)

    logger.info(f"Generated {len(all_chunks)} chunks from {len(file_paths)} files.")
    return all_chunks