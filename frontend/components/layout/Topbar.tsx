'use client';

import { useRouter } from 'next/navigation';
import { Command, Menu, Plus, Search, Sparkles } from 'lucide-react';
import { Button } from '@/components/ui/button';
import Breadcrumbs from '@/components/layout/Breadcrumbs';
import { ThemeToggle } from '@/components/layout/ThemeToggle';

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
  const initials = userEmail?.[0]?.toUpperCase() ?? 'G';

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

        <div className="hidden md:flex items-center gap-2">
          <ThemeToggle />
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
          <div className="ml-1 flex items-center gap-2 rounded-full border border-border bg-card/80 px-3 py-1.5 text-xs shadow-sm shadow-black/5">
            <div className="flex h-6 w-6 items-center justify-center rounded-full bg-brand/10 text-brand font-semibold">
              {initials}
            </div>
            <span className="max-w-[140px] truncate text-muted-foreground">{userEmail ?? 'Guest'}</span>
          </div>
        </div>

        <div className="flex items-center gap-2 md:hidden">
          <ThemeToggle />
          <Button variant="outline" size="icon-sm" className="border-border/70" onClick={openCommandPalette} aria-label="Open command palette">
            <Command size={14} />
          </Button>
          <Button variant="outline" size="icon-sm" className="border-border/70" onClick={() => router.push('/dashboard')} aria-label="Index repository">
            <Plus size={14} />
          </Button>
        </div>
      </div>
    </header>
  );
}
