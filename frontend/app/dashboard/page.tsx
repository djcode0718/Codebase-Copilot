'use client';
/**
 * app/dashboard/page.tsx
 * Main dashboard: quick-index input, repo grid, empty state.
 */
import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { motion } from 'framer-motion';
import { Plus, Loader2, GitBranch, ArrowRight } from 'lucide-react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import RepoCard from '@/components/repo/RepoCard';
import { indexRepo, listRepos, deleteRepo } from '@/lib/api';
import { createClient } from '@/lib/supabase/client';
import { toast } from 'sonner';
import type { Repo } from '@/lib/types';

async function getToken(): Promise<string> {
  const supabase = createClient();
  const { data } = await supabase.auth.getSession();
  return data.session?.access_token ?? '';
}

export default function DashboardPage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [url, setUrl] = useState('');

  const { data: repos = [], isLoading } = useQuery<Repo[]>({
    queryKey: ['repos'],
    queryFn: async () => {
      const token = await getToken();
      return listRepos(token);
    },
  });

  const indexMutation = useMutation({
    mutationFn: async (source: string) => {
      const token = await getToken();
      return indexRepo(token, source);
    },
    onSuccess: (data) => {
      toast.success(`Indexing started for "${data.index_name}"`);
      queryClient.invalidateQueries({ queryKey: ['repos'] });
      router.push(`/repo/${data.repo_id}/indexing`);
    },
    onError: (err: Error) => toast.error(err.message),
  });

  const deleteMutation = useMutation({
    mutationFn: async (repoId: string) => {
      const token = await getToken();
      return deleteRepo(token, repoId);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['repos'] });
      toast.success('Repository deleted');
    },
    onError: (err: Error) => toast.error(err.message),
  });

  function handleIndex(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = url.trim();
    if (!trimmed) return;
    indexMutation.mutate(trimmed);
  }

  const readyRepos = repos.filter((r) => r.status === 'ready');
  const indexingRepos = repos.filter((r) => r.status === 'indexing');
  const failedRepos = repos.filter((r) => r.status === 'failed');

  return (
    <div className="p-8 max-w-6xl">
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.25 }}
        className="mb-8"
      >
        <h1 className="font-heading text-2xl font-bold mb-1">Dashboard</h1>
        <p className="text-muted-foreground text-sm">
          Index a GitHub repository to start chatting with it.
        </p>
      </motion.div>

      {/* Quick index input */}
      <motion.form
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.05, duration: 0.25 }}
        onSubmit={handleIndex}
        className="flex gap-2 mb-10"
      >
        <div className="relative flex-1 max-w-xl">
          <GitBranch
            size={15}
            className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground pointer-events-none"
          />
          <Input
            type="url"
            placeholder="https://github.com/owner/repository"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            className="pl-9 bg-card border-border focus-visible:ring-brand"
            disabled={indexMutation.isPending}
          />
        </div>
        <Button
          type="submit"
          className="bg-brand hover:bg-green-400 text-green-950 font-semibold cursor-pointer transition-colors duration-200"
          disabled={indexMutation.isPending || !url.trim()}
        >
          {indexMutation.isPending ? (
            <Loader2 size={15} className="animate-spin mr-2" />
          ) : (
            <Plus size={15} className="mr-2" />
          )}
          {indexMutation.isPending ? 'Starting…' : 'Index repository'}
        </Button>
      </motion.form>

      {/* Indexing repos */}
      {indexingRepos.length > 0 && (
        <section className="mb-8">
          <h2 className="font-heading text-sm font-semibold text-muted-foreground uppercase tracking-wider mb-3">
            Currently indexing
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {indexingRepos.map((repo, i) => (
              <RepoCard key={repo.id} repo={repo} index={i} />
            ))}
          </div>
        </section>
      )}

      {/* Ready repos */}
      {isLoading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {[0, 1, 2].map((i) => (
            <div key={i} className="bg-card border border-border rounded-xl h-32 animate-pulse" />
          ))}
        </div>
      ) : readyRepos.length > 0 ? (
        <section className="mb-8">
          <h2 className="font-heading text-sm font-semibold text-muted-foreground uppercase tracking-wider mb-3">
            Ready to chat
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {readyRepos.map((repo, i) => (
              <RepoCard
                key={repo.id}
                repo={repo}
                index={i}
                onDelete={(id) => deleteMutation.mutate(id)}
              />
            ))}
          </div>
        </section>
      ) : (
        !indexingRepos.length && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.2 }}
            className="flex flex-col items-center justify-center py-20 text-center"
          >
            <div className="w-16 h-16 bg-card border border-border rounded-2xl flex items-center justify-center mb-4">
              <GitBranch size={24} className="text-muted-foreground" />
            </div>
            <h3 className="font-heading font-semibold mb-2">No repositories yet</h3>
            <p className="text-muted-foreground text-sm max-w-xs mb-6">
              Paste a GitHub URL above to index your first repository and start chatting with it.
            </p>
            <div className="flex items-center gap-2 text-xs text-brand">
              <span>Try: github.com/openai/whisper</span>
              <ArrowRight size={12} />
            </div>
          </motion.div>
        )
      )}

      {/* Failed repos */}
      {failedRepos.length > 0 && (
        <section>
          <h2 className="font-heading text-sm font-semibold text-muted-foreground uppercase tracking-wider mb-3">
            Failed
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {failedRepos.map((repo, i) => (
              <RepoCard
                key={repo.id}
                repo={repo}
                index={i}
                onDelete={(id) => deleteMutation.mutate(id)}
              />
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
