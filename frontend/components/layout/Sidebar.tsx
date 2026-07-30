'use client';
/**
 * components/layout/Sidebar.tsx
 * Persistent left sidebar: nav links, repo list shortcut, user avatar.
 * Collapses to icon-only on mobile via sheet.
 */
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { motion } from 'framer-motion';
import {
  LayoutDashboard,
  GitBranch,
  Settings,
  LogOut,
  Plus,
  ChevronRight,
  Terminal,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { createClient } from '@/lib/supabase/client';
import { toast } from 'sonner';
import type { Repo } from '@/lib/types';

const NAV = [
  { href: '/dashboard', icon: LayoutDashboard, label: 'Dashboard' },
  { href: '/settings', icon: Settings, label: 'Settings' },
];

interface SidebarProps {
  repos?: Repo[];
  userEmail?: string;
}

export default function Sidebar({ repos = [], userEmail }: SidebarProps) {
  const pathname = usePathname();
  const router = useRouter();
  const supabase = createClient();

  async function handleSignOut() {
    await supabase.auth.signOut();
    router.push('/auth/sign-in');
    router.refresh();
    toast.success('Signed out');
  }

  return (
    <aside className="w-60 min-h-screen bg-sidebar border-r border-sidebar-border flex flex-col">
      {/* Logo */}
      <div className="px-4 py-5 border-b border-sidebar-border">
        <Link href="/dashboard" className="flex items-center gap-2 group">
          <div className="w-7 h-7 bg-brand rounded-md flex items-center justify-center flex-shrink-0">
            <Terminal size={14} className="text-green-950" />
          </div>
          <span className="font-heading font-semibold text-sm tracking-tight truncate">
            Codebase Copilot
          </span>
        </Link>
      </div>

      {/* Main nav */}
      <nav className="p-2 space-y-0.5 border-b border-sidebar-border">
        {NAV.map((item) => {
          const active = pathname === item.href || pathname.startsWith(item.href + '/');
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                'flex items-center gap-2.5 px-2.5 py-2 rounded-lg text-sm font-medium transition-all duration-150 cursor-pointer group',
                active
                  ? 'bg-accent text-brand'
                  : 'text-sidebar-foreground/70 hover:bg-sidebar-accent hover:text-sidebar-foreground'
              )}
            >
              <item.icon size={16} className={active ? 'text-brand' : ''} />
              {item.label}
            </Link>
          );
        })}
      </nav>

      {/* Repos section */}
      <div className="flex-1 overflow-y-auto p-2 scrollbar-thin">
        <div className="flex items-center justify-between px-2.5 py-1.5 mb-1">
          <span className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
            Repositories
          </span>
          <Link
            href="/repo/new"
            className="text-muted-foreground hover:text-brand transition-colors cursor-pointer"
            aria-label="Index new repository"
          >
            <Plus size={14} />
          </Link>
        </div>

        {repos.length === 0 && (
          <p className="text-xs text-muted-foreground px-2.5 py-1">
            No repositories yet
          </p>
        )}

        {repos.map((repo) => {
          const isActive = pathname.startsWith(`/repo/${repo.id}`);
          return (
            <Link
              key={repo.id}
              href={repo.status === 'ready' ? `/repo/${repo.id}` : `/repo/${repo.id}/indexing`}
              className={cn(
                'flex items-center gap-2 px-2.5 py-2 rounded-lg text-xs transition-all duration-150 cursor-pointer group',
                isActive
                  ? 'bg-accent text-foreground'
                  : 'text-muted-foreground hover:bg-sidebar-accent hover:text-foreground'
              )}
            >
              <GitBranch size={12} className="flex-shrink-0" />
              <span className="truncate flex-1">{repo.name}</span>
              {/* Status dot */}
              <span
                className={cn('w-1.5 h-1.5 rounded-full flex-shrink-0', {
                  'bg-brand': repo.status === 'ready',
                  'bg-amber-400 animate-pulse': repo.status === 'indexing',
                  'bg-destructive': repo.status === 'failed',
                })}
              />
              {isActive && <ChevronRight size={10} className="text-brand" />}
            </Link>
          );
        })}
      </div>

      {/* User */}
      <div className="p-2 border-t border-sidebar-border">
        <div className="flex items-center gap-2 px-2.5 py-2">
          <div className="w-7 h-7 rounded-full bg-secondary flex items-center justify-center flex-shrink-0">
            <span className="text-xs font-medium">
              {userEmail?.[0]?.toUpperCase() ?? 'G'}
            </span>
          </div>
          <span className="text-xs text-muted-foreground truncate flex-1">
            {userEmail ?? 'Guest'}
          </span>
          <button
            onClick={handleSignOut}
            className="text-muted-foreground hover:text-destructive transition-colors cursor-pointer"
            aria-label="Sign out"
          >
            <LogOut size={14} />
          </button>
        </div>
      </div>
    </aside>
  );
}
