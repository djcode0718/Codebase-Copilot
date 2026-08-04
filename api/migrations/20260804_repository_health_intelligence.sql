-- Repository Health Intelligence Engine schema
-- PostgreSQL / Supabase compatible

create table if not exists repository_health_runs (
  id uuid primary key,
  repo_id uuid not null references repositories(id) on delete cascade,
  user_id uuid not null,
  repository_health int not null,
  grade text not null,
  status text not null,
  trend int default 0,
  repository_size text,
  language_detection jsonb default '[]'::jsonb,
  framework_detection jsonb default '[]'::jsonb,
  executive_summary text,
  strengths jsonb default '[]'::jsonb,
  weaknesses jsonb default '[]'::jsonb,
  critical_risks jsonb default '[]'::jsonb,
  architecture_risks jsonb default '[]'::jsonb,
  security_risks jsonb default '[]'::jsonb,
  performance_risks jsonb default '[]'::jsonb,
  recommended_sprint jsonb default '[]'::jsonb,
  improved_categories jsonb default '[]'::jsonb,
  declining_categories jsonb default '[]'::jsonb,
  new_risks jsonb default '[]'::jsonb,
  resolved_risks jsonb default '[]'::jsonb,
  benchmark jsonb default '{}'::jsonb,
  created_at timestamptz default now()
);

create index if not exists idx_repo_health_runs_repo_time on repository_health_runs (repo_id, created_at desc);
create index if not exists idx_repo_health_runs_user_repo on repository_health_runs (user_id, repo_id, created_at desc);

create table if not exists repository_health_category_scores (
  id uuid primary key,
  run_id uuid not null references repository_health_runs(id) on delete cascade,
  repo_id uuid not null references repositories(id) on delete cascade,
  user_id uuid not null,
  category text not null,
  score int not null,
  grade text not null,
  trend int default 0,
  explanation text,
  detected_problems jsonb default '[]'::jsonb,
  positive_findings jsonb default '[]'::jsonb,
  recommendations jsonb default '[]'::jsonb,
  affected_files jsonb default '[]'::jsonb,
  affected_modules jsonb default '[]'::jsonb,
  created_at timestamptz default now()
);

create index if not exists idx_repo_health_cat_run on repository_health_category_scores (run_id, category);
create index if not exists idx_repo_health_cat_repo on repository_health_category_scores (repo_id, category, created_at desc);

create table if not exists repository_health_findings (
  id uuid primary key,
  run_id uuid not null references repository_health_runs(id) on delete cascade,
  repo_id uuid not null references repositories(id) on delete cascade,
  user_id uuid not null,
  category text not null,
  finding_type text not null,
  severity text not null,
  title text not null,
  details text,
  evidence jsonb default '{}'::jsonb,
  recommendation text,
  affected_files jsonb default '[]'::jsonb,
  affected_modules jsonb default '[]'::jsonb,
  expected_score_gain int default 0,
  created_at timestamptz default now()
);

create index if not exists idx_repo_health_findings_run on repository_health_findings (run_id, category);
create index if not exists idx_repo_health_findings_severity on repository_health_findings (repo_id, severity, created_at desc);

create table if not exists repository_health_recommendations (
  id uuid primary key,
  run_id uuid not null references repository_health_runs(id) on delete cascade,
  repo_id uuid not null references repositories(id) on delete cascade,
  user_id uuid not null,
  priority_rank int not null,
  category text not null,
  title text not null,
  description text,
  estimated_effort text,
  expected_score_gain int default 0,
  impact_score numeric(10,2) default 0,
  action_items jsonb default '[]'::jsonb,
  affected_files jsonb default '[]'::jsonb,
  created_at timestamptz default now()
);

create index if not exists idx_repo_health_reco_run_rank on repository_health_recommendations (run_id, priority_rank);

alter table if exists repository_health_runs enable row level security;
alter table if exists repository_health_category_scores enable row level security;
alter table if exists repository_health_findings enable row level security;
alter table if exists repository_health_recommendations enable row level security;

