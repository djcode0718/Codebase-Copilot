# 🚀 Codebase Copilot

> An **Enterprise Repository Intelligence Platform** — your AI-powered Digital Twin and Knowledge Authority for any software repository. Combines hybrid RAG retrieval, architecture discovery, Mermaid diagram generation, security intelligence, health scoring, live visualization, and 18 intelligence capabilities into a unified workspace.

<p align="center">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.10-blue?logo=python&logoColor=white">
  <img alt="FastAPI" src="https://img.shields.io/badge/FastAPI-Backend-009688?logo=fastapi&logoColor=white">
  <img alt="Next.js" src="https://img.shields.io/badge/Next.js-16-black?logo=next.js&logoColor=white">
  <img alt="Supabase" src="https://img.shields.io/badge/Supabase-Auth%20%2B%20DB-3ECF8E?logo=supabase&logoColor=white">
  <img alt="Tests" src="https://img.shields.io/badge/Tests-238%20passing-brightgreen?logo=pytest&logoColor=white">
  <img alt="License" src="https://img.shields.io/badge/License-MIT-lightgrey">
</p>

---

## 📌 Overview

**Codebase Copilot** is a modular, enterprise-grade Repository Intelligence Platform built on Retrieval-Augmented Generation (RAG). It acts as your permanent **Repository Digital Twin** — an AI system that understands, analyzes, visualizes, and continuously learns from software repositories.

The system combines:

* hybrid retrieval (dense + BM25 + RRF)
* semantic search & symbol analysis
* reranking & dual-mode query routing
* **architecture discovery & Mermaid diagram generation**
* **repository health scoring (0–100)**
* **12 intelligence action categories** (security, code quality, tech debt, onboarding, etc.)
* **structured intelligence response format** (Answer / Architecture View / Engineering View / Business View / Evidence / Risks / Recommendations / Confidence)
* **Mermaid diagram rendering** in chat responses
* **export capabilities** (MD, JSON, chat history)
* conversational memory & multi-turn context
* evaluation pipelines (Hit Rate, MRR, Faithfulness, Relevancy, Latency)
* multi-LLM orchestration (Ollama, Groq, Gemini, OpenAI)
* a REST API backend (FastAPI)
* persistent storage & auth (Supabase)
* a production-grade Next.js frontend
* an extensive automated test suite

to provide:

✅ low-level code understanding (code lookup mode)
✅ higher-order architectural reasoning (architectural mode)
✅ business flow discovery and impact analysis
✅ security intelligence and vulnerability identification
✅ developer onboarding guides and mastery plans
✅ repository digital twin with evolving architecture model

---

## ✨ Key Features

### 🏛️ Repository Intelligence Platform

The workspace goes far beyond chat — it's a full **Repository Intelligence Platform** with 12 pre-built intelligence capabilities:

| Intelligence Action | What It Does |
|---|---|
| **Architecture Map** | Discovers system design, patterns, service relationships, generates Mermaid diagram |
| **Security Review** | Analyzes auth, input validation, secrets, API risks with severity ratings |
| **Business Flows** | Discovers all business capabilities, entry points, data sources, events |
| **Code Quality** | Quality score (0–100), anti-patterns, tech debt, remediation plan |
| **Impact Analysis** | Blast-radius analysis for change risk, dependency chain mapping |
| **Test Intelligence** | Coverage gaps, missing tests, edge cases, suggested test scenarios |
| **Onboarding Guide** | Role-based 30-minute → 30-day mastery plan |
| **API Documentation** | Enterprise-grade API docs for all endpoints |
| **Dependency Graph** | Module coupling, circular deps, critical path — Mermaid diagram |
| **Engineering Report** | Executive summary for engineering managers, technical + business view |
| **Tech Debt Scan** | Categorized debt inventory with prioritized remediation roadmap |
| **Digital Twin** | Living architecture model with full Mermaid diagram |

### 🧱 Why This Is Enterprise-Grade

This platform is intentionally designed as a **defensible enterprise-grade system**, not just another AI coding tool.
It combines:

- **Repository Chat**
- **Architecture Intelligence**
- **Knowledge Graph Thinking** (code relationships and dependency reasoning)
- **Business Flow Discovery**
- **Code Validation**
- **Live Visualization** (Mermaid + inspectable metadata)
- **Conversation Export**
- **Digital Twin Modeling**

Together, these capabilities create a durable repository intelligence layer for engineering, architecture, security, and leadership workflows.

### 📊 Repository Health Score

Every repository now gets an automatic **Health Score (0–100, graded A–F)** computed from:
- Indexing completeness
- File and chunk coverage
- LLM provider configuration
- Codebase richness

### 🏗️ Mermaid Diagram Rendering

AI responses containing `mermaid` code blocks are **automatically rendered as interactive diagrams** directly in the chat interface — supporting architecture diagrams, sequence diagrams, dependency graphs, and more.

### 📐 Structured Intelligence Responses

Intelligence queries return **structured, collapsible response sections**:
- **Answer** — direct, grounded response
- **Architecture View** — system design perspective
- **Engineering View** — implementation perspective
- **Business View** — business capability context
- **Evidence** — files, classes, methods cited
- **Risks** — identified risks and severity
- **Recommendations** — actionable next steps
- **Confidence** — evidence-based confidence level

### 📤 Export Capabilities

Every artifact is exportable:
- Repository Report (`.md`) — executive summary with metrics
- Repository Data (`.json`) — structured data with full metadata
- Chat History (`.md`) — complete conversation export with timestamps

### 🔄 Repository Refresh

From the repository overview page, you can now trigger a **Refresh index** action to ingest latest source changes:
- Reuses the same repository record and ID
- Clears stale local index/repo artifacts before re-indexing
- Re-runs the indexing pipeline so health score and follow-up evaluations reflect current code

### 🧠 Hybrid Retrieval Pipeline

Combines dense semantic retrieval, sparse keyword retrieval (BM25), and Reciprocal Rank Fusion (RRF), followed by an optional reranking pass — improving retrieval precision, contextual relevance, and architectural understanding.

### 🔀 Intelligent Query Routing

Queries are automatically classified into:


| Mode            | Purpose                            |
| --------------- | ----------------------------------- |
| `code_lookup`   | strict grounded code explanations   |
| `architectural` | higher-order engineering reasoning  |

This lets the system stay faithful for code lookup while reasoning more broadly for design discussions.

### ⚡ Multi-LLM Support

Supports **Ollama** (offline/local), **Groq**, **Gemini**, and **OpenAI** — with local inference, cloud inference, and evaluation-specific switching, all through centralized configuration.

### 🌐 FastAPI REST Backend

A full production-ready REST API layer that exposes all core functionality over HTTP:

* JWT-authenticated endpoints via Supabase
* SSE (Server-Sent Events) for real-time streaming of indexing progress and chat responses
* Supabase-backed persistence for repositories, chats, messages, and evaluations
* CORS-configured for frontend integration

### 🖥️ Next.js Frontend

A complete production frontend — an **Enterprise Repository Intelligence Workspace**:

* Next.js 16 (App Router) + React 19 + TypeScript
* Supabase Auth (sign up / sign in) with session middleware
* Dashboard for managing indexed repositories
* Live indexing progress view (SSE-driven pipeline steps)
* **Repository overview with Health Score (0–100, graded A–F)**
* **12 Intelligence Action quick-launch cards** (Architecture, Security, Code Quality, Onboarding, etc.)
* **Mermaid diagram auto-rendering** in chat responses
* **Structured intelligence response sections** (collapsible: Answer, Architecture, Engineering, Business, Evidence, Risks, Recommendations, Confidence)
* **Export menu** for MD reports, JSON data, and chat history
* Streaming chat interface with "AI Inspector" panel showing retrieved files, query mode, and latency breakdowns
* Evaluation results view with radar chart and metric cards
* shadcn/ui + Tailwind CSS v4 + Framer Motion animations
* Command palette for global workspace navigation

### 💬 Conversational Memory

Multi-turn conversation support, persistent chat context (per session and across restarts via Supabase), memory-aware prompting, and a ChatGPT-style interface.

### 📊 Evaluation Framework

A complete evaluation pipeline measuring retrieval quality (Hit Rate, MRR), generation quality (Faithfulness, Relevancy), routing accuracy, and system latency — runnable via CLI or via the API (with results persisted to Supabase).

### 🧩 Advanced Parsing & Chunking

Recursive repository traversal, metadata-rich chunking, function-aware splitting, tree-sitter parsing, and semantic file summaries.

### 🧪 Comprehensive Automated Testing

A dedicated `tests/` suite (pytest) covering config, ingestion, utilities, query routing, chunking, Supabase persistence, auth dependencies, Pydantic models, and every FastAPI router — **238 test functions across 13 test files**, run via a single `pytest` command.

---

## 🏗️ System Architecture

```text
                    ┌──────────────────────────┐
                    │   Next.js Frontend        │
                    │  (dashboard / chat / eval)│
                    └──────────┬────────────────┘
                               │  Supabase JWT
                               ▼
                  ┌────────────────────────┐
                  │   FastAPI REST API     │
                  │  (api/main.py)         │
                  │  JWT Auth via Supabase │
                  └────────┬───────────────┘
                           │
           ┌───────────────┼────────────────────────┐
           ▼               ▼                        ▼
    ┌─────────────┐ ┌────────────┐          ┌──────────────┐
    │  /api/repo  │ │ /api/chat  │          │  /api/eval   │
    │  Indexing   │ │  Streaming │          │  Evaluation  │
    │  SSE stream │ │  SSE + DB  │          │  SSE stream  │
    └──────┬──────┘ └─────┬──────┘          └──────┬───────┘
           │              │                        │
           └──────────────┼────────────────────────┘
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

## ⚙️ Tech Stack

| Layer            | Technologies                                                              |
| ----------------- | -------------------------------------------------------------------------- |
| **AI / Retrieval**| LlamaIndex, BM25, ChromaDB, ColBERT, Hybrid Retrieval, Reciprocal Rank Fusion |
| **LLMs**          | Ollama, Groq, Gemini, OpenAI                                              |
| **Parsing**       | tree-sitter, tree-sitter-language-pack                                   |
| **Backend API**   | FastAPI, Uvicorn, Pydantic, Server-Sent Events (SSE)                      |
| **Database & Auth**| Supabase (PostgreSQL), Supabase Auth (JWT)                              |
| **Frontend**      | Next.js 16, React 19, TypeScript, Tailwind CSS v4, shadcn/ui, TanStack Query, Framer Motion |
| **Legacy UI**     | Streamlit (still available for quick local testing)                      |
| **Testing**       | pytest, pytest-asyncio, FastAPI TestClient, unittest.mock                 |
| **Evaluation**    | LlamaIndex Evaluators — FaithfulnessEvaluator, RelevancyEvaluator          |

---

## 📂 Project Structure

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
│   │   └── context_builder.py
│   ├── retrieval/
│   │   ├── retriever.py
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
│   │   ├── repo.py
│   │   ├── chat.py
│   │   └── eval.py
│   └── services/
│       ├── chat_service.py       # SSE streaming + session cache
│       ├── indexing_service.py   # Async indexing pipeline with SSE
│       └── supabase_service.py   # All Supabase DB operations
│
├── frontend/                     # Next.js production frontend
│   ├── app/
│   │   ├── auth/sign-in, sign-up
│   │   ├── dashboard/
│   │   ├── repo/[id]/            # overview, chat, eval, indexing views
│   │   └── settings/
│   ├── components/
│   │   ├── ui/                   # shadcn/ui primitives
│   │   ├── chat/                 # MessageBubble, AIInspector
│   │   ├── indexing/              # PipelineStep
│   │   ├── layout/                # Sidebar, CommandPalette
│   │   ├── landing/                # Hero, FeatureSection, PipelineVisual
│   │   └── repo/                  # RepoCard
│   ├── hooks/
│   │   ├── useChatStream.ts
│   │   └── useIndexingStream.ts
│   └── proxy.ts                    # Supabase session proxy for route protection
│
├── ui/
│   └── streamlit_app.py          # Legacy/lightweight local UI
│
├── tests/                        # 238 tests across 13 files
│   ├── conftest.py                # Shared fixtures (FastAPI TestClient, mock Supabase)
│   ├── test_app_config.py
│   ├── test_app_file_filter.py
│   ├── test_app_utils.py
│   ├── test_app_query_router.py
│   ├── test_dependencies.py
│   ├── test_models.py
│   ├── test_supabase_service.py
│   ├── test_health.py
│   ├── test_router_chat.py
│   ├── test_router_repo.py
│   ├── test_router_eval.py
│   ├── test_router_suggestions.py
│   ├── pipeline_runner.py        # End-to-end manual pipeline exerciser
│   └── indexing_runner.py
│
├── data/
│   ├── repos/
│   ├── index/
│   └── eval_results*.json
│
├── evaluate.py
├── pytest.ini
├── requirements.txt
├── start.ps1                     # One-command launcher for backend + frontend
├── start.sh                      # One-command launcher for macOS/Linux
├── .env
├── .gitignore
└── README.md
```

---

## 🌐 REST API Reference

The FastAPI backend is served at `http://localhost:8000` and exposes the following endpoints. All endpoints require a valid Supabase JWT in the `Authorization: Bearer <token>` header (except where noted).

### Health

| Method | Endpoint       | Description                                                 |
| ------ | -------------- | ------------------------------------------------------------ |
| `GET`  | `/api/health`  | Returns LLM provider, ColBERT status, and embed model info    |

### Repository — `/api/repo`

| Method   | Endpoint                             | Description                                                   |
| -------- | ------------------------------------- | -------------------------------------------------------------- |
| `POST`   | `/api/repo/index`                     | Create a repo record and begin indexing (returns `repo_id`)    |
| `POST`   | `/api/repo/{repo_id}/refresh`         | Reset an existing repo and re-index the latest source changes  |
| `GET`    | `/api/repo/{repo_id}/index-progress`  | **SSE stream** — real-time indexing progress events            |
| `GET`    | `/api/repo/list`                      | List all repositories for the authenticated user               |
| `GET`    | `/api/repo/{repo_id}`                 | Get status and metadata for a single repository                |
| `DELETE` | `/api/repo/{repo_id}`                 | Delete a repository, its ChromaDB index, and cloned files      |
| `GET`    | `/api/repo/{repo_id}/suggestions`     | Return 6 LLM-generated suggested questions for the repository  |

**Indexing SSE Events**

```json
{ "step": "cloning",   "message": "Cloning repository...", "progress": 10 }
{ "step": "filtering", "message": "Filtering files...",    "progress": 20 }
{ "step": "parsing",   "message": "Parsing 47 files...",   "progress": 40 }
{ "step": "embedding", "message": "Building embeddings...", "progress": 65 }
{ "step": "summary",   "message": "Finalising architectural context...", "progress": 90 }
{ "step": "done",      "message": "Indexing complete!", "progress": 100, "file_count": 47, "node_count": 312 }
{ "step": "error",     "message": "...", "progress": 100 }
```

If Python AI dependencies are missing (for example `llama_index`), the stream emits a terminal `error` event with installation guidance instead of hanging silently.

### Chat — `/api/chat`

| Method   | Endpoint                              | Description                                          |
| -------- | -------------------------------------- | ------------------------------------------------------ |
| `POST`   | `/api/chat/session`                    | Create a new chat session for a repository            |
| `POST`   | `/api/chat/{chat_id}/message/stream`   | **SSE stream** — stream AI response token-by-token     |
| `GET`    | `/api/chat/{chat_id}/messages`         | Fetch full message history for a chat                  |
| `GET`    | `/api/chat/list?repo_id=...`           | List all chats for a repository                        |
| `DELETE` | `/api/chat/{chat_id}`                  | Delete a chat session and all its messages              |
**Chat SSE Events**

```json
{ "type": "token",    "content": "..." }
{ "type": "metadata", "query_mode": "code_lookup", "retrieved_files": [...], "latency_retrieval_ms": 95, "latency_llm_ms": 2100, "latency_total_ms": 2210 }
{ "type": "done" }
{ "type": "error",   "message": "..." }
```

Each message is persisted to Supabase after streaming completes, including `query_mode`, `retrieved_files`, and `latency_ms`.

### Evaluation — `/api/eval`

| Method | Endpoint                     | Description                                                    |
| ------ | ----------------------------- | ----------------------------------------------------------------- |
| `POST` | `/api/eval/run`               | **SSE stream** — run the full evaluation suite (~3–10 min)        |
| `GET`  | `/api/eval/{repo_id}/latest`  | Retrieve the most recent evaluation results for a repository       |

**Eval SSE Events**

```json
{ "type": "progress", "message": "Running query 3/10..." }
{ "type": "result",   "summary": { "hit_rate": 0.8, "mrr": 0.65, ... } }
{ "type": "done" }
{ "type": "error",    "message": "..." }
```

Results are automatically persisted to Supabase on completion.

---

## 🗄️ Supabase Schema

| Table          | Purpose                                                    |
| --------------- | ------------------------------------------------------------ |
| `profiles`     | User profile data                                           |
| `repositories` | Indexed repo records (status, file/node count, provider)    |
| `chats`        | Chat sessions linked to a repository                        |
| `messages`     | Individual messages with role, content, mode, latency        |
| `evaluations`  | Stored evaluation summaries with all metric fields           |

All Supabase operations are centralized in `api/services/supabase_service.py`. Routers never make raw Supabase calls directly.

---

## 🔐 Authentication

The API uses Supabase JWT authentication:

* the Next.js frontend sends `Authorization: Bearer <supabase_access_token>`, managed via `frontend/proxy.ts`
* `api/dependencies.py` verifies the token using the Supabase service role key
* `get_current_user()` — raises `401` if the token is missing or invalid
* `get_optional_user()` — returns `None` for unauthenticated requests (guest mode)

The Supabase client uses the **service role key** (never exposed to the frontend).

## 🛡️ Reliability and Hardening

This project is production-oriented, but large-scale and regulated environments usually require additional hardening. The checklist below captures the recommended baseline.

### 1) Robust Error Handling

* Standardize API error payloads across all routers (for example: `code`, `message`, `request_id`, `retryable`, `details`) so frontend error handling is deterministic.
* Preserve SSE reliability by always emitting a terminal `error` or `done` event, including partial-failure paths.
* Add timeout, cancellation, and cleanup guards for long-running indexing/evaluation jobs to prevent stuck work.
* Classify failures into `user`, `dependency`, `transient`, and `internal`, with retry guidance per class.
* Include correlation IDs in both logs and response payloads so one frontend failure can be traced end-to-end.
* Add explicit fallback messages for missing AI dependencies (for example `llama_index`) and model/provider unavailability.

### 2) Security Hardening (Including Test Security)

* Keep `mock_supabase` only for fast unit tests; move security confidence to real integration/security tests.
* Replace mock-only security validation with an ephemeral Supabase/Postgres test environment in CI using short-lived credentials.
* Add contract tests for JWT validation edge cases (expired tokens, malformed claims, wrong audience, revoked sessions).
* Enforce secret hygiene: `.env` never committed, service-role key only in backend runtime, optional secret scanning in CI.
* Add authorization regression tests for repository/chat/eval ownership boundaries and cross-tenant access attempts.
* Treat the security lane as a required merge gate for auth/authz-sensitive changes.

### 3) Evaluation Pipeline Optimization

* Parallelize independent evaluation queries with bounded worker pools to reduce wall-clock runtime.
* Add caching for immutable artifacts (parsed nodes, embeddings, retrieval candidates, rerank outputs where valid).
* Split evaluation into stages: retrieval-only, generation-only, and end-to-end to isolate bottlenecks faster.
* Persist per-stage timings and resource metrics so regressions can be detected automatically.
* Add provider-aware execution policies (local/offline vs cloud) to keep CI reliable and cost-aware.
* Add resumable evaluation runs (stage checkpoints) so failures do not require restarting the entire pipeline.

### 4) Scalability Design

* Run API instances statelessly behind a load balancer; move any process-local state to shared infrastructure.
* Use a distributed cache (for example Redis) for hot retrieval artifacts and short-lived chat metadata.
* Offload indexing/evaluation to worker queues so API latency is not coupled to heavy background workloads.
* Add database index/partition tuning for `repositories`, `chats`, `messages`, and `evaluations` as data grows.
* Introduce observability SLIs/SLOs (latency, error rate, queue depth, throughput) before high-scale rollout.
* Add concurrency limits and backpressure on SSE and long-running endpoints to protect service stability under load.

### 5) Expanded Testing Strategy

* Keep the fast unit suite and enforce a two-lane strategy: mocked fast lane + ephemeral real-backend security lane.
* Expand the test pyramid explicitly: unit -> integration -> end-to-end -> security -> performance.
* Add SSE contract tests that verify event ordering, terminal events, and error propagation behavior.
* Add integration tests that run against real persistence/auth boundaries (ephemeral environment, not production).
* Add performance guard tests for indexing and retrieval latency budgets.
* Add chaos-style failure tests for dependency outages (LLM provider, vector store, Supabase) and retry behavior.

---

## 🔄 End-to-End Workflow

### 1️⃣ Repository Ingestion

Accepts GitHub repository URLs or local repository paths. Repositories are cloned locally, recursively traversed, and filtered for relevant files. Ignored directories include `node_modules/`, `.git/`, `dist/`, `venv/`, `__pycache__/`.

### 2️⃣ Parsing & Chunking

Reads code safely, extracts metadata, performs semantic chunking, and generates file-level summaries. Each chunk stores file path, file name, entity information, chunk text, and metadata.

### 3️⃣ Embedding & Indexing

Dense embeddings via `nomic-embed-text`, stored in **ChromaDB**. Keyword retrieval via **BM25**.

### 4️⃣ Hybrid Retrieval

Combines semantic, keyword, and file-level retrieval using `QueryFusionRetriever` and Reciprocal Rank Fusion (RRF) — improving retrieval precision, architectural reasoning, and contextual grounding.

### 5️⃣ Reranking

Optional ColBERT reranking improves ranking quality, retrieval precision, and Mean Reciprocal Rank (MRR).

### 6️⃣ Query Routing

Queries are classified into code lookup mode or architectural reasoning mode, enabling stricter grounded answers, broader engineering analysis, and better faithfulness control.

### 7️⃣ Prompt Construction

Prompts include retrieved chunks, repository summaries, metadata, routing instructions, and conversational history.

### 8️⃣ Conversational Memory

Stores previous interactions, enables follow-up questions, preserves context across turns, and persists messages to Supabase via the API layer.

### 9️⃣ LLM Generation

Responses generated via Ollama, Groq, Gemini, or OpenAI, with local inference, cloud inference, evaluation-specific LLM switching, and token-level SSE streaming via the FastAPI backend.

---

## 📊 Evaluation Framework

| Category    | Metrics                          |
| ------------ | ---------------------------------- |
| Retrieval   | Hit Rate, MRR                      |
| Generation  | Faithfulness, Relevancy              |
| Routing     | Mode Accuracy                       |
| Performance | Retrieval, rerank, LLM latency        |

### 📈 Example Evaluation Results

| Metric             | Score      |
| -------------------- | ------------ |
| Hit Rate            | 0.80+        |
| MRR                 | 0.60+        |
| Faithfulness        | 0.60–0.80    |
| Relevancy           | 0.90+        |
| Routing Accuracy    | 1.00         |
| Retrieval Latency   | ~0.1s        |
| Rerank Latency      | ~1s          |
| Local LLM Latency   | ~15s         |
| Groq LLM Latency    | ~2–4s        |

---

## 🧪 Testing

The project ships with a dedicated `tests/` suite built on **pytest** and **pytest-asyncio**, exercising the core engine, the FastAPI routers, and Supabase persistence in isolation from live services.

### Coverage at a Glance

**238 test functions across 13 test files**, organized with `unit`, `integration`, and `slow` markers:

| Test File                     | Focus                                                                  |
| ------------------------------- | -------------------------------------------------------------------------- |
| `test_app_config.py`           | LLM provider config, fast-LLM toggle, API keys, directories, ColBERT flag |
| `test_app_file_filter.py`      | Valid extensions, ignored directories, recursive traversal                |
| `test_app_utils.py`            | Logger behavior, file extension parsing, directory cleanup                |
| `test_app_query_router.py`     | Query mode classification, keyword routing, LLM fallback, text chunking   |
| `test_dependencies.py`         | Supabase client singleton, JWT auth (`get_current_user`, `get_optional_user`) |
| `test_models.py`               | Pydantic request/response models for repo, chat, and eval endpoints        |
| `test_supabase_service.py`     | All Supabase CRUD operations for repos, chats, messages, evaluations        |
| `test_health.py`               | `/api/health` response shape and status                                    |
| `test_router_repo.py`          | Repo indexing, listing, retrieval, deletion, ownership checks              |
| `test_router_chat.py`          | Chat session creation, message history, streaming, deletion                |
| `test_router_eval.py`          | Evaluation run and latest-result retrieval, ownership checks               |
| `test_router_suggestions.py`   | Cached vs. generated question suggestions, default fallback behavior       |
| `conftest.py`                  | Shared fixtures — FastAPI `TestClient`, mocked Supabase client, fake users  |

Integration tests use FastAPI's `TestClient` with a mocked Supabase backend (via `unittest.mock`) for fast local feedback and **zero external network calls**.

For stronger security assurance, run a CI security lane against an ephemeral Supabase/Postgres target with real JWT verification and row-level authorization checks; treat this lane as the source of truth for auth/authz behavior and as a required gate for security-sensitive merges.

### Running the Tests

```bash
# Run the full suite
pytest

# Run only fast unit tests
pytest -m unit

# Run only integration tests (FastAPI TestClient)
pytest -m integration

# Run a specific file
pytest tests/test_router_chat.py

# Verbose output with short tracebacks (already the default via pytest.ini)
pytest -v --tb=short
```

`pytest.ini` configures `asyncio_mode = auto`, so `async def test_...` functions (used for the async auth dependency tests) run without extra decorators.

There are also two manual/live scripts for exercising the pipeline against real services when needed:

* `tests/pipeline_runner.py` — end-to-end manual pipeline run (ingestion → indexing → retrieval → generation)
* `tests/indexing_runner.py` — manual indexing-only smoke test
* `tests/live_api_test.py` — hits a running FastAPI instance directly (not part of the default `pytest` run)

---

## 💬 Example Queries

**Code Lookup**

```text
How does retrieve_relevant_chunks work?
Where is the vector store initialized?
How does the indexing pipeline work?
```

**Architectural Reasoning**

```text
What are the main limitations of this project?
How can retrieval quality be improved?
What changes are needed for production deployment?
```

---

## 🚀 Running the Project

### 1️⃣ Create Environment

```bash
conda create -n ai-copilot-env python=3.10
conda activate ai-copilot-env
```

### 2️⃣ Install Backend Dependencies

```bash
pip install -r requirements.txt
```

### 3️⃣ Start Ollama (for local inference)

```bash
ollama serve
ollama pull llama3.2:3b
ollama pull nomic-embed-text
```

### 4️⃣ Configure `.env`

```env
LLM_PROVIDER=ollama

OLLAMA_LLM_MODEL=llama3.2:3b
OLLAMA_EMBED_MODEL=nomic-embed-text

USE_COLBERT=true
USE_FAST_LLM=false
GROQ_FAST_MODEL=llama-3.3-70b-versatile

# Required for FastAPI backend
SUPABASE_URL=https://xxxx.supabase.co
SUPABASE_SERVICE_KEY=eyJ...

# Optional — used for CORS
FRONTEND_URL=http://localhost:3000
```

### 5️⃣ Start Both Servers with a Single Script (Recommended)

Run both the FastAPI backend and the Next.js frontend together from one terminal window:

```powershell
# Windows (PowerShell)
powershell -ExecutionPolicy Bypass -File "start.ps1"
```

```bash
# macOS / Linux
./start.sh
```

If your clone strips executable bits, run `chmod +x start.sh` once.

Both scripts:

* free ports `8000` and `3000` before startup
* stream prefixed logs in one terminal (`[backend]` / `[frontend]`)
* stop both services on **Ctrl+C**
* exit if either backend or frontend stops unexpectedly

| Service  | URL                      |
| -------- | ------------------------ |
| Backend  | http://localhost:8000    |
| Frontend | http://localhost:3000    |

### 5️⃣a Start the FastAPI Backend (standalone)

```bash
# Windows
./.venv/Scripts/python.exe -m uvicorn api.main:app --reload --port 8000

# macOS / Linux
./.venv/bin/python -m uvicorn api.main:app --reload --port 8000
```

The API is available at `http://localhost:8000`, with interactive Swagger docs at `http://localhost:8000/docs`.

### 6️⃣ Launch the Next.js Frontend (standalone)

```bash
cd frontend
npm install
npm run dev
```
The app is available at `http://localhost:3000`.

### 7️⃣ (Optional) Launch the Legacy Streamlit UI

```bash
streamlit run ui/streamlit_app.py
```

---

## 🧪 Running Evaluation

**Via CLI (standalone)**

```bash
python evaluate.py
```

**Via API (persists results to Supabase)**

```bash
POST /api/eval/run
{ "repo_id": "<uuid>", "index_name": "<index_name>" }
```

---

## 🧠 Key Engineering Insights

**Retrieval Pipeline** — retrieval latency is extremely low (~0.1s), reranking adds modest overhead (~1s), and the primary bottleneck is local LLM inference.

**Backend Architecture** — the `api/` layer is deliberately thin: routers handle HTTP concerns only (auth, validation, response shaping), all business logic lives in `app/` (provider-agnostic core), and `api/services/` handles Supabase persistence and SSE coordination. This separation means the Next.js frontend, the legacy Streamlit UI, and the evaluation CLI all share the same core RAG engine without duplication.

**Streaming Design** — both indexing and chat use Server-Sent Events (SSE): indexing progress is streamed step-by-step so the frontend can show a live progress bar, and chat responses are streamed token-by-token using LlamaIndex's `stream_complete()`. A `metadata` event is emitted after the full response, carrying `query_mode`, `retrieved_files`, and latency breakdowns. Messages are persisted to Supabase after the stream closes.

**Test Strategy** — testing is split into two lanes: a fast mocked lane for rapid feedback and an ephemeral real-backend lane for auth/authz and persistence confidence, balancing speed with security assurance.

**Local AI Optimization** — the system was optimized specifically for Apple Silicon Macs, 16GB RAM systems, and local inference workflows.

**Hallucination Reduction** — implemented using hybrid retrieval, reranking, query routing, and retrieval-grounded prompting.

---

## 🔮 Future Improvements

**Incremental Indexing** — detect changed files via hash/git diff and only re-embed deltas instead of full refresh runs.

**Background Job Control Plane** — move indexing/eval to queue workers with retry, cancellation, and job history for long-running tasks.

**Evaluation Freshness Signals** — mark results stale when `indexed_at` is newer than latest eval, with one-click rerun and metric diffs.

**Retrieval Observability** — persist per-query retrieval traces (hit positions, rerank lift, misses) and trend them in the evaluation UI.

**Shared Workspaces + RBAC** — repository sharing, role-based access, and audit trails for exports, evaluations, and destructive actions.

**Security Intelligence Pipeline** — wire dependency/secret scanners into intelligence cards with severity, owner, and remediation tracking.

**Contract-Driven API Stability** — generate typed clients from versioned OpenAPI and add compatibility checks to prevent frontend/backend drift.

---

## 🎯 What This Project Demonstrates

* Retrieval-Augmented Generation (RAG) and hybrid retrieval systems
* Reranking pipelines and evaluation engineering
* Conversational memory and LLM orchestration
* Query routing and latency optimization
* AI infrastructure design
* Production-style REST API design (FastAPI + Supabase)
* Server-Sent Events for real-time AI streaming
* JWT authentication and multi-user data isolation
* A full production frontend (Next.js + TypeScript + Tailwind)
* Rigorous automated testing (238 tests, unit + integration, mocked external services)

---

## 🙌 Final Note

Codebase Copilot was built to deeply explore retrieval quality, architectural reasoning, evaluation methodology, scalable AI system design, production API engineering, frontend engineering, and test-driven reliability — with a strong focus on modularity, explainability, optimization, extensibility, and real-world AI engineering workflows.
