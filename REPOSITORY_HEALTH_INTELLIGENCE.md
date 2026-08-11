# Repository Health Intelligence Engine

This feature replaces the static repository health indicator with a dynamic,
evidence-backed engineering KPI system that tracks repository metrics over time,
provides actionable recommendations, and enables data-driven engineering decisions.

## What is implemented

### Core Features
- **Dynamic repository health scoring** with 14-category analysis
- **Time-series trend tracking** persisted per-run to track score changes over 30 days
- **API Endpoints:**
  - `POST /api/repo/{repo_id}/health/run` - Trigger new health analysis
  - `GET /api/repo/{repo_id}/health/latest` - Retrieve latest analysis results
  - `GET /api/repo/{repo_id}/health/history?days=30&limit=30` - Get historical trend data
  - `GET /api/repo/{repo_id}/health/categories/{category}` - Category drill-down with evidence

### Analysis Categories (14 Analyzers)
1. **Architecture** - Design patterns, modularity, coupling analysis
2. **Security** - Authentication guards, hardcoded secrets, credential exposure
3. **Testing** - Test coverage, test-to-code ratio, test patterns
4. **Documentation** - README quality, inline comments, API documentation
5. **Performance** - Optimization hotspots, resource efficiency, caching patterns
6. **Maintainability** - Code duplication, function complexity, naming conventions
7. **Technical Debt** - TODO markers, deprecated APIs, anti-patterns
8. **Dependency Management** - Outdated packages, version conflicts, supply chain risks
9. **Code Quality** - Complexity metrics, cohesion, cyclomatic complexity
10. **Scalability** - Horizontal/vertical scaling readiness, distributed patterns
11. **Observability** - Logging coverage, metrics instrumentation, error handling
12. **Developer Experience** - Setup complexity, documentation clarity, community health
13. **Type Safety** - Type annotations, TypeScript coverage, null safety
14. **Custom Risk Analysis** - Repository-specific pattern detection

### Output & Recommendations
- Explainable findings with file/module evidence
- Top 10 prioritized recommendations ranked by impact/effort ratio
- Executive summary with strengths/weaknesses analysis
- Risk categorization (critical, architecture, security, performance)
- Sprint guidance with actionable next steps
- Grade system: A (90-100), B (80-89), C (70-79), D (60-69), F (<60)
- Trend indicator: shows score delta vs previous analysis (+2, -3, etc.)

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

Apply the migration to set up the database schema:

```sql
api/migrations/20260804_repository_health_intelligence.sql
```

### View Migration Content

To see what tables and indexes are created by the migration:

**PowerShell:**
```powershell
Get-Content "C:\SourceCode\Codebase-Copilot\api\migrations\20260804_repository_health_intelligence.sql" | Select-Object -First 50
```

**PowerShell (Full file):**
```powershell
Get-Content "C:\SourceCode\Codebase-Copilot\api\migrations\20260804_repository_health_intelligence.sql"
```

**PowerShell (Read line by line with line numbers):**
```powershell
$file = "C:\SourceCode\Codebase-Copilot\api\migrations\20260804_repository_health_intelligence.sql"
Get-Content $file | ForEach-Object { Write-Host "$([System.IO.File]::ReadAllLines($file) | Select-Object -Index ([array]::IndexOf([System.IO.File]::ReadAllLines($file), $_))) | $_" }

# Simpler alternative - show line numbers
$content = Get-Content $file
$content | ForEach-Object -Begin { $line = 1 } -Process { Write-Host "$($line.ToString().PadLeft(3)): $_"; $line++ }
```

**VS Code / Text Editor (Easiest Method):**
```powershell
# Open in VS Code
code "C:\SourceCode\Codebase-Copilot\api\migrations\20260804_repository_health_intelligence.sql"

# Or open in default text editor
Invoke-Item "C:\SourceCode\Codebase-Copilot\api\migrations\20260804_repository_health_intelligence.sql"
```

**Manual File Viewing Steps:**

1. **Navigate to file location:**
   ```powershell
   cd "C:\SourceCode\Codebase-Copilot\api\migrations\"
   Dir  # List files
   ```

2. **View file size and basic info:**
   ```powershell
   Get-Item "20260804_repository_health_intelligence.sql" | Select-Object FullName, Length, CreationTime
   ```

3. **Count total lines:**
   ```powershell
   @(Get-Content "20260804_repository_health_intelligence.sql").Length
   ```

4. **View specific sections (tables):**
   ```powershell
   # View create table statements
   Get-Content "20260804_repository_health_intelligence.sql" | Select-String "create table"
   
   # View index creation
   Get-Content "20260804_repository_health_intelligence.sql" | Select-String "create index"
   
   # View RLS policies
   Get-Content "20260804_repository_health_intelligence.sql" | Select-String "row level security"
   ```

5. **Extract specific table schema:**
   ```powershell
   $file = "C:\SourceCode\Codebase-Copilot\api\migrations\20260804_repository_health_intelligence.sql"
   $content = Get-Content $file -Raw
   
   # Extract repository_health_runs table
   if ($content -match '(?s)(create table.*repository_health_runs.*?);') {
       $Matches[1] | Write-Host
   }
   ```

**Python Script to Parse and Display Migration:**

```powershell
.\.venv\Scripts\python.exe << 'EOPYTHON'
import re

migration_file = r"C:\SourceCode\Codebase-Copilot\api\migrations\20260804_repository_health_intelligence.sql"

with open(migration_file, 'r') as f:
    content = f.read()

# Extract all CREATE TABLE statements
tables = re.findall(r'create table if not exists (\w+)', content, re.IGNORECASE)
indexes = re.findall(r'create index if not exists (\w+)', content, re.IGNORECASE)

print("\n✓ Migration Schema Summary\n")
print(f"File: {migration_file}")
print(f"Total lines: {len(content.splitlines())}")

print(f"\nTables Created ({len(tables)}):")
for table in tables:
    print(f"  • {table}")

print(f"\nIndexes Created ({len(indexes)}):")
for idx in indexes:
    print(f"  • {idx}")

print("\nMigration Components:")
if "row level security" in content.lower():
    print("  ✓ Row Level Security (RLS) enabled")
if "references" in content.lower():
    print("  ✓ Foreign key constraints")
if "jsonb" in content.lower():
    print("  ✓ JSON fields (JSONB)")
if "timestamptz" in content.lower():
    print("  ✓ Timezone-aware timestamps")

EOPYTHON
```

**Expected Output:**
```
✓ Migration Schema Summary

File: C:\SourceCode\Codebase-Copilot\api\migrations\20260804_repository_health_intelligence.sql
Total lines: 100

Tables Created (4):
  • repository_health_runs
  • repository_health_category_scores
  • repository_health_findings
  • repository_health_recommendations

Indexes Created (7):
  • idx_repo_health_runs_repo_time
  • idx_repo_health_runs_user_repo
  • idx_repo_health_cat_run
  • idx_repo_health_cat_repo
  • idx_repo_health_findings_run
  • idx_repo_health_findings_severity
  • idx_repo_health_reco_run_rank

Migration Components:
  ✓ Row Level Security (RLS) enabled
  ✓ Foreign key constraints
  ✓ JSON fields (JSONB)
  ✓ Timezone-aware timestamps
```

## Triggering Health Analysis via CLI

### Option 1: Using debug_health.py Script (Recommended)

The recommended way to trigger health analysis from CLI:

```powershell
# Navigate to project root
cd C:\SourceCode\Codebase-Copilot

# Run health analysis with debug output
.\.venv\Scripts\python.exe debug_health.py --repo-id "YOUR_REPO_UUID_HERE"

# Example output:
# Running health check for repo: YOUR_REPO_UUID_HERE
# Health Score: 87
# Grade: B
# Status: completed
# Trend: +2
# Categories Analyzed: 14
```

### Option 2: Using HTTP API Endpoints (Simplest Method)

Make sure backend is running on `http://localhost:8000`:

```powershell
# Step 1: Get JWT token from login
$login_response = Invoke-WebRequest `
  -Uri "http://localhost:8000/api/auth/login" `
  -Method POST `
  -ContentType "application/json" `
  -Body '{"email":"YOUR_EMAIL","password":"YOUR_PASSWORD"}'

$login_data = $login_response.Content | ConvertFrom-Json
$auth_token = $login_data.access_token

# Step 2: Trigger health analysis run
$repo_id = "YOUR_REPO_UUID_HERE"
$response = Invoke-WebRequest `
  -Uri "http://localhost:8000/api/repo/$repo_id/health/run" `
  -Method POST `
  -Headers @{"Authorization" = "Bearer $auth_token"} `
  -ContentType "application/json"

$result = $response.Content | ConvertFrom-Json
Write-Host "✓ Analysis triggered:"
Write-Host "  Score: $($result.repository_health)/100"
Write-Host "  Grade: $($result.grade)"
Write-Host "  Status: $($result.status)"
Write-Host "  Trend: $($result.trend)"
```

### Option 3: Retrieve Latest Health Analysis

```powershell
$repo_id = "YOUR_REPO_UUID_HERE"
$auth_token = "YOUR_JWT_TOKEN_HERE"

$response = Invoke-WebRequest `
  -Uri "http://localhost:8000/api/repo/$repo_id/health/latest" `
  -Method GET `
  -Headers @{"Authorization" = "Bearer $auth_token"}

$latest = $response.Content | ConvertFrom-Json
Write-Host "Latest Health Analysis:"
Write-Host "  Score: $($latest.repository_health)"
Write-Host "  Grade: $($latest.grade)"
Write-Host "  Status: $($latest.status)"
Write-Host "  Trend: $($latest.trend)"
```

### Option 4: Retrieve 30-Day Trend History

```powershell
# Using Python CLI Script (Recommended for viewing trends)
cd C:\SourceCode\Codebase-Copilot

$repo_id = "c5fd7db8-7ed0-431b-ad8f-80e3dfd04677"  # Replace with your repo ID

.\.venv\Scripts\python.exe << 'EOPYTHON'
import sys
sys.path.insert(0, ".")

import os
from dotenv import load_dotenv
load_dotenv()

from supabase import create_client

# Initialize Supabase client
url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
supabase = create_client(url, key)

repo_id = "$repo_id"

# Query health runs (30 days max, ordered by date DESC)
response = supabase.table("repository_health_runs").select(
    "id, repository_health, grade, trend, status, created_at"
).eq("repo_id", repo_id).order("created_at", desc=True).limit(30).execute()

print(f"\n✓ Health Trend History for Repository: {repo_id}")
print(f"  Total runs found: {len(response.data)}\n")

if response.data:
    print(f"{'Date':<12} | {'Score':<6} | {'Grade':<6} | {'Trend':<7} | {'Status':<12}")
    print("-" * 62)
    
    for run in response.data:
        date = run["created_at"][:10]
        score = run["repository_health"]
        grade = run["grade"]
        trend = f"{run['trend']:+d}" if run["trend"] else "0"
        status = run["status"]
        
        print(f"{date} | {score:>4} | {grade:>4} | {trend:>5} | {status:<10}")
else:
    print("No health runs found for this repository.")

EOPYTHON
```

**Expected Output:**
```
✓ Health Trend History for Repository: c5fd7db8-7ed0-431b-ad8f-80e3dfd04677
  Total runs found: 5

Date       | Score | Grade | Trend | Status
--------------------------------------------------------------
2026-08-11 |    87 |   B   |   +2  | completed
2026-08-09 |    85 |   B   |   -1  | completed
2026-08-08 |    86 |   B   |   +3  | completed
2026-08-07 |    83 |   B   |   +0  | completed
2026-08-06 |    83 |   B   |   -5  | completed
```

**Using HTTP API (PowerShell Alternative):**

```powershell
# Retrieve 30-day health trend history via HTTP API
$repo_id = "YOUR_REPO_UUID_HERE"
$auth_token = "YOUR_JWT_TOKEN_HERE"

$response = Invoke-WebRequest `
  -Uri "http://localhost:8000/api/repo/$repo_id/health/history?days=30&limit=30" `
  -Method GET `
  -Headers @{"Authorization" = "Bearer $auth_token"}

Write-Host "Health Trend History (30 days):`n"
Write-Host "Date       | Score | Grade | Trend | Status"
Write-Host "---------------------------------------------------"
$trend_data = $response.Content | ConvertFrom-Json
$trend_data | ForEach-Object {
    $date = ($_.created_at).Substring(0,10)
    $score = $_.repository_health
    $grade = $_.grade
    $trend = "{0:+d}" -f $_.trend
    $status = $_.status
    Write-Host "$date | $score | $grade | $trend | $status"
}
```

### Option 5: View Category Breakdown with Evidence

```powershell
$repo_id = "YOUR_REPO_UUID_HERE"
$category = "Security"
$auth_token = "YOUR_JWT_TOKEN_HERE"

$response = Invoke-WebRequest `
  -Uri "http://localhost:8000/api/repo/$repo_id/health/categories/$category" `
  -Method GET `
  -Headers @{"Authorization" = "Bearer $auth_token"}

$category_details = $response.Content | ConvertFrom-Json
Write-Host "Category: $category"
Write-Host "  Score: $($category_details.score)"
Write-Host "  Grade: $($category_details.grade)"
Write-Host "  Explanation: $($category_details.explanation)"
```

### Expected Health Analysis Output

When a health analysis completes successfully, you should see:

```json
{
  "id": "uuid",
  "repo_id": "repo-uuid",
  "repository_health": 87,
  "grade": "B",
  "status": "completed",
  "trend": 2,
  "repository_size": "Medium",
  "language_detection": ["Python", "TypeScript"],
  "executive_summary": "Repository demonstrates good engineering practices...",
  "strengths": [
    "Comprehensive test coverage (85%)",
    "Well-documented APIs",
    "Strong architectural separation"
  ],
  "weaknesses": [
    "Some long functions (>200 lines)",
    "Missing type annotations in legacy modules"
  ],
  "critical_risks": [],
  "architecture_risks": ["Monolithic patterns in services"],
  "security_risks": ["Hardcoded configuration in frontend"],
  "performance_risks": [],
  "recommended_sprint": ["Add type annotations", "Refactor long functions"],
  "category_scores": [
    {
      "category": "Security",
      "score": 70,
      "grade": "C",
      "trend": 5
    },
    ...
  ],
  "recommendations": [
    {
      "priority_rank": 1,
      "category": "Security",
      "title": "Fix hardcoded secrets",
      "expected_score_gain": 10,
      "estimated_effort": "2-3 hours"
    },
    ...
  ]
}
```

### Troubleshooting Health Analysis

**Issue: No trend data showing (all same score)**
- Ensure multiple health runs exist (run analysis on different days)
- Check `repository_health_runs` table has multiple records for the repo_id
- Verify timestamps differ across runs

**Issue: Categories returning 0 or N/A scores**
- Ensure repository is properly indexed (run indexing first)
- Check that repository path is accessible and contains code files
- Verify LLM providers are configured (check .env for LLM_PROVIDER, MODEL settings)

**Issue: "Token is expired" error**
- Refresh authentication token via login endpoint
- Check JWT expiration time in .env (JWT_EXPIRATION_HOURS)

## Database Schema Reference

### repository_health_runs
Stores overall health analysis results per run.

**Key Columns:**
- `id` - UUID primary key
- `repo_id` - Foreign key to repositories table
- `repository_health` - Overall score (0-100)
- `grade` - Letter grade (A, B, C, D, F)
- `trend` - Score change since previous run (-100 to +100)
- `status` - Analysis status (pending, in_progress, completed, failed)
- `language_detection` - JSON array of detected languages
- `executive_summary` - High-level summary of health status
- `strengths` - JSON array of top strengths
- `weaknesses` - JSON array of areas needing improvement
- `critical_risks` - JSON array of critical issues
- `created_at` - Timestamp of analysis run

**Indexes:**
- `idx_repo_health_runs_repo_time` - (repo_id, created_at DESC)
- `idx_repo_health_runs_user_repo` - (user_id, repo_id, created_at DESC)

### repository_health_category_scores
Per-category scores (14 categories) for each health run.

**Key Columns:**
- `id` - UUID primary key
- `run_id` - Foreign key to repository_health_runs
- `category` - Category name (Security, Testing, Architecture, etc.)
- `score` - Category score (0-100)
- `grade` - Category grade
- `trend` - Category trend since previous run
- `explanation` - Category analysis explanation
- `recommendations` - JSON array of category-specific recommendations

**Indexes:**
- `idx_repo_health_cat_run` - (run_id, category)
- `idx_repo_health_cat_repo` - (repo_id, category, created_at DESC)

### repository_health_findings
Detailed findings and evidence for specific issues.

**Key Columns:**
- `id` - UUID primary key
- `run_id` - Foreign key to repository_health_runs
- `category` - Which category this finding belongs to
- `finding_type` - Type of finding (pattern_detected, metric_threshold, etc.)
- `severity` - Severity level (info, warning, critical)
- `title` - Brief title of the finding
- `details` - Detailed explanation
- `evidence` - JSON object with file paths, line numbers, code snippets
- `affected_files` - JSON array of file paths with issues

**Indexes:**
- `idx_repo_health_findings_run` - (run_id, category)
- `idx_repo_health_findings_severity` - (repo_id, severity, created_at DESC)

### repository_health_recommendations
Prioritized action items to improve health score.

**Key Columns:**
- `id` - UUID primary key
- `run_id` - Foreign key to repository_health_runs
- `priority_rank` - Ranking (1 = highest priority, up to 10)
- `category` - Which category this addresses
- `title` - Recommendation title
- `description` - Full description of the recommendation
- `estimated_effort` - Effort estimate (e.g., "2-3 hours", "1-2 days")
- `expected_score_gain` - Expected score improvement if implemented (0-20)
- `impact_score` - Calculated impact/effort ratio for prioritization
- `action_items` - JSON array of specific steps to implement

**Indexes:**
- `idx_repo_health_reco_run_rank` - (run_id, priority_rank)

### View Schema in Database

```powershell
# Query tables information from Supabase
$env:SUPABASE_URL = "YOUR_SUPABASE_URL"
$env:SUPABASE_SERVICE_KEY = "YOUR_SERVICE_KEY"

# List all health-related tables
C:\SourceCode\Codebase-Copilot\.venv\Scripts\python.exe -c "
import os
from supabase import create_client, Client

url = os.getenv('SUPABASE_URL')
key = os.getenv('SUPABASE_SERVICE_KEY')
supabase: Client = create_client(url, key)

# Query information about tables
tables = ['repository_health_runs', 'repository_health_category_scores', 'repository_health_findings', 'repository_health_recommendations']

for table in tables:
    data = supabase.table(table).select('*').limit(1).execute()
    print(f'\nTable: {table}')
    if data.data:
        print(f'Columns: {list(data.data[0].keys())}')
"
```

## Quick Verification

Run unit tests to verify implementation:

```powershell
# Test health engine functionality
C:\SourceCode\Codebase-Copilot\.venv\Scripts\python.exe -m pytest C:\SourceCode\Codebase-Copilot\tests\unit\test_repository_health_engine.py -v

# Test database persistence
C:\SourceCode\Codebase-Copilot\.venv\Scripts\python.exe -m pytest C:\SourceCode\Codebase-Copilot\tests\unit\test_supabase_service.py -v
```

## Integration Verification

To verify the health intelligence system is working end-to-end:

1. **Start Backend Server:**
   ```powershell
   cd C:\SourceCode\Codebase-Copilot
   .\.venv\Scripts\python.exe -m uvicorn api.main:app --reload --host 127.0.0.1 --port 8000
   ```

2. **Check Health Endpoint Availability:**
   ```powershell
   # Verify endpoints are registered
   Invoke-WebRequest -Uri "http://localhost:8000/api/docs" -Method GET
   # Look for /api/repo/{repo_id}/health/run, /health/latest, /health/history endpoints
   ```

3. **Run a Health Analysis:**
   ```powershell
   # Use the CLI commands from "Triggering Health Analysis via CLI" section above
   ```

4. **Verify Data Persistence:**
   ```powershell
   # Check that results appear in Supabase
   # Navigate to Supabase console and verify repository_health_runs table has new entries
   ```

5. **Check Frontend Display:**
   - Open repository in web interface
   - Navigate to "Repository Health Intelligence" section
   - Verify health score, grade, and trend display correctly
   - Click on categories to see findings and recommendations
