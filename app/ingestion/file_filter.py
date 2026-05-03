import os
from typing import List
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Common code file extensions
VALID_EXTENSIONS = {
    '.py', '.js', '.ts', '.java', '.cpp', '.c', '.h', '.hpp', '.cs', 
    '.go', '.rs', '.rb', '.php', '.html', '.css', '.md', '.sh'
}

# Directories to ignore
IGNORE_DIRS = {
    'node_modules', '.git', '.github', 'dist', 'build', '__pycache__',
    'venv', 'env', '.idea', '.vscode', 'out', 'target'
}

def filter_files(repo_path: str) -> List[str]:
    """
    Traverses the repository directory and returns a list of valid code file paths.
    Ignores specified directories like node_modules, .git, etc.
    """
    valid_files = []
    
    for root, dirs, files in os.walk(repo_path):
        # Modify dirs in-place to skip ignored directories
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
        
        for file in files:
            _, ext = os.path.splitext(file)
            if ext.lower() in VALID_EXTENSIONS:
                full_path = os.path.join(root, file)
                logger.debug(f"Checking file: {full_path}")

                valid_files.append(full_path)
                logger.info(f"Accepted file: {full_path}")
                
    logger.info(f"Found {len(valid_files)} valid code files in {repo_path}")
    return valid_files
