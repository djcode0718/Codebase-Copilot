'use client';

import * as React from 'react';
import { useRouter } from 'next/navigation';
import {
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandSeparator,
  CommandShortcut,
} from '@/components/ui/command';
import { listRepos } from '@/lib/api';
import { auditLogout } from '@/lib/auth-api';
import { createClient } from '@/lib/supabase/client';
import { getRepoWorkspaceHref } from '@/lib/repo-routing';
import type { Repo } from '@/lib/types';
import { FolderGit2, LayoutDashboard, LogOut, Plus, Search, Settings } from 'lucide-react';

const SORTED_RECENT_LIMIT = 5;

export function CommandPalette() {
  const [open, setOpen] = React.useState(false);
  const [repos, setRepos] = React.useState<Repo[]>([]);
  const [reposLoaded, setReposLoaded] = React.useState(false);
  const [reposLoading, setReposLoading] = React.useState(false);
  const router = useRouter();
  const supabase = React.useMemo(() => createClient(), []);

  React.useEffect(() => {
    const down = (e: KeyboardEvent) => {
      if (e.key === 'k' && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        setOpen((value) => !value);
      }
    };

    const openPalette = () => setOpen(true);

    document.addEventListener('keydown', down);
    window.addEventListener('codebase:open-command-palette', openPalette as EventListener);

    return () => {
      document.removeEventListener('keydown', down);
      window.removeEventListener('codebase:open-command-palette', openPalette as EventListener);
    };
  }, []);

  React.useEffect(() => {
    if (!open || reposLoaded || reposLoading) {
      return;
    }

    const fetchRepos = async () => {
      setReposLoading(true);
      try {
        const {
          data: { session },
        } = await supabase.auth.getSession();
        if (session?.access_token) {
          const data = await listRepos(session.access_token);
          setRepos(Array.isArray(data) ? data : []);
        }
      } catch (error) {
        console.error('Failed to fetch repos for command palette', error);
      } finally {
        setReposLoaded(true);
        setReposLoading(false);
      }
    };

    fetchRepos();
  }, [open, reposLoaded, reposLoading, supabase]);

  const runCommand = React.useCallback((command: () => unknown) => {
    setOpen(false);
    command();
  }, []);

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
    runCommand(() => {
      router.push('/');
      router.refresh();
    });
  }

  const recentRepos = React.useMemo(
    () => [...repos].sort((a, b) => (b.created_at || '').localeCompare(a.created_at || '')).slice(0, SORTED_RECENT_LIMIT),
    [repos]
  );

  return (
    <CommandDialog open={open} onOpenChange={setOpen} title="Codebase Copilot" description="Search the workspace, open repositories, or jump to common actions.">
      <CommandInput placeholder="Search repositories, pages, actions, or repo names…" />
      <CommandList>
        <CommandEmpty className="py-8 text-sm text-muted-foreground">No results found.</CommandEmpty>

        <CommandGroup heading="Quick actions">
          <CommandItem onSelect={() => runCommand(() => router.push('/dashboard'))}>
            <Plus className="mr-2 h-4 w-4" />
            <span>Index repository</span>
            <CommandShortcut>⌘N</CommandShortcut>
          </CommandItem>
          <CommandItem onSelect={() => runCommand(() => router.push('/dashboard'))}>
            <LayoutDashboard className="mr-2 h-4 w-4" />
            <span>Open dashboard</span>
          </CommandItem>
          <CommandItem onSelect={() => runCommand(() => router.push('/settings'))}>
            <Settings className="mr-2 h-4 w-4" />
            <span>Open settings</span>
          </CommandItem>
          <CommandItem onSelect={handleSignOut}>
            <LogOut className="mr-2 h-4 w-4" />
            <span>Sign out</span>
          </CommandItem>
        </CommandGroup>

        <CommandSeparator />

        <CommandGroup heading="Navigation">
          <CommandItem onSelect={() => runCommand(() => router.push('/dashboard'))}>
            <LayoutDashboard className="mr-2 h-4 w-4" />
            <span>Dashboard</span>
          </CommandItem>
          <CommandItem onSelect={() => runCommand(() => router.push('/settings'))}>
            <Settings className="mr-2 h-4 w-4" />
            <span>Settings</span>
          </CommandItem>
        </CommandGroup>

        <CommandSeparator />

        <CommandGroup heading="Recent repositories">
          {reposLoading && (
            <div className="py-6 text-center text-sm text-muted-foreground">
              Loading repositories...
            </div>
          )}
          {!reposLoading && reposLoaded && recentRepos.length === 0 && (
            <div className="py-6 text-center text-sm text-muted-foreground">
              No repositories indexed yet.
            </div>
          )}
          {!reposLoading && recentRepos.map((repo) => (
            <CommandItem
              key={repo.id}
              value={repo.name}
              onSelect={() => runCommand(() => router.push(getRepoWorkspaceHref(repo)))}
            >
              <FolderGit2 className="mr-2 h-4 w-4" />
              <span className="truncate">{repo.name}</span>
            </CommandItem>
          ))}
        </CommandGroup>

        <CommandSeparator />

        <CommandGroup heading="Workspace search">
          <CommandItem onSelect={() => runCommand(() => router.push('/dashboard'))}>
            <Search className="mr-2 h-4 w-4" />
            <span>Search across the workspace</span>
            <CommandShortcut>⌘K</CommandShortcut>
          </CommandItem>
        </CommandGroup>
      </CommandList>
    </CommandDialog>
  );
}
