'use client';
/**
 * components/layout/Sidebar.tsx
 * Persistent workspace navigation: collapsible shell, quick actions, recent repos, user controls.
 */
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { useEffect, useMemo, useSyncExternalStore } from 'react';
import {
  GitBranch,
  LayoutDashboard,
  LogOut,
  PanelLeftClose,
  PanelLeftOpen,
  Plus,
  Search,
  Settings,
  Sparkles,
  Terminal,
  Clock3,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { createClient } from '@/lib/supabase/client';
import { toast } from 'sonner';
import type { Repo } from '@/lib/types';
import { ThemeToggle } from '@/components/layout/ThemeToggle';

const NAV = [
  { href: '/dashboard', icon: LayoutDashboard, label: 'Dashboard' },
  { href: '/settings', icon: Settings, label: 'Settings' },
];

const STORAGE_KEY = 'codebase-copilot.sidebar.collapsed';

interface SidebarProps {
  repos?: Repo[];
  userEmail?: string;
  mobileOpen?: boolean;
  onMobileClose?: () => void;
}

function openCommandPalette() {
  window.dispatchEvent(new Event('codebase:open-command-palette'));
}

export default function Sidebar({
  repos = [],
  userEmail,
  mobileOpen = false,
  onMobileClose,
}: SidebarProps) {
  const pathname = usePathname();
  const router = useRouter();
  const supabase = useMemo(() => createClient(), []);
  const isHydrated = useSyncExternalStore(
    () => () => {},
    () => true,
    () => false
  );
  const collapsedStored = useSyncExternalStore(
    (onStoreChange) => {
      window.addEventListener('storage', onStoreChange);
      window.addEventListener('codebase-sidebar-collapsed-change', onStoreChange);
      return () => {
        window.removeEventListener('storage', onStoreChange);
        window.removeEventListener('codebase-sidebar-collapsed-change', onStoreChange);
      };
    },
    () => {
      try {
        return window.localStorage.getItem(STORAGE_KEY) === '1';
      } catch {
        return false;
      }
    },
    () => false
  );
  const collapsed = isHydrated ? collapsedStored : false;

  function setCollapsed(nextValue: boolean) {
    try {
      window.localStorage.setItem(STORAGE_KEY, nextValue ? '1' : '0');
    } catch {
      // ignore storage errors
    }

    window.dispatchEvent(new Event('codebase-sidebar-collapsed-change'));
  }

  useEffect(() => {
    if (mobileOpen) {
      document.body.style.overflow = 'hidden';
      return () => {
        document.body.style.overflow = '';
      };
    }

    document.body.style.overflow = '';
    return undefined;
  }, [mobileOpen]);

  function closeMobileIfOpen() {
    onMobileClose?.();
  }

  const sortedRepos = useMemo(
    () => [...repos].sort((a, b) => (b.created_at || '').localeCompare(a.created_at || '')),
    [repos]
  );
  const recentRepos = sortedRepos.slice(0, 5);

  async function handleSignOut() {
    await supabase.auth.signOut();
    closeMobileIfOpen();
    router.push('/auth/sign-in');
    router.refresh();
    toast.success('Signed out');
  }

  return (
    <>
      <div
        className={cn(
          'fixed inset-0 z-40 bg-black/35 backdrop-blur-[1px] transition-opacity md:hidden',
          mobileOpen ? 'opacity-100' : 'pointer-events-none opacity-0'
        )}
        onClick={closeMobileIfOpen}
        aria-hidden="true"
      />

      <aside
        className={cn(
          'fixed inset-y-0 left-0 z-50 flex h-screen flex-col border-r border-sidebar-border bg-sidebar/95 text-sidebar-foreground shadow-[0_0_0_1px_rgba(255,255,255,0.02),0_24px_80px_rgba(15,23,42,0.16)] backdrop-blur-xl transition-all duration-200 md:static md:z-auto md:translate-x-0',
          mobileOpen ? 'translate-x-0' : '-translate-x-full',
          collapsed ? 'w-20 max-w-20 md:w-20' : 'w-[18.5rem] max-w-[88vw] md:w-72'
        )}
      >
      {/* Brand + collapse */}
      <div
        className={cn(
          'flex items-center gap-2 border-b border-sidebar-border p-4',
          collapsed ? 'flex-col justify-center gap-3 px-2 py-3' : 'justify-between'
        )}
      >
        <Link
          href="/dashboard"
          onClick={closeMobileIfOpen}
          className={cn('flex items-center gap-2 group', collapsed && 'justify-center')}
          title="Codebase Copilot"
        >
          <div className="w-10 h-10 rounded-2xl bg-brand/15 border border-brand/20 flex items-center justify-center flex-shrink-0 shadow-lg shadow-brand/10">
            <Terminal size={15} className="text-brand" />
          </div>
          {!collapsed && (
            <div className="min-w-0">
              <span className="block font-heading font-semibold text-sm tracking-tight truncate">Codebase Copilot</span>
              <span className="block text-[11px] text-sidebar-foreground/60 truncate">Enterprise workspace</span>
            </div>
          )}
        </Link>

        <div className={cn('flex items-center gap-2', collapsed && 'flex-col')}>
          {!collapsed && <ThemeToggle className="hidden lg:inline-flex" />}
          <button
            type="button"
            onClick={() => setCollapsed(!collapsed)}
            className="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-sidebar-border bg-sidebar-accent/60 text-sidebar-foreground/70 hover:text-sidebar-foreground hover:bg-sidebar-accent transition-colors"
            aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          >
            {collapsed ? <PanelLeftOpen size={15} /> : <PanelLeftClose size={15} />}
          </button>
        </div>
      </div>

      {/* Quick actions */}
      <div className="border-b border-sidebar-border p-3 space-y-2">
        {!collapsed && (
          <div className="flex items-center gap-2 px-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-sidebar-foreground/55">
            <Sparkles size={12} />
            Quick actions
          </div>
        )}
        <div className={cn('grid gap-2', collapsed && 'place-items-center')}>
          <button
            type="button"
            onClick={() => {
              openCommandPalette();
              closeMobileIfOpen();
            }}
            className={cn(
              'flex items-center gap-2 rounded-2xl border border-sidebar-border bg-sidebar-accent/50 px-3 py-2.5 text-sm text-sidebar-foreground/80 hover:bg-sidebar-accent hover:text-sidebar-foreground transition-colors',
              collapsed && 'h-11 w-11 justify-center px-0'
            )}
            title="Search workspace (⌘K)"
          >
            <Search size={15} className="shrink-0" />
            {!collapsed && <span className="truncate">Search workspace</span>}
          </button>
          <button
            type="button"
            onClick={() => {
              closeMobileIfOpen();
              router.push('/dashboard');
            }}
            className={cn(
              'flex items-center gap-2 rounded-2xl bg-brand px-3 py-2.5 text-sm font-semibold text-green-950 hover:bg-green-400 transition-colors shadow-sm shadow-brand/10',
              collapsed && 'h-11 w-11 justify-center px-0'
            )}
            title="Index a repository"
          >
            <Plus size={15} className="shrink-0" />
            {!collapsed && <span className="truncate">Index repository</span>}
          </button>
        </div>
      </div>

      {/* Main nav */}
      <nav className="p-2 space-y-0.5 border-b border-sidebar-border">
        {NAV.map((item) => {
          const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
          return (
            <Link
              key={item.href}
              href={item.href}
              onClick={closeMobileIfOpen}
              className={cn(
                'flex items-center gap-2.5 rounded-2xl px-3 py-2.5 text-sm font-medium transition-all duration-150 group',
                collapsed && 'justify-center px-0',
                active
                  ? 'bg-brand/10 text-brand border border-brand/20 shadow-sm shadow-brand/5'
                  : 'text-sidebar-foreground/72 hover:bg-sidebar-accent hover:text-sidebar-foreground'
              )}
              title={item.label}
            >
              <item.icon size={16} className={active ? 'text-brand' : ''} />
              {!collapsed && <span>{item.label}</span>}
            </Link>
          );
        })}
      </nav>

      {/* Recent repositories */}
      <div className="flex-1 overflow-y-auto p-2 scrollbar-thin">
        {!collapsed && (
          <div className="flex items-center justify-between px-2.5 py-1.5 mb-1">
            <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
              Recent
            </span>
          </div>
        )}

        {recentRepos.length === 0 ? (
          <div className={cn('rounded-xl border border-dashed border-sidebar-border/80 bg-sidebar-accent/20 p-3', collapsed && 'text-center') }>
            {!collapsed ? (
              <>
                <p className="text-sm font-medium text-sidebar-foreground">No repositories yet</p>
                <p className="mt-1 text-xs text-sidebar-foreground/60">
                  Index a repository to populate the workspace and unlock chat.
                </p>
              </>
            ) : (
              <Clock3 size={15} className="mx-auto text-sidebar-foreground/55" />
            )}
          </div>
        ) : (
          <div className="space-y-3">
            {!collapsed && (
              <div className="px-2.5 text-[11px] font-semibold uppercase tracking-[0.18em] text-sidebar-foreground/55">
                Repositories
              </div>
            )}
            <div className="space-y-1">
              {recentRepos.map((repo) => {
                const isActive = pathname.startsWith(`/repo/${repo.id}`);
                const href = repo.status === 'ready' ? `/repo/${repo.id}` : `/repo/${repo.id}/indexing`;
                return (
                  <Link
                    key={repo.id}
                    href={href}
                    onClick={closeMobileIfOpen}
                    className={cn(
                      'flex items-center gap-2 rounded-2xl px-3 py-2.5 text-sm transition-all duration-150 group',
                      collapsed && 'justify-center px-0',
                      isActive
                        ? 'bg-sidebar-accent text-foreground border border-sidebar-border'
                        : 'text-sidebar-foreground/72 hover:bg-sidebar-accent hover:text-foreground'
                    )}
                    title={repo.name}
                  >
                    <GitBranch size={14} className="flex-shrink-0" />
                    {!collapsed && (
                      <div className="min-w-0 flex-1">
                        <div className="truncate text-sm font-medium">{repo.name}</div>
                        <div className="truncate text-[11px] text-sidebar-foreground/55">{repo.index_name}</div>
                      </div>
                    )}
                  </Link>
                );
              })}
            </div>
          </div>
        )}
      </div>

      {/* User */}
      <div className="border-t border-sidebar-border p-3">
        <div className={cn('flex items-center gap-2 rounded-2xl bg-sidebar-accent/35 px-3 py-2.5', collapsed && 'justify-center px-0')}>
          <div className="w-8 h-8 rounded-full bg-brand/10 flex items-center justify-center flex-shrink-0 border border-sidebar-border">
            <span className="text-xs font-semibold">
              {userEmail?.[0]?.toUpperCase() ?? 'G'}
            </span>
          </div>
          {!collapsed && (
            <div className="min-w-0 flex-1">
              <span className="block text-xs font-medium truncate">{userEmail ?? 'Guest'}</span>
              <span className="block text-[11px] text-sidebar-foreground/55 truncate">Workspace member</span>
            </div>
          )}
          <button
            onClick={handleSignOut}
            className={cn(
              'inline-flex h-8 w-8 items-center justify-center rounded-lg text-sidebar-foreground/70 hover:text-destructive hover:bg-destructive/10 transition-colors',
              collapsed && 'ml-0'
            )}
            aria-label="Sign out"
            title="Sign out"
          >
            <LogOut size={14} />
          </button>
        </div>
      </div>
    </aside>
    </>
  );
}
