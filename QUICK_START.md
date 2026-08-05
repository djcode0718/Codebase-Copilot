# 📋 Codebase-Copilot Installation Quick Reference

## Installation Stages - Copy & Paste These Commands

```bash
# Stage 1: FastAPI Backend ✓ DONE
py -3.10 -m pip install fastapi uvicorn pydantic supabase python-dotenv --default-timeout=1000

# Stage 2: Retrieval Stack
py -3.10 -m pip install chromadb sentence-transformers rank-bm25 --default-timeout=1000

# Stage 3: LLM Integration
py -3.10 -m pip install llama-index-core openai ollama llama-index-llms-groq --default-timeout=1000

# Stage 4: Code Parsing
py -3.10 -m pip install gitpython tree-sitter scikit-learn --default-timeout=1000

# Stage 5: Optional Advanced
py -3.10 -m pip install ragatouille colbert-ai --default-timeout=1000
```

---

## Verify Installation Works

```bash
# Test all stages
py -3.10 -c "import fastapi, chromadb, llama_index, tree_sitter; print('✓ All OK')"

# Test individual stages
py -3.10 -c "import fastapi; print('✓ Stage 1')"
py -3.10 -c "import chromadb; print('✓ Stage 2')"
py -3.10 -c "import llama_index; print('✓ Stage 3')"
py -3.10 -c "import tree_sitter; print('✓ Stage 4')"
```

---

## Run Codebase-Copilot

```bash
# Terminal 1: Start API server
cd C:\SourceCode\Codebase-Copilot
py -3.10 -m uvicorn api.main:app --reload --port 8000

# Terminal 2: Start Next.js frontend
cd C:\SourceCode\Codebase-Copilot\frontend
npm install
npm run dev

# Terminal 3: Start Ollama (for embeddings)
ollama serve
```

---

## Access Points

| Service | URL | Purpose |
|---------|-----|---------|
| API Docs | http://localhost:8000/docs | REST API Swagger UI |
| API | http://localhost:8000/api | Direct API calls |
| Frontend UI | http://localhost:3000 | Next.js application |
| Ollama | http://localhost:11434 | Local LLM/embeddings |

---

## Environment Setup

```bash
# Copy example config
copy env.api.example .env

# Edit .env file with your settings:
LLM_PROVIDER=groq
GROQ_API_KEY=your_key_here
OLLAMA_BASE_URL=http://localhost:11434
SUPABASE_URL=your_url
SUPABASE_SERVICE_KEY=your_key
```

---

## Common Issues & Fixes

| Problem | Solution |
|---------|----------|
| Timeout during pip install | Re-run the stage (uses cache) |
| "Module not found" | Run pip stage for that module |
| API won't start | Check Python 3.10 available: `py -3.10 --version` |
| No embeddings | Start Ollama: `ollama serve` |
| Slow LLM responses | Use Groq: `USE_FAST_LLM=true` in .env |

---

## Documentation Files

Read these for more info:

- `COMPLETE_PROJECT_GUIDE.md` - Full system overview
- `INSTALLATION_RECOVERY.md` - Detailed timeout recovery
- `INSTALLATION_STATUS.md` - Installation tracking
- `api/main.py` - API entry point (comments included)
- `app/config.py` - Configuration options

---

## Example: Index a Repository

After backend starts:

```bash
# HTTP POST to index a repo
curl -X POST http://localhost:8000/api/repo/index \
  -H "Content-Type: application/json" \
  -d '{
    "source": "https://github.com/openai/gpt-2",
    "repo_name": "gpt-2"
  }'
```

---

**Status**: Installation in progress  
**Last Updated**: July 8, 2026  
**Python Version**: 3.10+

