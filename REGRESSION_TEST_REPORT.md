# Codebase-Copilot — Regression Test Report (Phase 2)
**Branch**: `fix/demo-readiness`  
**Base Commit**: `497b63c93fc98349e190b5d693256e57450f1c04`  
**Date**: October 31, 2026  
**Status**: All B1–B9 Regression Targets Evaluated and Passing  
**Backend Automated Tests**: 702 Passed (524 Unit + 178 Integration), 0 Failed  
**Frontend Automated Tests**: 7 Passed, 0 Failed  
**Frontend Build**: TypeScript 0 Errors, Next.js Turbopack 10/10 Pages Static/Dynamic Prerendered  

---

## 1. Definitive B1–B9 Regression Matrix (Original Definitions)

> **Important Note on Methodology**: Mocked unit tests and live integration tests are strictly distinguished below. No mocked test is reported as live verification.

| ID | Original Issue Definition | Test Type & Methodology | Test Files / Endpoints | Expected Result | Actual Result | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **B1** | **Wrong repository context contamination** | Live & Unit Retrieval Isolation | `tests/integration/test_rag2_validation_suite.py`, Chroma `repo_id` partitioning | Querying repo A never retrieves chunks, symbols, or files from repo B. | Context strictly partitioned by `repo_id`. Chroma metadata filter isolates collections. Zero cross-repo contamination. | **PASS** |
| **B2** | **Expired-JWT chat failure** | Live HTTP & Mocked Unit | `tests/unit/test_auth_router.py`, `POST /api/auth/login/preflight` | Public preflight endpoints succeed without token; expired/invalid tokens return 401; token refresh restores session. | Public preflight endpoints return 200 without token; protected routes return 401 on expired tokens; frontend `AuthRecoveryPrimitives` recovers gracefully. | **PASS** |
| **B3** | **Chat switching/loading** | Live HTTP & Mocked Unit | `tests/integration/test_router_chat.py`, `tests/unit/test_chat_service.py` | Switching active chat session properly cleans state, loads target session messages, and preserves chat isolation. | `GET /api/chat/{id}/messages` loads target history without stale leak; UI state transitions smoothly. | **PASS** |
| **B4** | **Analysis actions unreliable** | Unit & Frontend UI | `frontend/app/repo/[id]/chat/page.tsx`, `tests/integration/test_router_reviews.py`, `tests/integration/test_router_health_recommendation_status.py` | Clicking analysis actions (Health, Review, Impact Analysis) provides loading/error feedback rather than silent return when `chatId` is initializing; results persist and retrieve. | Silent return eliminated in `handleSend`. Toast notifications inform user; action prompt is queued in `pendingAutoPromptRef` and auto-dispatched once session is ready. | **PASS** |
| **B5** | **Vague questions unhelpful** | Unit & Integration Query Routing | `tests/unit/test_query_router_intents.py`, `tests/integration/test_app_query_router.py` | Vague queries ('security', 'how does it work?', 'what is this?', 'explain') route to `ARCHITECTURAL` instead of blindly falling back to `CODE_LOOKUP`. | Replaced unconfigured `Settings.llm` with `_get_router_llm()` backed by resilient LLM provider. All 4 target vague queries route to `ARCHITECTURAL`. | **PASS** |
| **B6** | **Missing Supabase schema** | SQL Validation & Mocked Resilience | `api/migrations/20261031_stabilization_schema_repair.sql`, `tests/unit/test_supabase_service.py` | Remote schema repair migration contains all tables, columns, indexes, RLS policies, and grants. Application gracefully handles missing tables prior to remote execution. | Migration script validated (idempotent DDL, chat-ownership RLS on attachments, exports, tags, and grants). Graceful fallbacks prevent 500s. Remote execution held for user approval. | **PASS** (Local/Staging Verified; Remote Execution Pending Approval) |
| **B7** | **Destructive refresh ordering** | Mocked Unit & Filesystem Regression | `tests/unit/test_repo_refresh_regression.py`, `api/routers/repo.py`, `api/services/indexing_service.py` | Re-indexing builds in unique staging folder; validates SQLite and manifest; swaps atomically; preserves old index on failure; prevents concurrent refresh corruption. | 10/10 regression tests pass: staging folder used, validation verified, atomic swap executed, rollback on filesystem error verified, concurrent refresh rejected with HTTP 409, and old index preserved on indexing/cloning failure. | **PASS** |
| **B8** | **Unsupported citations** | Mocked Unit Regression | `tests/unit/test_citation.py`, `app/services/qa_service.py` | Nonexistent files and fabricated line numbers are detected and sanitized. Safe default is `strict` enforcement, not warning-only logging. Valid citations preserved. | Default `CITATION_VALIDATION_MODE="strict"`. Fabricated lines stripped, non-existent files neutralized, valid citations and line references preserved. 9/9 tests pass. | **PASS** |
| **B9** | **Retrieved chunks but generic no-results** | Unit QA Service & Retrieval | `tests/unit/test_qa_service.py`, `api/services/chat_service.py` | Reciprocal Rank Fusion (RRF) scores (`top_score <= 0.10`) not rejected by similarity threshold. Relevant retrieved chunks reach synthesis. Genuine refusals preserved for empty context. | Score types calibrated in `_check_low_confidence()`. Architectural queries bypass confidence checks when chunks exist. Empty retrievals still return honest refusal. 6/6 tests pass. | **PASS** |

---

## 2. Test Execution Details

### A. Backend Unit Test Suite (`tests/unit/`)
- **Execution Command**: `conda run -n ai-copilot-env pytest tests/unit/ -v`
- **Result**: **524 passed**, 0 failed, 5 warnings in 8.66s
- **Highlighted New Test Modules**:
  - `tests/unit/test_repo_refresh_regression.py` (10 passed):
    - `test_validate_staged_index_success`
    - `test_validate_staged_index_missing_dir`
    - `test_validate_staged_index_missing_manifest`
    - `test_promote_staged_index_new`
    - `test_promote_staged_index_atomic_swap`
    - `test_promote_staged_index_rollback_on_failure`
    - `test_refresh_indexing_failure_preserves_old_index`
    - `test_refresh_clone_failure_preserves_existing_clone`
    - `test_concurrent_refresh_requests_locked`
    - `test_refresh_pipeline_successful_flow`
  - `tests/unit/test_query_router_intents.py` (68 passed in query router suite):
    - Tests for `'security'`, `'how does it work?'`, `'what is this?'`, `'explain'` routing to `ARCHITECTURAL`.
  - `tests/unit/test_citation.py` (9 passed):
    - Tests for valid citations, invalid filenames, fabricated line numbers exceeding file length, mixed valid/invalid citations, citations outside context, and sanitization.
  - `tests/unit/test_qa_service.py` (6 passed):
    - Tests for RRF score handling, architectural query bypass, empty retrieval rejection, and answerable query answer synthesis.
  - `tests/unit/test_auth_router.py` (8 passed):
    - Tests for public auth preflight without token and protected auth endpoints.
  - `tests/unit/test_supabase_service.py` (49 passed):
    - Tests for health runs, categories, recommendations, attachments, and saved reports fallbacks.

### B. Backend Integration Test Suite (`tests/integration/`)
- **Execution Command**: `conda run -n ai-copilot-env pytest tests/integration/ -v`
- **Result**: **178 passed**, 0 failed, 7 warnings in 13.56s
- **Coverage**:
  - `test_router_repo.py`: 22 passed (Index, refresh, branches, delete, access control).
  - `test_router_chat.py`: 12 passed (Streaming, messages, schema sanitization).
  - `test_router_reviews.py`: 4 passed (File review, files review, list, delete).
  - `test_router_graph.py`: 5 passed (Graph retrieval, keys, permissions).
  - `test_router_suggestions.py`: 8 passed (Question generation, caching, defaults).
  - `test_rag2_validation_suite.py`: 1 passed (End-to-end RAG pipeline).
  - `test_llm_fallback.py`: 14 passed (Provider fallback, circuit breaker, quota exhaustion bypass).

### C. Frontend Vitest Suite (`frontend/`)
- **Execution Command**: `npm --prefix frontend test`
- **Result**: **7 passed**, 0 failed in 0.44s
- **Coverage**:
  - `lib/engineering-actions.test.ts`: 4 passed.
  - `lib/chat-context.test.ts`: 3 passed.

### D. Frontend Linter (`eslint`)
- **Execution Command**: `npm --prefix frontend run lint`
- **Result**: **0 errors**, 6 non-blocking unused-variable warnings.

### E. Frontend Production Build (`next build`)
- **Execution Command**: `npm --prefix frontend run build`
- **Result**:
  - Compiler: Next.js 16.2.10 (Turbopack)
  - TypeScript Compilation: Finished in 3.2s, **0 errors**
  - Page Collection: 10 static/dynamic routes compiled
  - Prerendering: **10/10 routes successfully generated**
