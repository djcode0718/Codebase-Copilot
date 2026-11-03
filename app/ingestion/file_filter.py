import os
from typing import List
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Maximum file size to index (1 MB) to prevent out-of-memory on giant dumps
MAX_FILE_SIZE = 1024 * 1024

# Supported code and text file extensions
VALID_EXTENSIONS = {
    # Core code
    '.py', '.js', '.ts', '.java', '.cpp', '.c', '.h', '.hpp', '.cs', 
    '.go', '.rs', '.rb', '.php', '.html', '.css', '.md', '.sh', '.ipynb',
    # Data and configuration formats
    '.json', '.csv', '.yaml', '.yml', '.txt', '.jsonl'
}

# Exact canonical extensionless filenames to ingest as code/config
EXACT_FILENAMES = {
    'license', 'licence', 'dockerfile', 'makefile', 'gemfile', 'procfile', 'vagrantfile'
}

# Explicit binary file extensions to always reject
BINARY_EXTENSIONS = {
    '.png', '.jpg', '.jpeg', '.gif', '.bmp', '.ico', '.svg',
    '.h5', '.hdf5', '.pyc', '.pyd', '.so', '.dll', '.exe', '.bin',
    '.pkl', '.pickle', '.pt', '.pth', '.onnx',
    '.wav', '.mp3', '.ogg', '.flac', '.m4a',
    '.zip', '.tar', '.gz', '.bz2', '.7z', '.rar'
}

# Directories to ignore
IGNORE_DIRS = {
    'node_modules', '.git', 'dist', 'build', '__pycache__',
    'venv', 'env', '.idea', '.vscode', 'out', 'target', '.ipynb_checkpoints'
}

def filter_files(repo_path: str) -> List[str]:
    """
    Traverses the repository directory and returns a list of valid code and config file paths.
    Ignores specified directories like node_modules, .git, etc.
    Enforces file-size limits and rejects binary formats.
    """
    valid_files = []
    
    for root, dirs, files in os.walk(repo_path):
        # Modify dirs in-place to skip ignored directories
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
        
        for file in files:
            base_lower = file.lower()
            _, ext = os.path.splitext(file)
            ext_lower = ext.lower()
            
            # Skip explicit binary formats
            if ext_lower in BINARY_EXTENSIONS:
                continue

            # Accept if valid extension or known exact extensionless filename
            is_valid_ext = ext_lower in VALID_EXTENSIONS
            is_valid_exact = (not ext_lower or ext_lower == '') and (base_lower in EXACT_FILENAMES)

            if is_valid_ext or is_valid_exact:
                full_path = os.path.join(root, file)
                
                # Check file size limit
                try:
                    if os.path.islink(full_path):
                        # Skip broken symlinks or directory symlinks
                        if not os.path.exists(full_path) or os.path.isdir(full_path):
                            continue
                    file_size = os.path.getsize(full_path)
                    if file_size > MAX_FILE_SIZE:
                        logger.warning(f"Skipping oversized file ({file_size} bytes > {MAX_FILE_SIZE}): {full_path}")
                        continue
                    if file_size == 0:
                        continue
                except OSError as err:
                    logger.warning(f"Could not stat file {full_path}: {err}")
                    continue

                valid_files.append(full_path)
                logger.debug(f"Accepted file: {full_path}")
                
    logger.info(f"Found {len(valid_files)} valid code/config files in {repo_path}")
    return valid_files
