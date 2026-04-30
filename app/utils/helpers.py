import os
import shutil
from typing import Optional

def clean_directory(directory_path: str):
    """Removes all contents from the given directory."""
    if os.path.exists(directory_path):
        for filename in os.listdir(directory_path):
            file_path = os.path.join(directory_path, filename)
            try:
                if os.path.isfile(file_path) or os.path.islink(file_path):
                    os.unlink(file_path)
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)
            except Exception as e:
                print(f"Failed to delete {file_path}. Reason: {e}")

def get_file_extension(file_path: str) -> str:
    """Returns the lowercase extension of a file."""
    _, ext = os.path.splitext(file_path)
    return ext.lower()
