/**
 * app/dashboard/layout.tsx — Dashboard shell with sidebar
 */
import { redirect } from 'next/navigation';
import { createServerSupabaseClient } from '@/lib/supabase/server';
import Sidebar from '@/components/layout/Sidebar';
import { listRepos } from '@/lib/api';
import type { Repo } from '@/lib/types';

export default async function DashboardLayout({
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
      <main className="flex-1 overflow-auto">
        {children}
      </main>
    </div>
  );
}
