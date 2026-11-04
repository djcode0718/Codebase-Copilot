"""Unit tests for the 20261031 stabilization schema repair migration."""

import re
from pathlib import Path


def test_stabilization_migration_syntax_and_safety_checks():
    migration_path = Path(__file__).resolve().parents[2] / "api" / "migrations" / "20261031_stabilization_schema_repair.sql"
    assert migration_path.exists(), f"Migration file missing at {migration_path}"

    content = migration_path.read_text(encoding="utf-8")
    assert content.strip(), "Migration file is empty"

    # 1. Transactional safety
    assert "BEGIN;" in content, "Migration must be wrapped in a transaction block (BEGIN)"
    assert "COMMIT;" in content, "Migration must end with COMMIT"

    # 2. Target tables presence
    target_tables = [
        "public.saved_reports",
        "public.repository_reviews",
        "public.conversation_summaries",
        "public.conversation_tags",
        "public.attachments",
        "public.exports",
    ]
    for table in target_tables:
        assert f"CREATE TABLE IF NOT EXISTS {table}" in content, f"Missing CREATE TABLE for {table}"
        # Pre-existing table compatibility: must also include ADD COLUMN IF NOT EXISTS
        assert f"ALTER TABLE IF EXISTS {table}" in content, f"Missing ALTER TABLE compatibility block for {table}"
        assert f"ENABLE ROW LEVEL SECURITY" in content, f"RLS not enabled for {table}"

    # 3. Chats and messages column additions
    assert "ALTER TABLE IF EXISTS public.chats" in content
    assert "ADD COLUMN IF NOT EXISTS session_type" in content
    assert "ALTER TABLE IF EXISTS public.messages" in content
    assert "ADD COLUMN IF NOT EXISTS token_count" in content

    # 4. Attachment RLS: Dual ownership check
    # Check that attachment SELECT requires both user_id = auth.uid() AND chat ownership
    assert "user_id = auth.uid()" in content
    assert "chats.id = attachments.chat_id" in content
    assert "chats.user_id = auth.uid()" in content

    # Check that attachment UPDATE specifies both USING and WITH CHECK
    attachment_update_match = re.search(
        r'CREATE POLICY "Users can update own attachments" ON public\.attachments\s+FOR UPDATE TO authenticated\s+USING \((.*?)\)\s+WITH CHECK \((.*?)\);',
        content,
        re.DOTALL,
    )
    assert attachment_update_match, "Attachment UPDATE policy must have both USING and WITH CHECK clauses"
    using_clause = attachment_update_match.group(1)
    with_check_clause = attachment_update_match.group(2)
    assert "user_id = auth.uid()" in using_clause
    assert "chats.user_id = auth.uid()" in using_clause
    assert "user_id = auth.uid()" in with_check_clause
    assert "chats.user_id = auth.uid()" in with_check_clause

    # 5. Least privilege grants: anon must be revoked, authenticated gets specific DML
    assert "REVOKE ALL ON TABLE public.attachments FROM anon;" in content
    assert "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.attachments TO authenticated;" in content
    assert "GRANT ALL ON TABLE public.attachments TO service_role;" in content
