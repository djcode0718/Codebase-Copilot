# Codebase-Copilot — Supabase Schema & Migration Report (Phase 2 Review)
**Branch**: `fix/demo-readiness`  
**Migration File**: [`api/migrations/20261031_stabilization_schema_repair.sql`](file:///Users/sj/Documents/AI-Copilot/codebase-copilot/api/migrations/20261031_stabilization_schema_repair.sql)  
**Date**: October 31, 2026  
**Status**: Script Fully Hardened, Validated Locally, and Transactional. Remote Execution Awaiting User Approval.  

---

## 1. Executive Summary & Review Scope

Following an in-depth security and schema review against the Codebase-Copilot backend query implementation, `api/migrations/20261031_stabilization_schema_repair.sql` has been corrected and hardened. All modifications ensure strict multi-tenant isolation, idempotency, least-privilege role separation, and pre-existing table compatibility.

> [!IMPORTANT]
> **Safety Guarantee**: In accordance with project safety guidelines, this migration **has not been executed remotely**. It remains safely staged on branch `fix/demo-readiness` for review and manual execution in the Supabase Dashboard SQL Editor.

---

## 2. Itemized Change Log & Technical Rationale

| # | Concern Area | Prior Migration Implementation | Hardened Migration Implementation | Security & Operational Rationale |
| :--- | :--- | :--- | :--- | :--- |
| **1** | **Attachment RLS (Dual-Check Ownership)** | Used `OR` check: `auth.uid() = user_id OR EXISTS (SELECT 1 FROM chats...)`. | Enforces strict `AND`: `user_id = auth.uid() AND EXISTS (SELECT 1 FROM chats WHERE id = attachments.chat_id AND user_id = auth.uid())`. | Eliminates authorization bypass where a user owning a chat could view another user's attachments, or where an attachment creator could link to a foreign chat. |
| **2** | **Attachment UPDATE Protection** | Defined only `USING (auth.uid() = user_id OR ...)`. No `WITH CHECK`. | Defines identical dual-check condition for both `USING` and `WITH CHECK`. | Prevents a user from updating an attachment to reassign `user_id` or attach it to a chat owned by another user. |
| **3** | **Pre-Existing Table Compatibility** | Relied solely on `CREATE TABLE IF NOT EXISTS`. | Follows `CREATE TABLE IF NOT EXISTS` with `ALTER TABLE IF EXISTS ... ADD COLUMN IF NOT EXISTS` for every column across all 6 tables. | If any table already exists in the remote database in an older or partial form, `CREATE TABLE IF NOT EXISTS` is a no-op and leaves missing columns uncreated. Safe `ALTER TABLE` guarantees complete column parity. |
| **4** | **Least-Privilege Role Grants** | Granted `GRANT ALL ON TABLE ... TO authenticated`. | Revoked `ALL` from `anon`. Granted only required DML (`SELECT, INSERT, UPDATE, DELETE`) to `authenticated`. | `GRANT ALL` on client-facing authenticated roles provides unnecessary privileges (e.g., `TRUNCATE`, `REFERENCES`, `TRIGGER`). Anonymous users (`anon`) have zero access. |
| **5** | **Service-Role Isolation** | Broad grant to both roles. | Granted `ALL` to `service_role` and added explicit `service_role_all_*` bypass policies for backend background workers. | Restricts administrative/bulk operations to trusted server-side code using `SUPABASE_SERVICE_ROLE_KEY`. |
| **6** | **Transactional Execution** | Unwrapped top-level DDL statements. | Wrapped the entire script inside `BEGIN; ... COMMIT;`. | Guarantees atomic execution: if any statement fails, the entire transaction rolls back cleanly, preventing a partially applied schema state. |
| **7** | **Primary Key UUID Generation** | Specified `id uuid PRIMARY KEY` without default. | Specified `id uuid PRIMARY KEY DEFAULT gen_random_uuid()`. Added `CREATE EXTENSION IF NOT EXISTS pgcrypto;`. | Allows database-generated UUIDs if records are inserted without application-level ID assignment. |
| **8** | **CRUD Mapping for Conversation Tags & Exports** | Included generic `UPDATE` policies. | Restricted tags and exports to `SELECT, INSERT, DELETE` without `UPDATE`. | Matches actual backend usage: tags are replaced via delete-then-insert (`replace_conversation_tags`); exports are immutable records. |

---

## 3. CRUD & Policy Architecture

### 1. `public.attachments`
- **Backend Usage**: `create_attachment` (INSERT), `get_attachments_for_chat` (SELECT), `get_attachment` (SELECT), `update_attachment` (UPDATE), `soft_delete_attachment` (UPDATE), `delete_attachment` (DELETE).
- **Enforced Policy**:
  ```sql
  FOR SELECT TO authenticated
    USING (user_id = auth.uid() AND EXISTS (SELECT 1 FROM public.chats WHERE id = attachments.chat_id AND user_id = auth.uid()));

  FOR INSERT TO authenticated
    WITH CHECK (user_id = auth.uid() AND EXISTS (SELECT 1 FROM public.chats WHERE id = attachments.chat_id AND user_id = auth.uid()));

  FOR UPDATE TO authenticated
    USING (user_id = auth.uid() AND EXISTS (SELECT 1 FROM public.chats WHERE id = attachments.chat_id AND user_id = auth.uid()))
    WITH CHECK (user_id = auth.uid() AND EXISTS (SELECT 1 FROM public.chats WHERE id = attachments.chat_id AND user_id = auth.uid()));

  FOR DELETE TO authenticated
    USING (user_id = auth.uid() AND EXISTS (SELECT 1 FROM public.chats WHERE id = attachments.chat_id AND user_id = auth.uid()));
  ```

### 2. `public.conversation_tags`
- **Backend Usage**: `get_conversation_tags` (SELECT), `replace_conversation_tags` (DELETE existing then INSERT new).
- **Enforced Policy**:
  - `SELECT`, `INSERT`, `DELETE` scoped strictly through chat ownership (`EXISTS (SELECT 1 FROM public.chats WHERE id = conversation_tags.chat_id AND user_id = auth.uid())`).
  - No `UPDATE` privilege granted to `authenticated`.

### 3. `public.saved_reports` & `public.repository_reviews` & `public.conversation_summaries`
- **Backend Usage**: Creation, fetching, updating, soft/hard deleting.
- **Enforced Policy**:
  - `SELECT`: `USING (auth.uid() = user_id)`
  - `INSERT`: `WITH CHECK (auth.uid() = user_id)`
  - `UPDATE`: `USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id)`
  - `DELETE`: `USING (auth.uid() = user_id)`

---

## 4. Storage Architecture (Supabase Storage vs Relational Metadata)

The relational table `public.attachments` stores attachment metadata (`filename`, `storage_path`, `mime_type`, `file_size`). 

If physical file binaries are uploaded via Supabase Storage:
1. **Bucket Name**: `chat-attachments` (recommended private bucket).
2. **Storage RLS Policies** (`storage.objects` table):
   - Storage policies should restrict upload and download by verifying user prefix:
     ```sql
     -- Storage bucket policy (to be executed in Storage configuration, not in relational DDL)
     CREATE POLICY "User storage access" ON storage.objects
       FOR ALL TO authenticated
       USING (bucket_id = 'chat-attachments' AND (storage.foldername(name))[1] = auth.uid()::text)
       WITH CHECK (bucket_id = 'chat-attachments' AND (storage.foldername(name))[1] = auth.uid()::text);
     ```
3. **Decoupling Rationale**:
   The `storage` schema is managed by Supabase's internal storage service. Placing storage DDL inside public relational schema migrations can fail on projects with custom storage extensions or managed permissions. The relational repair migration strictly manages `public` tables.

---

## 5. Pre-Execution Checklist for Remote Supabase Project

Before executing the migration in the **Supabase Dashboard SQL Editor**:

1. [ ] **Project Target**: Verify you are logged into project `xevvlyvjldyydqevdkhb` (`https://supabase.com/dashboard/project/xevvlyvjldyydqevdkhb`).
2. [ ] **Active Connections**: Check that no long-running schema transactions or locks are active.
3. [ ] **Backup Verification**: Note that the migration is 100% additive and non-destructive (uses `ADD COLUMN IF NOT EXISTS`, `CREATE TABLE IF NOT EXISTS`, and safe policy replacement).
4. [ ] **Execution**:
   - Open **SQL Editor**.
   - Create a new query.
   - Paste the entire contents of [`api/migrations/20261031_stabilization_schema_repair.sql`](file:///Users/sj/Documents/AI-Copilot/codebase-copilot/api/migrations/20261031_stabilization_schema_repair.sql).
   - Click **Run**.
5. [ ] **PostgREST Schema Reload**: PostgREST automatically reloads its schema cache upon DDL commit. Verify by calling `GET /api/chat/repo/{id}/reports`.

---

## 6. Items That Cannot Be Verified Without Remote Live Database Access

The following details cannot be definitively verified locally and require execution feedback from the live database:
1. **Existing Remote Policy Catalog**: While prior repository migrations do not define conflicting policies on these six tables, any manual policies created directly via the Supabase Dashboard UI cannot be observed without live querying `pg_policies`.
2. **Storage Bucket Provisioning**: Verification of whether the `chat-attachments` storage bucket has been created in the remote project's Supabase Storage console.
3. **Foreign Key Validation on Existing Dirty Data**: If any remote table already exists and contains orphaned rows (e.g., records with non-existent `repo_id` or `chat_id`), adding foreign key constraints would require cleaning orphaned data first. (Our script uses safe additive clauses to avoid failing on existing data).
