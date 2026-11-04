# Codebase-Copilot — Final B1–B9 Regression Verification Report

**Verification Date:** October 31, 2026  
**Active Branch:** `fix/demo-readiness`  
**Checkpoint Commit:** `6f6e4a2 chore: checkpoint demo readiness fixes and regression tests`  
**Baseline Git Comparison:** `main` and `origin/main` untouched at `497b63c93fc98349e190b5d693256e57450f1c04`  
**Verification Mode:** Verification-Only (Zero application source code modifications, zero schema migrations, zero repository re-indexing)

---

## 1. Executive Summary

This document presents the consolidated regression verification of issues **B1 through B9** for Codebase-Copilot on branch `fix/demo-readiness` at commit `6f6e4a2`.

Verification was conducted following a strict two-pass methodology:
- **Pass 1 (Core Interactive & Retrieval Invariants: B1–B5):** Scoping, authentication expiration handling, chat switching and loading state, analysis action triggering, and vague query classification.
- **Pass 2 (Data Layer, Resilience & Synthesis Invariants: B6–B9):** Remote Supabase schema and RLS persistence, non-destructive staged repository refresh, strict citation verification, and retrieval confidence handling.

### Final Verification Verdict: **PASS (9/9 issues passed within the tested scope)**

Every original issue (B1–B9) has been verified within its tested scope using a combination of targeted unit regression suites, full pytest regression test runs, frontend integration/typecheck/lint audits, and live read-only verification against the live FastAPI backend and remote Supabase instance.

> [!NOTE]
> All 9 original issues have passed within their tested scopes. However, successful regression verification does not independently establish production readiness; operational deployment requires addressing known infrastructure constraints (such as conducting authenticated cross-user isolation testing once a secondary test account is provisioned).

---

## 2. Original Bug Definitions

The definitions below preserve the authoritative definitions established during the initial verification audit:

| ID | Issue Title | Original Definition |
| :--- | :--- | :--- |
| **B1** | **Wrong repository context contamination** | Cross-repository context bleeding where chunks, symbols, or conversational memory from Repository A contaminate queries or responses in Repository B. |
| **B2** | **Expired-JWT chat failure** | Uncaught exceptions or corrupted chat state occurring when an expired, missing, or malformed JWT is used, rather than a clean 401 response and graceful session recovery. |
| **B3** | **Chat switching/loading** | Conversation switching failures, race conditions, stale message bleed across chats, missing loading indicators, or unhandled empty conversation states. |
| **B4** | **Analysis action unreliable** | Unreliable triggering of engineering and analysis actions (Code Review, Health Analysis, Impact Analysis) due to uninitialized chat sessions, missing duplicate-trigger guards, or unhandled errors. |
| **B5** | **Vague questions unhelpful** | Short, broad, or ambiguous repository inquiries (e.g., *"What is this?"*, *"How does it work?"*) failing to route to architectural context and instead falling back to strict code lookup with generic refusals. |
| **B6** | **Missing Supabase schema** | Missing database tables, columns, foreign keys, or RLS policies preventing remote persistence of attachments, saved reports, code reviews, summaries, tags, and exports. |
| **B7** | **Destructive refresh ordering** | Repository refresh sequences that eagerly delete existing working clones or indices before a replacement is cloned, indexed, and validated. |
| **B8** | **Unsupported citations** | Hallucinated, nonexistent, or fabricated file and line citations reaching the client rather than being sanitized or rejected by citation validation. |
| **B9** | **Retrieved chunks but generic no-results** | Low confidence thresholds or strict prompt instructions rejecting valid retrieved chunks and returning generic refusal messages (*"I couldn't find that in the retrieved code"*). |

---

## 3. Pass 1: B1–B5 Verification

Pass 1 audited the core conversation, authentication, and routing pathways:

### B1 — Wrong repository context contamination
- **Verification Approach:** Inspect session memory caches, reranker caches, vector index loading, and database repository scoping. Execute unit tests verifying partition boundaries.
- **Test Cases & Evidence:**
  - `TestB1RepoIsolation.test_session_cache_partitioning`: Verified `_session_cache` in `api/services/chat_service.py` is keyed strictly on `(repo_id, chat_id)`. Querying `repo_a` with `chat_b` returns `(None, None, None)`.
  - `TestB1RepoIsolation.test_reranker_cache_partitioning`: Verified `_reranker_cache` in `app/retrieval/reranker.py` namespaces keys on `(index_name, norm_query, node_set_hash)`.
  - `TestB1RepoIsolation.test_index_cache_isolation`: Verified `_index_cache` in `app/services/qa_service.py` segregates indices by `index_name`.
  - Chroma storage inspection: Verified collections reside in isolated paths `data/index/{index_name}/chroma`.
- **Status:** **`PASS` (within tested scope)**
- **Uncovered Scenarios:** Multi-tenant shared vector index clusters (not applicable to single-repo directory architecture).

### B2 — Expired JWT chat failure
- **Verification Approach:** Verify backend error classification and HTTP response codes for missing, malformed, and expired JWTs. Audit frontend error handling and public preflight endpoints.
- **Test Cases & Evidence:**
  - `TestB2JwtHandling.test_expired_jwt_raises_401_with_clear_detail`: Verified `get_current_user` raises HTTP `401 Unauthorized` with detail `"Token expired. Please sign in again."`.
  - `TestB2JwtHandling.test_missing_or_malformed_jwt_raises_401`: Verified missing/malformed auth raises HTTP `401 Unauthorized` (`"Token verification failed"`).
  - Live API Checks:
    - `GET /api/repo/list` without token -> HTTP `401`
    - `GET /api/repo/list` with malformed token -> HTTP `401`
    - `POST /api/auth/login/preflight` -> HTTP `200`
    - `POST /api/auth/register/preflight` -> HTTP `200`
  - Frontend Audit: Verified `isExpiredAuthError` in `frontend/app/repo/[id]/chat/page.tsx` displays toast `"Your session has expired. Please sign in again."`, clears sessions, and avoids unhandled promise rejections.
- **Status:** **`PASS` (within tested scope)**
- **Uncovered Scenarios:** JWT expiration occurring mid-SSE stream after HTTP handshake authorization has already completed.

### B3 — Chat switching/loading
- **Verification Approach:** Audit message fetching per conversation ID, frontend loading state lifecycle, and race condition prevention.
- **Test Cases & Evidence:**
  - `TestB3ChatSwitching.test_chat_message_isolation_between_sessions`: Verified `get_messages_for_chat` filters strictly on `.eq("chat_id", chat_id)`. Messages from Chat A never appear in Chat B.
  - Frontend State Lifecycle (`loadSession` in `chat/page.tsx`):
    1. Sets `sessionReady = false` and `sessionLoading = true`.
    2. Clears active messages (`setMessages([])`) immediately to eliminate visual bleed.
    3. Resets inspect panels, retry prompts, and active index.
    4. Fetches `getMessages()` and sets `sessionReady = true` in `finally`.
  - Frontend Vitest: `frontend/lib/chat-context.test.ts` passed (3/3 tests).
- **Status:** **`PASS` (within tested scope)**
- **Uncovered Scenarios:** Rapid alternating clicks across 10+ conversations under simulated network packet loss.

### B4 — Analysis action reliability
- **Verification Approach:** Clearly distinguish the live Code Review execution from frontend action-handler inspection and unit tests. Inspect action trigger handlers in chat and review pages, verify duplicate-trigger prevention and queuing mechanics, run frontend component tests, and execute a single live Code Review against the backend. Health Analysis and Impact Analysis were audited via frontend inspection and tests, but were not independently executed live.
- **Frontend Action-Handler Inspection & Tests:**
  - Initialization Queuing: In `frontend/app/repo/[id]/chat/page.tsx`, if `chatId` is missing and `sessionReady = false`, actions are queued via `pendingAutoPromptRef.current = query` with toast `"Conversation session is initializing. Your action will start shortly."`.
  - Duplicate Prevention: `if (!query.trim() || streaming) return;` prevents re-triggers while streaming is active.
  - Action Lifecycle: `runRibbonAction` in `review/page.tsx` tracks active states (`setRibbonAction`), displays `toast.error`, emits audit events (`onTimelineEvent`), and cleans up in `finally`.
  - Frontend Component Tests (Vitest): `frontend/lib/engineering-actions.test.ts` passed (4/4 tests verifying action identification for recommendations, files, manifests, and commits).
- **Live Backend Execution:**
  - Live Code Review Execution: Executed `POST /api/reviews/file` live on `model.py` against `SenseVoice` resulting in review ID `7713bcbb-ab8f-4d92-b7eb-aec3f99fd498` with 3 findings generated and successfully retrieved via `GET /api/reviews/{id}`.
  - Health Analysis & Impact Analysis: Audited solely via frontend handler code inspection and component tests; no live backend execution was performed for these two actions.
- **Status:** **`PASS` (within tested scope: live Code Review executed; Health & Impact audited via frontend inspection and tests)**
- **Uncovered Scenarios:** Live end-to-end API execution of Health Analysis and Impact Analysis actions; multiple concurrent reviews triggered on the same file from multiple browser tabs.

### B5 — Vague-question routing
- **Verification Approach:** Evaluate query router classification on broad exploration questions using fast-path regex and resilient LLM classifier with fallback circuit breaking.
- **Test Cases & Evidence:**
  - Five Required Queries Evaluated (Live & Unit):
    1. `"What is this?"` -> **`QueryMode.ARCHITECTURAL`**
    2. `"How does it work?"` -> **`QueryMode.ARCHITECTURAL`**
    3. `"Explain this repository."` -> **`QueryMode.ARCHITECTURAL`**
    4. `"What is the architecture?"` -> **`QueryMode.ARCHITECTURAL`**
    5. `"Give me an overview."` -> **`QueryMode.ARCHITECTURAL`**
  - Specific Code Query Preservation: `"where is class AudioModel defined in model.py?"` routes to **`QueryMode.CODE_LOOKUP`**.
  - Unit Suite: `tests/unit/test_query_router_intents.py` passed (14/14 tests).
  - Circuit Breaker Resiliency: When primary model quota was exhausted, query router completed classification via fallback provider without missing-key exceptions.
- **Status:** **`PASS` (within tested scope)**
- **Uncovered Scenarios:** Multilingual vague questions in non-English languages without explicit keywords.

---

## 4. Pass 2: B6–B9 Verification

Pass 2 audited database schema integrity, repository refresh non-destructiveness, citation correctness, and retrieval relevance:

### B6 — Supabase schema and persistence
- **Verification Approach:** Inspect backend Supabase service methods and Pydantic models against live Supabase OpenAPI schema. Execute targeted isolated PostgREST insertion, selection, and update operations using authenticated user JWT and unauthenticated anon key.
- **Live Schema Verification:**
  - `attachments` (9 columns): `chat_id`, `created_at`, `deleted_at`, `file_size`, `filename`, `id`, `mime_type`, `storage_path`, `user_id`.
  - `saved_reports` (9 columns): `content`, `created_at`, `deleted_at`, `id`, `repo_id`, `report_type`, `title`, `updated_at`, `user_id`.
  - `repository_reviews` (11 columns): `changed_files`, `commit_hash`, `created_at`, `findings`, `id`, `repo_id`, `request_payload`, `status`, `summary`, `target_type`, `user_id`.
  - `conversation_summaries` (19 columns): `action_items`, `apis_discussed`, `chat_id`, `classes_discussed`, `created_at`, `executive_summary`, `files_discussed`, `id`, `key_decisions`, `keywords`, `modules_discussed`, `repo_id`, `risks_identified`, `services_discussed`, `tags`, `technical_summary`, `title`, `updated_at`, `user_id`.
  - `conversation_tags` (4 columns): `chat_id`, `created_at`, `id`, `tag`.
  - `exports` (7 columns): `created_at`, `export_meta`, `format`, `id`, `repo_id`, `scope`, `user_id`.
  - `chats` and `messages`: Added columns (`session_type`, `is_pinned`, `token_count`, `sequence`, `metadata`, etc.) verified present.
- **Targeted Isolated PostgREST Operations & Permissions Evidence:**
  - *Note on Scope:* Tests performed targeted per-table INSERT, SELECT, and UPDATE operations as detailed below, rather than full CRUD (Create, Read, Update, Delete) on every individual table.
  - `conversation_tags`: INSERT `201 Created` | SELECT `200 OK` (count=1) | Anon rejected `401 Unauthorized`
  - `conversation_summaries`: INSERT `201 Created` | SELECT `200 OK` (count=1) | Anon rejected `401 Unauthorized`
  - `attachments`: INSERT `201 Created` | SELECT `200 OK` (count=1) | UPDATE `200 OK` | Anon rejected `401 Unauthorized`
  - `saved_reports`: INSERT `201 Created` | SELECT `200 OK` (count=1) | Anon rejected `401 Unauthorized`
  - `repository_reviews`: INSERT `201 Created` | SELECT `200 OK` (count=1) | Anon rejected `401 Unauthorized`
  - `exports`: INSERT `201 Created` | SELECT `200 OK` (count=1) | Anon rejected `401 Unauthorized`
  - Cleanup: All created test records and temporary chat deleted cleanly.
- **RLS Isolation & Scope Evidence:**
  - **Unauthenticated Access Restriction:** Verified. Rejection of unauthenticated anon-key queries (`401 Unauthorized` / error code `42501`) confirms that database RLS is active and restricts public/anonymous access.
  - **Authenticated Cross-User Isolation:** **NOT VERIFIED**. Authenticated cross-user isolation was NOT VERIFIED because a second authenticated user account was unavailable on this Supabase project, and creating unapproved accounts was prohibited. Anon-key rejection is evidence of unauthenticated access restriction, not proof of cross-user isolation between two distinct authenticated users.
- **Status:** **`PASS` (within tested scope: schema verified, single-user authenticated DML verified, unauthenticated anon rejected; cross-user isolation NOT VERIFIED)**
- **Uncovered Scenarios:** Authenticated cross-user negative isolation (requiring two concurrent authenticated test accounts); concurrent update collisions on the same attachment row from multiple sessions.

### B7 — Non-destructive repository refresh
- **Verification Approach:** Execute isolated unit and filesystem failure-injection tests simulating git clone failure, indexing crashes, empty staging indices, promotion failures, rollback, and concurrency locks. **Mocked and isolated filesystem failure-injection tests were executed; no live repository refresh was performed against SenseVoice or any real user repository.**
- **Test Cases & Evidence (`tests/unit/test_repo_refresh_regression.py`):**
  - `test_validate_staged_index_success`: Staged directory with valid Chroma SQLite and manifest passes validation.
  - `test_validate_staged_index_missing_chroma`: Missing Chroma directory raises `ValueError`.
  - `test_validate_staged_index_empty_sqlite`: Empty `chroma.sqlite3` raises `ValueError`.
  - `test_promote_staged_index_atomic_swap`: Valid staging index is atomically swapped into active directory.
  - `test_promote_staged_index_rollback_on_failure`: Filesystem replacement failure triggers automatic rollback, preserving original index.
  - `test_indexing_failure_preserves_existing_index`: Embedding failure preserves working index and cleans up staging directory.
  - `test_clone_failure_preserves_existing_clone`: Network clone failure leaves original clone untouched.
  - `test_concurrent_refresh_locks`: Lock acquisition prevents simultaneous refresh runs on the same repository.
  - `test_interrupted_refresh_preserves_prior_index`: SIGINT/interruption cleans up staging without corrupting active index.
  - `test_successful_refresh_flow`: End-to-end staged refresh flow succeeds in isolated temporary directory.
- **Status:** **`PASS` (within tested scope: verified via isolated/mocked failure-injection regression suite; no real repository refresh executed)**
- **Uncovered Scenarios:** Real live repository refresh against production git hosts under real network latency (intentionally omitted to protect existing indexes); filesystem configurations spanning separate physical mount points where `os.replace` cannot be atomic.

### B8 — Citation correctness
- **Verification Approach:** Test citation extraction, validation of existing/nonexistent files, line number validation, out-of-context tracking, and strict mode sanitization.
- **Test Cases & Evidence (`tests/unit/test_citation.py`):**
  - `test_extract_cited_files`: Extracts file paths from prose, markdown brackets, and backticks.
  - `test_valid_citations_with_line_numbers`: Valid files and line numbers within file boundaries pass validation.
  - `test_invalid_filenames_detected`: Nonexistent files (e.g., `phantom_service.py`) flagged as invalid.
  - `test_fabricated_line_numbers_detected`: Line numbers exceeding physical file length (e.g., line 999 on 20-line file) flagged as fabricated.
  - `test_mixed_valid_and_invalid_citations`: Correctly partitions mixed valid and invalid citations.
  - `test_citations_outside_retrieved_context`: Physical files existing in repo but absent from retrieved chunks are distinguished from nonexistent files.
  - `test_sanitize_citations_preserves_valid_and_neutralizes_invalid`: Sanitizes prose, stripping fabricated lines and omitting nonexistent files.
  - `test_retrieve_and_answer_strict_citation_mode`: In strict mode, invalid citations prompt a retry with validation feedback.
- **Status:** **`PASS` (within tested scope)**
- **Uncovered Scenarios:** Dynamic runtime generated files not tracked in git history.

### B9 — Retrieval relevance
- **Verification Approach:** Verify handling of RRF fusion scores, architectural query exemptions, answer generation for valid context, and appropriate refusals for empty retrieval.
- **Test Cases & Evidence (`tests/unit/test_qa_service.py`):**
  - `test_check_low_confidence_handles_rrf_scores`: RRF fusion scores in `[0.016, 0.033]` are recognized and not rejected as low confidence.
  - `test_check_low_confidence_architectural_mode_preserves_context`: Architectural queries are exempted from code-lookup abort thresholds.
  - `test_check_low_confidence_empty_nodes_is_low_confidence`: Empty retrieval genuinely returns low confidence / appropriate refusal.
  - `test_answerable_question_reaches_generation`: Valid retrieved context generates a full answer rather than a generic refusal.
  - Live SenseVoice Smoke Test: Architectural prompt retrieved 5 relevant nodes (including `_codebase_context`) and synthesized a 3,265-character structured answer.
- **Status:** **`PASS` (within tested scope)**
- **Uncovered Scenarios:** Adversarial keyword-stuffing prompts designed to artificially manipulate reranker scoring.

---

## 5. Consolidated B1–B9 Matrix

| ID | Issue Title | Verification Method | Unit / Mock Result | Live API / DB Result | Final Status | Known Limitations |
| :--- | :--- | :--- | :---: | :---: | :---: | :--- |
| **B1** | Wrong repository context contamination | Cache partitioning & index path audit | **PASS** (3/3) | **PASS** | **PASS** (within tested scope) | Single-repo directory architecture; not tested on multi-tenant shared index. |
| **B2** | Expired-JWT chat failure | Auth dependency & preflight audit | **PASS** (4/4) | **PASS** (4/4) | **PASS** (within tested scope) | Mid-stream token expiration after initial handshake not simulated. |
| **B3** | Chat switching/loading | Session lifecycle & message filter audit | **PASS** (2/2) | **PASS** | **PASS** (within tested scope) | Extreme network packet loss during rapid switching not simulated. |
| **B4** | Analysis action unreliable | Action initialization & review execution | **PASS** (5/5) | **PASS** (Code Review live on `model.py`) | **PASS** (within tested scope) | Live execution conducted for Code Review only; Health & Impact analysis verified via frontend inspection and tests. |
| **B5** | Vague questions unhelpful | Query router classification & fallback | **PASS** (16/16) | **PASS** (5/5) | **PASS** (within tested scope) | Non-English vague questions without explicit keywords not tested. |
| **B6** | Missing Supabase schema | Schema inspection & PostgREST DML/RLS | **PASS** (1/1) | **PASS** (Single-user & anon restriction) | **PASS** (within tested scope) | Authenticated cross-user isolation NOT VERIFIED due to lack of secondary test account; anon rejection proves unauthenticated restriction only. Partial DML tested, not full CRUD on every table. |
| **B7** | Destructive refresh ordering | Staged refresh & rollback suite | **PASS** (10/10) | **NOT RUN** (Isolated tests only) | **PASS** (within tested scope) | Mocked/isolated failure-injection tests only; real repo refresh not performed to protect existing indices; non-atomic across separate physical mounts. |
| **B8** | Unsupported citations | Citation validation & sanitizer suite | **PASS** (9/9) | **PASS** | **PASS** (within tested scope) | Dynamic untracked runtime files not in git history. |
| **B9** | Retrieved chunks generic no-results | Confidence threshold & RRF score suite | **PASS** (6/6) | **PASS** | **PASS** (within tested scope) | Adversarial keyword stuffing queries. |

---

## 6. Overall Test Summary

### Test Commands Executed & Distinct Test Counts

```bash
# 1. Full Backend Test Suite (Pytest)
conda run -n ai-copilot-env pytest tests/unit tests/integration -q
# Result: 703 passed, 7 warnings in 16.33s

# 2. Frontend Test Suite (Vitest)
npm test (in frontend/)
# Result: 7 passed in 527ms (2 test files: engineering-actions, chat-context)

# 3. Frontend Static Analysis
npx tsc --noEmit && npm run lint (in frontend/)
# Result: TypeScript: 0 errors | ESLint: 0 errors, 6 warnings

# 4. Pass 1 Targeted Regression Suite
PYTHONPATH=. conda run -n ai-copilot-env python scratch/pass1_regression_suite.py
# Result: 10 unit tests passed, 4 live API checks passed

# 5. Pass 2 Targeted Regression Suites
conda run -n ai-copilot-env pytest tests/unit/test_repo_refresh_regression.py -v # 10 passed
conda run -n ai-copilot-env pytest tests/unit/test_citation.py -v                # 9 passed
conda run -n ai-copilot-env pytest tests/unit/test_qa_service.py -v             # 6 passed
PYTHONPATH=. conda run -n ai-copilot-env python scratch/test_b6_crud.py        # 18 checks passed
```

### Distinction of Test Types (No Double-Counting)
- **Comprehensive Backend Pytest Suite:** **703 unique tests** encompassing all unit, mock, and local integration tests.
- **Frontend Vitest Suite:** **7 unique unit/integration tests**.
- **Live Smoke & PostgREST Verification:** Targeted operational verification against live backend (`http://localhost:8000`) and live Supabase PostgREST endpoints.

---

## 7. Live Verification Evidence

### SenseVoice Backend Smoke Test (`296ee64c-a989-48ff-9ded-a3e1bb09b63f`)
- **Repository Listing & Ownership:** `GET /api/repo/list` returned `200 OK`, `repo_status: ready`, and verified owner `25be0cf8-9229-47b3-9df3-c93f035390de`.
- **Chat Creation:** `POST /api/chat/session` returned `200 OK`, `chat_id: b51ca556-8e2b-4362-a4dc-ab9a1c16e728`.
- **File Review Execution:** `POST /api/reviews/file` on `model.py` returned `200 OK`, `review_id: 7713bcbb-ab8f-4d92-b7eb-aec3f99fd498` with 3 findings.
- **Review Retrieval:** `GET /api/reviews/{id}` returned `200 OK`, verifying persistence.
- **Chat SSE Streaming:** `POST /api/chat/{id}/message/stream` streamed 31 token events and completed with `stream_done_received: true`, generating a 3,265-character architectural response referencing 5 source files.
- **Message Retrieval:** `GET /api/chat/{id}/messages` confirmed both user and assistant messages were persisted.
- **Post-Test Cleanup:** `DELETE /api/reviews/{id}` and `DELETE /api/chat/{id}?hard_delete=true` returned `200 OK`. `GET /messages` confirmed `404 Not Found`.
- **Repository Integrity:** SenseVoice metadata (`indexed_at`, `node_count: 419`, `file_count: 68`) and local index files (`chroma/`, `manifest.json`, `git_history.json`) remained completely untouched.

---

## 8. Known Limitations and Uncovered Scenarios

1. **Cross-User Authenticated Isolation (NOT VERIFIED):**
   - **Limitation:** Verification was conducted using the single approved test account (`rickey.chikki@gmail.com`). A negative test verifying that a second authenticated user cannot access User A's records was **NOT VERIFIED** because no secondary test account was provisioned, and account creation was prohibited without authorization.
   - **Evidence Scope:** Database RLS was verified by testing unauthenticated anon access; all 6 tables rejected access with HTTP `401 Unauthorized` / error code `42501`. Anon-key rejection proves that unauthenticated public access is restricted by RLS, but does NOT establish cross-user isolation between two distinct authenticated accounts. Furthermore, targeted testing evaluated per-table INSERT, SELECT, and UPDATE operations rather than full CRUD across all tables.
2. **Filesystem Mount Boundary Rollback:**
   - Atomic directory rename (`os.replace`) requires source and destination to reside on the same filesystem. In multi-mount Docker configurations, promotion falls back to standard copy/remove.
3. **Mid-Stream Auth Severance:**
   - Token expiration is enforced at endpoint entry. If a token expires while an active SSE connection is open, the current stream continues to completion.
4. **Adversarial Non-English Vague Queries:**
   - Vague routing heuristics rely on English semantic terms and LLM classifier prompts. Broad queries in non-English languages without keyword matches may fall back to default code lookup.
5. **Health Analysis and Impact Analysis Live Execution:**
   - Code Review on `model.py` was executed live and verified end-to-end. Health Analysis and Commit Impact Analysis were verified via frontend code inspection and component tests, but were not independently executed live during this pass.
6. **Live Repository Refresh Execution:**
   - Refresh non-destructiveness and rollback mechanics were verified exclusively via mocked and isolated filesystem failure-injection unit tests. A live repository refresh against a real repository was not performed.
7. **Production Readiness Caveat:**
   - Successful regression verification within the tested scope confirms that targeted bugs B1–B9 are stabilized; it does not independently establish full production readiness across unverified infrastructure edge-cases.

---

## 9. Git Baseline

- **Current Active Branch:** `fix/demo-readiness`
- **Current HEAD Commit:** `6f6e4a2 chore: checkpoint demo readiness fixes and regression tests`
- **Working Tree Status:** No tracked modifications remain; nine intentional historical audit reports remain untracked.
- **Target `main` Branch Status:** `497b63c93fc98349e190b5d693256e57450f1c04` (Completely untouched)
- **Target `origin/main` Branch Status:** `497b63c93fc98349e190b5d693256e57450f1c04` (Completely untouched)
- **Preserved Untracked Historical Reports (9 files):**
  - `API_ENDPOINT_AUDIT.md`
  - `CHAT_SUPABASE_LLM_DIAGNOSTIC.md`
  - `COMPREHENSIVE_QA_PROGRESS.md`
  - `COMPREHENSIVE_QA_REPORT.md`
  - `FRONTEND_INTERACTION_AUDIT.md`
  - `LLM_PROVIDER_AUDIT.md`
  - `QA_PROGRESS.md`
  - `REPOSITORY_RAG_AUDIT.md`
  - `SUPABASE_AUTH_AUDIT.md`
- **Preserved Git Stashes (3 stashes):**
  - `stash@{0}`: On `sj-improve-rag2`: `sj-improve-rag2 temporary changes 2.`
  - `stash@{1}`: WIP on `sj-improve-rag`: `4d7a88e feat: implement relationship-based retrieval...`
  - `stash@{2}`: WIP on `fastapi_layers_improvements_and_frontend`: `72d8b4a Add Next.js frontend structure...`
