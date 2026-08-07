# Repository Health Intelligence Engine

This feature replaces the static repository health indicator with a dynamic,
evidence-backed engineering KPI system.

## What is implemented

- Dynamic repository health run: `POST /api/repo/{repo_id}/health/run`
- Latest run retrieval: `GET /api/repo/{repo_id}/health/latest`
- Trend history: `GET /api/repo/{repo_id}/health/history`
- Category drill-down: `GET /api/repo/{repo_id}/health/categories/{category}`
- Explainable findings with file/module evidence
- Top 10 prioritized recommendations with effort and expected score gain
- Executive summary, strengths/weaknesses, risk slices, sprint guidance
- Persisted runs, categories, findings, recommendations, and trend metadata

## Backend architecture

- `api/services/repository_health_engine.py`
  - `RepositoryHealthEngine`
  - `ArchitectureAnalyzer`
  - `SecurityAnalyzer`
  - `TestingAnalyzer`
  - `DocumentationAnalyzer`
  - `PerformanceAnalyzer`
  - `MaintainabilityAnalyzer`
  - `TechnicalDebtAnalyzer`
  - `DependencyAnalyzer`
  - `CodeQualityAnalyzer`
  - `ScalabilityAnalyzer`
  - `ObservabilityAnalyzer`
  - `DeveloperExperienceAnalyzer`
  - `TrendAnalyzer`
  - `RecommendationEngine`
- `api/routers/health.py` for health intelligence APIs
- `api/routers/_repo_access.py` shared access guard used by health/evaluation routers to avoid duplicated ownership checks
- `api/services/supabase_service.py` persistence helpers
- `api/migrations/20260804_repository_health_intelligence.sql`

## Frontend architecture

- `frontend/components/repo/RepositoryHealthDashboard.tsx`
  - Top-level health KPI card
  - 30-day trend chart
  - Clickable category breakdown
  - Category findings evidence panel
  - Top 10 recommendation panel
- `frontend/lib/types.ts` health intelligence contracts
- `frontend/lib/api.ts` health intelligence client calls
- `frontend/app/repo/[id]/page.tsx` integration into repository dashboard
- Additive maintainability refactors in explorer-related UI (`frontend/components/layout/RepositoryExplorer.tsx`, `frontend/components/layout/Sidebar.tsx`, `frontend/hooks/useIndexingStream.ts`) to split oversized blocks while preserving behavior

## Backward compatibility

- All updates are additive internal refactors; no API path, request/response contract, or migration behavior changes were introduced by these maintainability updates.

## Migration

Apply:

```sql
api/migrations/20260804_repository_health_intelligence.sql
```

## Quick verification

```powershell
C:\SourceCode\Codebase-Copilot\venv_copilot\Scripts\python.exe -m pytest C:\SourceCode\Codebase-Copilot\tests\unit\test_repository_health_engine.py -q
C:\SourceCode\Codebase-Copilot\venv_copilot\Scripts\python.exe -m pytest C:\SourceCode\Codebase-Copilot\tests\unit\test_supabase_service.py -q
```

