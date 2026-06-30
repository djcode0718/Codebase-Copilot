# 🚀 Codebase Copilot

> An AI-powered codebase intelligence system that understands repositories using hybrid retrieval, reranking, query routing, conversational memory, and evaluation-driven RAG pipelines — now with a production-ready FastAPI backend and Supabase integration.

---

# 📌 Overview

**Codebase Copilot** is a modular Retrieval-Augmented Generation (RAG) system designed to help developers understand large and unfamiliar repositories through natural language interaction.

The system combines:

* hybrid retrieval
* semantic search
* BM25 keyword retrieval
* reranking
* query routing
* conversational memory
* evaluation pipelines
* multi-LLM orchestration
* REST API backend (FastAPI)
* persistent storage (Supabase)

to provide both:

✅ low-level code understanding
✅ higher-order architectural reasoning

Unlike simple repository chatbots, this project focuses heavily on:

* retrieval quality
* evaluation methodology
* latency analysis
* modular AI engineering
* production-style RAG architecture

---

# ✨ Key Features

## 🧠 Hybrid Retrieval Pipeline

The system combines:

* dense semantic retrieval
* sparse keyword retrieval (BM25)
* Reciprocal Rank Fusion (RRF)
* reranking pipelines

to improve:

* retrieval precision
* contextual relevance
* architectural understanding

---

## 🔀 Intelligent Query Routing

Queries are automatically classified into:

| Mode            | Purpose                            |
| --------------- | ---------------------------------- |
| `code_lookup`   | strict grounded code explanations  |
| `architectural` | higher-order engineering reasoning |

This enables the system to:

* remain faithful for code lookup
* reason more broadly for design discussions

---

## ⚡ Multi-LLM Support

Supports:

* Ollama (offline/local)
* Groq
* Gemini
* OpenAI

The system supports:

* local inference
* cloud inference
* evaluation-specific switching

through centralized configuration.

---

## 🌐 FastAPI REST Backend

A full production-ready REST API layer built with FastAPI that exposes all core functionality over HTTP:

* JWT-authenticated endpoints via Supabase
* SSE (Server-Sent Events) for real-time streaming of indexing progress and chat responses
* Supabase-backed persistence for repositories, chats, messages, and evaluations
* CORS-configured for frontend integration

---

## 💬 Conversational Memory

Includes:

* multi-turn conversation support
* persistent chat context (per session and across restarts via Supabase)
* memory-aware prompting
* ChatGPT-style interface

---

## 📊 Evaluation Framework

The project includes a complete evaluation pipeline for measuring:

### Retrieval Quality

* Hit Rate
* MRR (Mean Reciprocal Rank)

### Generation Quality

* Faithfulness
* Relevancy

### System Metrics

* retrieval latency
* reranking latency
* LLM latency
* routing accuracy

---

## 🧩 Advanced Parsing & Chunking

The pipeline supports:

* recursive repository traversal
* metadata-rich chunking
* function-aware splitting
* tree-sitter parsing
* semantic file summaries

---

# 🏗️ System Architecture

```text
                    ┌──────────────────────┐
                    │     Streamlit UI     │
                    └──────────┬───────────┘
                               │
                               ▼
                  ┌────────────────────────┐
                  │   FastAPI REST API     │
                  │  (api/main.py)         │
                  │  JWT Auth via Supabase │
                  └────────┬───────────────┘
                           │
           ┌───────────────┼────────────────┐
           ▼               ▼                ▼
    ┌─────────────┐ ┌────────────┐  ┌──────────────┐
    │  /api/repo  │ │ /api/chat  │  │  /api/eval   │
    │  Indexing   │ │  Streaming │  │  Evaluation  │
    │  SSE stream │ │  SSE + DB  │  │  SSE stream  │
    └──────┬──────┘ └─────┬──────┘  └──────┬───────┘
           │              │                │
           └──────────────┼────────────────┘
                          ▼
           ┌──────────────────────────┐
           │     Core RAG Engine      │
           │   (app/ layer)           │
           └──────────┬───────────────┘
                      │
          ┌───────────┴────────────────┐
          ▼                            ▼
 ┌─────────────────┐        ┌────────────────────┐
 │ Hybrid Retriever│        │ Architectural Flow │
 │  BM25 + Dense   │        │ Contextual Reasoner│
 └────────┬────────┘        └────────┬───────────┘
          │                          │
          └────────────┬─────────────┘
                       ▼
             ┌──────────────────┐
             │  ColBERT Rerank  │
             └────────┬─────────┘
                      ▼
             ┌──────────────────┐
             │   LlamaIndex     │
             │  Retrieval Core  │
             └────────┬─────────┘
                      ▼
             ┌──────────────────┐
             │   LLM Provider   │
             │ Ollama/Groq/etc  │
             └────────┬─────────┘
                      ▼
             ┌──────────────────┐
             │  Supabase (DB)   │
             │  Persist Results │
             └──────────────────┘
```

---

# ⚙️ Tech Stack

## AI / Retrieval

* LlamaIndex
* BM25
* ChromaDB
* ColBERT
* Hybrid Retrieval
* Reciprocal Rank Fusion

## LLMs

* Ollama
* Groq
* Gemini
* OpenAI

## Parsing

* tree-sitter
* tree-sitter-language-pack

## Backend API

* FastAPI
* Uvicorn
* Pydantic (request/response models)
* Server-Sent Events (SSE)

## Database & Auth

* Supabase (PostgreSQL)
* Supabase Auth (JWT)

## Frontend

* Streamlit

## Evaluation

* LlamaIndex Evaluators
* FaithfulnessEvaluator
* RelevancyEvaluator

---

# 📂 Project Structure

```text
codebase-copilot/
│
├── app/                          # Core RAG engine (provider-agnostic)
│   ├── config.py
│   ├── ingestion/
│   │   ├── repo_loader.py
│   │   └── file_filter.py
│   ├── parsing/
│   │   ├── code_parser.py
│   │   └── chunk_utils.py
│   ├── indexing/
│   │   ├── index_builder.py
│   │   ├── vector_store.py
│   │   ├── file_map_builder.py
│   │   └── summary_index_builder.py
│   ├── retrieval/
│   │   ├── retriever.py
│   │   ├── hybrid_retriever.py
│   │   ├── reranker.py
│   │   ├── ranking.py
│   │   ├── query_router.py
│   │   └── file_map_retriever.py
│   ├── llm/
│   │   ├── llm_client.py
│   │   └── prompts.py
│   ├── memory/
│   │   └── chat_memory.py
│   ├── services/
│   │   ├── repo_service.py
│   │   └── qa_service.py
│   └── utils/
│       ├── logger.py
│       └── helpers.py
│
├── api/                          # FastAPI REST backend
│   ├── main.py                   # App entry point, CORS, router registration
│   ├── dependencies.py           # Supabase client, JWT auth dependencies
│   ├── routers/
│   │   ├── repo.py               # Repository indexing endpoints
│   │   ├── chat.py               # Chat session + SSE streaming endpoints
│   │   ├── eval.py               # Evaluation endpoints
│   │   └── suggestions.py        # LLM-generated question suggestions
│   ├── models/
│   │   ├── repo.py               # Pydantic models for repo endpoints
│   │   ├── chat.py               # Pydantic models for chat endpoints
│   │   └── eval.py               # Pydantic models for eval endpoints
│   └── services/
│       ├── chat_service.py       # SSE streaming + session cache
│       ├── indexing_service.py   # Async indexing pipeline with SSE
│       └── supabase_service.py   # All Supabase DB operations
│
├── ui/
│   └── streamlit_app.py
│
├── data/
│   ├── repos/
│   ├── index/
│   └── eval_results*.json
│
├── evaluate.py
├── copy_codes.py
│
├── requirements.txt
├── requirements-llamaindex.txt
│
├── .env
├── .gitignore
└── README.md
```

---

# 🌐 REST API Reference

The FastAPI backend is served at `http://localhost:8000` and exposes the following endpoints. All endpoints require a valid Supabase JWT in the `Authorization: Bearer <token>` header.

## Health

| Method | Endpoint       | Description                             |
| ------ | -------------- | --------------------------------------- |
| `GET`  | `/api/health`  | Returns LLM provider, ColBERT status, and embed model info |

---

## Repository — `/api/repo`

| Method   | Endpoint                           | Description                                                    |
| -------- | ---------------------------------- | -------------------------------------------------------------- |
| `POST`   | `/api/repo/index`                  | Create a repo record and begin indexing (returns `repo_id`)    |
| `GET`    | `/api/repo/{repo_id}/index-progress` | **SSE stream** — real-time indexing progress events          |
| `GET`    | `/api/repo/list`                   | List all repositories for the authenticated user               |
| `GET`    | `/api/repo/{repo_id}`              | Get status and metadata for a single repository                |
| `DELETE` | `/api/repo/{repo_id}`              | Delete a repository, its ChromaDB index, and cloned files      |
| `GET`    | `/api/repo/{repo_id}/suggestions`  | Return 6 LLM-generated suggested questions for the repository  |

### Indexing SSE Events

```json
{ "step": "cloning",   "message": "Cloning repository...", "progress": 10 }
{ "step": "filtering", "message": "Filtering files...",    "progress": 25 }
{ "step": "parsing",   "message": "Parsing 47 files...",   "progress": 40 }
{ "step": "embedding", "message": "Building embeddings...", "progress": 65 }
{ "step": "indexing",  "message": "Building summary index...", "progress": 80 }
{ "step": "done",      "message": "Indexing complete!", "progress": 100, "file_count": 47, "node_count": 312 }
{ "step": "error",     "message": "..." }
```

---

## Chat — `/api/chat`

| Method   | Endpoint                             | Description                                        |
| -------- | ------------------------------------ | -------------------------------------------------- |
| `POST`   | `/api/chat/session`                  | Create a new chat session for a repository         |
| `POST`   | `/api/chat/{chat_id}/message/stream` | **SSE stream** — stream AI response token-by-token |
| `GET`    | `/api/chat/{chat_id}/messages`       | Fetch full message history for a chat              |
| `GET`    | `/api/chat/list?repo_id=...`         | List all chats for a repository                    |
| `DELETE` | `/api/chat/{chat_id}`                | Delete a chat session and all its messages         |

### Chat SSE Events

```json
{ "type": "token",    "content": "..." }
{ "type": "metadata", "query_mode": "code_lookup", "retrieved_files": [...], "latency_retrieval_ms": 95, "latency_llm_ms": 2100, "latency_total_ms": 2210 }
{ "type": "done" }
{ "type": "error",   "message": "..." }
```

Each message is persisted to Supabase after streaming completes, including `query_mode`, `retrieved_files`, and `latency_ms`.

---

## Evaluation — `/api/eval`

| Method | Endpoint                     | Description                                                         |
| ------ | ---------------------------- | ------------------------------------------------------------------- |
| `POST` | `/api/eval/run`              | **SSE stream** — run the full evaluation suite (~3–10 min)         |
| `GET`  | `/api/eval/{repo_id}/latest` | Retrieve the most recent evaluation results for a repository        |

### Eval SSE Events

```json
{ "type": "progress", "message": "Running query 3/10..." }
{ "type": "result",   "summary": { "hit_rate": 0.8, "mrr": 0.65, ... } }
{ "type": "done" }
{ "type": "error",    "message": "..." }
```

Results are automatically persisted to Supabase on completion.

---

# 🗄️ Supabase Schema

The backend uses five Supabase tables:

| Table            | Purpose                                                  |
| ---------------- | -------------------------------------------------------- |
| `profiles`       | User profile data                                        |
| `repositories`   | Indexed repo records (status, file/node count, provider) |
| `chats`          | Chat sessions linked to a repository                     |
| `messages`       | Individual messages with role, content, mode, latency    |
| `evaluations`    | Stored evaluation summaries with all metric fields       |

All Supabase operations are centralized in `api/services/supabase_service.py`. Routers never make raw Supabase calls directly.

---

# 🔐 Authentication

The API uses Supabase JWT authentication:

* the frontend sends `Authorization: Bearer <supabase_access_token>`
* `api/dependencies.py` verifies the token using the Supabase service role key
* `get_current_user()` — raises `401` if the token is missing or invalid
* `get_optional_user()` — returns `None` for unauthenticated requests (guest mode)

The Supabase client uses the **service role key** (never exposed to the frontend).

---

# 🔄 End-to-End Workflow

## 1️⃣ Repository Ingestion

The system accepts:

* GitHub repository URLs
* local repository paths

Repositories are:

* cloned locally
* recursively traversed
* filtered for relevant files

Ignored directories:

```text
node_modules/
.git/
dist/
venv/
__pycache__/
```

---

## 2️⃣ Parsing & Chunking

The parser:

* reads code safely
* extracts metadata
* performs semantic chunking
* generates file-level summaries

Each chunk stores:

* file path
* file name
* entity information
* chunk text
* metadata

---

## 3️⃣ Embedding & Indexing

Dense embeddings:

```text
nomic-embed-text
```

Storage:

```text
ChromaDB
```

Keyword retrieval:

```text
BM25
```

---

## 4️⃣ Hybrid Retrieval

The retrieval system combines:

* semantic retrieval
* keyword retrieval
* file-level retrieval

using:

* QueryFusionRetriever
* Reciprocal Rank Fusion (RRF)

This improves:

* retrieval precision
* architectural reasoning
* contextual grounding

---

## 5️⃣ Reranking

Optional ColBERT reranking improves:

* ranking quality
* retrieval precision
* Mean Reciprocal Rank (MRR)

---

## 6️⃣ Query Routing

Queries are classified into:

* code lookup mode
* architectural reasoning mode

This allows:

* stricter grounded answers
* broader engineering analysis
* better faithfulness control

---

## 7️⃣ Prompt Construction

Prompts include:

* retrieved chunks
* repository summaries
* metadata
* routing instructions
* conversational history

---

## 8️⃣ Conversational Memory

The memory system:

* stores previous interactions
* enables follow-up questions
* preserves context across turns
* persists messages to Supabase via the API layer

---

## 9️⃣ LLM Generation

Responses are generated using:

* Ollama
* Groq
* Gemini
* OpenAI

The system supports:

* local inference
* cloud inference
* evaluation-specific LLM switching
* token-level SSE streaming via the FastAPI backend

---

# 📊 Evaluation Framework

The project includes a dedicated evaluation pipeline.

## Metrics Measured

| Category    | Metrics                        |
| ----------- | ------------------------------ |
| Retrieval   | Hit Rate, MRR                  |
| Generation  | Faithfulness, Relevancy        |
| Routing     | Mode Accuracy                  |
| Performance | Retrieval, rerank, LLM latency |

---

# 📈 Example Evaluation Results

| Metric            | Score     |
| ----------------- | --------- |
| Hit Rate          | 0.80+     |
| MRR               | 0.60+     |
| Faithfulness      | 0.60–0.80 |
| Relevancy         | 0.90+     |
| Routing Accuracy  | 1.00      |
| Retrieval Latency | ~0.1s     |
| Rerank Latency    | ~1s       |
| Local LLM Latency | ~15s      |
| Groq LLM Latency  | ~2–4s     |

---

# 🧠 Key Engineering Insights

## Retrieval Pipeline

The retrieval stack is highly optimized:

* retrieval latency is extremely low (~0.1s)
* reranking adds modest overhead (~1s)
* the primary bottleneck is local LLM inference

---

## Backend Architecture

The `api/` layer is deliberately thin:

* routers handle HTTP concerns only (auth, validation, response shaping)
* all business logic lives in `app/` (provider-agnostic core)
* `api/services/` handles Supabase persistence and SSE coordination
* this separation means the Streamlit UI and FastAPI backend share the same core RAG engine without duplication

---

## Streaming Design

Both indexing and chat use Server-Sent Events (SSE):

* indexing progress is streamed step-by-step so the frontend can show a live progress bar
* chat responses are streamed token-by-token using LlamaIndex's `stream_complete()` 
* a `metadata` event is emitted after the full response, carrying `query_mode`, `retrieved_files`, and latency breakdowns
* messages are persisted to Supabase after the stream closes

---

## Local AI Optimization

The system was optimized specifically for:

* Apple Silicon Macs
* 16GB RAM systems
* local inference workflows

---

## Hallucination Reduction

Implemented using:

* hybrid retrieval
* reranking
* query routing
* retrieval-grounded prompting

---

# 💬 Example Queries

## Code Lookup

```text
How does retrieve_relevant_chunks work?
```

```text
Where is the vector store initialized?
```

```text
How does the indexing pipeline work?
```

---

## Architectural Reasoning

```text
What are the main limitations of this project?
```

```text
How can retrieval quality be improved?
```

```text
What changes are needed for production deployment?
```

---

# 🚀 Running the Project

## 1️⃣ Create Environment

```bash
conda create -n ai-copilot-env python=3.10
conda activate ai-copilot-env
```

---

## 2️⃣ Install Dependencies

```bash
pip install -r requirements-llamaindex.txt
```

---

## 3️⃣ Start Ollama

```bash
ollama serve
```

Pull required models:

```bash
ollama pull mistral
ollama pull nomic-embed-text
```

---

## 4️⃣ Configure `.env`

```env
LLM_PROVIDER=ollama

OLLAMA_MODEL=mistral
OLLAMA_EMBED_MODEL=nomic-embed-text

USE_COLBERT=true
USE_FAST_LLM=false

# Required for FastAPI backend
SUPABASE_URL=https://xxxx.supabase.co
SUPABASE_SERVICE_KEY=eyJ...

# Optional — used for CORS
FRONTEND_URL=http://localhost:3000
```

---

## 5️⃣ Start the FastAPI Backend

```bash
uvicorn api.main:app --reload --port 8000
```

The API will be available at `http://localhost:8000`.

Interactive API docs (Swagger UI): `http://localhost:8000/docs`

---

## 6️⃣ Launch Streamlit App (optional)

```bash
streamlit run ui/streamlit_app.py
```

---

# 🧪 Running Evaluation

### Via CLI (standalone)

```bash
python evaluate.py
```

### Via API (persists results to Supabase)

```bash
POST /api/eval/run
{ "repo_id": "<uuid>", "index_name": "<index_name>" }
```

---

# 🔮 Future Improvements

## Retrieval

* GraphRAG integration
* dependency graph reasoning
* AST-aware retrieval
* cross-repository retrieval

---

## LLM

* tool-using agents
* autonomous debugging workflows
* structured reasoning pipelines

---

## Product Features

* authentication UI (sign up / login flow)
* persistent long-term memory across sessions
* multi-user support
* streaming already implemented — frontend integration pending

---

# 🎯 What This Project Demonstrates

This project demonstrates practical understanding of:

* Retrieval-Augmented Generation (RAG)
* hybrid retrieval systems
* reranking pipelines
* evaluation engineering
* conversational memory
* LLM orchestration
* routing systems
* latency optimization
* AI infrastructure design
* production-style REST API design (FastAPI + Supabase)
* Server-Sent Events for real-time AI streaming
* JWT authentication and multi-user data isolation

---

# 🙌 Final Note

Codebase Copilot was built to deeply explore:

* retrieval quality
* architectural reasoning
* evaluation methodology
* scalable AI system design
* production API engineering

with a strong focus on:

* modularity
* explainability
* optimization
* extensibility
* real-world AI engineering workflows.
