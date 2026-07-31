/**
 * app/repo/[id]/layout.tsx — Repo layout with sidebar
 * Re-uses the dashboard sidebar so sidebar shows for all repo sub-pages.
 */
import { redirect } from 'next/navigation';
import { createServerSupabaseClient } from '@/lib/supabase/server';

export default async function RepoLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const supabase = await createServerSupabaseClient();
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) redirect('/auth/sign-in');


  return (
    <>{children}</>
  );
}
