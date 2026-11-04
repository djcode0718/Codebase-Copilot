-- ==============================================================================
-- 20261031_stabilization_schema_repair.sql
-- Consolidated Schema Repair Migration for Codebase-Copilot Demo Readiness
-- Target Database: Supabase PostgreSQL (public schema)
-- Safety: Fully transactional, non-destructive, idempotent (safe to rerun)
-- ==============================================================================

BEGIN;

-- Ensure UUID generation functions are present
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ------------------------------------------------------------------------------
-- 1. Missing columns on public.chats
-- ------------------------------------------------------------------------------
ALTER TABLE IF EXISTS public.chats
  ADD COLUMN IF NOT EXISTS session_type text DEFAULT 'quick_ask',
  ADD COLUMN IF NOT EXISTS is_pinned boolean DEFAULT false,
  ADD COLUMN IF NOT EXISTS is_favorite boolean DEFAULT false,
  ADD COLUMN IF NOT EXISTS is_archived boolean DEFAULT false,
  ADD COLUMN IF NOT EXISTS archived_at timestamptz,
  ADD COLUMN IF NOT EXISTS deleted_at timestamptz,
  ADD COLUMN IF NOT EXISTS last_message_at timestamptz,
  ADD COLUMN IF NOT EXISTS last_message_preview text,
  ADD COLUMN IF NOT EXISTS message_count integer DEFAULT 0,
  ADD COLUMN IF NOT EXISTS summary text;

-- ------------------------------------------------------------------------------
-- 2. Missing columns on public.messages
-- ------------------------------------------------------------------------------
ALTER TABLE IF EXISTS public.messages
  ADD COLUMN IF NOT EXISTS token_count integer,
  ADD COLUMN IF NOT EXISTS llm_provider text,
  ADD COLUMN IF NOT EXISTS llm_model text,
  ADD COLUMN IF NOT EXISTS metadata jsonb DEFAULT '{}'::jsonb,
  ADD COLUMN IF NOT EXISTS sequence integer;

-- Indexes for chats and messages
CREATE INDEX IF NOT EXISTS idx_chats_repo_updated ON public.chats (repo_id, updated_at desc);
CREATE INDEX IF NOT EXISTS idx_chats_repo_deleted ON public.chats (repo_id, deleted_at);
CREATE INDEX IF NOT EXISTS idx_chats_user_repo_type ON public.chats (user_id, repo_id, session_type);
CREATE INDEX IF NOT EXISTS idx_chats_repo_activity ON public.chats (repo_id, deleted_at, is_pinned desc, last_message_at desc, updated_at desc);
CREATE INDEX IF NOT EXISTS idx_messages_chat_created ON public.messages (chat_id, created_at asc);
CREATE INDEX IF NOT EXISTS idx_messages_chat_sequence ON public.messages (chat_id, sequence asc);

-- ------------------------------------------------------------------------------
-- 3. Saved Reports Table
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.saved_reports (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  repo_id uuid NOT NULL REFERENCES public.repositories(id) ON DELETE CASCADE,
  user_id uuid NOT NULL,
  report_type text NOT NULL,
  title text,
  content jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  deleted_at timestamptz
);

-- Safeguard for pre-existing tables missing newly added columns
ALTER TABLE IF EXISTS public.saved_reports
  ADD COLUMN IF NOT EXISTS repo_id uuid REFERENCES public.repositories(id) ON DELETE CASCADE,
  ADD COLUMN IF NOT EXISTS user_id uuid,
  ADD COLUMN IF NOT EXISTS report_type text,
  ADD COLUMN IF NOT EXISTS title text,
  ADD COLUMN IF NOT EXISTS content jsonb DEFAULT '{}'::jsonb,
  ADD COLUMN IF NOT EXISTS created_at timestamptz DEFAULT now(),
  ADD COLUMN IF NOT EXISTS updated_at timestamptz DEFAULT now(),
  ADD COLUMN IF NOT EXISTS deleted_at timestamptz;

CREATE INDEX IF NOT EXISTS idx_saved_reports_repo_user ON public.saved_reports (repo_id, user_id, updated_at desc);
CREATE INDEX IF NOT EXISTS idx_saved_reports_deleted ON public.saved_reports (deleted_at);

-- ------------------------------------------------------------------------------
-- 4. Repository Reviews Table
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.repository_reviews (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  repo_id uuid NOT NULL REFERENCES public.repositories(id) ON DELETE CASCADE,
  user_id uuid NOT NULL,
  target_type text NOT NULL DEFAULT 'file',
  status text NOT NULL DEFAULT 'completed',
  summary text NOT NULL DEFAULT '',
  findings jsonb NOT NULL DEFAULT '[]'::jsonb,
  changed_files jsonb NOT NULL DEFAULT '[]'::jsonb,
  commit_hash text NULL,
  request_payload jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);

-- Safeguard for pre-existing tables missing newly added columns
ALTER TABLE IF EXISTS public.repository_reviews
  ADD COLUMN IF NOT EXISTS repo_id uuid REFERENCES public.repositories(id) ON DELETE CASCADE,
  ADD COLUMN IF NOT EXISTS user_id uuid,
  ADD COLUMN IF NOT EXISTS target_type text DEFAULT 'file',
  ADD COLUMN IF NOT EXISTS status text DEFAULT 'completed',
  ADD COLUMN IF NOT EXISTS summary text DEFAULT '',
  ADD COLUMN IF NOT EXISTS findings jsonb DEFAULT '[]'::jsonb,
  ADD COLUMN IF NOT EXISTS changed_files jsonb DEFAULT '[]'::jsonb,
  ADD COLUMN IF NOT EXISTS commit_hash text,
  ADD COLUMN IF NOT EXISTS request_payload jsonb DEFAULT '{}'::jsonb,
  ADD COLUMN IF NOT EXISTS created_at timestamptz DEFAULT now();

CREATE INDEX IF NOT EXISTS idx_repository_reviews_repo_user_created ON public.repository_reviews (repo_id, user_id, created_at desc);
CREATE INDEX IF NOT EXISTS idx_repository_reviews_target_type ON public.repository_reviews (target_type);

-- ------------------------------------------------------------------------------
-- 5. Conversation Summaries Table
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.conversation_summaries (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  chat_id uuid NOT NULL REFERENCES public.chats(id) ON DELETE CASCADE,
  repo_id uuid NOT NULL REFERENCES public.repositories(id) ON DELETE CASCADE,
  user_id uuid NOT NULL,
  title text,
  executive_summary text,
  technical_summary text,
  key_decisions jsonb DEFAULT '[]'::jsonb,
  action_items jsonb DEFAULT '[]'::jsonb,
  risks_identified jsonb DEFAULT '[]'::jsonb,
  files_discussed jsonb DEFAULT '[]'::jsonb,
  services_discussed jsonb DEFAULT '[]'::jsonb,
  modules_discussed jsonb DEFAULT '[]'::jsonb,
  classes_discussed jsonb DEFAULT '[]'::jsonb,
  apis_discussed jsonb DEFAULT '[]'::jsonb,
  tags jsonb DEFAULT '[]'::jsonb,
  keywords jsonb DEFAULT '[]'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

-- Safeguard for pre-existing tables missing newly added columns
ALTER TABLE IF EXISTS public.conversation_summaries
  ADD COLUMN IF NOT EXISTS chat_id uuid REFERENCES public.chats(id) ON DELETE CASCADE,
  ADD COLUMN IF NOT EXISTS repo_id uuid REFERENCES public.repositories(id) ON DELETE CASCADE,
  ADD COLUMN IF NOT EXISTS user_id uuid,
  ADD COLUMN IF NOT EXISTS title text,
  ADD COLUMN IF NOT EXISTS executive_summary text,
  ADD COLUMN IF NOT EXISTS technical_summary text,
  ADD COLUMN IF NOT EXISTS key_decisions jsonb DEFAULT '[]'::jsonb,
  ADD COLUMN IF NOT EXISTS action_items jsonb DEFAULT '[]'::jsonb,
  ADD COLUMN IF NOT EXISTS risks_identified jsonb DEFAULT '[]'::jsonb,
  ADD COLUMN IF NOT EXISTS files_discussed jsonb DEFAULT '[]'::jsonb,
  ADD COLUMN IF NOT EXISTS services_discussed jsonb DEFAULT '[]'::jsonb,
  ADD COLUMN IF NOT EXISTS modules_discussed jsonb DEFAULT '[]'::jsonb,
  ADD COLUMN IF NOT EXISTS classes_discussed jsonb DEFAULT '[]'::jsonb,
  ADD COLUMN IF NOT EXISTS apis_discussed jsonb DEFAULT '[]'::jsonb,
  ADD COLUMN IF NOT EXISTS tags jsonb DEFAULT '[]'::jsonb,
  ADD COLUMN IF NOT EXISTS keywords jsonb DEFAULT '[]'::jsonb,
  ADD COLUMN IF NOT EXISTS created_at timestamptz DEFAULT now(),
  ADD COLUMN IF NOT EXISTS updated_at timestamptz DEFAULT now();

CREATE INDEX IF NOT EXISTS idx_conv_summary_repo_user ON public.conversation_summaries (repo_id, user_id, updated_at desc);
CREATE INDEX IF NOT EXISTS idx_conv_summary_chat ON public.conversation_summaries (chat_id);

-- ------------------------------------------------------------------------------
-- 6. Conversation Tags Table
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.conversation_tags (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  chat_id uuid NOT NULL REFERENCES public.chats(id) ON DELETE CASCADE,
  tag text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

-- Safeguard for pre-existing tables missing newly added columns
ALTER TABLE IF EXISTS public.conversation_tags
  ADD COLUMN IF NOT EXISTS chat_id uuid REFERENCES public.chats(id) ON DELETE CASCADE,
  ADD COLUMN IF NOT EXISTS tag text,
  ADD COLUMN IF NOT EXISTS created_at timestamptz DEFAULT now();

CREATE INDEX IF NOT EXISTS idx_conv_tags_chat ON public.conversation_tags (chat_id);
CREATE INDEX IF NOT EXISTS idx_conv_tags_tag ON public.conversation_tags (tag);

-- ------------------------------------------------------------------------------
-- 7. Attachments Table
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.attachments (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  chat_id uuid NOT NULL REFERENCES public.chats(id) ON DELETE CASCADE,
  user_id uuid NOT NULL,
  filename text NOT NULL,
  storage_path text NOT NULL,
  mime_type text,
  file_size bigint,
  created_at timestamptz NOT NULL DEFAULT now(),
  deleted_at timestamptz
);

-- Safeguard for pre-existing tables missing newly added columns
ALTER TABLE IF EXISTS public.attachments
  ADD COLUMN IF NOT EXISTS chat_id uuid REFERENCES public.chats(id) ON DELETE CASCADE,
  ADD COLUMN IF NOT EXISTS user_id uuid,
  ADD COLUMN IF NOT EXISTS filename text,
  ADD COLUMN IF NOT EXISTS storage_path text,
  ADD COLUMN IF NOT EXISTS mime_type text,
  ADD COLUMN IF NOT EXISTS file_size bigint,
  ADD COLUMN IF NOT EXISTS created_at timestamptz DEFAULT now(),
  ADD COLUMN IF NOT EXISTS deleted_at timestamptz;

CREATE INDEX IF NOT EXISTS idx_attachments_chat ON public.attachments (chat_id, deleted_at);
CREATE INDEX IF NOT EXISTS idx_attachments_user ON public.attachments (user_id);

-- ------------------------------------------------------------------------------
-- 8. Exports Table
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.exports (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  repo_id uuid NOT NULL REFERENCES public.repositories(id) ON DELETE CASCADE,
  user_id uuid NOT NULL,
  format text NOT NULL,
  scope text NOT NULL,
  export_meta jsonb DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);

-- Safeguard for pre-existing tables missing newly added columns
ALTER TABLE IF EXISTS public.exports
  ADD COLUMN IF NOT EXISTS repo_id uuid REFERENCES public.repositories(id) ON DELETE CASCADE,
  ADD COLUMN IF NOT EXISTS user_id uuid,
  ADD COLUMN IF NOT EXISTS format text,
  ADD COLUMN IF NOT EXISTS scope text,
  ADD COLUMN IF NOT EXISTS export_meta jsonb DEFAULT '{}'::jsonb,
  ADD COLUMN IF NOT EXISTS created_at timestamptz DEFAULT now();

CREATE INDEX IF NOT EXISTS idx_exports_repo_user ON public.exports (repo_id, user_id, created_at desc);

-- ==============================================================================
-- Row-Level Security (RLS) Enablement & Strict User-Isolation Policies
-- ==============================================================================

ALTER TABLE IF EXISTS public.saved_reports ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.repository_reviews ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.conversation_summaries ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.conversation_tags ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.attachments ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.exports ENABLE ROW LEVEL SECURITY;

-- ------------------------------------------------------------------------------
-- saved_reports policies
-- ------------------------------------------------------------------------------
DROP POLICY IF EXISTS "Users can view own saved reports" ON public.saved_reports;
CREATE POLICY "Users can view own saved reports" ON public.saved_reports
  FOR SELECT TO authenticated
  USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can insert own saved reports" ON public.saved_reports;
CREATE POLICY "Users can insert own saved reports" ON public.saved_reports
  FOR INSERT TO authenticated
  WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can update own saved reports" ON public.saved_reports;
CREATE POLICY "Users can update own saved reports" ON public.saved_reports
  FOR UPDATE TO authenticated
  USING (auth.uid() = user_id)
  WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can delete own saved reports" ON public.saved_reports;
CREATE POLICY "Users can delete own saved reports" ON public.saved_reports
  FOR DELETE TO authenticated
  USING (auth.uid() = user_id);

-- ------------------------------------------------------------------------------
-- repository_reviews policies
-- ------------------------------------------------------------------------------
DROP POLICY IF EXISTS "Users can view own repository reviews" ON public.repository_reviews;
CREATE POLICY "Users can view own repository reviews" ON public.repository_reviews
  FOR SELECT TO authenticated
  USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can insert own repository reviews" ON public.repository_reviews;
CREATE POLICY "Users can insert own repository reviews" ON public.repository_reviews
  FOR INSERT TO authenticated
  WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can update own repository reviews" ON public.repository_reviews;
CREATE POLICY "Users can update own repository reviews" ON public.repository_reviews
  FOR UPDATE TO authenticated
  USING (auth.uid() = user_id)
  WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can delete own repository reviews" ON public.repository_reviews;
CREATE POLICY "Users can delete own repository reviews" ON public.repository_reviews
  FOR DELETE TO authenticated
  USING (auth.uid() = user_id);

-- ------------------------------------------------------------------------------
-- attachments policies
-- Strict ownership: Requires BOTH attachments.user_id = auth.uid() AND
-- chat ownership (chats.user_id = auth.uid()).
-- Both USING and WITH CHECK are enforced on UPDATE to prevent ownership reassignment.
-- ------------------------------------------------------------------------------
DROP POLICY IF EXISTS "Users can view own attachments" ON public.attachments;
CREATE POLICY "Users can view own attachments" ON public.attachments
  FOR SELECT TO authenticated
  USING (
    user_id = auth.uid()
    AND EXISTS (
      SELECT 1 FROM public.chats
      WHERE chats.id = attachments.chat_id
        AND chats.user_id = auth.uid()
    )
  );

DROP POLICY IF EXISTS "Users can insert own attachments" ON public.attachments;
CREATE POLICY "Users can insert own attachments" ON public.attachments
  FOR INSERT TO authenticated
  WITH CHECK (
    user_id = auth.uid()
    AND EXISTS (
      SELECT 1 FROM public.chats
      WHERE chats.id = attachments.chat_id
        AND chats.user_id = auth.uid()
    )
  );

DROP POLICY IF EXISTS "Users can update own attachments" ON public.attachments;
CREATE POLICY "Users can update own attachments" ON public.attachments
  FOR UPDATE TO authenticated
  USING (
    user_id = auth.uid()
    AND EXISTS (
      SELECT 1 FROM public.chats
      WHERE chats.id = attachments.chat_id
        AND chats.user_id = auth.uid()
    )
  )
  WITH CHECK (
    user_id = auth.uid()
    AND EXISTS (
      SELECT 1 FROM public.chats
      WHERE chats.id = attachments.chat_id
        AND chats.user_id = auth.uid()
    )
  );

DROP POLICY IF EXISTS "Users can delete own attachments" ON public.attachments;
CREATE POLICY "Users can delete own attachments" ON public.attachments
  FOR DELETE TO authenticated
  USING (
    user_id = auth.uid()
    AND EXISTS (
      SELECT 1 FROM public.chats
      WHERE chats.id = attachments.chat_id
        AND chats.user_id = auth.uid()
    )
  );

-- ------------------------------------------------------------------------------
-- conversation_summaries policies
-- ------------------------------------------------------------------------------
DROP POLICY IF EXISTS "Users can view own summaries" ON public.conversation_summaries;
CREATE POLICY "Users can view own summaries" ON public.conversation_summaries
  FOR SELECT TO authenticated
  USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can insert own summaries" ON public.conversation_summaries;
CREATE POLICY "Users can insert own summaries" ON public.conversation_summaries
  FOR INSERT TO authenticated
  WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can update own summaries" ON public.conversation_summaries;
CREATE POLICY "Users can update own summaries" ON public.conversation_summaries
  FOR UPDATE TO authenticated
  USING (auth.uid() = user_id)
  WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can delete own summaries" ON public.conversation_summaries;
CREATE POLICY "Users can delete own summaries" ON public.conversation_summaries
  FOR DELETE TO authenticated
  USING (auth.uid() = user_id);

-- ------------------------------------------------------------------------------
-- conversation_tags policies (tied strictly to chat ownership)
-- ------------------------------------------------------------------------------
DROP POLICY IF EXISTS "Users can view own chat tags" ON public.conversation_tags;
CREATE POLICY "Users can view own chat tags" ON public.conversation_tags
  FOR SELECT TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM public.chats
      WHERE chats.id = conversation_tags.chat_id
        AND chats.user_id = auth.uid()
    )
  );

DROP POLICY IF EXISTS "Users can insert own chat tags" ON public.conversation_tags;
CREATE POLICY "Users can insert own chat tags" ON public.conversation_tags
  FOR INSERT TO authenticated
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM public.chats
      WHERE chats.id = conversation_tags.chat_id
        AND chats.user_id = auth.uid()
    )
  );

DROP POLICY IF EXISTS "Users can delete own chat tags" ON public.conversation_tags;
CREATE POLICY "Users can delete own chat tags" ON public.conversation_tags
  FOR DELETE TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM public.chats
      WHERE chats.id = conversation_tags.chat_id
        AND chats.user_id = auth.uid()
    )
  );

-- ------------------------------------------------------------------------------
-- exports policies
-- ------------------------------------------------------------------------------
DROP POLICY IF EXISTS "Users can view own exports" ON public.exports;
CREATE POLICY "Users can view own exports" ON public.exports
  FOR SELECT TO authenticated
  USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can insert own exports" ON public.exports;
CREATE POLICY "Users can insert own exports" ON public.exports
  FOR INSERT TO authenticated
  WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can delete own exports" ON public.exports;
CREATE POLICY "Users can delete own exports" ON public.exports
  FOR DELETE TO authenticated
  USING (auth.uid() = user_id);

-- ------------------------------------------------------------------------------
-- Service-Role Bypass Policies (Explicitly restricted to service_role)
-- ------------------------------------------------------------------------------
DROP POLICY IF EXISTS "service_role_all_saved_reports" ON public.saved_reports;
CREATE POLICY "service_role_all_saved_reports" ON public.saved_reports
  FOR ALL TO service_role USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS "service_role_all_repository_reviews" ON public.repository_reviews;
CREATE POLICY "service_role_all_repository_reviews" ON public.repository_reviews
  FOR ALL TO service_role USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS "service_role_all_conversation_summaries" ON public.conversation_summaries;
CREATE POLICY "service_role_all_conversation_summaries" ON public.conversation_summaries
  FOR ALL TO service_role USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS "service_role_all_conversation_tags" ON public.conversation_tags;
CREATE POLICY "service_role_all_conversation_tags" ON public.conversation_tags
  FOR ALL TO service_role USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS "service_role_all_attachments" ON public.attachments;
CREATE POLICY "service_role_all_attachments" ON public.attachments
  FOR ALL TO service_role USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS "service_role_all_exports" ON public.exports;
CREATE POLICY "service_role_all_exports" ON public.exports
  FOR ALL TO service_role USING (true) WITH CHECK (true);

-- ------------------------------------------------------------------------------
-- Least-Privilege Grants
-- Authenticated users receive only required DML operations.
-- Service role receives administrative access for trusted background services.
-- Anon role receives no permissions.
-- ------------------------------------------------------------------------------
REVOKE ALL ON TABLE public.saved_reports FROM anon;
REVOKE ALL ON TABLE public.repository_reviews FROM anon;
REVOKE ALL ON TABLE public.conversation_summaries FROM anon;
REVOKE ALL ON TABLE public.conversation_tags FROM anon;
REVOKE ALL ON TABLE public.attachments FROM anon;
REVOKE ALL ON TABLE public.exports FROM anon;

GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.saved_reports TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.repository_reviews TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.conversation_summaries TO authenticated;
GRANT SELECT, INSERT, DELETE ON TABLE public.conversation_tags TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.attachments TO authenticated;
GRANT SELECT, INSERT, DELETE ON TABLE public.exports TO authenticated;

GRANT ALL ON TABLE public.saved_reports TO service_role;
GRANT ALL ON TABLE public.repository_reviews TO service_role;
GRANT ALL ON TABLE public.conversation_summaries TO service_role;
GRANT ALL ON TABLE public.conversation_tags TO service_role;
GRANT ALL ON TABLE public.attachments TO service_role;
GRANT ALL ON TABLE public.exports TO service_role;

COMMIT;
