-- Repository AI engineering review persistence

create table if not exists public.repository_reviews (
    id uuid primary key,
    repo_id uuid not null references public.repositories(id) on delete cascade,
    user_id uuid not null,
    target_type text not null,
    status text not null default 'completed',
    summary text not null default '',
    findings jsonb not null default '[]'::jsonb,
    changed_files jsonb not null default '[]'::jsonb,
    commit_hash text null,
    request_payload jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now()
);

create index if not exists idx_repository_reviews_repo_user_created
    on public.repository_reviews (repo_id, user_id, created_at desc);

create index if not exists idx_repository_reviews_target_type
    on public.repository_reviews (target_type);

alter table public.repository_reviews enable row level security;

