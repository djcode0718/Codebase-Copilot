import os
import shutil
import git
from urllib.parse import urlparse
from app.config import REPOS_DIR
from app.utils.logger import get_logger

logger = get_logger(__name__)

def is_valid_url(url: str) -> bool:
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except ValueError:
        return False

def load_repository(source: str) -> str:
    """
    Clones a GitHub repository or validates a local path.
    Returns the local path to the repository.
    """
    if is_valid_url(source):
        logger.info(f"Source identified as URL: {source}")
        # Create a folder name from the repo url
        repo_name = source.rstrip('/').split('/')[-1]
        if repo_name.endswith('.git'):
            repo_name = repo_name[:-4]
            
        target_dir = os.path.join(REPOS_DIR, repo_name)
        
        # If it already exists, remove it to ensure a fresh clone
        if os.path.exists(target_dir):
            logger.info(f"Removing existing directory {target_dir}")
            shutil.rmtree(target_dir)
            
        logger.info(f"Cloning repository into {target_dir}")
        git.Repo.clone_from(source, target_dir)
        return target_dir
    else:
        logger.info(f"Source identified as local path: {source}")
        if not os.path.exists(source) or not os.path.isdir(source):
            raise ValueError(f"Invalid local directory path: {source}")
        return source
