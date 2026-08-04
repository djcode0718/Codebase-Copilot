'use client';

import { useEffect, useMemo, useState, useSyncExternalStore } from 'react';
import { usePathname } from 'next/navigation';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import Sidebar from '@/components/layout/Sidebar';
import Topbar from '@/components/layout/Topbar';
import { listRepos } from '@/lib/api';
import { createClient } from '@/lib/supabase/client';
import { cn } from '@/lib/utils';
import type { Repo } from '@/lib/types';

const SHELL_PREFIXES = ['/dashboard', '/repo', '/settings'];
const REPOS_CACHE_KEY = 'codebase-copilot.repos.cache.v1';

function isShellRoute(pathname: string) {
  return SHELL_PREFIXES.some((prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`));
}

function readCachedRepos(): Repo[] {
  try {
    const raw = window.localStorage.getItem(REPOS_CACHE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as Repo[];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

export default function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const showShell = isShellRoute(pathname);
  const supabase = useMemo(() => createClient(), []);
  const queryClient = useQueryClient();
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);
  const isHydrated = useSyncExternalStore(
    () => () => {},
    () => true,
    () => false
  );

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
    queryKey: ['repos'],
    queryFn: async () => listRepos(token),
    staleTime: 20_000,
    refetchOnWindowFocus: false,
    refetchOnMount: false,
    placeholderData: (prev) => prev,
    enabled: showShell && Boolean(token),
  });

  useEffect(() => {
    if (!showShell || !isHydrated) return;
    const hasCached = (queryClient.getQueryData<Repo[]>(['repos']) ?? []).length > 0;
    if (hasCached) return;

    const localCached = readCachedRepos();
    if (localCached.length > 0) {
      queryClient.setQueryData(['repos'], localCached);
    }
  }, [isHydrated, queryClient, showShell]);

  useEffect(() => {
    if (!showShell || repos.length === 0) return;
    try {
      window.localStorage.setItem(REPOS_CACHE_KEY, JSON.stringify(repos));
    } catch {
      // ignore storage errors
    }
  }, [repos, showShell]);

  if (!showShell) {
    return <>{children}</>;
  }

  return (
    <div className={cn('min-h-screen bg-background text-foreground')}>
      <div className="flex min-h-screen min-w-0">
        <Sidebar
          repos={isHydrated ? repos : []}
          userEmail={userEmail}
          mobileOpen={mobileSidebarOpen}
          onMobileClose={() => setMobileSidebarOpen(false)}
        />
        <div className="flex min-h-screen min-w-0 flex-1 flex-col">
          <Topbar
            userEmail={userEmail}
            repoCount={isHydrated ? repos.length : 0}
            onToggleSidebar={() => setMobileSidebarOpen((prev) => !prev)}
          />
          <main className="min-h-0 flex-1 px-4 py-5 sm:px-6 lg:px-8">
            <div className="mx-auto flex w-full max-w-[1600px] min-w-0 flex-col gap-6">
              {children}
            </div>
          </main>
        </div>
      </div>
    </div>
  );
}
