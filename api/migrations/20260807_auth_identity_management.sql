-- Authentication and identity management schema (additive, non-breaking)

create extension if not exists pgcrypto;

create table if not exists public.auth_account_state (
  user_id uuid primary key,
  email_normalized text not null unique,
  account_status text not null default 'active',
  failed_login_attempts integer not null default 0,
  locked_until timestamptz,
  last_login_at timestamptz,
  last_logout_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  deleted_at timestamptz,
  constraint auth_account_state_status_ck check (account_status in ('active', 'disabled', 'locked', 'deleted'))
);

create index if not exists idx_auth_account_state_email on public.auth_account_state (email_normalized);
create index if not exists idx_auth_account_state_locked_until on public.auth_account_state (locked_until);

create table if not exists public.auth_identity_links (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null,
  email_normalized text not null,
  provider text not null,
  provider_user_id text,
  provider_email_verified boolean,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint auth_identity_links_provider_ck check (provider in ('password', 'github', 'google', 'azure', 'anonymous', 'other')),
  constraint auth_identity_links_user_provider_uq unique (user_id, provider),
  constraint auth_identity_links_provider_user_uq unique (provider, provider_user_id)
);

create index if not exists idx_auth_identity_links_email on public.auth_identity_links (email_normalized);
create index if not exists idx_auth_identity_links_user on public.auth_identity_links (user_id);

create table if not exists public.auth_login_history (
  id uuid primary key default gen_random_uuid(),
  user_id uuid,
  email_normalized text,
  provider text not null default 'password',
  auth_method text not null default 'interactive',
  session_id text,
  ip_address text,
  browser text,
  os text,
  device text,
  user_agent text,
  success boolean not null,
  failure_reason text,
  login_at timestamptz not null default now(),
  logout_at timestamptz,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists idx_auth_login_history_user_login on public.auth_login_history (user_id, login_at desc);
create index if not exists idx_auth_login_history_email_login on public.auth_login_history (email_normalized, login_at desc);
create index if not exists idx_auth_login_history_session on public.auth_login_history (session_id);
create index if not exists idx_auth_login_history_success on public.auth_login_history (success, login_at desc);

create table if not exists public.auth_audit_logs (
  id uuid primary key default gen_random_uuid(),
  user_id uuid,
  email_normalized text,
  action text not null,
  outcome text not null,
  provider text,
  ip_address text,
  browser text,
  os text,
  device text,
  user_agent text,
  reason text,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists idx_auth_audit_logs_user_created on public.auth_audit_logs (user_id, created_at desc);
create index if not exists idx_auth_audit_logs_email_created on public.auth_audit_logs (email_normalized, created_at desc);
create index if not exists idx_auth_audit_logs_action_created on public.auth_audit_logs (action, created_at desc);

alter table if exists public.auth_account_state enable row level security;
alter table if exists public.auth_identity_links enable row level security;
alter table if exists public.auth_login_history enable row level security;
alter table if exists public.auth_audit_logs enable row level security;
