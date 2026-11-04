# Deployment Readiness Audit — Technical Appendix

**Document Version:** 1.0.0  
**Repository:** Codebase-Copilot  
**Reference Document:** [DEPLOYMENT_READINESS_AUDIT.md](./DEPLOYMENT_READINESS_AUDIT.md)  
**Execution Context:** Production Deployment Pre-Flight  

---

## Appendix Table of Contents
1. [Full API Route and Authorization Inventory](#1-full-api-route-and-authorization-inventory)
2. [Complete Environment Variable Catalog](#2-complete-environment-variable-catalog)
3. [Branch Feature Presence Matrix](#3-branch-feature-presence-matrix)
4. [Verbatim Code Excerpts](#4-verbatim-code-excerpts)
   - [Excerpt 4.1: SharedRetrievalOrchestrator Threshold and Tier Section](#excerpt-41-sharedretrievalorchestrator-threshold-and-tier-section)
   - [Excerpt 4.2: CrossEncoder Reranker Scoring Block](#excerpt-42-crossencoder-reranker-scoring-block)
   - [Excerpt 4.3: Code Parser Truncation Block](#excerpt-43-code-parser-truncation-block)
   - [Excerpt 4.4: load_repository Local and Remote Resolution](#excerpt-44-load_repository-local-and-remote-resolution)
   - [Excerpt 4.5: derive_repo_name Path Segment Extraction](#excerpt-45-derive_repo_name-path-segment-extraction)
   - [Excerpt 4.6: resolve_repository_id and enforce_chunk_isolation](#excerpt-46-resolve_repository_id-and-enforce_chunk_isolation)
   - [Excerpt 4.7: Stream Bridge Single-Threaded Executor](#excerpt-47-stream-bridge-single-threaded-executor)
   - [Excerpt 4.8: Query Router Production Test-Mock Inspection](#excerpt-48-query-router-production-test-mock-inspection)

---

## 1. Full API Route and Authorization Inventory

Every route exposed by the FastAPI backend (`api.main.app`), extracted programmatically via application introspection:

| Method | Path | Auth Dependency | Repository Access Check | LLM Spend | Embed Spend | Clone Spend |
| :--- | :--- | :--- | :--- | :---: | :---: | :---: |
| `GET` | `/openapi.json` | `none` | **None** | No | No | No |
| `GET` | `/docs` | `none` | **None** | No | No | No |
| `GET` | `/docs/oauth2-redirect` | `none` | **None** | No | No | No |
| `GET` | `/redoc` | `none` | **None** | No | No | No |
| `POST` | `/api/repo/index` | `get_current_user` | User-scoped (`user_id`) | Yes | No | Yes |
| `POST` | `/api/repo/{repo_id}/refresh` | `get_current_user` | User-scoped (`user_id`) | Yes | Yes | Yes |
| `GET` | `/api/repo/{repo_id}/index-progress` | `get_current_user` | User-scoped (`user_id`) | Yes | No | No |
| `GET` | `/api/repo/list` | `get_current_user` | User-scoped (`user_id`) | No | No | No |
| `GET` | `/api/repo/{repo_id}` | `get_current_user` | User-scoped (`user_id`) | No | No | No |
| `DELETE` | `/api/repo/{repo_id}` | `get_current_user` | User-scoped (`user_id`) | No | No | Yes |
| `GET` | `/api/repo/{repo_id}/branches` | `get_current_user` | Yes (`ensure_repo_access`) | No | No | No |
| `POST` | `/api/repo/{repo_id}/branches/refresh` | `get_current_user` | Yes (`ensure_repo_access`) | No | No | No |
| `GET` | `/api/repo/{repo_id}/branches/status` | `get_current_user` | Yes (`ensure_repo_access`) | No | No | No |
| `POST` | `/api/repo/{repo_id}/branches/pull` | `get_current_user` | Yes (`ensure_repo_access`) | No | No | No |
| `POST` | `/api/repo/{repo_id}/branches/checkout` | `get_current_user` | Yes (`ensure_repo_access`) | No | No | No |
| `POST` | `/api/repo/{repo_id}/branches/return-default` | `get_current_user` | Yes (`ensure_repo_access`) | No | No | No |
| `GET` | `/api/repo/{repo_id}/branches/compare` | `get_current_user` | Yes (`ensure_repo_access`) | No | No | No |
| `POST` | `/api/chat/session` | `get_current_user` | Yes (`ensure_repo_access`) | Yes | No | No |
| `POST` | `/api/chat/session/quick-ask` | `get_current_user` | Yes (`ensure_repo_access`) | No | No | No |
| `POST` | `/api/chat/session/main` | `get_current_user` | Yes (`ensure_repo_access`) | No | No | No |
| `POST` | `/api/chat/{chat_id}/message/stream` | `get_current_user` | Yes (`ensure_repo_access`) | Yes | No | No |
| `GET` | `/api/chat/sessions` | `get_current_user` | Yes (`ensure_repo_access`) | No | No | No |
| `GET` | `/api/chat/list` | `get_current_user` | Yes (`ensure_repo_access`) | No | No | No |
| `GET` | `/api/chat/search` | `get_current_user` | Yes (`ensure_repo_access`) | No | No | No |
| `GET` | `/api/chat/{chat_id}/messages` | `get_current_user` | User-scoped (`user_id`) | No | No | No |
| `POST` | `/api/chat/{chat_id}/messages` | `get_current_user` | User-scoped (`user_id`) | Yes | No | No |
| `PATCH` | `/api/chat/{chat_id}` | `get_current_user` | User-scoped (`user_id`) | No | No | No |
| `GET` | `/api/chat/{chat_id}/summary` | `get_current_user` | User-scoped (`user_id`) | No | No | No |
| `POST` | `/api/chat/{chat_id}/summary/regenerate` | `get_current_user` | User-scoped (`user_id`) | No | No | No |
| `GET` | `/api/chat/export` | `get_current_user` | Yes (`ensure_repo_access`) | No | No | No |
| `POST` | `/api/chat/{chat_id}/attachments` | `get_current_user` | User-scoped (`user_id`) | No | No | No |
| `GET` | `/api/chat/{chat_id}/attachments` | `get_current_user` | User-scoped (`user_id`) | No | No | No |
| `GET` | `/api/chat/attachments/{attachment_id}` | `get_current_user` | User-scoped (`user_id`) | No | No | No |
| `PATCH` | `/api/chat/attachments/{attachment_id}` | `get_current_user` | User-scoped (`user_id`) | No | No | No |
| `DELETE` | `/api/chat/attachments/{attachment_id}` | `get_current_user` | User-scoped (`user_id`) | No | No | No |
| `POST` | `/api/chat/repo/{repo_id}/reports` | `get_current_user` | Yes (`ensure_repo_access`) | No | No | No |
| `GET` | `/api/chat/repo/{repo_id}/reports` | `get_current_user` | Yes (`ensure_repo_access`) | No | No | No |
| `GET` | `/api/chat/reports/{report_id}` | `get_current_user` | User-scoped (`user_id`) | No | No | No |
| `PATCH` | `/api/chat/reports/{report_id}` | `get_current_user` | User-scoped (`user_id`) | No | No | No |
| `DELETE` | `/api/chat/reports/{report_id}` | `get_current_user` | User-scoped (`user_id`) | No | No | No |
| `DELETE` | `/api/chat/batch` | `get_current_user` | Yes (`ensure_repo_access`) | No | No | No |
| `DELETE` | `/api/chat/{chat_id}` | `get_current_user` | User-scoped (`user_id`) | No | No | No |
| `POST` | `/api/chat/{chat_id}/restore` | `get_current_user` | User-scoped (`user_id`) | No | No | No |
| `DELETE` | `/api/chat/repo/{repo_id}/all` | `get_current_user` | Yes (`ensure_repo_access`) | No | No | No |
| `POST` | `/api/eval/run` | `get_current_user` | Yes (`ensure_repo_access`) | Yes | Yes | No |
| `GET` | `/api/eval/{repo_id}/latest` | `get_current_user` | Yes (`ensure_repo_access`) | No | No | No |
| `GET` | `/api/eval/{repo_id}/history` | `get_current_user` | Yes (`ensure_repo_access`) | No | No | No |
| `GET` | `/api/eval/{repo_id}/compare` | `get_current_user` | Yes (`ensure_repo_access`) | No | No | No |
| `GET` | `/api/repo/{repo_id}/suggestions` | `get_current_user` | User-scoped (`user_id`) | No | No | No |
| `POST` | `/api/repo/{repo_id}/health/run` | `get_current_user` | Yes (`ensure_repo_access`) | No | No | No |
| `GET` | `/api/repo/{repo_id}/health/latest` | `get_current_user` | Yes (`ensure_repo_access`) | No | No | No |
| `GET` | `/api/repo/{repo_id}/health/history` | `get_current_user` | Yes (`ensure_repo_access`) | No | No | No |
| `PATCH` | `/api/repo/{repo_id}/health/recommendations/{recommendation_id}/status` | `get_current_user` | Yes (`ensure_repo_access`) | No | No | No |
| `GET` | `/api/repo/{repo_id}/health/categories/{category}` | `get_current_user` | Yes (`ensure_repo_access`) | No | No | No |
| `POST` | `/api/reviews/file` | `get_current_user` | Yes (`ensure_repo_access`) | No | No | No |
| `POST` | `/api/reviews/files` | `get_current_user` | Yes (`ensure_repo_access`) | No | No | No |
| `POST` | `/api/reviews/commit` | `get_current_user` | Yes (`ensure_repo_access`) | No | No | No |
| `POST` | `/api/reviews/pr` | `get_current_user` | Yes (`ensure_repo_access`) | No | No | No |
| `POST` | `/api/reviews/fix` | `get_current_user` | Yes (`ensure_repo_access`) | No | No | No |
| `GET` | `/api/reviews` | `get_current_user` | Yes (`ensure_repo_access`) | Yes | No | No |
| `GET` | `/api/reviews/{review_id}` | `get_current_user` | Yes (`ensure_repo_access`) | No | No | No |
| `DELETE` | `/api/reviews/{review_id}` | `get_current_user` | Yes (`ensure_repo_access`) | No | No | No |
| `GET` | `/api/repo/{repo_id}/explorer/tree` | `get_current_user` | Yes (`ensure_repo_access`) | No | No | No |
| `GET` | `/api/repo/{repo_id}/explorer/file` | `get_current_user` | Yes (`ensure_repo_access`) | No | No | No |
| `POST` | `/api/repo/{repo_id}/explorer/review/file` | `get_current_user` | Yes (`ensure_repo_access`) | No | No | No |
| `POST` | `/api/repo/{repo_id}/explorer/review/files` | `get_current_user` | Yes (`ensure_repo_access`) | No | No | No |
| `POST` | `/api/repo/{repo_id}/explorer/fix/generate` | `get_current_user` | Yes (`ensure_repo_access`) | No | No | No |
| `POST` | `/api/repo/{repo_id}/explorer/fix/apply` | `get_current_user` | Yes (`ensure_repo_access`) | No | No | No |
| `POST` | `/api/repo/{repo_id}/explorer/tests/discover` | `get_current_user` | Yes (`ensure_repo_access`) | No | No | No |
| `POST` | `/api/repo/{repo_id}/explorer/tests/run` | `get_current_user` | Yes (`ensure_repo_access`) | No | No | No |
| `GET` | `/api/repo/{repo_id}/explorer/history` | `get_current_user` | Yes (`ensure_repo_access`) | No | No | No |
| `POST` | `/api/repo/{repo_id}/explorer/conversations` | `get_current_user` | Yes (`ensure_repo_access`) | No | No | No |
| `POST` | `/api/auth/register/preflight` | `get_optional_user` | **None** | No | No | No |
| `POST` | `/api/auth/login/preflight` | `get_optional_user` | **None** | No | No | No |
| `POST` | `/api/auth/login/audit` | `get_optional_user` | User-scoped (`user_id`) | No | No | No |
| `POST` | `/api/auth/logout/audit` | `get_current_user` | User-scoped (`user_id`) | No | No | No |
| `POST` | `/api/auth/password-reset/audit-request` | `get_optional_user` | **None** | No | No | No |
| `POST` | `/api/auth/password-reset/audit-complete` | `get_current_user` | User-scoped (`user_id`) | Yes | No | No |
| `POST` | `/api/auth/oauth/link` | `get_current_user` | User-scoped (`user_id`) | No | No | No |
| `GET` | `/api/auth/sessions` | `get_current_user` | User-scoped (`user_id`) | No | No | No |
| `GET` | `/api/repo/{repo_id}/relationship-graph` | `get_current_user` | User-scoped (`user_id`) | No | No | No |
| `GET` | `/api/repo/{repo_id}/relationship-graph/keys` | `get_current_user` | User-scoped (`user_id`) | No | No | No |
| `GET` | `/api/health` | `none` | **None** | Yes | Yes | No |

---

## 2. Complete Environment Variable Catalog

Extracted across backend (`app/` and `api/`), detailing where each variable is consumed, defaults, and whether it handles secret credentials:

| Variable Name | Required? | Default Value | Used In (File:Line) | Secret? |
| :--- | :---: | :--- | :--- | :---: |
| `AUTH_LOCKOUT_MINUTES` | Optional | `15` | `config.py:114` | No |
| `AUTH_LOGIN_HISTORY_LIMIT` | Optional | `50` | `config.py:117` | No |
| `AUTH_MAX_FAILED_LOGINS` | Optional | `5` | `config.py:113` | No |
| `AUTH_RATE_LIMIT_PER_MINUTE` | Optional | `60` | `config.py:115` | No |
| `AUTH_REQUIRE_EMAIL_VERIFICATION` | Optional | `true` | `config.py:116` | No |
| `BM25_TOP_K` | Optional | `30` | `config.py:74` | No |
| `CITATION_VALIDATION_MODE` | Optional | `strict` | `config.py:131` | No |
| `CROSS_ENCODER_DEPTH` | Optional | `15` | `config.py:76` | No |
| `DENSE_TOP_K` | Optional | `30` | `config.py:73` | No |
| `DEV_ALLOWED_ORIGINS` | Optional | `` | `main.py:169` | No |
| `EVAL_EST_COST_PER_1K_TOKENS_USD` | Optional | `0.0012` | `evaluation_center_service.py:23` | Yes (Redacted) |
| `EVAL_PROMPT_VERSION` | Optional | `v1` | `evaluation_center_service.py:21` | No |
| `EVAL_STATIC_CONFIDENCE_THRESHOLD` | Optional | `0.78` | `evaluation_center_service.py:22` | No |
| `FRONTEND_URL` | Optional | `http://localhost:3000` | `main.py:55`, `main.py:168` | No |
| `GEMINI_API_KEY` | Optional | `` | `config.py:40` | Yes (Redacted) |
| `GEMINI_LLM_MODEL` | Optional | `models/gemini-3.5-flash` | `config.py:44` | No |
| `GIT_HISTORY_MAX_COMMITS_PER_FILE` | Optional | `50` | `config.py:128` | No |
| `GROQ_API_KEY` | Optional | `` | `config.py:41` | Yes (Redacted) |
| `GROQ_FAST_MODEL` | Optional | `qwen/qwen3.8-27b` | `config.py:37` | No |
| `GROQ_LLM_MODEL` | Optional | `qwen/qwen3.8-27b` | `config.py:45` | No |
| `GUEST_READ_ONLY_MODE` | Optional | `false` | `config.py:118` | No |
| `INDEX_DIR` | Optional | `os.path.join(DATA_DIR, "index` | `config.py:56` | No |
| `INDEX_GIT_HISTORY` | Optional | `true` | `config.py:127` | No |
| `LLAMAINDEX_PREWARM_DELAY_SECONDS` | Optional | `0` | `config.py:124` | No |
| `LLAMAINDEX_PREWARM_ON_STARTUP` | Optional | `false` | `config.py:122` | No |
| `LLM_FALLBACK_RETRY_THRESHOLD` | Optional | `10` | `config.py:94` | No |
| `LLM_PROVIDER` | Optional | `*None*` | `main.py:38`, `config.py:13` | No |
| `OLLAMA_BASE_URL` | Optional | `http://localhost:11434` | `config.py:48` | No |
| `OLLAMA_EMBED_MODEL` | Optional | `*None*` | `main.py:37`, `config.py:50` | No |
| `OLLAMA_LLM_MODEL` | Optional | `*None*` | `config.py:49` | No |
| `OLLAMA_MODEL` | Optional | `*None*` | `config.py:49` | No |
| `OPENAI_API_KEY` | Optional | `*None*` | `query_router.py:180` | Yes (Redacted) |
| `REPOS_DIR` | Optional | `os.path.join(DATA_DIR, "repos` | `config.py:55` | No |
| `RETRIEVAL_RECALL_EXTRA` | Optional | `5` | `retriever.py:41` | No |
| `RRF_OUTPUT_CUTOFF` | Optional | `20` | `config.py:75` | No |
| `STREAM_FIRST_TOKEN_FALLBACK_TEXT` | Optional | `` | `config.py:110` | Yes (Redacted) |
| `STREAM_FIRST_TOKEN_TIMEOUT_SECONDS` | Optional | `25` | `config.py:108` | Yes (Redacted) |
| `SUPABASE_SERVICE_KEY` | Yes | `*None*` | `dependencies.py:48` | Yes (Redacted) |
| `SUPABASE_URL` | Yes | `*None*` | `dependencies.py:47` | No |
| `TOP_K_RERANK` | Optional | `5` | `config.py:77` | No |
| `USE_FAST_LLM` | Optional | `false` | `config.py:30` | No |
| `USE_RERANKER` | Optional | `os.getenv("USE_CROSS_ENCODER", os.getenv("USE_COLBERT", "true` | `config.py:90` | No |

---

## 3. Branch Feature Presence Matrix

Comparing the 6 active / unmerged branches against the 9 key capability groups:

| Feature Capability Area | `main` | `fix/review-service-truncation` | `fix/demo-readiness` | `feature_enhancements_v2` | `fastapi_layers_improvements_and_frontend` | `sj-feature-mods2` |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **1. CrossEncoder Header Injection** (`File: / Symbol:`) | Absent | Present (uncommitted) | Absent | Absent | Absent | Absent |
| **2. Reranker Score Formula** | Double Sigmoid (`sig(predict())`) | Double Sigmoid (`sig(predict())`) | Double Sigmoid (`sig(predict())`) | Absent | Absent | Absent |
| **3. Top-K Pipeline Tuning** (`30/30/20/15/5`) | Absent | Present (uncommitted) | Absent | Absent | Absent | Absent |
| **4. 4-Tier Orchestrator** (`SharedRetrievalOrchestrator`) | Absent | Present (uncommitted) | Absent | Absent | Absent | Absent |
| **5. Tier 1 Context Restriction** (`_codebase_context`) | Absent | Present (uncommitted) | Absent | Absent | Absent | Absent |
| **6. Extended File Filter & 20k Truncation** | Partial (Filter only) | Present (uncommitted) | Partial | Partial | Partial | Partial |
| **7. Notebook Parser, Staged Index & RWLock** | Absent | Present (uncommitted) | Partial | Absent | Absent | Absent |
| **8. Repo Isolation & Health Trust Layer** | Health only | Present (uncommitted) | Health only | Absent | Absent | Health only |
| **9. Evaluation Harness (BM25 pass + 100-Q dataset)** | Absent | Present (uncommitted) | Absent | Absent | Absent | Absent |

---

## 4. Verbatim Code Excerpts

### Excerpt 4.1: SharedRetrievalOrchestrator Threshold and Tier Section
**File:** `app/retrieval/orchestrator.py` (Lines 575–625)

```python
        # Tier 3 (Hybrid Code) confidence check
        if code_nodes and tier3_score >= _active_thresholds[RetrievalTier.TIER3_HYBRID_CODE]:
            selected_tier = RetrievalTier.TIER3_HYBRID_CODE
            overall_confidence = tier3_score
            selected_nodes = code_nodes[:top_k]
        # Tier 2 (Documentation) fallback
        elif doc_nodes and tier2_score >= _active_thresholds[RetrievalTier.TIER2_DOCUMENTATION]:
            selected_tier = RetrievalTier.TIER2_DOCUMENTATION
            overall_confidence = tier2_score
            selected_nodes = doc_nodes[:top_k]
        # Tier 1 (Architecture) fallback
        elif tier1_nodes and tier1_score >= _active_thresholds[RetrievalTier.TIER1_ARCHITECTURE]:
            selected_tier = RetrievalTier.TIER1_ARCHITECTURE
            overall_confidence = tier1_score
            selected_nodes = tier1_nodes[:top_k]
        else:
            selected_tier = RetrievalTier.TIER4_ABSTENTION
            should_abstain = True
            overall_confidence = max(tier3_score, tier2_score, tier1_score, 0.0)
            selected_nodes = []
```

---

### Excerpt 4.2: CrossEncoder Reranker Scoring Block
**File:** `app/retrieval/reranker.py` (Lines 174–185)

```python
                # Assign scores to the nodes (sigmoid normalization to [0, 1])
                node_scores = {}
                for node, score in zip(nodes, scores):
                    sig_score = 1 / (1 + math.exp(-float(score)))
                    node.score = sig_score
                    node_scores[node.node.node_id] = sig_score

                # Populate cache
                _reranker_cache.put(cache_key, node_scores)
```

---

### Excerpt 4.3: Code Parser Truncation Block
**File:** `app/parsing/code_parser.py` (Lines 175–194)

```python
        # Hard cap — protects memory on massive generated files
        content = content[:20000]

        meta = {
            "file_name": file_name,
            "path": relative_path,
            "extension": ext,
            "format": format_type,
            "file_size": len(content),
        }
        meta.update(extra_meta)

        doc = Document(
            text=content,
            metadata=meta,
            excluded_embed_metadata_keys=["file_size", "top_keys", "headers"],
            excluded_llm_metadata_keys=["file_size", "extension", "top_keys", "headers"],
        )
        documents.append(doc)
```

---

### Excerpt 4.4: load_repository Local and Remote Resolution
**File:** `app/ingestion/repo_loader.py` (Lines 465–479, 512–518)

```python
                try:
                    _clone_repository(clone_source, stage_dir)
                    logger.debug("Clone into staging path completed: %s", stage_dir)
                    _remove_existing_repo_dir(candidate_target)
                    logger.debug(
                        "Promoting staged clone into final target (stage=%s, target=%s)",
                        stage_dir,
                        candidate_target,
                    )
                    _promote_staged_clone(stage_dir, candidate_target)
                    return candidate_target
...
    else:
        logger.info("Source identified as local path: %s", source)
        if not os.path.exists(source) or not os.path.isdir(source):
            logger.error("Local repository source is invalid: %s", source)
            raise ValueError(f"Invalid local directory path: {source}")
        logger.info("Local repository source validated: %s", source)
        return source
```

---

### Excerpt 4.5: derive_repo_name Path Segment Extraction
**File:** `app/ingestion/repo_naming.py` (Lines 41–56)

```python
def derive_repo_name(source: str) -> str:
    """Derive a filesystem-safe repository folder name from URL or local path."""
    raw_source = (source or "").strip()
    if not raw_source:
        return "repo"

    if is_valid_url(raw_source):
        parsed = urlparse(raw_source)
        candidate = (parsed.path or "").rstrip("/").split("/")[-1]
    else:
        candidate = os.path.basename(os.path.normpath(raw_source))

    if candidate.endswith('.git'):
        candidate = candidate[:-4]
```

---

### Excerpt 4.6: resolve_repository_id and enforce_chunk_isolation
**File:** `app/retrieval/repository_isolation.py` (Lines 51–80, 154–164)

```python
def resolve_repository_id(repo_name_or_id: str) -> Optional[str]:
    ...
    # Try querying Supabase
    try:
        from api.dependencies import get_supabase
        sb = get_supabase()
        res = sb.table("repositories").select("id, name, index_name").execute()
        for r in res.data or []:
            r_id = r.get("id")
            r_name = r.get("name")
            r_idx = r.get("index_name")
            if r_id and r_name:
                _dynamic_cache[r_name] = r_id
                _dynamic_cache[r_id] = r_name
            if r_id and r_idx:
                _dynamic_cache[r_idx] = r_id
...
        # Check missing metadata in strict testing mode
        if require_existing_metadata and not chunk_repo_id:
            logger.warning("Strict isolation rejection: chunk missing required repository_id metadata")
            continue

        # Stamp verified repository metadata
        n.node.metadata["repository_id"] = target_repo_id
        n.node.metadata["index_name"] = active_index_name
        verified_nodes.append(n)
```

---

### Excerpt 4.7: Stream Bridge Single-Threaded Executor
**File:** `app/services/llm_fallback.py` (Lines 23, 187–203)

```python
_STREAM_BRIDGE_EXECUTOR = ThreadPoolExecutor(max_workers=1, thread_name_prefix="llm-sync-stream")

async def _bridge_sync_stream_complete(llm: Any, prompt: str, **kwargs: Any) -> AsyncGenerator[Any, None]:
    """Bridge sync stream_complete() to async iteration without blocking event loop."""
    loop = asyncio.get_running_loop()
    stream_iter = await loop.run_in_executor(
        _STREAM_BRIDGE_EXECUTOR,
        partial(llm.stream_complete, prompt, **kwargs),
    )
    try:
        while True:
            chunk = await loop.run_in_executor(_STREAM_BRIDGE_EXECUTOR, _next_chunk_or_end, stream_iter)
            if chunk is _STREAM_END:
                return
            yield chunk
    finally:
        if hasattr(stream_iter, "close"):
            await loop.run_in_executor(_STREAM_BRIDGE_EXECUTOR, stream_iter.close)
```

---

### Excerpt 4.8: Query Router Production Test-Mock Inspection
**File:** `app/retrieval/query_router.py` (Lines 171–183)

```python
def _get_router_llm():
    """Retrieve LLM client for query routing, prioritizing resilient LLM provider while respecting test mocks."""
    try:
        if hasattr(Settings, "_mock_name") or hasattr(Settings, "mock_calls"):
            return getattr(Settings, "llm", None)
        if hasattr(Settings, "llm") and Settings.llm is not None:
            llm_type = type(Settings.llm).__name__
            if "Mock" in llm_type:
                return Settings.llm
            if llm_type not in ("OpenAI", "OpenAILike") or os.getenv("OPENAI_API_KEY"):
                return Settings.llm
    except Exception:
        pass
```
