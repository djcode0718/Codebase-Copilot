# Phase 0 Reconnaissance Map

## Frontend

- Route surface:
  - `frontend/app/repo/[id]/page.tsx` (workspace overview)
  - `frontend/app/repo/[id]/chat/page.tsx` (persisted chat + SSE)
  - `frontend/app/repo/[id]/explorer/page.tsx` + `frontend/components/repo/RepositoryExplorerPageClient.tsx` (code explorer + actions)
  - `frontend/app/repo/[id]/review/page.tsx` (engineering review)
  - `frontend/app/repo/[id]/eval/page.tsx` (evaluation dashboard)
- Shared clients/types:
  - `frontend/lib/api.ts` (typed API client)
  - `frontend/lib/types.ts` (repo/branch/chat/health/eval schemas)
  - `frontend/lib/engineering-actions.ts` (context-sensitive action catalog)
  - `frontend/lib/chat-context.ts` (chat context preloading)
- Existing branch-aware UX:
  - `frontend/components/repo/BranchWorkspacePanel.tsx` supports branch search/list/checkout/pull/default return/compare/status.
- Existing health UX:
  - `frontend/components/repo/RepositoryHealthDashboard.tsx` supports score/category/recommendation/finding actions.

## Backend

- Routers:
  - `api/routers/repo.py` (repo lifecycle, branch endpoints)
  - `api/routers/chat.py` (chat session/message/SSE/persistence)
  - `api/routers/health.py` (health run/latest/history/category/recommendation status)
  - `api/routers/eval.py` (evaluation run/history/comparison)
  - `api/routers/reviews.py` (AI engineering review)
- Services:
  - `api/services/supabase_service.py` (persistence abstraction, lifecycle state, history)
  - `api/services/repo_branch_service.py` (branch discovery/status/sync semantics)
  - `api/services/chat_service.py` (retrieval + LLM streaming + safety fallbacks)

## AI / Cost / Context

- Chat flow already includes deterministic + retrieval + targeted generation layering in practice.
- SSE metadata captures query mode, retrieved files, latency breakdown, provider/model.
- Evaluation models include cache and estimated cost fields (`EvalEfficiency`).
- Recommendation lifecycle normalization already exists in backend and has now been test-hardened.

## Testing Coverage Snapshot

- Unit tests:
  - `tests/unit/test_supabase_service.py`
  - `tests/unit/test_chat_stream_utils.py`
  - `tests/unit/test_chat_session_service.py`
  - additional parser/eval/indexing helpers.
- Integration tests:
  - `tests/integration/test_repository_health_trend_api.py`
  - `tests/integration/test_router_reviews.py`
  - auth/repo/chat pathway coverage distributed across existing tests.

## Immediate Gaps Observed

- Cross-page evidence handoff existed inconsistently; addressed in this iteration for chat -> explorer.
- Chat page contained render-time state update anti-pattern for graph availability cache coherence; corrected.
- Recommendation lifecycle persistence accepted only exact-case statuses in one path; normalized.

## Minimal-Risk Execution Principle Applied

- Extend existing abstractions; avoid route/API breaks.
- Preserve existing workflows and DB schema assumptions.
- Add targeted test coverage around status normalization and lifecycle persistence behavior.

