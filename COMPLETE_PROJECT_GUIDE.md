# 🚀 Codebase Copilot - Complete Project Guide

> An AI-powered codebase intelligence system that understands repositories using hybrid retrieval, reranking, query routing, conversational memory, and evaluation-driven RAG pipelines — with a production-ready FastAPI backend and Supabase integration.

**Date**: July 2026
**Version**: 1.0.0

---

## 📖 Table of Contents

1. [Project Overview](#project-overview)
2. [Key Features](#key-features)
3. [Technology Stack](#technology-stack)
4. [Architecture & Design](#architecture--design)
5. [Project Structure](#project-structure)
6. [Data Flow & Workflows](#data-flow--workflows)
7. [Configuration & Setup](#configuration--setup)
8. [Installation & Running](#installation--running)
9. [API Reference](#api-reference)
10. [Database Schema](#database-schema)
11. [Usage Examples](#usage-examples)
12. [Troubleshooting](#troubleshooting)

---

## Project Overview

**Codebase Copilot** is a modular Retrieval-Augmented Generation (RAG) system designed to help developers understand large and unfamiliar repositories through natural language interaction.

### Core Purpose

- 🧠 **Low-level code understanding** — Grounded code explanations using retrieval
- 🏗️ **Higher-order architectural reasoning** — Design pattern analysis and technical insights
- 🔍 **Intelligent query routing** — Automatically classifies queries to use the best retrieval strategy
- ⚡ **Multi-LLM support** — Works offline with Ollama or with cloud providers (Groq, Gemini, OpenAI)
- 📊 **Evaluation-driven** — Includes comprehensive evaluation pipelines for measuring system quality
- 🌐 **Production-ready API** — FastAPI REST backend with Supabase persistence and JWT authentication
- 💬 **Conversational memory** — Multi-turn conversation support with persistent storage

### What Makes This Different

Unlike simple repository chatbots, Codebase Copilot focuses on:

✅ **Retrieval Quality** — Hybrid retrieval combining dense semantic + sparse keyword matching
✅ **Reranking** — ColBERT-based reranking for precision
✅ **Query Understanding** — Dual-mode routing (code lookup vs. architectural)
✅ **Latency Analysis** — Performance metrics on all components
✅ **Modular Design** — Provider-agnostic core + pluggable LLM backends
✅ **Production Architecture** — REST API, authentication, real-time streaming, persistent storage

---

## Key Features

### 🧠 Hybrid Retrieval Pipeline

Combines multiple retrieval strategies:

| Strategy | Purpose | Implementation |
|----------|---------|-----------------|
| **Dense Semantic** | Understand query meaning in context | Ollama embeddings (nomic-embed-text) |
| **Sparse Keyword** | Match exact terms and identifiers | BM25 ranking |
| **File-Level** | Coarse-to-fine narrowing | LlamaIndex DocumentSummaryIndex |
| **Fusion** | Combine all signals | Reciprocal Rank Fusion (RRF) |
| **Reranking** | Final precision pass | ColBERT (optional, configurable) |

**Result**: Top 5 chunks presented to LLM with highest relevance confidence

---

### 🔀 Intelligent Query Routing

Queries are automatically classified into two modes:

| Mode | Use Cases | Behavior |
|------|-----------|----------|
| **code_lookup** | How does X work? / Where is Y? / Show me implementation | **Strict retrieval-grounded responses**, cite exact code |
| **architectural** | Design patterns / Limitations / Improvements / Comparisons | **Broader reasoning**, incorporate architectural knowledge |

This enables:
- High faithfulness in code lookup (reduced hallucination)
- Flexible reasoning in architectural discussions

---

### ⚡ Multi-LLM Support

Supports multiple LLM providers:

```
┌─────────────────┬──────────────┬──────────────┬─────────────────┐
│  Provider       │  Latency     │  Cost        │  Best For       │
├─────────────────┼──────────────┼──────────────┼─────────────────┤
│ Ollama (local)  │ ~10-15s      │ Free (local) │ Offline work    │
│ Groq            │ ~2-3s        │ Free/paid    │ Fast iteration  │
│ Gemini          │ ~3-5s        │ Paid         │ Quality output  │
│ OpenAI (GPT-4)  │ ~2-4s        │ Paid         │ Premium quality │
└─────────────────┴──────────────┴──────────────┴─────────────────┘
```

**Configuration**: Switch providers via environment variables (`LLM_PROVIDER`, `GROQ_API_KEY`, etc.)

---

### 🌐 FastAPI REST Backend

Full REST API layer with:

- ✅ **JWT Authentication** — Supabase-based auth
- ✅ **Server-Sent Events (SSE)** — Real-time streaming for indexing and chat
- ✅ **Persistent Storage** — All data in Supabase PostgreSQL
- ✅ **CORS Configuration** — Ready for frontend integration
- ✅ **Modular Routers** — Separate endpoints for repo, chat, evaluation, suggestions

**Access**: Run backend at `http://localhost:8000` with Swagger docs at `/docs`

---

### 💬 Conversational Memory

Features:

- Multi-turn conversation support
- Full message history per chat session
- Memory-aware prompt construction (includes previous messages)
- Persistent storage via Supabase
- ChatGPT-style interface

---

### 📊 Evaluation Framework

Complete evaluation pipeline measuring:

**Retrieval Metrics:**
- Hit Rate — Did ground truth chunks appear in retrieved set?
- MRR (Mean Reciprocal Rank) — How highly ranked were they?

**Generation Metrics:**
- Faithfulness — Is response grounded in retrieved context?
- Relevancy — Does response answer the question?

**System Metrics:**
- Routing Accuracy — Did query route to correct mode?
- Latency breakdown — Retrieval, reranking, LLM generation time

**Example Results:**
```
Hit Rate:              0.80+
MRR:                   0.60+
Faithfulness:          0.60–0.80
Relevancy:             0.90+
Routing Accuracy:      1.00
Retrieval Latency:     ~0.1s
Rerank Latency:        ~1s
LLM Latency:           ~2-15s (provider dependent)
```

---

## Technology Stack

### AI & Retrieval

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **LLM Framework** | LlamaIndex | High-level RAG orchestration |
| **Embeddings** | Ollama (nomic-embed-text) | Dense semantic search |
| **Keyword Matching** | BM25 | Sparse retrieval |
| **Vector Store** | ChromaDB | Store + retrieve embeddings |
| **Reranking** | ColBERT | Precision ranking |
| **Fusion** | Reciprocal Rank Fusion | Combine multiple signals |

### Language Models

| Provider | Model | Speed | Quality |
|----------|-------|-------|---------|
| Ollama | Llama 3.2 (3B/8B) | Slow (local) | Good |
| Groq | Llama 3.3 70B | 2-3s | Excellent |
| Gemini | Gemini 1.5 Flash | 3-5s | Excellent |
| OpenAI | GPT-4o, GPT-4o-mini | 2-4s | Excellent |

### Code Parsing

| Tool | Purpose |
|------|---------|
| **tree-sitter** | AST-aware code parsing |
| **tree-sitter-languages** | Multi-language support (Python, JS, Java, C++, etc.) |

### Backend Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Web Framework** | FastAPI | REST API with auto-docs |
| **Server** | Uvicorn | ASGI server |
| **Validation** | Pydantic | Request/response models |
| **Streaming** | Server-Sent Events (SSE) | Real-time updates |
| **Database** | Supabase (PostgreSQL) | Persistent storage |
| **Auth** | Supabase Auth (JWT) | User authentication |
| **Environment** | python-dotenv | Configuration management |

### Frontend

| Component | Technology |
|-----------|-----------|
| **Web Frontend** | Next.js 16 (App Router, TypeScript, Tailwind) |
| **State/Data** | TanStack Query + local streaming reducers |
| **Auth Client** | Supabase JS (`@supabase/supabase-js`) |
| **Prototype UI** | Streamlit (`ui/streamlit_app.py`, optional) |

---

## Architecture & Design

### System Architecture Diagram

```
┌────────────────────────────────────────────────────────┐
│                  Frontend Layer                        │
├────────────────────────────────────────────────────────┤
│  Next.js Frontend (frontend/)                          │
│  - Authenticated repo/chat/eval UX                     │
│  - SSE streaming visualizations                         │
│  - Streamlit retained for internal testing (optional)   │
└────────────────────┬─────────────────────────────────┘
                     │ HTTP + SSE
                     ▼
┌────────────────────────────────────────────────────────┐
│              FastAPI REST Backend                      │
├────────────────────────────────────────────────────────┤
│  (api/main.py)                                         │
│  - CORS middleware                                     │
│  - JWT auth (Supabase)                                 │
│  - Router registration                                 │
└───┬──────────┬──────────┬──────────────────────────┬──┘
    │          │          │                          │
    ▼          ▼          ▼                          ▼
 /repo      /chat      /eval              /suggestions
 routers   routers    routers               routers
    │          │          │                          │
    └──────────┴──────────┴──────────────────────────┘
                          │
                          ▼
┌────────────────────────────────────────────────────────┐
│           API Service Layer                           │
├────────────────────────────────────────────────────────┤
│  - indexing_service.py   (SSE progress)               │
│  - chat_service.py       (SSE streaming)              │
│  - supabase_service.py   (DB operations)              │
└────────────────────┬───────────────────────────────┘
                     │
                     ▼
┌────────────────────────────────────────────────────────┐
│           Core RAG Engine (app/)                       │
├────────────────────────────────────────────────────────┤
│                                                        │
│  ┌──────────────────────────────────────────────────┐ │
│  │ Ingestion Layer                                  │ │
│  │  - repo_loader.py    (clone / load repos)        │ │
│  │  - file_filter.py    (ignore patterns)           │ │
│  └──────────────────────────────────────────────────┘ │
│                         ▼                             │
│  ┌──────────────────────────────────────────────────┐ │
│  │ Parsing & Chunking                               │ │
│  │  - code_parser.py    (tree-sitter, AST aware)    │ │
│  │  - chunk_utils.py    (semantic chunking)         │ │
│  └──────────────────────────────────────────────────┘ │
│                         ▼                             │
│  ┌──────────────────────────────────────────────────┐ │
│  │ Indexing                                         │ │
│  │  - index_builder.py  (ChromaDB + LlamaIndex)     │ │
│  │  - vector_store.py   (embedding storage)         │ │
│  │  - file_map_builder  (coarse search index)       │ │
│  └──────────────────────────────────────────────────┘ │
│                         ▼                             │
│  ┌──────────────────────────────────────────────────┐ │
│  │ Retrieval Pipeline                               │ │
│  │  - hybrid_retriever  (dense + sparse fusion)     │ │
│  │  - query_router      (code vs architectural)     │ │
│  │  - reranker          (ColBERT, optional)         │ │
│  │  - ranking           (RRF scoring)               │ │
│  │  - file_map_retriever (coarse filtering)         │ │
│  └──────────────────────────────────────────────────┘ │
│                         ▼                             │
│  ┌──────────────────────────────────────────────────┐ │
│  │ LLM & Prompt                                     │ │
│  │  - llm_client.py     (multi-provider support)    │ │
│  │  - prompts.py        (query routing logic)       │ │
│  └──────────────────────────────────────────────────┘ │
│                         ▼                             │
│  ┌──────────────────────────────────────────────────┐ │
│  │ QA Service                                       │ │
│  │  - qa_service.py     (answer generation)         │ │
│  │  - chat_memory.py    (conversation history)      │ │
│  └──────────────────────────────────────────────────┘ │
└────────────────────┬───────────────────────────────┘
                     │
                     ▼
┌────────────────────────────────────────────────────────┐
│           External Services                           │
├────────────────────────────────────────────────────────┤
│  - Supabase PostgreSQL (persistent storage)           │
│  - Ollama (local embeddings + optional LLM)           │
│  - Groq API (fast cloud LLM, optional)                │
│  - Gemini API (cloud LLM, optional)                   │
│  - OpenAI API (cloud LLM, optional)                   │
│  - GitHub (source code repositories)                  │
└────────────────────────────────────────────────────────┘
```

---

### Core Design Principles

#### 1. **Provider Agnostic Core**

- All LLM logic lives in `app/` layer (provider-neutral)
- Switchable backends: Ollama → Groq → OpenAI without code changes
- Configuration-driven provider selection

```python
# Switch LLM with one env var:
LLM_PROVIDER=ollama     # local inference
LLM_PROVIDER=groq       # cloud (fast, free)
LLM_PROVIDER=openai     # premium quality
```

#### 2. **API Layer Separation**

- `api/` — HTTP concerns only (auth, validation, response shaping)
- `app/` — Pure business logic, reusable by any client
- Result: Streamlit UI and FastAPI backend share the same core without duplication

#### 3. **Real-Time Streaming**

- Indexing progress streamed via SSE (step-by-step 0% → 100%)
- Chat responses streamed token-by-token via SSE
- Metadata emitted after stream (latency, query mode, retrieved files)
- Messages persisted to DB after streaming completes

#### 4. **Modular Retrieval Pipeline**

```
User Query
    ↓
Query Router (code_lookup vs architectural?)
    ↓
Hybrid Retriever (dense + sparse + file-level)
    ↓
Reciprocal Rank Fusion (merge signals)
    ↓
ColBERT Reranker (optional, configurable)
    ↓
Top 5 Chunks → Prompt
    ↓
LLM Generation (Ollama/Groq/etc)
    ↓
Stream Response + Save to DB
```

---

### Data Flow

#### Flow 1: Repository Indexing

```
1. User provides GitHub URL or local path
                ↓
2. Backend clones repo or validates local path (emit: "cloning", 10%)
                ↓
3. File filter ignores node_modules, .git, venv, etc (emit: "filtering", 20%)
                ↓
4. tree-sitter parses all files, extracts functions/classes (emit: "parsing", 40%)
                ↓
5. Semantic chunking creates ~50-line blocks with metadata (emit: "embedding", 65%)
                ↓
6. Ollama embedding: dense vector for each chunk
   ChromaDB: stores vectors + metadata
                ↓
7. BM25 index: sparse keyword index on chunk text
                ↓
8. LlamaIndex DocumentSummaryIndex: coarse file-level index (emit: "indexing", 80%)
                ↓
9. Context builder: generates file summaries (emit: "done", 100%)
                ↓
10. Supabase: save repo metadata, file count, node count, status="ready"
```

**SSE Events Sent to Frontend:**
```json
{ "step": "cloning",   "message": "Cloning repository...",        "progress": 10 }
{ "step": "filtering", "message": "Filtering files...",           "progress": 25 }
{ "step": "parsing",   "message": "Parsing 47 files...",          "progress": 40 }
{ "step": "embedding", "message": "Building embeddings...",       "progress": 65 }
{ "step": "indexing",  "message": "Building summary index...",    "progress": 80 }
{ "step": "done",      "message": "Indexing complete!",           "progress": 100, "file_count": 47, "node_count": 312 }
```

---

#### Flow 2: Chat / Question Answering

```
1. User submits query + chat_id
                ↓
2. Load chat history from Supabase (previous messages)
                ↓
3. Query Router: classify query (code_lookup vs architectural?)
                ↓
4a [code_lookup mode]:
    - Dense retrieval: embed query, find similar chunks (ChromaDB)
    - Sparse retrieval: BM25 keyword match
    - File-level: DocumentSummaryIndex narrows to top 3 files
    - Fusion: RRF combines all signals → top 10 chunks
                ↓
4b [architectural mode]:
    - Same retrieval, but prompt tells LLM to reason more broadly
    - Can reference architectural patterns, not just code
                ↓
5. Reranking (if USE_COLBERT=true):
    - ColBERT reranks top 10 → top 5 chunks (~1-2s)
                ↓
6. Prompt Assembly:
    - System prompt (role, instructions based on query_mode)
    - Retrieved chunks (with file paths, metadata)
    - Conversation history (previous messages)
    - User query
                ↓
7. LLM Generation (streaming):
    - Stream tokens to client as SSE
    - Measure latency (retrieval, rerank, LLM time)
                ↓
8. After stream completes:
    - Emit metadata event: {query_mode, retrieved_files, latencies}
    - Save user message + assistant response to Supabase
    - Include mode, retrieved files, latency breakdown
```

**SSE Events Sent to Frontend:**
```json
{ "type": "token",    "content": "The retrieve_relevant_chunks function..." }
{ "type": "token",    "content": " is located in retrieval/retriever.py" }
...
{ "type": "metadata", 
  "query_mode": "code_lookup", 
  "retrieved_files": ["retrieval/retriever.py", "retrieval/hybrid_retriever.py", ...],
  "latency_retrieval_ms": 95,
  "latency_rerank_ms": 0,
  "latency_llm_ms": 2100,
  "latency_total_ms": 2195
}
{ "type": "done" }
```

---

## Project Structure

```
codebase-copilot/
│
├── app/                                    # Core RAG engine (provider-agnostic)
│   ├── config.py                           # Configuration (LLM provider, paths, etc)
│   ├── main.py                             # App entry point (currently unused, kept for reference)
│   │
│   ├── ingestion/                          # Step 1: Load repositories
│   │   ├── __init__.py
│   │   ├── repo_loader.py                  # Clone GitHub repos or load local paths
│   │   └── file_filter.py                  # Ignore patterns (node_modules, .git, etc)
│   │
│   ├── parsing/                            # Step 2: Parse and chunk code
│   │   ├── __init__.py
│   │   ├── code_parser.py                  # tree-sitter AST parsing
│   │   └── chunk_utils.py                  # Semantic chunking logic
│   │
│   ├── indexing/                           # Step 3: Build indexes
│   │   ├── __init__.py
│   │   ├── index_builder.py                # Main indexing pipeline
│   │   ├── vector_store.py                 # ChromaDB integration
│   │   ├── file_map_builder.py             # Coarse file-level index
│   │   └── summary_index_builder.py        # Context building
│   │
│   ├── retrieval/                          # Step 4: Retrieve relevant chunks
│   │   ├── __init__.py
│   │   ├── retriever.py                    # Main retriever interface
│   │   ├── hybrid_retriever.py             # Dense + sparse fusion
│   │   ├── query_router.py                 # Classify queries (code vs architectural)
│   │   ├── reranker.py                     # ColBERT reranking (optional)
│   │   ├── ranking.py                      # RRF and ranking logic
│   │   └── file_map_retriever.py           # Coarse file filtering
│   │
│   ├── llm/                                # Step 5: LLM integration
│   │   ├── __init__.py
│   │   ├── llm_client.py                   # Multi-provider LLM factory
│   │   └── prompts.py                      # Prompt templates + routing logic
│   │
│   ├── memory/                             # Conversation history
│   │   └── chat_memory.py                  # In-memory chat context
│   │
│   ├── services/                           # High-level services
│   │   ├── __init__.py
│   │   ├── repo_service.py                 # Orchestrate indexing pipeline
│   │   └── qa_service.py                   # Orchestrate QA pipeline
│   │
│   └── utils/                              # Utilities
│       ├── __init__.py
│       ├── helpers.py                      # Common utility functions
│       └── logger.py                       # Logging configuration
│
├── api/                                    # FastAPI REST backend
│   ├── main.py                             # App entry point, CORS, routers
│   ├── dependencies.py                     # Supabase client, JWT auth
│   │
│   ├── routers/                            # HTTP endpoints
│   │   ├── repo.py                         # POST /api/repo/index, GET /api/repo/{id}, etc
│   │   ├── chat.py                         # POST /api/chat/session, POST /api/chat/{id}/message/stream
│   │   ├── eval.py                         # POST /api/eval/run, GET /api/eval/{repo_id}/latest
│   │   └── suggestions.py                  # GET /api/repo/{repo_id}/suggestions
│   │
│   ├── models/                             # Pydantic request/response schemas
│   │   ├── repo.py                         # Repository models
│   │   ├── chat.py                         # Chat models
│   │   └── eval.py                         # Evaluation models
│   │
│   └── services/                           # API-layer services
│       ├── indexing_service.py             # SSE-based indexing orchestration
│       ├── chat_service.py                 # SSE streaming responses
│       └── supabase_service.py             # All Supabase DB operations
│
├── frontend/                               # Next.js production frontend
│   ├── app/                                # Routes (repos/chat/eval/login)
│   ├── components/                         # UI components
│   ├── hooks/                              # React Query hooks
│   └── lib/                                # API clients + SSE parser + types
│
├── ui/                                     # Internal prototype frontend
│   └── streamlit_app.py                    # Streamlit UI
│
├── data/                                   # Local storage
│   ├── repos/                              # Cloned repositories (during indexing)
│   ├── index/                              # ChromaDB + LlamaIndex indexes
│   └── eval_results*.json                  # Evaluation results
│
├── requirements.txt                        # Core dependencies
├── requirements-api.txt                    # FastAPI-specific dependencies
├── requirements-llamaindex.txt             # LlamaIndex + RAG dependencies
│
├── evaluate.py                             # Standalone evaluation script
├── run_complete_features.py                # Single-command launcher
├── env.api.example                         # Example environment variables
├── run_api.sh                              # Shell script to start FastAPI backend
├── README.md                               # Original project README
└── COMPLETE_PROJECT_GUIDE.md               # This file
```

---

### Key Files Explained

#### `app/config.py`
Centralized configuration for the entire system:
```python
LLM_PROVIDER       # "ollama", "groq", "gemini", "openai"
OLLAMA_BASE_URL    # http://localhost:11434
OLLAMA_LLM_MODEL   # llama3.2:3b (or your model)
OLLAMA_EMBED_MODEL # nomic-embed-text
USE_COLBERT        # true/false — enable ColBERT reranking
USE_FAST_LLM       # true/false — use Groq instead of LLM_PROVIDER
GROQ_FAST_MODEL    # llama-3.3-70b-versatile or llama-3.1-8b-instant
TOP_K_FILES        # 3 — files returned by coarse index
TOP_K_CHUNKS       # 10 — chunks returned by hybrid retriever
TOP_K_RERANK       # 5 — final chunks to LLM
```

#### `api/main.py`
FastAPI application setup:
```python
- CORS middleware configuration
- LlamaIndex pre-initialization at startup
- Router registration (/api/repo, /api/chat, /api/eval, /api/suggestions)
- Health check endpoint
```

#### `api/dependencies.py`
Authentication and Supabase client setup:
```python
get_current_user()    # JWT verification, returns user_id
get_optional_user()   # Returns None if no token (guest mode)
get_supabase()        # Supabase client instance
```

#### `api/services/indexing_service.py`
Wraps the core indexing pipeline with SSE progress streaming:
```python
- Emits progress events every step (cloning, filtering, parsing, etc)
- Frontend receives real-time progress bar updates
- Handles errors gracefully
```

#### `api/services/chat_service.py`
Orchestrates chat responses with SSE streaming:
```python
- Loads chat history from Supabase
- Calls core QA service (app/services/qa_service.py)
- Streams tokens to client in real-time
- Emits metadata after stream completes
- Persists message to Supabase asynchronously
```

#### `api/services/supabase_service.py`
All database operations:
```python
Tables:
  - profiles       (user data)
  - repositories   (indexed repos, status, file count)
  - chats          (chat sessions per repo)
  - messages       (individual messages with latency/mode)
  - evaluations    (eval results with all metrics)
```

#### `app/ingestion/repo_loader.py`
Load repositories from GitHub or local filesystem:
```python
- Git clone if GitHub URL
- Local validation if file path
- Handle errors (network, permissions, disk space)
```

#### `app/parsing/code_parser.py`
Parse code using tree-sitter for AST awareness:
```python
- Support multiple languages (Python, JS, Java, C++, etc)
- Extract functions, classes, methods with metadata
- Preserve code structure information
```

#### `app/indexing/index_builder.py`
Main indexing orchestrator:
```python
1. Load repository files
2. Parse and chunk code
3. Generate embeddings via Ollama
4. Store vectors in ChromaDB
5. Build BM25 index
6. Create DocumentSummaryIndex
7. Generate context summaries
```

#### `app/retrieval/hybrid_retriever.py`
Hybrid retrieval combining dense + sparse:
```python
- Dense: semantic search via embeddings (ChromaDB)
- Sparse: keyword matching (BM25)
- Fusion: Reciprocal Rank Fusion combines scores
- Returns top 10 ranked chunks
```

#### `app/retrieval/query_router.py`
Classify queries into two modes:
```python
code_lookup mode:
  - Instruction: be grounded, cite code
  - Use standard retrieval
  - Higher specificity

architectural mode:
  - Instruction: can reason broadly
  - Same retrieval
  - Broader interpretation
```

#### `app/llm/llm_client.py`
Multi-provider LLM factory:
```python
get_llm():
  if USE_FAST_LLM: return Groq(GROQ_FAST_MODEL)
  elif LLM_PROVIDER == "ollama": return Ollama(...)
  elif LLM_PROVIDER == "groq": return Groq(...)
  elif LLM_PROVIDER == "gemini": return Gemini(...)
  elif LLM_PROVIDER == "openai": return OpenAI(...)

get_embed_model():
  return Ollama(OLLAMA_EMBED_MODEL)  # Always local
```

---

## Configuration & Setup

### Environment Variables

Create `.env` in project root with these variables:

```bash
# ═══════════════════════════════════════════════════════════════
# LLM Provider Selection
# ═══════════════════════════════════════════════════════════════
LLM_PROVIDER=ollama                    # Options: ollama, groq, gemini, openai

# ═══════════════════════════════════════════════════════════════
# Fast LLM Toggle (switch to Groq for faster iteration)
# ═══════════════════════════════════════════════════════════════
USE_FAST_LLM=false                     # Set to true to use Groq instead
GROQ_FAST_MODEL=llama-3.3-70b-versatile  # or llama-3.1-8b-instant for speed

# ═══════════════════════════════════════════════════════════════
# API Keys (as needed based on LLM_PROVIDER)
# ═══════════════════════════════════════════════════════════════
GEMINI_API_KEY=                        # Required if LLM_PROVIDER=gemini
GROQ_API_KEY=                          # Required if LLM_PROVIDER=groq
OPENAI_API_KEY=                        # Required if LLM_PROVIDER=openai

# ═══════════════════════════════════════════════════════════════
# Ollama Configuration (used for local embeddings + optional LLM)
# ═══════════════════════════════════════════════════════════════
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_LLM_MODEL=llama3.2:3b           # Or mistral, llama2, etc
OLLAMA_EMBED_MODEL=nomic-embed-text

# ═══════════════════════════════════════════════════════════════
# Retrieval Configuration
# ═══════════════════════════════════════════════════════════════
USE_COLBERT=true                       # Enable ColBERT reranking (adds ~1-2s)
TOP_K_FILES=3                          # Coarse file filtering
TOP_K_CHUNKS=10                        # Pre-rerank chunk count
TOP_K_RERANK=5                         # Final chunks to LLM

# ═══════════════════════════════════════════════════════════════
# Supabase (FastAPI Backend Only)
# ═══════════════════════════════════════════════════════════════
SUPABASE_URL=https://your-project.supabase.co/rest/v1/
SUPABASE_SERVICE_KEY=eyJ...           # Service role key (NOT anon key)

# ═══════════════════════════════════════════════════════════════
# Frontend URL (for CORS)
# ═══════════════════════════════════════════════════════════════
FRONTEND_URL=http://localhost:3000
```

### Getting API Keys

#### Ollama (Free, Local)
```bash
# Download from https://ollama.ai/download
# Then pull required models
ollama pull llama3.2:3b
ollama pull nomic-embed-text
```

#### Groq (Free Tier Available)
```
1. Sign up: https://console.groq.com/keys
2. Copy API key
3. Add to .env: GROQ_API_KEY=...
```

#### Gemini (Paid)
```
1. Go to: https://aistudio.google.com/app/apikeys
2. Create API key
3. Add to .env: GEMINI_API_KEY=...
```

#### OpenAI (Paid)
```
1. Sign up: https://platform.openai.com/account/api-keys
2. Create API key
3. Add to .env: OPENAI_API_KEY=...
```

#### Supabase (Paid, Free tier available)
```
1. Sign up: https://supabase.com
2. Create new project
3. Get URL from Settings → API
4. Get service role key from Settings → API → Service role
5. Add to .env: SUPABASE_URL=... SUPABASE_SERVICE_KEY=...
```

---

## Installation & Running

### Prerequisites

- **Python 3.10+** (3.10 or 3.11 recommended)
- **Git** (for cloning repositories)
- **Ollama** (if using local LLM or embeddings) — Download from https://ollama.ai/download

### Step 1: Clone Repository

```bash
git clone <repository-url>
cd codebase-copilot
```

### Step 2: Create Python Environment

```bash
# Using conda (recommended)
conda create -n codebase-copilot python=3.10
conda activate codebase-copilot

# OR using venv
python -m venv venv
source venv/bin/activate           # On macOS/Linux
# OR
venv\Scripts\activate              # On Windows
```

### Step 3: Install Dependencies

```bash
# Install core RAG + LlamaIndex dependencies
pip install -r requirements-llamaindex.txt

# Install FastAPI backend dependencies
pip install -r requirements-api.txt

# OR install all at once
pip install -r requirements.txt -r requirements-api.txt -r requirements-llamaindex.txt
```

### Step 4: Configure Environment

```bash
# Copy example and fill in your API keys
cp env.api.example .env

# Edit .env with your values
nano .env  # or use your editor
```

### Step 5: Start Ollama (if using local LLM)

```bash
# Terminal 1: Start Ollama server
ollama serve

# In another terminal, pull models
ollama pull llama3.2:3b
ollama pull nomic-embed-text
```

### Step 6: Start all services (recommended)

```bash
python run_complete_features.py
```

This launches backend + Next.js frontend in one command.

### Step 7: Start services manually (alternative)

```bash
# Terminal 2: Start FastAPI backend
uvicorn api.main:app --reload --port 8000

# Terminal 3: Start Next.js frontend
cd frontend
npm install
npm run dev
```

### Step 8: Start Streamlit UI (Optional)

```bash
# Optional internal/prototype UI
streamlit run ui/streamlit_app.py
```

Streamlit opens at `http://localhost:8501`

### Step 9: Run Evaluation (Optional)

```bash
# Standalone evaluation (requires a repository to be indexed first)
python evaluate.py
```

---

## API Reference

All endpoints require a valid Supabase JWT in the `Authorization: Bearer <token>` header.

### Base URL
```
http://localhost:8000
```

### Health Check

#### `GET /api/health`

**Description**: Check API status and configuration

**Response**:
```json
{
  "status": "ok",
  "llm_provider": "ollama",
  "use_fast_llm": false,
  "colbert_enabled": true
}
```

---

### Repository Endpoints

#### `POST /api/repo/index`

**Description**: Start indexing a repository

**Request Body**:
```json
{
  "source": "https://github.com/user/repo",  // GitHub URL or local path
  "repo_name": "my-repo"  // Optional friendly name
}
```

**Response**:
```json
{
  "repo_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "indexing"
}
```

---

#### `GET /api/repo/{repo_id}/index-progress`

**Description**: Stream real-time indexing progress (Server-Sent Events)

**Response** (SSE Stream):
```
data: {"step": "cloning", "message": "Cloning repository...", "progress": 10}

data: {"step": "filtering", "message": "Filtering files...", "progress": 25}

data: {"step": "parsing", "message": "Parsing 47 files...", "progress": 40}

data: {"step": "embedding", "message": "Building embeddings...", "progress": 65}

data: {"step": "indexing", "message": "Building summary index...", "progress": 80}

data: {"step": "done", "message": "Indexing complete!", "progress": 100, "file_count": 47, "node_count": 312}
```

---

#### `GET /api/repo/list`

**Description**: List all repositories for authenticated user

**Response**:
```json
{
  "repositories": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "name": "my-repo",
      "status": "ready",
      "file_count": 47,
      "node_count": 312,
      "created_at": "2024-07-08T10:30:00Z"
    }
  ]
}
```

---

#### `GET /api/repo/{repo_id}`

**Description**: Get status and metadata for a single repository

**Response**:
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "my-repo",
  "status": "ready",
  "file_count": 47,
  "node_count": 312,
  "created_at": "2024-07-08T10:30:00Z",
  "error": null
}
```

---

#### `DELETE /api/repo/{repo_id}`

**Description**: Delete repository, index, and cloned files

**Response**:
```json
{
  "success": true,
  "message": "Repository deleted"
}
```

---

#### `GET /api/repo/{repo_id}/suggestions`

**Description**: Generate 6 suggested questions for a repository

**Response**:
```json
{
  "suggestions": [
    "How does the hybrid retriever work?",
    "What is the indexing pipeline?",
    "How are queries routed?",
    "What retrieval metrics are measured?",
    "How does conversational memory work?",
    "What LLM providers are supported?"
  ]
}
```

---

### Chat Endpoints

#### `POST /api/chat/session`

**Description**: Create a new chat session for a repository

**Request Body**:
```json
{
  "repo_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Response**:
```json
{
  "chat_id": "660e8400-e29b-41d4-a716-446655440001",
  "repo_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

---

#### `POST /api/chat/{chat_id}/message/stream`

**Description**: Send message and stream AI response (Server-Sent Events)

**Request Body**:
```json
{
  "query": "How does hybrid retrieval work?"
}
```

**Response** (SSE Stream):
```
data: {"type": "token", "content": "Hybrid retrieval"}

data: {"type": "token", "content": " combines dense semantic"}

data: {"type": "token", "content": " and sparse keyword matching..."}

data: {"type": "metadata", "query_mode": "code_lookup", "retrieved_files": ["retrieval/hybrid_retriever.py", "retrieval/ranking.py"], "latency_retrieval_ms": 95, "latency_rerank_ms": 1200, "latency_llm_ms": 2100, "latency_total_ms": 3395}

data: {"type": "done"}
```

---

#### `GET /api/chat/{chat_id}/messages`

**Description**: Fetch full message history for a chat

**Response**:
```json
{
  "messages": [
    {
      "id": "msg-1",
      "role": "user",
      "content": "How does hybrid retrieval work?",
      "created_at": "2024-07-08T10:30:00Z"
    },
    {
      "id": "msg-2",
      "role": "assistant",
      "content": "Hybrid retrieval combines...",
      "query_mode": "code_lookup",
      "retrieved_files": ["retrieval/hybrid_retriever.py"],
      "latency_ms": 3395,
      "created_at": "2024-07-08T10:30:05Z"
    }
  ]
}
```

---

#### `GET /api/chat/list?repo_id={repo_id}`

**Description**: List all chats for a repository

**Response**:
```json
{
  "chats": [
    {
      "id": "660e8400-e29b-41d4-a716-446655440001",
      "repo_id": "550e8400-e29b-41d4-a716-446655440000",
      "created_at": "2024-07-08T10:30:00Z",
      "message_count": 5
    }
  ]
}
```

---

#### `DELETE /api/chat/{chat_id}`

**Description**: Delete a chat session and all messages

**Response**:
```json
{
  "success": true,
  "message": "Chat deleted"
}
```

---

### Evaluation Endpoints

#### `POST /api/eval/run`

**Description**: Run evaluation pipeline (Server-Sent Events)

**Request Body**:
```json
{
  "repo_id": "550e8400-e29b-41d4-a716-446655440000",
  "index_name": "my-repo"
}
```

**Response** (SSE Stream):
```
data: {"type": "progress", "message": "Running query 1/10..."}

data: {"type": "progress", "message": "Running query 2/10..."}

data: {"type": "result", "summary": {"hit_rate": 0.80, "mrr": 0.65, "faithfulness": 0.72, "relevancy": 0.92, "retrieval_latency_ms": 95, "rerank_latency_ms": 1200, "llm_latency_ms": 2100}}

data: {"type": "done"}
```

---

#### `GET /api/eval/{repo_id}/latest`

**Description**: Get most recent evaluation results

**Response**:
```json
{
  "repo_id": "550e8400-e29b-41d4-a716-446655440000",
  "timestamp": "2024-07-08T10:30:00Z",
  "metrics": {
    "hit_rate": 0.80,
    "mrr": 0.65,
    "faithfulness": 0.72,
    "relevancy": 0.92,
    "routing_accuracy": 1.0,
    "retrieval_latency_ms": 95,
    "rerank_latency_ms": 1200,
    "llm_latency_ms": 2100,
    "total_latency_ms": 3395
  }
}
```

---

## Database Schema

### Supabase Tables

#### `profiles`
```sql
CREATE TABLE profiles (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  user_id UUID UNIQUE NOT NULL,
  email VARCHAR(255) NOT NULL,
  display_name VARCHAR(255),
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### `repositories`
```sql
CREATE TABLE repositories (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  user_id UUID NOT NULL REFERENCES profiles(user_id),
  name VARCHAR(255) NOT NULL,
  source VARCHAR(512) NOT NULL,
  status VARCHAR(50) NOT NULL,  -- 'indexing', 'ready', 'error'
  file_count INT,
  node_count INT,
  error_message TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### `chats`
```sql
CREATE TABLE chats (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  user_id UUID NOT NULL REFERENCES profiles(user_id),
  repo_id UUID NOT NULL REFERENCES repositories(id),
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### `messages`
```sql
CREATE TABLE messages (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  chat_id UUID NOT NULL REFERENCES chats(id),
  role VARCHAR(50) NOT NULL,  -- 'user', 'assistant'
  content TEXT NOT NULL,
  query_mode VARCHAR(50),     -- 'code_lookup', 'architectural'
  retrieved_files JSON,       -- Array of file paths
  latency_ms INT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### `evaluations`
```sql
CREATE TABLE evaluations (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  repo_id UUID NOT NULL REFERENCES repositories(id),
  hit_rate FLOAT,
  mrr FLOAT,
  faithfulness FLOAT,
  relevancy FLOAT,
  routing_accuracy FLOAT,
  retrieval_latency_ms FLOAT,
  rerank_latency_ms FLOAT,
  llm_latency_ms FLOAT,
  total_latency_ms FLOAT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## Usage Examples

### Example 1: Index a Repository via API

```bash
# Create a new repository indexing job
curl -X POST http://localhost:8000/api/repo/index \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "source": "https://github.com/openai/gpt-2",
    "repo_name": "gpt-2"
  }'

# Response:
{
  "repo_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "indexing"
}

# Monitor indexing progress
curl http://localhost:8000/api/repo/550e8400-e29b-41d4-a716-446655440000/index-progress \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -N

# Output (SSE stream):
# data: {"step": "cloning", "message": "Cloning repository...", "progress": 10}
# data: {"step": "filtering", "message": "Filtering files...", "progress": 25}
# ... etc
```

### Example 2: Chat with Indexed Repository

```bash
# Create chat session
curl -X POST http://localhost:8000/api/chat/session \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "repo_id": "550e8400-e29b-41d4-a716-446655440000"
  }'

# Response:
{
  "chat_id": "660e8400-e29b-41d4-a716-446655440001",
  "repo_id": "550e8400-e29b-41d4-a716-446655440000"
}

# Send message and stream response
curl -X POST http://localhost:8000/api/chat/660e8400-e29b-41d4-a716-446655440001/message/stream \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "How is attention implemented in this codebase?"
  }' \
  -N

# Output (SSE stream):
# data: {"type": "token", "content": "Attention"}
# data: {"type": "token", "content": " is implemented"}
# ... stream continues ...
# data: {"type": "metadata", "query_mode": "code_lookup", ...}
# data: {"type": "done"}
```

### Example 3: Get Repository Suggestions

```bash
curl http://localhost:8000/api/repo/550e8400-e29b-41d4-a716-446655440000/suggestions \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"

# Response:
{
  "suggestions": [
    "What is the attention mechanism?",
    "How does the transformer work?",
    "What is the GPT-2 architecture?",
    ...
  ]
}
```

### Example 4: Run Evaluation

```bash
curl -X POST http://localhost:8000/api/eval/run \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "repo_id": "550e8400-e29b-41d4-a716-446655440000",
    "index_name": "gpt-2"
  }' \
  -N

# Output (SSE stream):
# data: {"type": "progress", "message": "Running query 1/10..."}
# ... evaluation runs ...
# data: {"type": "result", "summary": {...}}
# data: {"type": "done"}
```

---

## Troubleshooting

### Issue: "ModuleNotFoundError: No module named 'app'"

**Solution**: Run FastAPI from project root:
```bash
cd /path/to/codebase-copilot
uvicorn api.main:app --reload --port 8000
```

---

### Issue: "ConnectionError: Failed to connect to Ollama"

**Solution**: Ensure Ollama is running:
```bash
# Terminal 1
ollama serve

# Terminal 2 (verify connection)
curl http://localhost:11434/api/tags
```

---

### Issue: "ValueError: OLLAMA_EMBED_MODEL not found"

**Solution**: Pull the embedding model:
```bash
ollama pull nomic-embed-text
```

---

### Issue: "401 Unauthorized" on API calls

**Solution**: Include valid Supabase JWT in header:
```bash
curl http://localhost:8000/api/health \
  -H "Authorization: Bearer YOUR_SUPABASE_JWT_TOKEN"
```

---

### Issue: "ChromaDB connection error"

**Solution**: Clear ChromaDB cache and restart:
```bash
rm -rf data/index/*
uvicorn api.main:app --reload --port 8000
```

---

### Issue: Slow LLM responses (~15+ seconds)

**Solution**: Switch to a faster LLM provider:
```bash
# In .env
USE_FAST_LLM=true
GROQ_FAST_MODEL=llama-3.3-70b-versatile
# or
GROQ_FAST_MODEL=llama-3.1-8b-instant  # Even faster
```

---

### Issue: High token usage / long response times

**Solutions**:
1. Disable ColBERT reranking (saves ~1-2s):
   ```bash
   USE_COLBERT=false
   ```

2. Reduce retrieved chunks:
   ```bash
   TOP_K_CHUNKS=5
   TOP_K_RERANK=3
   ```

3. Use faster embedding model (trade-off with quality):
   ```bash
   OLLAMA_EMBED_MODEL=all-MiniLM-L6-v2  # Faster but lower quality
   ```

---

### Issue: "Repository cloning failed"

**Solutions**:
1. Check network connectivity
2. Verify GitHub URL is correct
3. For private repos, ensure SSH keys are configured
4. Check disk space: `df -h`

---

### Issue: Evaluation takes too long (>10 minutes)

**Solution**: Use fast LLM during evaluation:
```bash
USE_FAST_LLM=true
GROQ_FAST_MODEL=llama-3.1-8b-instant
```

---

## Quick Reference: Common Commands

### Start Everything (single command)

```bash
python run_complete_features.py
```

### Start Everything (manual, 4-5 terminals)

```bash
# Terminal 1: Ollama server
ollama serve

# Terminal 2: FastAPI backend
cd /path/to/codebase-copilot
uvicorn api.main:app --reload --port 8000

# Terminal 3: Next.js frontend
cd frontend
npm install
npm run dev

# Terminal 4: Optional Streamlit prototype UI
streamlit run ui/streamlit_app.py

# Terminal 5: Optional evaluation
python evaluate.py
```

### Environment Switching

```bash
# Local LLM (Ollama) - Slow but free
LLM_PROVIDER=ollama

# Fast cloud (Groq) - Free tier available
USE_FAST_LLM=true
GROQ_FAST_MODEL=llama-3.3-70b-versatile

# Premium quality (OpenAI)
LLM_PROVIDER=openai

# Disable reranking for speed
USE_COLBERT=false
```

### Development Workflow

```bash
# 1. Create environment
conda create -n copilot python=3.10
conda activate copilot

# 2. Install dependencies
pip install -r requirements-llamaindex.txt requirements-api.txt

# 3. Configure .env
cp env.api.example .env
# Edit .env with your settings

# 4. Start backend (development mode with auto-reload)
uvicorn api.main:app --reload --port 8000

# 5. Test health endpoint
curl http://localhost:8000/api/health

# 6. Start Next.js frontend
cd frontend
npm install
npm run dev

# 7. (Optional) Start Streamlit prototype UI
streamlit run ui/streamlit_app.py
```

---

## Performance Tips

### Optimize for Speed
```bash
USE_FAST_LLM=true
GROQ_FAST_MODEL=llama-3.1-8b-instant
USE_COLBERT=false
TOP_K_CHUNKS=5
TOP_K_RERANK=3
```

### Optimize for Quality
```bash
LLM_PROVIDER=openai
USE_COLBERT=true
TOP_K_CHUNKS=10
TOP_K_RERANK=5
```

### Optimize for Free/Local
```bash
LLM_PROVIDER=ollama
USE_COLBERT=false
TOP_K_CHUNKS=5
```

---

## Next Steps

1. **Set up environment** — Follow installation steps
2. **Configure LLM** — Choose Ollama, Groq, or cloud provider
3. **Set up Supabase** — Create project and get credentials
4. **Start backend** — `uvicorn api.main:app --reload`
5. **Index a repository** — Use `/api/repo/index` endpoint
6. **Chat with codebase** — Use `/api/chat/{chat_id}/message/stream`
7. **Run evaluation** — Measure system quality with `/api/eval/run`
8. **Deploy to production** — Consider cloud hosting for API + database

---

## Additional Resources

- **LlamaIndex Docs**: https://docs.llamaindex.ai/
- **FastAPI Docs**: https://fastapi.tiangolo.com/
- **Supabase Docs**: https://supabase.com/docs/
- **Ollama Models**: https://ollama.ai/library
- **ColBERT**: https://github.com/stanford-futuredata/ColBERT

---

**Created**: July 2026  
**Version**: 1.0.0  
**Status**: Production Ready

For questions or issues, refer to the troubleshooting section or check GitHub issues.

