'use client';

import { useEffect, useMemo, useState, useSyncExternalStore } from 'react';
import { usePathname } from 'next/navigation';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import Sidebar from '@/components/layout/Sidebar';
import Topbar from '@/components/layout/Topbar';
import { listRepos } from '@/lib/api';
import { createClient } from '@/lib/supabase/client';
import { getUserReposCacheKey, LEGACY_REPOS_CACHE_KEY } from '@/lib/auth-storage';
import { cn } from '@/lib/utils';
import type { Repo } from '@/lib/types';

const SHELL_PREFIXES = ['/dashboard', '/repo', '/settings'];

function isShellRoute(pathname: string) {
  return SHELL_PREFIXES.some((prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`));
}

function readCachedRepos(userId: string): Repo[] {
  if (!userId) return [];
  try {
    const raw = window.localStorage.getItem(getUserReposCacheKey(userId));
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

  // Keep shell session in sync immediately when auth state changes
  useEffect(() => {
    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, session) => {
      queryClient.setQueryData(['shell-session'], {
        data: { session },
        error: null,
      });
    });
    return () => subscription.unsubscribe();
  }, [queryClient, supabase]);

  const token = sessionData?.data.session?.access_token ?? '';
  const userEmail = sessionData?.data.session?.user?.email ?? undefined;
  const userId = sessionData?.data.session?.user?.id ?? '';

  const { data: repos = [] } = useQuery({
    queryKey: ['repos', userId],
    queryFn: async () => listRepos(token),
    staleTime: 20_000,
    refetchOnWindowFocus: false,
    refetchOnMount: false,
    placeholderData: (prev) => prev,
    enabled: showShell && Boolean(token) && Boolean(userId),
  });

  useEffect(() => {
    if (!showShell || !isHydrated || !userId) return;

    // Clean legacy global cache if present
    try {
      window.localStorage.removeItem(LEGACY_REPOS_CACHE_KEY);
    } catch {}

    const hasCached = (queryClient.getQueryData<Repo[]>(['repos', userId]) ?? []).length > 0;
    if (hasCached) return;

    const localCached = readCachedRepos(userId);
    if (localCached.length > 0) {
      queryClient.setQueryData(['repos', userId], localCached);
    }
  }, [isHydrated, queryClient, showShell, userId]);

  useEffect(() => {
    if (!showShell || !userId || repos.length === 0) return;
    try {
      window.localStorage.setItem(getUserReposCacheKey(userId), JSON.stringify(repos));
    } catch {
      // ignore storage errors
    }
  }, [repos, showShell, userId]);

  if (!showShell) {
    return <>{children}</>;
  }

  return (
    <div className={cn('min-h-screen bg-background text-foreground')}>
      <div className="flex min-h-screen min-w-0">
        <Sidebar
          repos={isHydrated && userId ? repos : []}
          userEmail={userEmail}
          userId={userId}
          mobileOpen={mobileSidebarOpen}
          onMobileClose={() => setMobileSidebarOpen(false)}
        />
        <div className="flex min-h-screen min-w-0 flex-1 flex-col">
          <Topbar
            userEmail={userEmail}
            repoCount={isHydrated && userId ? repos.length : 0}
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
