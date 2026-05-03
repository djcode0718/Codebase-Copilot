# import os
# from dotenv import load_dotenv

# load_dotenv()

# GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
# EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")

# # Directories
# BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# DATA_DIR = os.path.join(BASE_DIR, "data")
# REPOS_DIR = os.path.join(DATA_DIR, "repos")
# INDEX_DIR = os.path.join(DATA_DIR, "index")

# # Ensure directories exist
# os.makedirs(REPOS_DIR, exist_ok=True)
# os.makedirs(INDEX_DIR, exist_ok=True)

import os
from dotenv import load_dotenv

load_dotenv()

# LLM provider selection: "gemini" | "groq" | "openai" | "ollama"
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "gemini")

# API keys
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# Ollama config (used for LLM and will be used for embeddings in LlamaIndex migration)
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:3b")
OLLAMA_EMBED_MODEL = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")  # ready for migration
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

# Directories
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
REPOS_DIR = os.path.join(DATA_DIR, "repos")
INDEX_DIR = os.path.join(DATA_DIR, "index")

# Ensure directories exist
os.makedirs(REPOS_DIR, exist_ok=True)
os.makedirs(INDEX_DIR, exist_ok=True)
