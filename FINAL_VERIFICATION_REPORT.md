# Codebase-Copilot — Final Verification & Audit Report
**Branch**: `fix/demo-readiness`  
**Head Commit**: `497b63c93fc98349e190b5d693256e57450f1c04`  
**Verification Date**: October 31, 2026  
**Audit Mode**: Verification-Only (Zero Code Modifications, Zero DB Writes)

---

## 1. Executive Summary & Corrected Demo-Readiness Verdict

### Corrected Demo-Readiness Verdict: **CONDITIONAL / PARTIAL (GRADE B+)**

While the application starts successfully and critical core interactive paths (instant greeting fast-path, repository-scoped codebase Q&A, Mermaid architecture diagrams, and Next.js frontend production build) are functional, **the application is NOT fully demo-ready without caveats**:

1. **Remote Database Persistence is Incomplete (B6)**:
   - Application-level graceful error handling prevents HTTP 500 crashes by catching missing table exceptions and returning empty lists (`[]`).
   - However, **actual persistence of attachments, saved reports, code reviews, conversation summaries, and conversation tags fails (`PGRST205` / `42703`)** because migration `api/migrations/20261031_stabilization_schema_repair.sql` has not yet been applied to the remote Supabase database.
2. **Destructive Refresh Ordering is Present (B7)**:
   - When a repository refresh is initiated (`POST /api/repo/{id}/refresh`), the system immediately removes the existing working index directory and repository clone (`_remove_repo_artifacts`) before beginning re-indexing. If the network or clone fails, the previous working index is destroyed.
3. **Vague Questions & Missing Key Fallback (B5)**:
   - When short/ambiguous queries are submitted without clear keyword matches, the query router calls `Settings.llm.complete()`. Because `Settings.llm` is not configured with the active fallback provider, it attempts to invoke OpenAI, fails with missing `OPENAI_API_KEY`, and blindly defaults to strict `CODE_LOOKUP` mode.
4. **Automated Test Suite Evidence Distinction**:
   - The reported **679 passing pytest tests** are almost entirely **unit tests running against mocked objects** (`MagicMock`, monkeypatched Supabase clients, synthetic dictionaries). They validate internal logic, but do not prove live remote Supabase persistence or live provider reliability.

---

## 2. Restored Original B1–B9 Verification Matrix

| ID | Original Issue Definition | Reproduction Scenario / Test Command | Expected Result | Actual Result | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **B1** | **Wrong repository context contamination** | Query SenseVoice repo (`296ee64c-...`) vs Codebase-Copilot repo (`034febb5-...`) with repository-specific classes and symbols. | ChromaDB and BM25 retrievers partition strictly by `repo_id`. Zero cross-repo node contamination. | Chroma directories and inverted indexes are isolated per repo. Retrieval traces confirmed 0 cross-contamination across 12 test queries. | **PASS** |
| **B2** | **Expired-JWT chat failure** | Test missing token, expired token, refresh token cycle, and public preflight endpoints against `/api/auth` and protected `/api/repo/list`. | Missing/expired tokens return `401 Unauthorized`. Preflights return `200 OK`. Token refresh restores authenticated access. | Public preflights (`/login/preflight`, `/register/preflight`, `/password-reset/audit-request`) return `200 OK`. Protected routes reject invalid/missing tokens with 401. Token refresh completes in 218ms. | **PASS** |
| **B3** | **Chat switching/loading** | Create multiple chat sessions (`POST /api/chat/session`), switch between them (`GET /api/chat/{id}/messages`), and verify message restoration. | Sessions load their own message histories cleanly; switching repositories preserves chat session isolation. | `POST /session` -> 200; `GET /{id}/messages` -> 200; `DELETE /{id}` -> 200. Messages restore accurately per `chat_id`. | **PASS** |
| **B4** | **Analysis action unreliable** | Trigger analysis actions (Health Analysis, Code Review, Impact Analysis button in chat bubble). | Correct endpoint called with selected repo/chat; loading/success/failure states shown; persists results. | Health analysis works and persists to remote health tables. However, code review analysis fails to persist due to missing `repository_reviews` table. If `chatId` is not loaded when a chat bubble action is clicked, it silently returns. | **PARTIAL** |
| **B5** | **Vague questions unhelpful** | Submit short/vague repository questions (`security`, `how does it work`, `what is this`, `explain`). | Query classifier evaluates intent, expands query or prompts for clarification in architectural mode. | `Settings.llm` in `query_router.py` defaults to OpenAI, throws missing `OPENAI_API_KEY` exception, and falls back to strict `CODE_LOOKUP`. Strict lookup against vague terms yields low similarity and unhelpful answers. | **FAIL** |
| **B6** | **Missing Supabase schema** | Probe remote Supabase for `saved_reports`, `repository_reviews`, `conversation_summaries`, `conversation_tags`, `attachments`, `exports`, and `chats` columns. | Tables and columns exist; INSERT, SELECT, UPDATE, DELETE succeed with RLS user ownership. | Tables and columns are **MISSING** on remote DB (`PGRST205` / `42703`). Application graceful fallbacks return `[]` to prevent 500s, but actual persistence fails. Migration prepared but unexecuted. | **BLOCKED** |
| **B7** | **Destructive refresh ordering** | Inspect `_remove_repo_artifacts` in `api/routers/repo.py` during `POST /{repo_id}/refresh`. | Old working index remains active until replacement is successfully cloned and indexed in staging. | `_remove_repo_artifacts` eagerly deletes existing index and repo directories with `shutil.rmtree` BEFORE cloning begins. Failed clone or interrupted indexing destroys the working index. | **FAIL** |
| **B8** | **Unsupported citations** | Inspect `validate_citations()` in `app/services/qa_service.py` under default configuration. | Hallucinated or non-existent file references are stripped or rejected before reaching the user. | `CITATION_VALIDATION_MODE` defaults to `"log"`. When the model hallucinates non-existent files, it logs a warning but still returns the invalid citation to the user. Retries occur only in non-default `"strict"` mode. | **FAIL** |
| **B9** | **Retrieved chunks but generic no-results** | Trace query flow when retrieval returns valid chunks: Query -> Classification -> Retrieval -> Reranking -> LLM Prompt -> Answer. | Relevant retrieved chunks are synthesized into an answer rather than returning generic refusal. | `LOW_CONFIDENCE_SIMILARITY_THRESHOLD = 0.40` aborts generation and returns clarification when raw scores fall below 0.40. In `CODE_LOOKUP` mode, prompt instructs model to say "I couldn't find that in the retrieved code" if context is not an exact match. | **PARTIAL** |

---

## 3. Deep-Dive Verification Findings

### 3.1 Supabase Schema & Persistence Verification (B6)
- **Migration Inspected**: [`api/migrations/20261031_stabilization_schema_repair.sql`](file:///Users/sj/Documents/AI-Copilot/codebase-copilot/api/migrations/20261031_stabilization_schema_repair.sql)
- **Completeness**:
  - Adds 10 missing columns to `public.chats` (`session_type`, `is_pinned`, `is_favorite`, `is_archived`, `archived_at`, `deleted_at`, `last_message_at`, `last_message_preview`, `message_count`, `summary`).
  - Adds 5 missing columns to `public.messages` (`token_count`, `llm_provider`, `llm_model`, `metadata`, `sequence`).
  - Creates 6 missing tables: `saved_reports`, `repository_reviews`, `conversation_summaries`, `conversation_tags`, `attachments`, `exports`.
  - Enables RLS on all 6 tables with strict user ownership (`auth.uid() = user_id` or chat ownership check).
  - Uses `IF NOT EXISTS` and non-destructive syntax.
- **Remote Database Reality**:
  - Direct live probing confirms **none of these 6 tables exist** on the remote database (`code: PGRST205`).
  - Column `chats.is_pinned` does not exist (`code: 42703`).
  - **Attachment Upload/CRUD**: Does NOT work on remote DB. Attempting to insert an attachment fails.
  - **Saved Reports & Reviews**: Do NOT persist on remote DB.
  - **Graceful Fallback vs. Persistence**: `api/services/supabase_service.py` was patched to catch `PGRST205` / `PGRST204` errors and return `[]` to prevent 500 errors on `GET /reports` and `GET /attachments`. **This prevents UI crashes, but data persistence remains blocked until the migration is executed in the Supabase SQL Editor.**

### 3.2 Destructive Refresh Ordering Verification (B7)
- **File**: [`api/routers/repo.py`](file:///Users/sj/Documents/AI-Copilot/codebase-copilot/api/routers/repo.py#L90-L111), [`api/routers/repo.py`](file:///Users/sj/Documents/AI-Copilot/codebase-copilot/api/routers/repo.py#L184-L187)
- **Code Trace**:
  ```python
  @router.post("/{repo_id}/refresh", response_model=IndexRepoResponse)
  async def refresh_repository(...):
      ...
      index_name = repo.get("index_name", repo.get("name", "repo"))
      _remove_repo_artifacts(index_name)  # <-- shutil.rmtree on index_path and repo_path!
      supabase_service.reset_repo_for_reindex(supabase, repo_id)
      return IndexRepoResponse(...)
  ```
- **Finding**: The deletion happens **synchronously during the initial POST request**, before the client even connects to the SSE progress stream (`/api/repo/{repo_id}/index-progress`) to clone the repository.
- **Failure Scenario**: If the remote git host is unreachable, authentication fails, or indexing is interrupted, the user's previously indexed codebase is completely lost and cannot be queried.
- **Recommendation**: Refresh operations should clone into a staging directory (e.g. `data/repos/{index_name}_staging`) and build a staging index. Only upon successful completion should an atomic directory swap take place.

### 3.3 Unsupported Citations (B8) & Generic No-Results (B9)
- **B8 (Unsupported Citations)**:
  - In [`app/config.py`](file:///Users/sj/Documents/AI-Copilot/codebase-copilot/app/config.py#L124), `CITATION_VALIDATION_MODE` defaults to `"log"`.
  - In [`app/services/qa_service.py`](file:///Users/sj/Documents/AI-Copilot/codebase-copilot/app/services/qa_service.py#L509-L510), when `CITATION_VALIDATION_MODE != "strict"`, hallucinated citations only produce a logger warning:
    ```python
    logger.warning(f"Response cited hallucinated files: {invalid_citations}")
    ```
    The unverified filenames are still delivered directly to the client.
- **B9 (Generic No-Results)**:
  - In [`app/services/qa_service.py`](file:///Users/sj/Documents/AI-Copilot/codebase-copilot/app/services/qa_service.py#L440-L448), `_check_low_confidence()` checks `top_score < 0.40`. If cross-encoder or vector similarity is below 0.40, it immediately aborts and returns:
    `"Could you point me to a specific file, folder, or function? I want to search the right part of the repo."`
  - In `CODE_LOOKUP_PROMPT`, the model is instructed: `"If the retrieved context does not contain enough information to answer the question, state clearly: 'I couldn't find that in the retrieved code.'"`. Combined with B5 (where ambiguous questions default to `CODE_LOOKUP`), the model frequently outputs this canned refusal even when relevant background files were retrieved.

### 3.4 LLM Fallback & Circuit Breaker Verification
- **Implemented Mechanics**:
  - `is_daily_quota_exhausted`: Correctly detects Gemini Free Tier `limit: 20/day` errors.
  - `record_quota_exhaustion`: Trips the circuit breaker with a cooldown timestamp.
  - `is_circuit_open`: Skips exhausted models in all 4 execution methods (`complete`, `stream_complete`, `acomplete`, `astream_complete`).
  - Thread-safe synchronization via `_cb_lock`.
- **Live Verification**:
  1. Daily quota error -> Trips circuit breaker: **PASS**
  2. Transient error (503 / short 429) -> Does not trip circuit breaker: **PASS**
  3. Cooldown expiry -> Automatically recovers after timestamp passes: **PASS**
  4. Concurrent operations -> 8 threads x 100 cycles under lock completed with 0 errors: **PASS**
  5. Fallback routing -> Directly routes to Groq (`qwen/qwen3.8-27b`) when Gemini circuit is open: **PASS**

### 3.5 Test Evidence Separation (Mocked vs. Live)
- **Automated Backend Pytest Suite (679 Tests)**:
  - **679 passed** in 16.66 seconds.
  - **Nature of Tests**: 100% of database tests in `tests/unit/test_supabase_service.py` (49 tests) and `test_chat_service.py` use `MagicMock` or in-memory stubs. **No live network or database calls are made during the standard pytest run.**
  - **Live End-to-End Verification**: Performed via dedicated scratch scripts (`verify_live_fixes.py`, `audit_auth_db_llm.py`) against `http://localhost:8000` and the remote Supabase API.

---

## 4. Summary of Outstanding Blockers

1. **Remote Database Schema Migration (User Action Required)**:
   - The remote Supabase PostgreSQL database is missing 6 tables and 15 columns.
   - **Action**: Run [`api/migrations/20261031_stabilization_schema_repair.sql`](file:///Users/sj/Documents/AI-Copilot/codebase-copilot/api/migrations/20261031_stabilization_schema_repair.sql) in the Supabase Dashboard SQL Editor.
2. **Query Router LLM Initialization (B5)**:
   - `app/retrieval/query_router.py` must use `get_resilient_llm()` instead of unconfigured `Settings.llm` to prevent OpenAI missing API key exceptions on ambiguous queries.
3. **Destructive Refresh Protection (B7)**:
   - `api/routers/repo.py` should stage refresh clones in a temporary folder before deleting the existing working index.
4. **Citation Validation Mode (B8)**:
   - `CITATION_VALIDATION_MODE` should be set to `"strict"` in `.env` if hallucinated file citations must be filtered out rather than logged.

---

## 5. Demonstration Recommendations

For the technical demonstration:
- **Use Working Paths**:
  - Conversational greetings (Fast-path: ~15ms).
  - Specific, well-scoped codebase questions on `SenseVoice` and `Codebase-Copilot` (e.g. `Where is model inference implemented?`, `Show me the retriever architecture`).
  - Architecture queries requesting Mermaid diagrams (`Explain architecture with a mermaid diagram`).
  - Repository Health Dashboard metrics and category breakdown.
- **Avoid During Demo** (Until migration & B7 fixes are applied):
  - Do not click "Refresh Repository" on the sole indexed copy of a repository.
  - Do not demonstrate attachment uploads or saved reports export until the Supabase migration script is executed.
  - Avoid single-word vague queries like `code` or `what is this` without a specific target noun.
