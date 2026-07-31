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
} from '@/components/ui/command';
import { createClient } from '@/lib/supabase/client';
import type { Repo } from '@/lib/types';
import { Settings, FolderGit2, Home, LogOut } from 'lucide-react';

export function CommandPalette() {
  const [open, setOpen] = React.useState(false);
  const [repos, setRepos] = React.useState<Repo[]>([]);
  const router = useRouter();
  const supabase = createClient();

  React.useEffect(() => {
    const down = (e: KeyboardEvent) => {
      if (e.key === 'k' && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        setOpen((open) => !open);
      }
    };
    document.addEventListener('keydown', down);
    return () => document.removeEventListener('keydown', down);
  }, []);

  React.useEffect(() => {
    if (open && repos.length === 0) {
      // Fetch repos when opened
      const fetchRepos = async () => {
        const { data: { session } } = await supabase.auth.getSession();
        if (session?.access_token) {
          try {
            const res = await fetch(`${process.env.NEXT_PUBLIC_API_BASE_URL}/api/repo/list`, {
              headers: { Authorization: `Bearer ${session.access_token}` },
            });
            if (res.ok) {
              const data = await res.json();
              setRepos(data);
            }
          } catch (e) {
            console.error('Failed to fetch repos for command palette', e);
          }
        }
      };
      fetchRepos();
    }
  }, [open, repos.length, supabase]);

  const runCommand = React.useCallback((command: () => unknown) => {
    setOpen(false);
    command();
  }, []);

  async function handleSignOut() {
    await supabase.auth.signOut();
    runCommand(() => {
      router.push('/');
      router.refresh();
    });
  }

  return (
    <CommandDialog open={open} onOpenChange={setOpen}>
      <CommandInput placeholder="Type a command or search..." />
      <CommandList>
        <CommandEmpty>No results found.</CommandEmpty>
        
        <CommandGroup heading="Navigation">
          <CommandItem onSelect={() => runCommand(() => router.push('/dashboard'))}>
            <Home className="mr-2 h-4 w-4" />
            <span>Dashboard</span>
          </CommandItem>
          <CommandItem onSelect={() => runCommand(() => router.push('/settings'))}>
            <Settings className="mr-2 h-4 w-4" />
            <span>Settings</span>
          </CommandItem>
        </CommandGroup>
        
        <CommandSeparator />
        
        <CommandGroup heading="Repositories">
          {repos.map((repo) => (
            <CommandItem
              key={repo.id}
              value={repo.name}
              onSelect={() => runCommand(() => router.push(`/repo/${repo.id}`))}
            >
              <FolderGit2 className="mr-2 h-4 w-4" />
              <span>{repo.name}</span>
            </CommandItem>
          ))}
          {repos.length === 0 && (
            <div className="py-6 text-center text-sm text-muted-foreground">
              Loading repositories...
            </div>
          )}
        </CommandGroup>

        <CommandSeparator />

        <CommandGroup heading="Account">
          <CommandItem onSelect={handleSignOut}>
            <LogOut className="mr-2 h-4 w-4" />
            <span>Sign out</span>
          </CommandItem>
        </CommandGroup>
      </CommandList>
    </CommandDialog>
  );
}
