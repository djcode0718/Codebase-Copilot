-- Additive migration for health analysis context and recommendation lifecycle tracking.
-- Backward compatible: no destructive changes.

alter table if exists repository_health_runs
  add column if not exists analysis_context jsonb default '{}'::jsonb;

alter table if exists repository_health_recommendations
  add column if not exists fingerprint text,
  add column if not exists severity text default 'medium',
  add column if not exists impact text default 'medium',
  add column if not exists confidence numeric(5,4) default 0,
  add column if not exists confidence_basis text default 'evidence',
  add column if not exists explanation text,
  add column if not exists evidence jsonb default '{}'::jsonb,
  add column if not exists affected_symbols jsonb default '[]'::jsonb,
  add column if not exists suggested_solution text,
  add column if not exists dependencies jsonb default '[]'::jsonb,
  add column if not exists risk text default 'medium';

create index if not exists idx_repo_health_reco_fingerprint
  on repository_health_recommendations (repo_id, user_id, fingerprint);

create table if not exists repository_health_recommendation_states (
  id uuid primary key,
  repo_id uuid not null references repositories(id) on delete cascade,
  user_id uuid not null,
  fingerprint text not null,
  category text,
  title text,
  status text not null default 'OPEN',
  dismissed_reason text,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

create unique index if not exists idx_repo_health_reco_state_unique
  on repository_health_recommendation_states (repo_id, user_id, fingerprint);

alter table if exists repository_health_recommendation_states enable row level security;
