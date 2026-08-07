'use client';

import { useRef, useEffect, useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Command, Home, LayoutDashboard, LogOut, Menu, Plus, Search, Settings, Sparkles } from 'lucide-react';
import { Button } from '@/components/ui/button';
import Breadcrumbs from '@/components/layout/Breadcrumbs';
import { ThemeToggle } from '@/components/layout/ThemeToggle';
import { createClient } from '@/lib/supabase/client';
import { auditLogout } from '@/lib/auth-api';
import { toast } from 'sonner';
import { cn } from '@/lib/utils';

interface TopbarProps {
  userEmail?: string;
  repoCount?: number;
  onToggleSidebar?: () => void;
}

function openCommandPalette() {
  window.dispatchEvent(new Event('codebase:open-command-palette'));
}

export default function Topbar({ userEmail, repoCount = 0, onToggleSidebar }: TopbarProps) {
  const router = useRouter();
  const supabase = useMemo(() => createClient(), []);
  const initials = userEmail?.[0]?.toUpperCase() ?? 'G';
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) setUserMenuOpen(false);
    }
    if (userMenuOpen) document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [userMenuOpen]);

  async function handleSignOut() {
    const {
      data: { session },
    } = await supabase.auth.getSession();

    await auditLogout({
      token: session?.access_token,
      email: session?.user?.email,
      sessionId: session?.access_token?.slice(-16),
    }).catch(() => undefined);

    await supabase.auth.signOut();
    setUserMenuOpen(false);
    router.push('/auth/sign-in');
    router.refresh();
    toast.success('Signed out');
  }

  const userMenuItems = [
    { icon: Home,            label: 'Home',             onClick: () => { router.push('/'); setUserMenuOpen(false); }, danger: false },
    { icon: LayoutDashboard, label: 'Dashboard',        onClick: () => { router.push('/dashboard'); setUserMenuOpen(false); }, danger: false },
    { icon: Plus,            label: 'Index repository', onClick: () => { router.push('/dashboard'); setUserMenuOpen(false); }, danger: false },
    { icon: Settings,        label: 'Settings',         onClick: () => { router.push('/settings'); setUserMenuOpen(false); }, danger: false },
    { icon: LogOut,          label: 'Sign out',         onClick: handleSignOut, danger: true },
  ];

  return (
    <header className="sticky top-0 z-30 border-b border-border/60 bg-background/75 backdrop-blur-xl">
      <div className="flex items-center gap-3 px-4 py-3 sm:px-6 lg:px-8">
        <div className="flex items-center gap-2 md:hidden">
          <Button
            variant="outline"
            size="icon-sm"
            className="border-border/70"
            onClick={onToggleSidebar}
            aria-label="Open navigation"
          >
            <Menu size={14} />
          </Button>
        </div>

        <div className="min-w-0 flex-1">
          <Breadcrumbs />
          <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
            <span className="inline-flex items-center gap-1.5 rounded-full border border-border/70 bg-card/80 px-2.5 py-1 shadow-sm shadow-black/5">
              <Sparkles size={11} className="text-brand" />
              Enterprise workspace
            </span>
            <span className="inline-flex items-center rounded-full border border-border/70 bg-card/70 px-2.5 py-1">
              {repoCount} repositories indexed
            </span>
          </div>
        </div>

        {/* Desktop right-side actions */}
        <div className="hidden md:flex items-center gap-2">
          <ThemeToggle />
          {/* Home button */}
          <Button variant="outline" size="sm" className="border-border/70" onClick={() => router.push('/')}>
            <Home size={14} className="mr-2" />
            Home
          </Button>
          <Button variant="outline" size="sm" className="border-border/70" onClick={openCommandPalette}>
            <Search size={14} className="mr-2" />
            Search
            <span className="ml-2 rounded border border-border/70 px-1.5 py-0 text-[10px] text-muted-foreground">
              ⌘K
            </span>
          </Button>
          <Button variant="outline" size="sm" className="border-border/70" onClick={() => router.push('/dashboard')}>
            <Plus size={14} className="mr-2" />
            Index repo
          </Button>

          {/* User menu */}
          <div className="relative ml-1" ref={menuRef}>
            <button
              type="button"
              onClick={() => setUserMenuOpen((v) => !v)}
              className="flex items-center gap-2 rounded-full border border-border bg-card/80 px-3 py-1.5 text-xs shadow-sm shadow-black/5 hover:bg-accent transition-colors"
            >
              <div className="flex h-6 w-6 items-center justify-center rounded-full bg-brand/10 text-brand font-semibold">
                {initials}
              </div>
              <span className="max-w-[140px] truncate text-muted-foreground">{userEmail ?? 'Guest'}</span>
            </button>

            {userMenuOpen && (
              <div className="absolute right-0 top-full mt-2 min-w-[190px] rounded-2xl border border-border bg-popover shadow-xl shadow-black/20 py-1 z-50">
                <div className="px-3 py-1.5 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground border-b border-border/60 mb-1 truncate">
                  {userEmail ?? 'Guest'}
                </div>
                {userMenuItems.map(({ icon: Icon, label, onClick, danger }) => (
                  <button
                    key={label}
                    type="button"
                    onClick={onClick}
                    className={cn(
                      'flex w-full items-center gap-2.5 px-3 py-2 text-sm transition-colors hover:bg-accent',
                      danger ? 'text-destructive hover:text-destructive' : 'text-foreground/80 hover:text-foreground'
                    )}
                  >
                    <Icon size={14} className="flex-shrink-0" />
                    {label}
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Mobile right-side actions */}
        <div className="flex items-center gap-2 md:hidden">
          <ThemeToggle />
          <Button variant="outline" size="icon-sm" className="border-border/70" onClick={openCommandPalette} aria-label="Open command palette">
            <Command size={14} />
          </Button>
          <Button variant="outline" size="icon-sm" className="border-border/70" onClick={() => router.push('/dashboard')} aria-label="Index repository">
            <Plus size={14} />
          </Button>
          {/* Mobile user menu */}
          <div className="relative" ref={undefined}>
            <button
              type="button"
              onClick={() => setUserMenuOpen((v) => !v)}
              className="flex h-8 w-8 items-center justify-center rounded-full border border-border bg-brand/10 text-brand font-semibold text-xs"
              aria-label="User menu"
            >
              {initials}
            </button>
            {userMenuOpen && (
              <div className="absolute right-0 top-full mt-2 min-w-[190px] rounded-2xl border border-border bg-popover shadow-xl shadow-black/20 py-1 z-50">
                {userMenuItems.map(({ icon: Icon, label, onClick, danger }) => (
                  <button
                    key={label}
                    type="button"
                    onClick={onClick}
                    className={cn(
                      'flex w-full items-center gap-2.5 px-3 py-2 text-sm transition-colors hover:bg-accent',
                      danger ? 'text-destructive hover:text-destructive' : 'text-foreground/80 hover:text-foreground'
                    )}
                  >
                    <Icon size={14} className="flex-shrink-0" />
                    {label}
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </header>
  );
}
