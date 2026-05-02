import os
from typing import Optional
from app.ingestion.repo_loader import load_repository
from app.ingestion.file_filter import filter_files
from app.parsing.code_parser import parse_code_files
from app.indexing.index_builder import build_index
from app.utils.logger import get_logger
from app.indexing.file_map_builder import build_file_map

logger = get_logger(__name__)

def process_repository(source: str) -> Optional[str]:
    """
    Orchestrates repository pipeline:
    load_repository -> filter_files -> parse_code_files -> build_index
    Returns the name of the index generated or None if failed.
    """
    try:
        logger.info(f"Starting pipeline for source: {source}")
        
        # 1. Load Repo
        repo_path = load_repository(source)
        
        # The index name will be the folder name
        index_name = os.path.basename(os.path.normpath(repo_path))
        
        # 2. Filter Files
        valid_files = filter_files(repo_path)
        if not valid_files:
            logger.warning("No valid code files found in the repository.")
            return None
            
        # 3. Parse Code Files
        chunks = parse_code_files(valid_files, repo_path)


        # 🔥 Build File Map (NEW STEP)
        build_file_map(valid_files, repo_path, index_name)

        if not chunks:
            logger.warning("No chunks generated from the code files.")
            return None
            
        # 4. Build Index
        build_index(chunks, index_name=index_name)
        
        logger.info(f"Successfully processed repository. Index name: {index_name}")
        return index_name
        
    except Exception as e:
        logger.error(f"Failed to process repository {source}: {e}", exc_info=True)
        return None
