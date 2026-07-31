'use client';

import { useMemo } from 'react';
import { usePathname } from 'next/navigation';
import { useQuery } from '@tanstack/react-query';
import Sidebar from '@/components/layout/Sidebar';
import Topbar from '@/components/layout/Topbar';
import { listRepos } from '@/lib/api';
import { createClient } from '@/lib/supabase/client';
import { cn } from '@/lib/utils';

const SHELL_PREFIXES = ['/dashboard', '/repo', '/settings'];

function isShellRoute(pathname: string) {
  return SHELL_PREFIXES.some((prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`));
}

export default function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const showShell = isShellRoute(pathname);
  const supabase = useMemo(() => createClient(), []);

  const { data: sessionData } = useQuery({
    queryKey: ['shell-session'],
    queryFn: async () => supabase.auth.getSession(),
    staleTime: 60_000,
    refetchOnWindowFocus: false,
    enabled: showShell,
  });

  const token = sessionData?.data.session?.access_token ?? '';
  const userEmail = sessionData?.data.session?.user?.email ?? undefined;

  const { data: repos = [] } = useQuery({
    queryKey: ['shell-repos', token],
    queryFn: async () => listRepos(token),
    staleTime: 30_000,
    refetchOnWindowFocus: false,
    enabled: showShell && Boolean(token),
  });

  if (!showShell) {
    return <>{children}</>;
  }

  return (
    <div className={cn('min-h-screen bg-background text-foreground')}>
      <div className="flex min-h-screen min-w-0">
        <Sidebar repos={repos} userEmail={userEmail} />
        <div className="flex min-h-screen min-w-0 flex-1 flex-col">
          <Topbar userEmail={userEmail} repoCount={repos.length} />
          <main className="min-h-0 flex-1 overflow-auto px-4 py-5 sm:px-6 lg:px-8">
            <div className="mx-auto flex w-full max-w-[1600px] min-w-0 flex-col gap-6">
              {children}
            </div>
          </main>
        </div>
      </div>
    </div>
  );
}

