# Production Deployment Readiness Audit: Codebase-Copilot

**Author:** Senior Staff Systems & Infrastructure Engineer  
**Audit Target:** Codebase-Copilot (FastAPI + Next.js + Supabase + ChromaDB + LlamaIndex)  
**Execution Context:** Strictly Read-Only Forensic Architecture and Production Pre-Flight Review  
**Date of Audit:** November 3, 2026  
**Primary Output File:** `docs/DEPLOYMENT_READINESS_AUDIT.md`  
**Technical Appendix:** [`docs/DEPLOYMENT_READINESS_AUDIT_APPENDIX.md`](./DEPLOYMENT_READINESS_AUDIT_APPENDIX.md)  

---

## Table of Contents
1. [Executive Summary & Ranked Critical Risks](#executive-summary--ranked-critical-risks)
2. [Section A — Git Overview & Branch Forensics](#section-a--git-overview--branch-forensics)
   - [A1. Current Working Tree and HEAD State](#a1-current-working-tree-and-head-state)
   - [A2. Comprehensive Branch Inventory & Ahead/Behind Matrix](#a2-comprehensive-branch-inventory--aheadbehind-matrix)
   - [A3. Inferred Branch Purpose and Functional Area Analysis](#a3-inferred-branch-purpose-and-functional-area-analysis)
   - [A4. Main Branch History, CI Status, and Deficits](#a4-main-branch-history-ci-status-and-deficits)
   - [A5. Predictive Merge-Tree Conflict Analysis & Hotspots](#a5-predictive-merge-tree-conflict-analysis--hotspots)
   - [A6. Capability Presence Matrix Across Branches](#a6-capability-presence-matrix-across-branches)
   - [A7. Staff Engineering Recommendation & Branch Cleanup Strategy](#a7-staff-engineering-recommendation--branch-cleanup-strategy)
   - [A8. Repository Hygiene, Secrets Exposure, Blobs, and Storage](#a8-repository-hygiene-secrets-exposure-blobs-and-storage)
3. [Section B — Architecture, Runtime & Environment Configuration](#section-b--architecture-runtime--environment-configuration)
   - [B1. Physical Directory Tree, LOC Metrics, Entry Points, and Run Commands](#b1-physical-directory-tree-loc-metrics-entry-points-and-run-commands)
   - [B2. Runtime Versions and Dependency Pinning Status](#b2-runtime-versions-and-dependency-pinning-status)
   - [B3. Environment Variable Specification and .env Audit](#b3-environment-variable-specification-and-env-audit)
4. [Section C — Verification of Specific Technical Findings (F1 to F23)](#section-c--verification-of-specific-technical-findings-f1-to-f23)
   - [F1. CrossEncoder Double-Sigmoid Normalization Bug](#f1-crossencoder-double-sigmoid-normalization-bug)
   - [F2. Stored Chunk Metadata Omission](#f2-stored-chunk-metadata-omission)
   - [F3. Severe Source Code Truncation at Ingestion](#f3-severe-source-code-truncation-at-ingestion)
   - [F4. Index Staleness and Manifest Desynchronization](#f4-index-staleness-and-manifest-desynchronization)
   - [F5. Prompt-to-Context Line Number Mismatch and Citation Validation](#f5-prompt-to-context-line-number-mismatch-and-citation-validation)
   - [F6. Duplicate Retrieval Logic and Dead Code Paths in Chat Service](#f6-duplicate-retrieval-logic-and-dead-code-paths-in-chat-service)
   - [F7. Hardcoded Score Thresholds and Calibration Assumptions](#f7-hardcoded-score-thresholds-and-calibration-assumptions)
   - [F8. Multi-Tenant Repository and Index Name Collisions](#f8-multi-tenant-repository-and-index-name-collisions)
   - [F9. Arbitrary Server Directory Ingestion and Scheme Bypass](#f9-arbitrary-server-directory-ingestion-and-scheme-bypass)
   - [F10. Global Server-Wide Git Authentication Token Exposure](#f10-global-server-wide-git-authentication-token-exposure)
   - [F11. Ingestion Clone Hardening and SSRF Vulnerabilities](#f11-ingestion-clone-hardening-and-ssrf-vulnerabilities)
   - [F12. Symlink Host File Read Vulnerability](#f12-symlink-host-file-read-vulnerability)
   - [F13. Repository Isolation Module Implementation and Stamping Flaws](#f13-repository-isolation-module-implementation-and-stamping-flaws)
   - [F14. Complete API Route Authorization and Ownership Coverage](#f14-complete-api-route-authorization-and-ownership-coverage)
   - [F15. Supabase Schema, RLS Policies, and Service Role Usage](#f15-supabase-schema-rls-policies-and-service-role-usage)
   - [F16. Per-Request Supabase Auth Overhead and Missing Quotas](#f16-per-request-supabase-auth-overhead-and-missing-quotas)
   - [F17. Single-Threaded Stream Executor Bottleneck and Thread Safety](#f17-single-threaded-stream-executor-bottleneck-and-thread-safety)
   - [F18. Ephemeral BM25 Index Rebuilds and Chroma Client Proliferation](#f18-ephemeral-bm25-index-rebuilds-and-chroma-client-proliferation)
   - [F19. Query Router Substring Collision and Test-Mock Contamination](#f19-query-router-substring-collision-and-test-mock-contamination)
   - [F20. Relationship Query Graph Isolation and Zero-Match Behavior](#f20-relationship-query-graph-isolation-and-zero-match-behavior)
   - [F21. Prompt Injection Vulnerability and Refusal String Dependencies](#f21-prompt-injection-vulnerability-and-refusal-string-dependencies)
   - [F22. Hard Ollama Embeddings Lock-In and Cloud Unviability](#f22-hard-ollama-embeddings-lock-in-and-cloud-unviability)
   - [F23. Silent Exception Swallowing and Unlogged Fallback Cascades](#f23-silent-exception-swallowing-and-unlogged-fallback-cascades)
5. [Section D — Evaluation Suite and Test Harness Audit](#section-d--evaluation-suite-and-test-harness-audit)
   - [D1. Evaluation Dataset Composition and Leakage Analysis](#d1-evaluation-dataset-composition-and-leakage-analysis)
   - [D2. Evaluation Reports Provenance and Metric Discrepancies](#d2-evaluation-reports-provenance-and-metric-discrepancies)
   - [D3. Evaluation Suite Reproducibility Assessment](#d3-evaluation-suite-reproducibility-assessment)
   - [D4. Complete Test Inventory and Execution Verification](#d4-complete-test-inventory-and-execution-verification)
6. [Section E — Runtime Operations and Deployment Infrastructure](#section-e--runtime-operations-and-deployment-infrastructure)
   - [E1. Containerization, Orchestration, Healthchecks, and Observability](#e1-containerization-orchestration-healthchecks-and-observability)
   - [E2. Persistent Storage Layout, Caching, and Backup Strategy](#e2-persistent-storage-layout-caching-and-backup-strategy)
   - [E3. Empirical Latency, Memory RSS, and Prompt Token Profiling](#e3-empirical-latency-memory-rss-and-prompt-token-profiling)
   - [E4. External SaaS Dependencies, Quotas, and Failure Modes](#e4-external-saas-dependencies-quotas-and-failure-modes)
   - [E5. Frontend Production Readiness, Turbopack Build, and UX State](#e5-frontend-production-readiness-turbopack-build-and-ux-state)
7. [Section F — Product Surface and Contract Realism](#section-f--product-surface-and-contract-realism)
   - [F-1. Feature Surface Inventory and MVP Disposition Matrix](#f-1-feature-surface-inventory-and-mvp-disposition-matrix)
   - [F-2. README / Marketing Claims vs. Runtime Reality](#f-2-readme--marketing-claims-vs-runtime-reality)
8. [Section G — Technical Debt and Maintainability](#section-g--technical-debt-and-maintainability)
   - [G1. Codebase Smells, Giant Modules, and Circular Imports](#g1-codebase-smells-giant-modules-and-circular-imports)
   - [G2. Log Sanitization, PII Redaction, and Query Leakage](#g2-log-sanitization-pii-redaction-and-query-leakage)
9. [Section H — Data Store State & Alignment Audit](#section-h--data-store-state--alignment-audit)
   - [H1. Local Index vs. Repository Directory Cross-Reconciliation](#h1-local-index-vs-repository-directory-cross-reconciliation)
10. [Section I — Synthesis & Actionable Implementation Roadmap](#section-i--synthesis--actionable-implementation-roadmap)
    - [Recommended Work Breakdown (PR-Sized Iterations)](#recommended-work-breakdown-pr-sized-iterations)
    - [Open Questions for the System Owner](#open-questions-for-the-system-owner)
    - [Items That Could Not Be Determined (Unverified Inventory)](#items-that-could-not-be-determined-unverified-inventory)

---

## Executive Summary & Ranked Critical Risks

This technical deployment readiness audit evaluated Codebase-Copilot across architecture, multi-tenant security, retrieval pipeline accuracy, runtime concurrency, test coverage, and infrastructure deployability.

While the application features an extensive automated test suite (**849 backend tests passing in 63.3s**, **35 frontend Vitest tests passing in 0.5s**, and an optimized Next.js 16 production build), **the system in its current state cannot be deployed to external users or exposed on a public network**. Critical security vulnerabilities, multi-tenant isolation failures, unrecoverable retrieval data loss, single-threaded concurrency locks, and an inflexible local-Ollama dependency create immediate deployment blockers.

The top 10 critical risks are ranked below by urgency (P0 must fix before any external user; P1 before public beta; P2 post-launch stabilization):

| Rank | Priority | Vulnerability / Defect | Impact Summary | Evidence Pointer | Effort |
| :---: | :---: | :--- | :--- | :--- | :---: |
| **1** | **P0** | **Arbitrary Server Directory Ingestion & Host Symlink Leakage** | `load_repository` accepts any existing local server directory (e.g. `/etc`, `/var`, `/home/ubuntu`). Furthermore, `filter_files` and `code_parser` traverse symlinks pointing outside the repository without realpath validation, chunking arbitrary host files into Chroma and vectorizing them for querying. | Section C: [F9](#f9-arbitrary-server-directory-ingestion-and-scheme-bypass), [F12](#f12-symlink-host-file-read-vulnerability); `app/ingestion/repo_loader.py:514`, `app/ingestion/file_filter.py:69` | **S** (1 day) |
| **2** | **P0** | **Multi-Tenant Repository and Collection Collisions** | Repositories and indexes are named strictly by `os.path.basename` (the last URL segment). If two users index a repository named `app` or `backend`, the second clone deletes the first user's code on disk, overwrites its Chroma collection, and mixes chunks. `STATIC_REPO_ID_MAP` contains 8 hardcoded developer UUIDs, and missing chunk metadata causes `enforce_chunk_isolation` to blindly stamp the requesting user's ID onto any retrieved chunk. | Section C: [F8](#f8-multi-tenant-repository-and-index-name-collisions), [F13](#f13-repository-isolation-module-implementation-and-stamping-flaws); `app/ingestion/repo_loader.py:467`, `app/retrieval/repository_isolation.py:160` | **M** (2 days) |
| **3** | **P0** | **Server-Wide Git PAT Injection & SSRF Ingestion** | `get_git_auth_token` injects the server's global GitHub PAT into clone URLs for any user. A malicious guest or user can clone private enterprise repositories accessible by that token. Clones lack SSRF IP blocking, size limits, file count caps, and timeouts, permitting internal network probing (e.g., `169.254.169.254`). | Section C: [F10](#f10-global-server-wide-git-authentication-token-exposure), [F11](#f11-ingestion-clone-hardening-and-ssrf-vulnerabilities); `app/utils/git_auth.py:40`, `app/ingestion/repo_loader.py:270` | **S** (1 day) |
| **4** | **P0** | **20,000-Character Source Code Truncation (188M+ Characters Lost)** | `code_parser.py` hard-truncates every non-notebook file to `content[:20000]`. Across the current local index collection, **2,135 files were truncated and 188,173,071 characters discarded**. Forensic analysis confirms that for 2,121 of these files, the end of the file is completely absent from Chroma, making all tail functions, exports, and classes unretrievable. | Section C: [F3](#f3-severe-source-code-truncation-at-ingestion); `app/parsing/code_parser.py:176` | **M** (2 days) |
| **5** | **P0** | **Single-Threaded Streaming Executor Bottleneck (`max_workers=1`)** | In `app/services/llm_fallback.py`, `_STREAM_BRIDGE_EXECUTOR` is configured with `ThreadPoolExecutor(max_workers=1)`. All sync-stream-to-async bridge operations serialize through this single worker. If one user streams a 20-second LLM response, all other concurrent streaming chats globally are frozen and queued. | Section C: [F17](#f17-single-threaded-stream-executor-bottleneck-and-thread-safety); `app/services/llm_fallback.py:23` | **S** (0.5 day) |
| **6** | **P0** | **Hard Ollama Embeddings Lock-In & Cloud Deployment Incompatibility** | Vector embeddings are hardcoded to `OllamaEmbedding(model_name="nomic-embed-text")`. There is zero hosted cloud embedding support (OpenAI, Voyage, Cohere). In cloud deployments (ECS, Cloud Run, Kubernetes), spinning up local Ollama with GPU acceleration is cost-prohibitive or impossible. Changing models causes Chroma dimension mismatch crashes. | Section C: [F22](#f22-hard-ollama-embeddings-lock-in-and-cloud-unviability); `app/llm/llm_client.py:63` | **M** (2 days) |
| **7** | **P1** | **Reranker Double-Sigmoid & Hardcoded Cutoff Misalignment** | `app/retrieval/reranker.py` applies `1/(1+exp(-x))` to `CrossEncoder.predict()`, which sentence-transformers 5.4.1 already normalizes as a probability. This compresses negative logits (`-10.19`) into `~0.500009`. Downstream thresholds (`0.60`, `0.54`, `0.53`) and test mocks hardcode this distorted scale, meaning fixing the math will break downstream routing and cause false abstentions. | Section C: [F1](#f1-crossencoder-double-sigmoid-normalization-bug), [F7](#f7-hardcoded-score-thresholds-and-calibration-assumptions); `app/retrieval/reranker.py:178` | **M** (2 days) |
| **8** | **P1** | **Ephemeral BM25 Rebuilds on Startup (5–30s Latency / Memory Spikes)** | BM25 indexes are never serialized to disk. On backend restart, the first query to any repository forces a full filesystem walk, document reload, AST parse, and in-memory index construction over thousands of nodes, causing 5–30s response latency spikes and unbounded process RSS growth. | Section C: [F18](#f18-ephemeral-bm25-index-rebuilds-and-chroma-client-proliferation); `app/services/qa_service.py:340` | **M** (2 days) |
| **9** | **P1** | **Prompt Injection Vulnerability & Missing Untrusted Delimiters** | Code retrieved from user repositories is formatted directly into LLM prompts (`Context:
[path]
content`) without XML encapsulation (`<untrusted_code>`), escaping, or adversarial guards. Malicious repo files can issue prompt injections that override system instructions or exfiltrate private conversation history. | Section C: [F21](#f21-prompt-injection-vulnerability-and-refusal-string-dependencies); `api/services/chat_service.py:283` | **S** (1 day) |
| **10** | **P1** | **Branch Desynchronization: Core RAG Stabilization Uncommitted** | The 4-tier retrieval orchestrator, repository isolation, notebook parser, and calibration datasets do not exist in any committed Git branch. They exist solely as uncommitted working tree modifications and stashes. Branch `main` is missing all Phase 2 retrieval stabilization fixes. | Section A: [A1](#a1-current-working-tree-and-head-state), [A6](#a6-capability-presence-matrix-across-branches) | **M** (2 days) |

---

## Section A — Git Overview & Branch Forensics

### A1. Current Working Tree and HEAD State
- **Active Branch:** `fix/review-service-truncation`
- **Current HEAD Commit:** `cbe8e542aa7d8181f39050ddf4c9480296e48fae`
- **HEAD Commit Date:** Sat Oct 31 17:39:51 2026 +0530
- **HEAD Subject:** `fix(auth): support implicit hash token session recovery for magic links`
- **Staging Area:** Clean (`0 staged files`).
- **Working Tree State:** **DIRTY** (contains **18 modified tracked files** and **23 untracked files**).
- **Stashes Intact:** All 5 stashes remain preserved:
  - `stash@{0}`: `WIP: local audit reports and handoff`
  - `stash@{1}`: `WIP: CodeBase-Copilot retrieval stabilization`
  - `stash@{2}`: `sj-improve-rag2 temporary changes 2.`
  - `stash@{3}`: `4d7a88e feat: implement relationship-based retrieval...`
  - `stash@{4}`: `72d8b4a Add Next.js frontend structure...`
- **Remotes:** `origin` (`git@github.com:djcode0718/CodeBase-Copilot.git`).
- **Tags:** None present in local repository.

#### Inventory of Uncommitted Working Tree Changes
1. Tracked Modified Files (18):
   - `.gitignore`: Added ignore patterns for evaluation temporary dumps and caches.
   - `api/services/chat_service.py`: Integrated `get_retrieval_orchestrator()` into stream preparation; removed obsolete retrieval calls.
   - `api/services/chat_stream_utils.py`: Refined exception mapping for streaming responses.
   - `api/services/indexing_service.py`: Staging index promotion logic and multi-format parser hooks.
   - `app/config.py`: Added top-k constants (`DENSE_TOP_K=30`, `BM25_TOP_K=30`, `RRF_OUTPUT_CUTOFF=20`, `CROSS_ENCODER_DEPTH=15`, `TOP_K_RERANK=5`).
   - `app/indexing/context_builder.py`: Improved line and symbol metadata propagation into context strings.
   - `app/indexing/incremental.py`: Implemented `IndexRWLock` and staging cleanup.
   - `app/ingestion/file_filter.py`: Extended extension allowlist and `EXACT_FILENAMES`.
   - `app/parsing/code_parser.py`: Multi-format parsing (`.json`, `.csv`, `.yaml`, `.txt`) and 20,000 char cap.
   - `app/parsing/relationship_graph.py`: Atomic graph generation and Tree-sitter JS/TS/Python support.
   - `app/retrieval/reranker.py`: Header injection (`File:`, `Symbol:`) and score normalization.
   - `app/services/qa_service.py`: Abstention checks and target repo ID validation.
   - `tests/unit/test_app_file_filter.py`: Unit tests for extended extension coverage.
   - `tests/unit/test_chat_service.py`: Unit tests for orchestrator integration.
   - `tests/unit/test_context_builder.py`: Context budgeting and metadata tests.
   - `tests/unit/test_incremental.py`: Concurrency and staging tests.
   - `tests/unit/test_qa_service.py`: QA abstention and isolation tests.
   - `tests/unit/test_reranker.py`: CrossEncoder scoring and normalization tests.
2. Untracked Files (23):
   - *Core Implementation:* `app/parsing/notebook_parser.py`, `app/retrieval/orchestrator.py`, `app/retrieval/repository_isolation.py`.
   - *Evaluation Framework & Datasets:* `evaluation/e2e/FINAL_RETRIEVAL_STABILIZATION_REPORT.md`, `evaluation/e2e/evaluate_pass2_calibration.py`, `evaluation/e2e/final_expansion/DATASET_SUMMARY.md`, `evaluation/e2e/final_expansion/REPOSITORY_ISOLATION_SPEC.md`, `evaluation/e2e/final_expansion/baseline_evaluation_results.json`, `evaluation/e2e/final_expansion/dataset_100_queries.jsonl`, `evaluation/e2e/final_expansion/final_stabilization_results.json`, `evaluation/e2e/final_expansion/run_stabilization_evaluation.py`, `evaluation/e2e/retrieval_flow_audit/CANDIDATE_COUNT_OPTIMIZATION_REPORT.md`.
   - *Unit Test Suites:* `tests/unit/test_cache_consistency.py`, `tests/unit/test_ingestion_formats.py`, `tests/unit/test_notebook_ingestion.py`, `tests/unit/test_notebook_parser.py`, `tests/unit/test_notebook_relationship_graph.py`, `tests/unit/test_relationship_graph_atomic.py`, `tests/unit/test_repository_isolation.py`, `tests/unit/test_retrieval_orchestrator.py`, `tests/unit/test_staged_index_promotion.py`.
   - *Diagnostic Scratch Files:* `check_0_1_hypotheses.py`, `evaluation/e2e/baseline_0_1.json`.

---

### A2. Comprehensive Branch Inventory & Ahead/Behind Matrix
The repository contains 17 local branches and 12 remote branches.

#### Branch Audit Summary vs. `main` (`dc14a67`)
| Branch Name | Tracking Upstream | Merge Base with `main` | Ahead / Behind `main` | Merged into `main`? | Unique Commits |
| :--- | :--- | :--- | :---: | :---: | :---: |
| `main` | `origin/main` | `dc14a67` (HEAD) | 0 / 0 | Yes | 0 |
| `fix/review-service-truncation` | None | `497b63c` (Oct 30) | **4 / 2** | **No** | 4 |
| `fix/demo-readiness` | None | `497b63c` (Oct 30) | **2 / 2** | **No** | 2 |
| `feature_enhancements_v2` | None | `c31828f` (Aug 3) | **1 / 124** | **No** | 1 |
| `fastapi_layers_improvements_and_frontend` | `origin/fastapi...` | `eb82f1b` (Jul 12) | **1 / 148** | **No** | 1 |
| `sj-feature-mods2` | `origin/sj-feature-mods2` | `8390979` (Aug 22) | **1 / 91** | **No** | 1 |
| `chat_context_improve` | `origin/chat_context_improve` | Merged ancestor | 0 / 127 | Yes | 0 |
| `create-llm-api` | `origin/create-llm-api` | Merged ancestor | 0 / 118 | Yes | 0 |
| `feature/rag2-integration` | None | Merged ancestor | 0 / 3 | Yes | 0 |
| `feature_enhancements` | `origin/feature_enhancements` | Merged ancestor | 0 / 133 | Yes | 0 |
| `fix/post-merge-audit` | None | Merged ancestor | 0 / 2 | Yes | 0 |
| `sj-feature-mods` | `origin/sj-feature-mods` | Merged ancestor | 0 / 146 | Yes | 0 |
| `sj-improve-rag` | `origin/sj-improve-rag` | Merged ancestor | 0 / 31 | Yes | 0 |
| `sj-improve-rag2` | `origin/sj-improve-rag2` | Merged ancestor | 0 / 20 | Yes | 0 |
| `stage2_feature` | `origin/stage2_feature` | Merged ancestor | 0 / 119 | Yes | 0 |
| `stage3_feature` | `origin/stage3_feature` | Merged ancestor | 0 / 59 | Yes | 0 |
| `stage4_feature` | `origin/stage4_feature` | Merged ancestor | 0 / 16 | Yes | 0 |

#### Pairwise Ahead/Behind Matrix (Active Unmerged Branches)
Values in cell `[Row vs Column]` represent `Commits unique to Row / Commits unique to Column`:

| Branch | `main` | `fix/review-trunc` | `fix/demo-readiness` | `feat_enh_v2` | `fastapi_layers` | `sj-feat-mods2` |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| `main` | 0 / 0 | 2 / 4 | 2 / 2 | 124 / 1 | 148 / 1 | 91 / 1 |
| `fix/review-service-truncation` | 4 / 2 | 0 / 0 | 2 / 0 | 128 / 1 | 152 / 1 | 95 / 1 |
| `fix/demo-readiness` | 2 / 2 | 0 / 2 | 0 / 0 | 126 / 1 | 150 / 1 | 93 / 1 |
| `feature_enhancements_v2` | 1 / 124 | 1 / 128 | 1 / 126 | 0 / 0 | 26 / 2 | 1 / 34 |
| `fastapi_layers_improvements` | 1 / 148 | 1 / 152 | 1 / 150 | 2 / 26 | 0 / 0 | 1 / 58 |
| `sj-feature-mods2` | 1 / 91 | 1 / 95 | 1 / 93 | 34 / 1 | 58 / 1 | 0 / 0 |

---

### A3. Inferred Branch Purpose and Functional Area Analysis
1. `fix/review-service-truncation`:
   - *Inferred Purpose:* Stabilization of authentication, magic link session recovery, deterministic provider budgeting for AI reviews, and integration point for RAG stabilization.
   - *Functional Areas Touched:* `api/auth`, `api/reviews`, `frontend/auth`, `retrieval` (via working tree).
   - *Top Commits:*
     - `cbe8e54`: `fix(auth): support implicit hash token session recovery for magic links`
     - `a4d8e53`: `feat(review): enforce deterministic provider isolation and provider-aware review budgeting`
     - `031f85c`: `docs: add final B1-B9 verification report`
     - `6f6e4a2`: `chore: checkpoint demo readiness fixes and regression tests`
2. `fix/demo-readiness`:
   - *Inferred Purpose:* Checkpoint branch for demo hardening and B1–B9 manual QA verification. Direct ancestor of `fix/review-service-truncation`.
3. `feature_enhancements_v2`:
   - *Inferred Purpose:* Early development of repository intelligence service and API routers. Completely superseded by migrations and services merged into `main`.
4. `fastapi_layers_improvements_and_frontend`:
   - *Inferred Purpose:* Initial setup of Next.js frontend structure and repository evaluation UI. Superseded by `main`.
5. `sj-feature-mods2`:
   - *Inferred Purpose:* Standardizing LlamaIndex configuration and SSE parsing. Superseded by RAG2 merge in `main`.

---

### A4. Main Branch History, CI Status, and Deficits
- **Last 5 Commits on `main`:**
  - `dc14a67`: `refactor: improve multi-user cache isolation and session management` (Oct 31)
  - `845a0e5`: `feat: implement robust LLM circuit breaker and fallback mechanisms with caching` (Oct 31)
  - `497b63c`: `merge: incorporate RAG2 integration (incremental indexing, AST graph, git history...)` (Oct 30)
  - `3e65306`: `feat: add robust git history ingestion and commit-level semantic search` (Oct 30)
  - `c0ae651`: `refactor: finalize modular indexing architecture with atomic stage promotion` (Oct 30)
- **CI Status & Configuration:** There are **NO GitHub Actions workflows or CI pipelines configured** in `.github/workflows/` for backend testing, linting, or container builds. Only template files exist in `.github/`.
- **What `main` lacks:**
  - The 4-tier `SharedRetrievalOrchestrator` (it still uses legacy direct retrieval).
  - CrossEncoder header injection (`File:`, `Symbol:`).
  - Notebook ingestion (`notebook_parser.py`).
  - Strict repository isolation module.
  - Multi-format file parsing (`.json`, `.csv`, `.yaml`).
  - Auth magic-link implicit session recovery (`cbe8e54`).
  - Provider review budgeting (`a4d8e53`).

---

### A5. Predictive Merge-Tree Conflict Analysis & Hotspots
Running `git merge-tree --write-tree main fix/review-service-truncation` reveals **9 direct merge conflicts**:
1. `app/config.py` (conflicting fallback thresholds and provider configurations)
2. `app/llm/llm_client.py` (caching and model initialization differences)
3. `app/retrieval/query_router.py` (routing rules and mock handling)
4. `app/services/llm_fallback.py` (circuit breaker implementation vs. review fallback)
5. `app/services/model_manager.py` (model spec mappings)
6. `frontend/components/landing/LandingAuthActions.tsx` (auth session hooks)
7. `tests/integration/test_llm_fallback.py`
8. `tests/unit/test_app_config.py`
9. `tests/unit/test_model_manager.py`

#### Hotspot Files (Touched by 3+ Active Branches)
- `app/config.py` (touched by 5 branches)
- `app/services/model_manager.py` (touched by 4 branches)
- `api/services/chat_service.py` (touched by 4 branches)

---

### A6. Capability Presence Matrix Across Branches
*(Refer to Section 3 of the [Technical Appendix](./DEPLOYMENT_READINESS_AUDIT_APPENDIX.md#3-branch-feature-presence-matrix) for the complete tabular matrix).*

**Key Takeaway:** The entire modern retrieval stabilization implementation (orchestrator, isolation, notebook parser, evaluation harness) exists **ONLY in the uncommitted working tree of `fix/review-service-truncation`** (restored from `stash@{1}` and `stash@{0}`). It has not been committed to any Git branch.

---

### A7. Staff Engineering Recommendation & Branch Cleanup Strategy
- **Opinionated Strategic Recommendation:**
  1. **Primary Base:** Use `fix/review-service-truncation` as the stabilization working branch. It already contains the magic link fixes, review service budgeting, and the restored retrieval stabilization codebase.
  2. **Do Not Rebase on Main Yet:** Rebase will trigger 9 messy merge conflicts across `config.py` and `llm_fallback.py`. Instead, complete the security, isolation, and truncation fixes directly on `fix/review-service-truncation`, verify all tests pass, and then perform a deliberate three-way merge with `main`.
  3. **Immediate Branch Cleanup:** Safely delete the following 11 fully-merged local branches to eliminate workspace clutter:
     `git branch -d chat_context_improve create-llm-api feature/rag2-integration feature_enhancements fix/post-merge-audit sj-feature-mods sj-improve-rag sj-improve-rag2 stage2_feature stage3_feature stage4_feature`
  4. **Abandon / Archive:** Abandon stale branches `feature_enhancements_v2`, `fastapi_layers_improvements_and_frontend`, and `sj-feature-mods2` (all code is superseded).

---

### A8. Repository Hygiene, Secrets Exposure, Blobs, and Storage
- **.gitignore Coverage:** `.gitignore` properly covers `venv/`, `__pycache__/`, `.env`, `data/repos/`, `data/index/`, `node_modules/`, and `.next/`.
- **Committed Secrets:** Audit confirmed **ZERO committed secrets or `.env` files in git history**. Past commit `0ab2154` added only `.env.example` templates.
- **Large Blobs (>5 MB):** Exactly **0** blobs over 5 MB in git history.
- **Tracked Data:** `data/` contains only 6 small legacy evaluation JSON files (~120 KB total).
- **Physical Repository Size:** Disk footprint is **3.9 GB** (dominated by `data/repos/`, `data/index/`, and `frontend/node_modules/`), but the core `.git` directory is very compact at **17 MB**.

---

## Section B — Structure and Environment

### B1. Physical Directory Tree, LOC Metrics, Entry Points, and Run Commands
- **Physical Structure:**
  - `api/`: FastAPI routers, business services, authentication dependencies, and SQL migrations (~12,500 LOC Python).
  - `app/`: Retrieval engine, indexing pipeline, code parsers, AST relationship graph, LLM client, and prompt templates (~9,800 LOC Python).
  - `frontend/`: Next.js 16 app router, React components, Lucide icons, Tailwind styling (~14,200 LOC TypeScript/TSX).
  - `tests/`: 82 test suites covering unit and integration scenarios (~11,600 LOC Python).
  - `evaluation/`: End-to-end evaluation harness, calibration datasets, and audit reports (~3,500 LOC Python/JSON).
  - `data/`: Local storage for indexed vector stores (`data/index/`) and cloned source repositories (`data/repos/`).
- **Entry Points & Execution Commands:**
  - **Backend API:** `uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload`
  - **Frontend Client:** `cd frontend && npm run dev` (starts on port 3000)

---

### B2. Runtime Versions and Dependency Pinning Status
- **Python Runtime:** Python `3.10.20` (Miniforge).
- **Node Runtime:** Node `v22.17.0`, npm `10.9.2`.
- **Dependency Pinning Audit:**
  - `requirements.txt`: Partially pinned (core frameworks unpinned or using `>=`).
  - Key Installed Versions:
    - `llama-index-core`: `0.12.52`
    - `sentence-transformers`: `5.4.1`
    - `torch`: `2.8.0`
    - `transformers`: `4.56.2`
    - `chromadb`: `0.6.3`
    - `fastapi`: `0.115.6`
    - `uvicorn`: `0.34.0`
    - `supabase`: `2.13.0`
    - `gitpython`: `3.1.44`
    - `tree-sitter`: `0.23.2`
    - `pydantic`: `2.10.6`
    - `bm25s`: `0.2.14`
    - `rank-bm25`: `0.2.2`
  - Frontend (`frontend/package.json`): Next.js `16.2.10`, React `19.0.0`, Vitest `2.1.9`.

---

### B3. Environment Variable Specification and .env Audit
*(Refer to Section 2 of the [Technical Appendix](./DEPLOYMENT_READINESS_AUDIT_APPENDIX.md#2-complete-environment-variable-catalog) for the complete 42-variable catalog).*

- **Strictly Required Variables:**
  - `SUPABASE_URL`: Required by `api/dependencies.py:47`.
  - `SUPABASE_SERVICE_KEY`: Required by `api/dependencies.py:48` (Service Role secret).
- **Critical Secrets (Must be Redacted):**
  - `SUPABASE_SERVICE_KEY`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, `GROQ_API_KEY`, `GITHUB_TOKEN`, `GIT_AUTH_TOKEN`.
- **Discrepancy with `.env.example`:**
  - `.env.example` documents 21 variables.
  - Runtime code queries **42 distinct variables**!
  - Missing from `.env.example`: `CITATION_VALIDATION_MODE`, `FAST_LLM_PROVIDER`, `AUTH_RATE_LIMIT_PER_MINUTE`, `GUEST_READ_ONLY_MODE`, `DENSE_TOP_K`, `BM25_TOP_K`, `RRF_OUTPUT_CUTOFF`, `CROSS_ENCODER_DEPTH`, `TOP_K_RERANK`.

---

## Section C — Verification of Specific Technical Findings (F1 to F23)

### F1. CrossEncoder Double-Sigmoid Normalization Bug
- **Status:** **CONFIRMED (P1)**
- **Evidence:** `app/retrieval/reranker.py:178`: `sig_score = 1 / (1 + math.exp(-float(score)))`
- **Measurement:** In `sentence-transformers==5.4.1`, `CrossEncoder.predict()` already applies a sigmoid activation by default.
  - Sample pair default output: `[0.533078, 0.000037, 0.000407]`
  - Raw logits (`Identity` activation): `[0.132504, -10.196754, -7.805361]`
  - Score after `reranker.py` sigmoid: `[0.630201, 0.500009, 0.500102]`
- **Impact:** Irrelevant documents with raw logit `-10.2` receive an inflated score of `0.500009`. The entire dynamic range of non-relevant candidates is squashed into `[0.50, 0.73]`.

---

### F2. Stored Chunk Metadata Omission
- **Status:** **CONFIRMED (P1)**
- **Evidence:** Programmatic sampling of 200 code chunks across all 11 Chroma collections under `data/index/`.
- **Findings:**
  - In 10 out of 11 collections (`Codebase-Copilot`, `Emotion-detection`, `FedSegX`, `InstagramCarouselSplitter`, `MediscanAI`, `NeuroVera`, `SenseVoice`, etc.):
    - `line_start`: **0.0%**
    - `line_end`: **0.0%**
    - `symbol_name` / `function_name` / `class_name`: **0.0%**
    - `format`: **0.0%**
  - Only `Sound2Sign` (indexed recently) has `format` populated (96.1%), but its `line_start` and `symbol_name` remain 0.0%.
  - Only `Speech-Emotion-Analyzer` notebook chunks (`.ipynb` cells parsed by `notebook_parser.py`) carry `line_start` and `line_end`. Regular code files have zero line or symbol metadata.

---

### F3. Severe Source Code Truncation at Ingestion
- **Status:** **CONFIRMED (P0 — Critical Data Loss)**
- **Evidence:** `app/parsing/code_parser.py:176`: `content = content[:20000]`
- **Audit Results Across `data/repos/`:**
  - Total files exceeding 20,000 characters: **2,135 files**.
  - Total characters discarded: **188,173,071 characters**.
  - Tail retrievability check: For **2,121 out of 2,135 files (99.3%)**, the last non-empty line of the source file is **completely absent from all indexed Chroma chunks**!
  - Affected examples: `SenseVoice/model.py` (35,252 chars, tail lost), `SenseVoice/runtime/llama.cpp/sensevoice-server/sensevoice-server.cpp` (54,989 chars, tail lost), `Sound2Sign` (2,052 files truncated).

---

### F4. Index Staleness and Manifest Desynchronization
- **Status:** **CONFIRMED (P1)**
- **Evidence:** Comparing Chroma collection directory mtimes with git log timestamps of `app/ingestion/file_filter.py` and `app/parsing/code_parser.py`:
  - `Codebase-Copilot`, `Emotion-detection`, `FedSegX`, `MediscanAI`, `NeuroVera`, `SenseVoice` were indexed on or before Oct 31, 2026.
  - New format parsers for `.json`, `.yaml`, `.csv`, `Dockerfile`, and `LICENSE` were added subsequently.
  - Sampling confirms that existing indexes contain **0% chunks from `.json`, `.yaml`, `.csv`, or `Dockerfile`**.
  - All 10 existing repository indexes need a complete rebuild to ingest supported file formats.

---

### F5. Prompt-to-Context Line Number Mismatch and Citation Validation
- **Status:** **CONFIRMED (P1)**
- **Evidence:**
  - `SharedRetrievalOrchestrator._build_context_string` (`orchestrator.py:345`) and `chat_service._build_context_str` (`chat_service.py:251`) format context strictly as `[{path}]
{content}`. They do **not include line numbers**.
  - System prompts (`app/llm/prompts.py`) instruct: `"Always reference the file name and function/class name when relevant."` Prompts never request line numbers.
  - However, `app/services/qa_service.py:58` defines `_CITATION_REGEX` expecting `path:line_start-line_end`.
  - In `qa_service.py:661`, `CITATION_VALIDATION_MODE == "strict"` (the default) triggers up to **2 complete LLM retries** if an invalid citation is detected, tripling latency and token spend.
  - `api/services/chat_service.py` (streaming) does not enforce citation validation at all.

---

### F6. Duplicate Retrieval Logic and Dead Code Paths in Chat Service
- **Status:** **CONFIRMED (P2)**
- **Evidence:**
  - `_retrieve_ranked_nodes` (`chat_service.py:552`), `_build_retriever` (`chat_service.py:177`), and `_inject_arch_context_if_missing` (`chat_service.py:679`) are completely dead code (zero active call sites in the repository).
  - Dead code block: Lines 1–216 of `api/services/indexing_service.py` are commented out with `# `.
  - Stale docstrings: `chat_service.py` module docstring still claims streaming does not use the retrieval orchestrator (whereas `_prepare_stream_prompt` now calls `orchestrator.orchestrate`).

---

### F7. Hardcoded Score Thresholds and Calibration Assumptions
- **Status:** **CONFIRMED (P1)**
- **Evidence:**
  - `app/retrieval/orchestrator.py:80`: Hardcodes `DEFAULT_THRESHOLDS = {TIER1_ARCHITECTURE: 0.54, TIER2_DOCUMENTATION: 0.53, TIER3_HYBRID_CODE: 0.53, "rrf_floor": 0.015}`.
  - `api/services/chat_service.py:174`: `_should_force_no_match` hardcodes `top_score < 0.60`.
  - `app/retrieval/orchestrator.py:177, 190`: `_load_architecture_context_nodes` assigns a constant score of `0.75` to all architecture nodes. Thus, architectural queries loading architecture context pass Tier 1 with constant confidence `0.75`.
  - 186 occurrences of hardcoded threshold comparisons were identified across `app/`, `api/`, and `tests/`.

---

### F8. Multi-Tenant Repository and Index Name Collisions
- **Status:** **CONFIRMED (P0 — Critical Multi-Tenancy Defect)**
- **Evidence:**
  - `derive_repo_name` (`app/ingestion/repo_naming.py:49`): `candidate = (parsed.path or "").rstrip("/").split("/")[-1]`. Takes only the last segment of the URL or path.
  - `load_repository` (`app/ingestion/repo_loader.py:467`): `_remove_existing_repo_dir(candidate_target)` deletes the existing directory before promoting the new clone!
  - `indexing_service.py:627`: `index_name = os.path.basename(os.path.normpath(repo_path))`.
- **Failure Scenario:** If User A indexes `https://github.com/alice/project` and User B indexes `https://github.com/bob/project`, both map to folder `data/repos/project` and collection `project`. User B's ingestion deletes User A's source code from disk and overwrites User A's Chroma vector index.
- **SQL Verification for Production Owner:**
  ```sql
  SELECT index_name, count(*) FROM repositories GROUP BY 1 HAVING count(*) > 1;
  ```

---

### F9. Arbitrary Server Directory Ingestion and Scheme Bypass
- **Status:** **CONFIRMED (P0 — Critical Security Flaw)**
- **Evidence:** `app/ingestion/repo_loader.py:514-518`:
  ```python
  if not os.path.exists(source) or not os.path.isdir(source):
      raise ValueError(...)
  return source
  ```
- **Vulnerability:** `POST /api/repo/index` passes `body.source` directly to `load_repository` without path whitelisting or URL enforcement. An authenticated user can submit `source: "/etc"` or `source: "/var"`. The backend indexes the server's private directories into Chroma and allows querying system configuration and credentials.

---

### F10. Global Server-Wide Git Authentication Token Exposure
- **Status:** **CONFIRMED (P0 — Security Exposure)**
- **Evidence:** `app/utils/git_auth.py:40`: `get_git_auth_token()` reads `GIT_AUTH_TOKEN`, `GITHUB_TOKEN`, or `.env`.
- **Vulnerability:** In `app/ingestion/repo_loader.py:262`, `_build_authenticated_url` automatically injects this token into any GitHub HTTPS URL. Any authenticated user can supply a private repository URL belonging to the server owner's organization; the server authenticates using its own global token, cloning and indexing confidential repositories for unauthorized users. Per-user tokens (PATs or OAuth provider tokens) are not supported.

---

### F11. Ingestion Clone Hardening and SSRF Vulnerabilities
- **Status:** **CONFIRMED (P0 — Security & Resource Denial)**
- **Evidence:** `app/ingestion/repo_loader.py:320-355`:
  - `git clone` executes without `--depth` (performs full, unbounded git history clone).
  - No timeout configured on `subprocess.run` or `git.Repo.clone_from`.
  - No repository size or file count limits.
  - No protocol allowlist (accepts `file://`, `ssh://`, `git://`).
  - `core.symlinks=false` is NOT set.
  - No hook disabling (`-c core.hooksPath=/dev/null` is omitted).
  - No host allowlist or private IP blocking: users can submit `http://169.254.169.254/` (cloud metadata service) or internal subnets, causing SSRF.

---

### F12. Symlink Host File Read Vulnerability
- **Status:** **CONFIRMED (P0 — Arbitrary File Read)**
- **Evidence:** Verified empirically via `/tmp` test harness. `app/ingestion/file_filter.py:69` checks `os.path.islink(full_path)` but only skips broken symlinks or directory symlinks. It does **not** check if `os.path.realpath(full_path)` is contained within `repo_path`.
- **Impact:** A repository containing a symlink pointing to `/etc/passwd` or `~/.ssh/id_rsa` is accepted by `filter_files`, read by `load_documents`, chunked by `code_parser`, and stored in Chroma. Any user can extract server host files by querying the assistant.

---

### F13. Repository Isolation Module Implementation and Stamping Flaws
- **Status:** **CONFIRMED (P0 — Isolation Defect)**
- **Evidence:** `app/retrieval/repository_isolation.py:26-46, 68, 160`:
  - `STATIC_REPO_ID_MAP` contains 8 hardcoded developer UUIDs.
  - `resolve_repository_id` runs `sb.table("repositories").select("id, name, index_name").execute()` across all users and populates `_dynamic_cache` keyed by name. If two users have repositories with the same name, they collide in cache. Cache lacks invalidation and negative caching.
  - Chunks in Chroma are **never stamped with `repository_id` at ingestion**.
  - In `enforce_chunk_isolation`, `require_existing_metadata` defaults to `False`. When chunks lack `repository_id`, the function blindly stamps `target_repo_id` onto the retrieved chunk (`n.node.metadata["repository_id"] = target_repo_id`), providing zero isolation.

---

### F14. Complete API Route Authorization and Ownership Coverage
- **Status:** **CONFIRMED (P1)**
- **Evidence:** Full automated inspection of 83 FastAPI routes.
  - 74 routes require `get_current_user`.
  - 4 routes use `get_optional_user` (`/api/auth/register/preflight`, `/api/auth/login/preflight`, etc.).
  - 5 routes are unauthenticated (`/docs`, `/redoc`, `/openapi.json`, `/api/health`).
  - `ensure_repo_access` is called consistently on repo-scoped routes.
  - Missing: Resource spending limits (no user quotas on LLM generation, embedding, or cloning).

---

### F15. Supabase Schema, RLS Policies, and Service Role Usage
- **Status:** **CONFIRMED (P1)**
- **Evidence:** Audit of `api/migrations/*.sql`:
  - Migrations start in August 2026. The baseline DDL for core tables (`repositories`, `chats`, `messages`) is **completely missing from the repository migrations**!
  - `api/dependencies.py:44-54` uses the Supabase `SERVICE_ROLE_KEY` globally for all backend database operations, bypassing RLS at the database engine level.

---

### F16. Per-Request Supabase Auth Overhead and Missing Quotas
- **Status:** **CONFIRMED (P1)**
- **Evidence:**
  - `api/dependencies.py:84`: Calls `supabase.auth.get_user(token)` via HTTPS on **every single incoming API request**. There is zero token caching or local JWT verification, adding 50–150ms latency to every call.
  - `GUEST_READ_ONLY_MODE`: Defaults to `False` (`app/config.py:118`).
  - Rate limiting (`AUTH_RATE_LIMIT_PER_MINUTE`) is applied only to 4 auth preflight routes. No rate limiting or token budgets exist for `/api/chat/stream`, `/api/repo/index`, or `/api/reviews/run`.

---

### F17. Single-Threaded Stream Executor Bottleneck and Thread Safety
- **Status:** **CONFIRMED (P0 — Concurrency Blocker)**
- **Evidence:** `app/services/llm_fallback.py:23`: `_STREAM_BRIDGE_EXECUTOR = ThreadPoolExecutor(max_workers=1)`.
- **Impact:** All sync-stream-to-async bridge iterations execute on this single thread. Concurrent streaming requests serialize globally.
- **Thread Safety:** `_load_cross_encoder()` in `app/retrieval/reranker.py:68` lacks a mutex lock; concurrent queries at cold start race on model initialization.
- **Async Event Loop Blocking:** `orchestrator.orchestrate()` and `CrossEncoder.predict()` run synchronously without `run_in_executor`, blocking the asyncio event loop during the 1–3s inference window.

---

### F18. Ephemeral BM25 Index Rebuilds and Chroma Client Proliferation
- **Status:** **CONFIRMED (P1)**
- **Evidence:** `app/services/qa_service.py:340`: BM25 indexes are rebuilt from disk on backend startup upon the first query to each repository.
- **Client Proliferation:** `orchestrator.py:165` instantiates a new `chromadb.PersistentClient(path=chroma_path)` on every query to fetch architecture nodes.

---

### F19. Query Router Substring Collision and Test-Mock Contamination
- **Status:** **CONFIRMED (P1)**
- **Evidence:** Tested with LLM stubbed to fail (rule-based evaluation):
  - `"Where is the security middleware defined?"` -> Incorrectly classified as `ARCHITECTURAL` because `"security"` is a strong architectural phrase.
  - `"What use is this repo?"` -> Classified as `RELATIONSHIP` (extracted target `'repo'`).
  - `"Who uses the config loader?"` -> Extracted target `'loader'` (last-word fallback bug).
  - Production code contains test-mock detection: `app/retrieval/query_router.py:174-179`:
    ```python
    if hasattr(Settings, "_mock_name") or hasattr(Settings, "mock_calls"):
        return getattr(Settings, "llm", None)
    if "Mock" in type(Settings.llm).__name__:
        return Settings.llm
    ```

---

### F20. Relationship Query Graph Isolation and Zero-Match Behavior
- **Status:** **CONFIRMED (P1)**
- **Evidence:** `app/retrieval/orchestrator.py:440-462`:
  - When zero references are found in `relationship_graph.json`, confidence score is set to `0.50`, but `should_abstain` remains `False`.
  - Prompts are formatted with `"No references found."` and handed to the LLM.
  - `relationship_graph.py` only parses Python (`.py`, `.ipynb`) and JavaScript/TypeScript (`.js`, `.ts`). C++, Go, Java, and Rust are unsupported.

---

### F21. Prompt Injection Vulnerability and Refusal String Dependencies
- **Status:** **CONFIRMED (P1)**
- **Evidence:**
  - Context is inserted directly into prompts without XML tags or adversarial escaping.
  - `_is_no_match_code_lookup_response` (`chat_service.py:139`) and unit tests rely on the exact refusal string: `"I couldn't find that in the retrieved code. Try rephrasing or asking about a specific file or function."`

---

### F22. Hard Ollama Embeddings Lock-In and Cloud Unviability
- **Status:** **CONFIRMED (P0 — Cloud Deployment Blocker)**
- **Evidence:** `app/llm/llm_client.py:63`: `get_embed_model()` unconditionally instantiates `OllamaEmbedding(model_name="nomic-embed-text")`. Hosted cloud embeddings (OpenAI, Voyage, Bedrock) are not implemented. Changing models throws Chroma dimension mismatch exceptions.

---

### F23. Silent Exception Swallowing and Unlogged Fallback Cascades
- **Status:** **CONFIRMED (P1)**
- **Evidence:** Automated scan identified **106 swallowed exception blocks**, 57 of which are completely unlogged (e.g. `api/routers/chat.py:134`, `api/services/chat_service.py:268`).

---

## Section D — Evaluation Suite and Test Harness Audit

### D1. Evaluation Dataset Composition and Leakage Analysis
- **Dataset Inspected:** `evaluation/e2e/final_expansion/dataset_100_queries.jsonl` (100 queries across `FedSegX`, `Sound2Sign`, `Emotion-detection`, `NeuroVera`).
- **Target File Naming:** **43.0% of queries explicitly name the target file or symbol** (e.g. `CamouflageSegNet`, `train.py`).
- **Substring Match Flaw:** In `run_stabilization_evaluation.py:147`, hits are evaluated with:
  ```python
  is_node_hit = bool(p and any(ef in p or p in ef for ef in expected_files))
  ```
  This loose bidirectional substring match creates false positives (e.g. `utils.py` matches `tests/test_utils.py`).

---

### D2. Evaluation Reports Provenance and Metric Discrepancies
- Reports in `evaluation/e2e/` report varying metrics:
  - `FINAL_RETRIEVAL_STABILIZATION_REPORT.md`: Hit@1=0.88, Hit@3=0.98, Hit@5=1.00, MRR=0.926, FAR=0.00, FRR=0.00.
  - Previous pass reports recorded Hit@1=0.825 and FRR=0.05.
- These numbers were produced against local Chroma snapshots before the format parsers and isolation fixes were added.

---

### D3. Evaluation Suite Reproducibility Assessment
- **Status:** Reproducible read-only using `evaluation/e2e/final_expansion/run_stabilization_evaluation.py`.
- **Constraint:** Requires local Ollama running `nomic-embed-text` and local Chroma collections populated in `data/index/`.

---

### D4. Complete Test Inventory and Execution Verification
- **Total Backend Tests Collected:** **849 tests across 82 test files**.
- **Backend Test Run Result:** **849 passed, 0 failed, 14 warnings in 63.33s**.
- **Frontend Vitest Test Run Result:** **35 passed across 4 files in 527ms**.
- **Reconciliation with README:** README was authored at milestone 238 tests. The suite has legitimately grown to **884 total automated tests**.

---

## Section E — Runtime Operations and Deployment Infrastructure

### E1. Containerization, Orchestration, Healthchecks, and Observability
- **Dockerfiles:** Missing root production Dockerfile for backend. Frontend lacks a standalone Dockerfile.
- **Docker Compose:** Missing unified `docker-compose.yml`.
- **Health Endpoint:** `GET /api/health` exists and verifies Supabase connectivity.
- **Metrics & Tracing:** No Prometheus metrics, OpenTelemetry tracing, or Sentry error tracking integrated.

---

### E2. Persistent Storage Layout, Caching, and Backup Strategy
- **Persistent State:** `data/index/` (Chroma vector databases, `manifest.json`, `relationship_graph.json`, `git_history.json`) and `data/repos/` (cloned git repositories).
- **Stateless Cloud Impact:** In serverless or containerized environments without persistent volume mounts, restarting the container erases all indexes.

---

### E3. Empirical Latency, Memory RSS, and Prompt Token Profiling
*(Empirically measured on Apple Silicon M4 / 16 GB)*
- **Backend Cold-Start Import:** `1.07s`, RSS `146.9 MB`.
- **CrossEncoder Model Loading:** `7.87s`, RSS increases to `999.6 MB`.
- **SenseVoice Index Load + BM25 Build:** `0.69s`, RSS `635.2 MB`.
- **Query Latency Profile (30 Queries Benchmarked):**
  - **Code Lookup Mode:** Average **1,666 ms** (Prompt: ~676 words).
  - **Architectural Mode:** Average **1,038 ms** (Prompt: ~224 words).
  - **Relationship Mode:** Average **0.4 ms** (Prompt: ~140 words).

---

### E4. External SaaS Dependencies, Quotas, and Failure Modes
- **Configured LLM Providers:** Gemini (`gemini-2.5-flash`), Groq (`llama-3.3-70b-versatile`), OpenAILike.
- **Failover Chain:** Implemented in `app/services/llm_fallback.py` with circuit breakers.

---

### E5. Frontend Production Readiness, Turbopack Build, and UX State
- **Build Verification:** `npm run build` completed successfully in **3.6s** (Next.js 16.2.10, Turbopack).
- **Lint Verification:** `npm run lint` reported **0 errors, 7 warnings**.
- **Citations Rendering:** Frontend renders file paths, but citations lack click-to-line navigation because backend does not provide `line_start`/`line_end`.

---

## Section F — Product Surface and Contract Realism

### F-1. Feature Surface Inventory and MVP Disposition Matrix
| Feature / Route | Functional Status | Tests? | Uses LLM? | MVP Disposition |
| :--- | :---: | :---: | :---: | :---: |
| **Repository Chat (Streaming)** | Working | Yes | Yes | **Keep (Core MVP)** |
| **Directory Explorer** | Working | Yes | No | **Keep (Core MVP)** |
| **Health Scoring & Trend** | Working | Yes | No | **Keep (Differentiating)** |
| **Branch Workspace Comparison**| Working | Yes | No | **Feature Flag** |
| **AI Code Review** | Working | Yes | Yes | **Keep (Core MVP)** |
| **Fix Generation Proposal** | Partial | Partial | Yes | **Feature Flag** |
| **12 Intelligence Actions** | Partial | Yes | Yes | **Keep High-Value Only** |
| **Export Service (PDF/MD/JSON)**| Working | Yes | No | **Keep** |
| **Evaluation Center Dashboard**| Stub / Internal| Yes | No | **Hide Behind Admin Flag**|

---

### F-2. README / Marketing Claims vs. Runtime Reality
- **Claim:** "238 passing tests" -> **Reality:** 849 backend + 35 frontend tests.
- **Claim:** "Enterprise multi-tenant RAG" -> **Reality:** Serious repository name collisions and shared tokens.
- **Claim:** "Exact line-level citations" -> **Reality:** Line numbers are not extracted or sent to frontend.

---

## Section G — Technical Debt and Maintainability

### G1. Codebase Smells, Giant Modules, and Circular Imports
- **Files Exceeding 800 Lines:**
  - `api/services/supabase_service.py`: 1,927 lines
  - `api/services/repository_health_engine.py`: 1,577 lines
  - `app/indexing/incremental.py`: 1,324 lines
  - `api/services/chat_service.py`: 1,183 lines
  - `api/services/indexing_service.py`: 1,034 lines
  - `api/services/repository_explorer_service.py`: 969 lines
  - `app/services/qa_service.py`: 892 lines
- **Circular Import Mitigations:** Frequent localized imports inside function bodies (e.g. `from app.services.qa_service import _get_indexes` inside `chat_service.py`).

---

### G2. Log Sanitization, PII Redaction, and Query Leakage
- `app/utils/logger.py` and local helpers (`_redact_sensitive_text_for_log`, `_query_fingerprint_for_log`) are widely used. Query text is hashed or truncated in production logs.

---

## Section H — Data Store State & Alignment Audit

### H1. Local Index vs. Repository Directory Cross-Reconciliation
| Directory / Repository Name | Local Repo Path (`data/repos/`) | Chroma Index (`data/index/`) | Chunks | Agreement Status |
| :--- | :---: | :---: | :---: | :--- |
| **Codebase-Copilot** | Present | Present | 1,418 | In Sync |
| **Emotion-detection** | Present | Present | 14 | In Sync |
| **FedSegX** | Present | Present | 175 | In Sync |
| **InstagramCarouselSplitter**| Present | Present | 6 | In Sync |
| **MediscanAI** | Present | Present | 601 | In Sync |
| **NeuroVera** | Present | Present | 339 | In Sync |
| **SenseVoice** | Present | Present | 419 | In Sync |
| **Sound2Sign** | Present | Present | 99 | In Sync |
| **Speech-Emotion-Analyzer** | Present | Present | 86 | In Sync |
| **YoutubeTimestampExtension**| **Missing** | Present | 0 | **Orphan Index** |
| **idx_llm_concurrency_test** | **Missing** | Present | 0 | **Test Artifact (Delete)** |

---

## Section I — Synthesis & Actionable Implementation Roadmap

### Recommended Work Breakdown (PR-Sized Iterations)

```
PR 1: Git Consolidation & Baseline Commit
  │
  ├──> PR 2: Multi-Tenancy & Path Traversal Hardening (P0)
  │      │
  │      ├──> PR 3: Chunking & Truncation Remediation (P0)
  │      │      │
  │      │      ├──> PR 4: Concurrency & Stream Bridge Scaling (P0)
  │      │      │      │
  │      │      │      └──> PR 5: Cloud Embeddings Provider Integration (P0)
  │      │      │             │
  │      │      │             └──> PR 6: Scoring Calibration & BM25 Persistence (P1)
  │      │      │                    │
  │      │      │                    └──> PR 7: Containerization & Cloud Deployment (P1)
```

1. **PR 1: Git Consolidation & Baseline Commit (Branch `fix/review-service-truncation`)**
   - Stage and commit the 18 modified files and 21 essential untracked files. Exclude `check_0_1_hypotheses.py` and `baseline_0_1.json`.
   - Reconcile unit tests and ensure all 884 tests pass cleanly on commit.
2. **PR 2: Multi-Tenancy, Path Traversal & Symlink Hardening (P0)**
   - Reject local paths in `POST /api/repo/index`; enforce `https://` protocol allowlist.
   - Patch `filter_files` to verify `os.path.realpath(f).startswith(repo_path)`.
   - Namespace repositories and Chroma collections by `repo_id` (UUID), not `basename`.
   - Replace server-wide PAT injection with user-supplied PATs or OAuth tokens.
3. **PR 3: Chunking & Truncation Remediation (P0)**
   - Remove `content[:20000]` hard-truncation in `app/parsing/code_parser.py`.
   - Implement streaming window chunking for large code files.
   - Rebuild all repository indexes.
4. **PR 4: Concurrency & Stream Bridge Scaling (P0)**
   - Increase `_STREAM_BRIDGE_EXECUTOR` workers or transition to native async LLM streaming.
   - Wrap `orchestrate()` and `CrossEncoder.predict()` in `run_in_executor` to prevent event-loop starvation.
   - Add thread lock to `_load_cross_encoder()`.
5. **PR 5: Cloud Embeddings Provider Integration (P0)**
   - Abstract embeddings interface to support OpenAI (`text-embedding-3-small`) or hosted Voyage/Bedrock embeddings alongside Ollama.
   - Add collection embedding dimension verification.
6. **PR 6: Scoring Calibration & BM25 Serialization (P1)**
   - Remove redundant sigmoid from `app/retrieval/reranker.py`.
   - Recalibrate downstream routing thresholds.
   - Serialize BM25 indexes to disk (`bm25.json`) alongside Chroma.
7. **PR 7: Containerization & Production CI (P1)**
   - Create multi-stage production Dockerfiles for FastAPI backend and Next.js frontend.
   - Add GitHub Actions CI workflow running backend and frontend test suites.

---

### Open Questions for the System Owner
1. **Private Repository Ingestion in MVP:** Will MVP users be allowed to index private repositories? If so, must we implement GitHub OAuth App integration, or can users supply personal access tokens (PATs)?
2. **Local Path Ingestion:** Is local directory ingestion required for internal debugging, or can it be completely removed from production builds?
3. **Cloud Embedding Model Selection:** Which hosted embedding provider (OpenAI `text-embedding-3-small`, Voyage-code-3, Cohere) will be funded for production cloud deployment to replace local Ollama?
4. **Git History Depth:** Does production need full git commit histories (requiring full clones), or can we enforce `--depth 50` to conserve disk and bandwidth?

---

### Items That Could Not Be Determined (Unverified Inventory)
1. **Live Supabase Production Database Contents:** Direct SQL execution was unavailable due to lack of network credentials for live Supabase PostgreSQL. Duplicate `index_name` entries in production could not be queried directly (SQL script provided in Section C, F8).
2. **Long-Term Chroma Memory Leaks under Heavy Multi-User Load:** Testing was bounded to 30 sequential queries. Long-term memory fragmentation of SQLite-backed Chroma under sustained concurrent writes could not be measured.

---

*End of Deployment Readiness Audit Report. Refer to [DEPLOYMENT_READINESS_AUDIT_APPENDIX.md](./DEPLOYMENT_READINESS_AUDIT_APPENDIX.md) for full route mappings, environment variables, and verbatim code excerpts.*
