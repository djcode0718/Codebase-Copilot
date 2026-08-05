# Quick Start — Codebase Copilot

## 1. Set Up Environment

```bash
# Copy example config and fill in your keys
copy env.api.example .env
```

Edit `.env`:
```
LLM_PROVIDER=groq
GROQ_API_KEY=your_key_here
SUPABASE_URL=your_supabase_url
SUPABASE_SERVICE_KEY=your_service_key
OLLAMA_BASE_URL=http://localhost:11434
```

---

## 2. Install Dependencies

```bash
# Backend (Python 3.10)
py -3.10 -m pip install -r requirements.txt --default-timeout=1000

# Frontend
cd frontend && npm install
```

---

## 3. Start Services

Open three terminals:

```bash
# Terminal 1 — API backend
py -3.10 -m uvicorn api.main:app --reload --port 8000

# Terminal 2 — Frontend
cd frontend && npm run dev

# Terminal 3 — Ollama (local embeddings)
ollama serve
```

---

## 4. Access

| Service | URL |
|---------|-----|
| Frontend | http://localhost:3000 |
| API docs | http://localhost:8000/docs |
| Ollama   | http://localhost:11434 |

---

## 5. Index Your First Repository

1. Open **http://localhost:3000**
2. Sign in and click **Index repository**
3. Paste a GitHub URL or local path
4. Wait for indexing to complete, then click **Repository Chat**
