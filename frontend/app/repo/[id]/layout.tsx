/**
 * app/repo/[id]/layout.tsx — Repo layout with sidebar
 * Re-uses the dashboard sidebar so sidebar shows for all repo sub-pages.
 */
import { redirect } from 'next/navigation';
import { createServerSupabaseClient } from '@/lib/supabase/server';
import Sidebar from '@/components/layout/Sidebar';
import { listRepos } from '@/lib/api';
import type { Repo } from '@/lib/types';

export default async function RepoLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const supabase = await createServerSupabaseClient();
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) redirect('/auth/sign-in');

  const { data: { session } } = await supabase.auth.getSession();
  const token = session?.access_token ?? '';

  let repos: Repo[] = [];
  try {
    repos = token ? await listRepos(token) : [];
  } catch {
    repos = [];
  }

  return (
    <div className="flex min-h-screen">
      <Sidebar repos={repos} userEmail={user.email} />
      <main className="flex-1 overflow-hidden flex flex-col">
        {children}
      </main>
    </div>
  );
}
