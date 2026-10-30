-- ==============================================================================
-- 20261030_complete_diagnostic_schema_repair.sql
-- Consolidated Schema Repair Migration for Codebase-Copilot
-- Target Database: Supabase PostgreSQL (public schema)
-- Non-destructive: Safe to run multiple times (uses IF NOT EXISTS / ADD COLUMN IF NOT EXISTS)
-- ==============================================================================

-- 1. Add missing branch workspace columns to repositories table
ALTER TABLE IF EXISTS repositories
  ADD COLUMN IF NOT EXISTS active_branch text,
  ADD COLUMN IF NOT EXISTS default_branch text,
  ADD COLUMN IF NOT EXISTS active_commit_sha text;

-- 2. Repository Health Intelligence Runs Table
CREATE TABLE IF NOT EXISTS repository_health_runs (
  id uuid PRIMARY KEY,
  repo_id uuid NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
  user_id uuid NOT NULL,
  repository_health int NOT NULL,
  grade text NOT NULL,
  status text NOT NULL,
  trend int DEFAULT 0,
  repository_size text,
  language_detection jsonb DEFAULT '[]'::jsonb,
  framework_detection jsonb DEFAULT '[]'::jsonb,
  executive_summary text,
  strengths jsonb DEFAULT '[]'::jsonb,
  weaknesses jsonb DEFAULT '[]'::jsonb,
  critical_risks jsonb DEFAULT '[]'::jsonb,
  architecture_risks jsonb DEFAULT '[]'::jsonb,
  security_risks jsonb DEFAULT '[]'::jsonb,
  performance_risks jsonb DEFAULT '[]'::jsonb,
  recommended_sprint jsonb DEFAULT '[]'::jsonb,
  improved_categories jsonb DEFAULT '[]'::jsonb,
  declining_categories jsonb DEFAULT '[]'::jsonb,
  new_risks jsonb DEFAULT '[]'::jsonb,
  resolved_risks jsonb DEFAULT '[]'::jsonb,
  benchmark jsonb DEFAULT '{}'::jsonb,
  analysis_context jsonb DEFAULT '{}'::jsonb,
  created_at timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_repo_health_runs_repo_time ON repository_health_runs (repo_id, created_at desc);
CREATE INDEX IF NOT EXISTS idx_repo_health_runs_user_repo ON repository_health_runs (user_id, repo_id, created_at desc);

-- 3. Health Category Scores Table
CREATE TABLE IF NOT EXISTS repository_health_category_scores (
  id uuid PRIMARY KEY,
  run_id uuid NOT NULL REFERENCES repository_health_runs(id) ON DELETE CASCADE,
  repo_id uuid NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
  user_id uuid NOT NULL,
  category text NOT NULL,
  score int NOT NULL,
  grade text NOT NULL,
  trend int DEFAULT 0,
  explanation text,
  detected_problems jsonb DEFAULT '[]'::jsonb,
  positive_findings jsonb DEFAULT '[]'::jsonb,
  recommendations jsonb DEFAULT '[]'::jsonb,
  affected_files jsonb DEFAULT '[]'::jsonb,
  affected_modules jsonb DEFAULT '[]'::jsonb,
  created_at timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_repo_health_cat_run ON repository_health_category_scores (run_id, category);
CREATE INDEX IF NOT EXISTS idx_repo_health_cat_repo ON repository_health_category_scores (repo_id, category, created_at desc);

-- 4. Health Findings Table
CREATE TABLE IF NOT EXISTS repository_health_findings (
  id uuid PRIMARY KEY,
  run_id uuid NOT NULL REFERENCES repository_health_runs(id) ON DELETE CASCADE,
  repo_id uuid NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
  user_id uuid NOT NULL,
  category text NOT NULL,
  finding_type text NOT NULL,
  severity text NOT NULL,
  title text NOT NULL,
  details text,
  evidence jsonb DEFAULT '{}'::jsonb,
  recommendation text,
  affected_files jsonb DEFAULT '[]'::jsonb,
  affected_modules jsonb DEFAULT '[]'::jsonb,
  expected_score_gain int DEFAULT 0,
  created_at timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_repo_health_findings_run ON repository_health_findings (run_id, category);
CREATE INDEX IF NOT EXISTS idx_repo_health_findings_severity ON repository_health_findings (repo_id, severity, created_at desc);

-- 5. Health Recommendations Table
CREATE TABLE IF NOT EXISTS repository_health_recommendations (
  id uuid PRIMARY KEY,
  run_id uuid NOT NULL REFERENCES repository_health_runs(id) ON DELETE CASCADE,
  repo_id uuid NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
  user_id uuid NOT NULL,
  priority_rank int NOT NULL,
  category text NOT NULL,
  title text NOT NULL,
  description text,
  estimated_effort text,
  expected_score_gain int DEFAULT 0,
  impact_score numeric(10,2) DEFAULT 0,
  action_items jsonb DEFAULT '[]'::jsonb,
  affected_files jsonb DEFAULT '[]'::jsonb,
  fingerprint text,
  severity text DEFAULT 'medium',
  impact text DEFAULT 'medium',
  confidence numeric(5,4) DEFAULT 0,
  confidence_basis text DEFAULT 'evidence',
  explanation text,
  evidence jsonb DEFAULT '{}'::jsonb,
  affected_symbols jsonb DEFAULT '[]'::jsonb,
  suggested_solution text,
  dependencies jsonb DEFAULT '[]'::jsonb,
  risk text DEFAULT 'medium',
  created_at timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_repo_health_reco_run_rank ON repository_health_recommendations (run_id, priority_rank);
CREATE INDEX IF NOT EXISTS idx_repo_health_reco_fingerprint ON repository_health_recommendations (repo_id, user_id, fingerprint);

-- 6. Recommendation Lifecycle States Table
CREATE TABLE IF NOT EXISTS repository_health_recommendation_states (
  id uuid PRIMARY KEY,
  repo_id uuid NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
  user_id uuid NOT NULL,
  fingerprint text NOT NULL,
  category text,
  title text,
  status text NOT NULL DEFAULT 'OPEN',
  dismissed_reason text,
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_repo_health_reco_state_unique
  ON repository_health_recommendation_states (repo_id, user_id, fingerprint);

-- 7. Enable RLS and setup permissive policies for authenticated users and service_role
ALTER TABLE IF EXISTS repository_health_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS repository_health_category_scores ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS repository_health_findings ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS repository_health_recommendations ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS repository_health_recommendation_states ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
  -- repository_health_runs policies
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'repository_health_runs' AND policyname = 'service_role_all_runs') THEN
    CREATE POLICY service_role_all_runs ON repository_health_runs FOR ALL TO service_role USING (true) WITH CHECK (true);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'repository_health_runs' AND policyname = 'user_all_runs') THEN
    CREATE POLICY user_all_runs ON repository_health_runs FOR ALL TO authenticated USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);
  END IF;

  -- repository_health_category_scores policies
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'repository_health_category_scores' AND policyname = 'service_role_all_scores') THEN
    CREATE POLICY service_role_all_scores ON repository_health_category_scores FOR ALL TO service_role USING (true) WITH CHECK (true);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'repository_health_category_scores' AND policyname = 'user_all_scores') THEN
    CREATE POLICY user_all_scores ON repository_health_category_scores FOR ALL TO authenticated USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);
  END IF;

  -- repository_health_findings policies
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'repository_health_findings' AND policyname = 'service_role_all_findings') THEN
    CREATE POLICY service_role_all_findings ON repository_health_findings FOR ALL TO service_role USING (true) WITH CHECK (true);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'repository_health_findings' AND policyname = 'user_all_findings') THEN
    CREATE POLICY user_all_findings ON repository_health_findings FOR ALL TO authenticated USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);
  END IF;

  -- repository_health_recommendations policies
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'repository_health_recommendations' AND policyname = 'service_role_all_recs') THEN
    CREATE POLICY service_role_all_recs ON repository_health_recommendations FOR ALL TO service_role USING (true) WITH CHECK (true);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'repository_health_recommendations' AND policyname = 'user_all_recs') THEN
    CREATE POLICY user_all_recs ON repository_health_recommendations FOR ALL TO authenticated USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);
  END IF;

  -- repository_health_recommendation_states policies
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'repository_health_recommendation_states' AND policyname = 'service_role_all_states') THEN
    CREATE POLICY service_role_all_states ON repository_health_recommendation_states FOR ALL TO service_role USING (true) WITH CHECK (true);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'repository_health_recommendation_states' AND policyname = 'user_all_states') THEN
    CREATE POLICY user_all_states ON repository_health_recommendation_states FOR ALL TO authenticated USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);
  END IF;
END $$;
