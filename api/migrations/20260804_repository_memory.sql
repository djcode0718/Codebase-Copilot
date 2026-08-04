-- Repository Memory & Conversation Intelligence migration
-- Compatible with PostgreSQL / Supabase

alter table if exists chats
  add column if not exists session_type text default 'quick_ask',
  add column if not exists is_pinned boolean default false,
  add column if not exists is_favorite boolean default false,
  add column if not exists is_archived boolean default false,
  add column if not exists archived_at timestamptz,
  add column if not exists deleted_at timestamptz,
  add column if not exists summary text;

create index if not exists idx_chats_repo_updated on chats (repo_id, updated_at desc);
create index if not exists idx_chats_repo_deleted on chats (repo_id, deleted_at);
create index if not exists idx_chats_user_repo_type on chats (user_id, repo_id, session_type);

create table if not exists conversation_summaries (
  id uuid primary key,
  chat_id uuid not null references chats(id) on delete cascade,
  repo_id uuid not null references repositories(id) on delete cascade,
  user_id uuid not null,
  title text,
  executive_summary text,
  technical_summary text,
  key_decisions jsonb default '[]'::jsonb,
  action_items jsonb default '[]'::jsonb,
  risks_identified jsonb default '[]'::jsonb,
  files_discussed jsonb default '[]'::jsonb,
  services_discussed jsonb default '[]'::jsonb,
  modules_discussed jsonb default '[]'::jsonb,
  classes_discussed jsonb default '[]'::jsonb,
  apis_discussed jsonb default '[]'::jsonb,
  tags jsonb default '[]'::jsonb,
  keywords jsonb default '[]'::jsonb,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

create index if not exists idx_conv_summary_repo_user on conversation_summaries (repo_id, user_id, updated_at desc);
create index if not exists idx_conv_summary_chat on conversation_summaries (chat_id);

create table if not exists conversation_tags (
  id uuid primary key,
  chat_id uuid not null references chats(id) on delete cascade,
  tag text not null,
  created_at timestamptz default now()
);

create index if not exists idx_conv_tags_chat on conversation_tags (chat_id);
create index if not exists idx_conv_tags_tag on conversation_tags (tag);

create table if not exists conversation_embeddings (
  id uuid primary key,
  chat_id uuid not null references chats(id) on delete cascade,
  repo_id uuid not null references repositories(id) on delete cascade,
  user_id uuid not null,
  source_type text not null,
  source_id text,
  embedding vector(1536),
  metadata jsonb default '{}'::jsonb,
  created_at timestamptz default now()
);

create table if not exists attachments (
  id uuid primary key,
  chat_id uuid not null references chats(id) on delete cascade,
  user_id uuid not null,
  filename text not null,
  storage_path text not null,
  mime_type text,
  file_size bigint,
  created_at timestamptz default now(),
  deleted_at timestamptz
);

create table if not exists exports (
  id uuid primary key,
  repo_id uuid not null references repositories(id) on delete cascade,
  user_id uuid not null,
  format text not null,
  scope text not null,
  export_meta jsonb default '{}'::jsonb,
  created_at timestamptz default now()
);

create table if not exists saved_reports (
  id uuid primary key,
  repo_id uuid not null references repositories(id) on delete cascade,
  user_id uuid not null,
  report_type text not null,
  title text,
  content jsonb not null,
  created_at timestamptz default now(),
  updated_at timestamptz default now(),
  deleted_at timestamptz
);

-- Optional full-text search acceleration
create extension if not exists pg_trgm;
create index if not exists idx_messages_content_trgm on messages using gin (content gin_trgm_ops);
create index if not exists idx_chats_title_trgm on chats using gin (title gin_trgm_ops);

-- RLS policy examples (apply if your project enforces RLS at table level)
alter table if exists conversation_summaries enable row level security;
alter table if exists conversation_tags enable row level security;
alter table if exists attachments enable row level security;
alter table if exists exports enable row level security;
alter table if exists saved_reports enable row level security;

