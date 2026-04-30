import os
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")

# Directories
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
REPOS_DIR = os.path.join(DATA_DIR, "repos")
INDEX_DIR = os.path.join(DATA_DIR, "index")

# Ensure directories exist
os.makedirs(REPOS_DIR, exist_ok=True)
os.makedirs(INDEX_DIR, exist_ok=True)
