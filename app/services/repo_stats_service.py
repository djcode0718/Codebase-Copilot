import os
import json
from app.config import INDEX_DIR
from app.indexing.index_builder import _get_chroma_collection
from app.utils.logger import get_logger

logger = get_logger(__name__)


def get_repo_stats(index_name: str) -> dict:
    """
    Directly query the codebase context file structure, ChromaDB collection,
    and relationship graph to return repository-wide statistics.
    NO LLM calls, NO vector search.
    """
    context_path = os.path.join(INDEX_DIR, index_name, "codebase_context.txt")
    files = []
    if os.path.exists(context_path):
        try:
            with open(context_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            
            in_structure = False
            for line in lines:
                if line.startswith("## Project File Structure"):
                    in_structure = True
                    continue
                if in_structure:
                    if line.startswith("##"):
                        break
                    stripped = line.strip()
                    if stripped:
                        files.append(stripped)
        except Exception as e:
            logger.warning(f"Failed to read codebase context structure for {index_name}: {e}")

    chunk_count = 0
    try:
        _, collection = _get_chroma_collection(index_name)
        chunk_count = collection.count()
    except Exception as e:
        logger.warning(f"Failed to get collection count for {index_name}: {e}")

    symbol_count = 0
    graph_path = os.path.join(INDEX_DIR, index_name, "relationship_graph.json")
    if os.path.exists(graph_path):
        try:
            with open(graph_path, "r", encoding="utf-8") as f:
                graph = json.load(f)
            symbol_count = len(graph)
        except Exception as e:
            logger.warning(f"Failed to read relationship graph for {index_name}: {e}")

    return {
        "files": files,
        "chunk_count": chunk_count,
        "symbol_count": symbol_count
    }


def handle_aggregation_query(query: str, index_name: str) -> str:
    """
    Deterministic, regex-based response to counting/list-all queries.
    NO LLM call, NO vector search.
    """
    stats = get_repo_stats(index_name)
    files = stats["files"]
    chunk_count = stats["chunk_count"]
    symbol_count = stats["symbol_count"]
    
    query_lower = (query or "").lower()
    
    # 1. Chunk/node count queries
    if "chunk" in query_lower or "node" in query_lower:
        return f"The repository has a total of {chunk_count} code chunks/nodes indexed in the database."

    # 2. Symbol/function/class count queries
    if "symbol" in query_lower or "function" in query_lower or "class" in query_lower:
        return f"The relationship graph for this repository contains {symbol_count} defined symbols (functions, classes, or modules)."

    # Determine the subset of files to search
    files_to_count = files
    label_prefix = ""
    if "test" in query_lower:
        test_files = []
        for f in files:
            parts = f.split("/")
            filename = parts[-1]
            is_test = False
            for p in parts[:-1]:
                if p.lower() in ("test", "tests"):
                    is_test = True
                    break
            if "test" in filename.lower():
                is_test = True
            if is_test:
                test_files.append(f)
        files_to_count = test_files
        label_prefix = "test "

    # 3. Check for specific folder count
    dirs = set()
    for f in files:
        parts = f.split("/")
        for i in range(1, len(parts)):
            dirs.add("/".join(parts[:i]))
            
    matched_dir = None
    # Sort by length descending to match most specific folder first
    for d in sorted(dirs, key=len, reverse=True):
        if d in query_lower or d.replace("/", " ") in query_lower:
            matched_dir = d
            break
            
    if matched_dir:
        dir_files = [f for f in files_to_count if f.startswith(matched_dir + "/") or f == matched_dir]
        return f"There are {len(dir_files)} indexed {label_prefix}files in the '{matched_dir}' directory/subdirectories."

    # 4. Check for specific file extension count
    ext_map = {
        ".py": ["python", ".py", "py files", "py"],
        ".js": ["javascript", ".js", "js files", "js"],
        ".ts": ["typescript", ".ts", "ts files", "ts"],
        ".tsx": ["tsx files", ".tsx", "tsx"],
        ".jsx": ["jsx files", ".jsx", "jsx"],
        ".md": ["markdown", ".md", "md files", "md"],
        ".html": ["html"],
        ".css": ["css"],
        ".sh": ["shell", "bash", ".sh"],
        ".java": ["java"],
        ".go": ["go"],
        ".rs": ["rust", ".rs"],
        ".cpp": ["c++", ".cpp"],
        ".c": ["c files", ".c"],
        ".h": ["header files", ".h"],
        ".cs": ["c#", ".cs"],
        ".rb": ["ruby", ".rb"],
        ".php": ["php"],
    }
    
    import re
    # Sort all (ext, alias) pairs by length of alias descending to check longer matches first
    all_aliases = []
    for ext, aliases in ext_map.items():
        for alias in aliases:
            all_aliases.append((ext, alias))
    all_aliases.sort(key=lambda x: len(x[1]), reverse=True)
    
    for ext, alias in all_aliases:
        if len(alias) <= 3:
            # Use word boundaries for short aliases to avoid matching substrings of other words
            pattern = re.compile(rf"\b{re.escape(alias)}\b", re.IGNORECASE)
            if pattern.search(query_lower):
                matching = [f for f in files_to_count if f.endswith(ext)]
                return f"There are {len(matching)} {label_prefix}files with the '{ext}' extension in the repository."
        else:
            if alias in query_lower:
                matching = [f for f in files_to_count if f.endswith(ext)]
                return f"There are {len(matching)} {label_prefix}files with the '{ext}' extension in the repository."

    # 5. Default fallback
    if label_prefix:
        return f"There are {len(files_to_count)} indexed {label_prefix}files in the repository."
    return f"The repository has a total of {len(files)} indexed source files, containing {chunk_count} chunks and {symbol_count} symbols."
