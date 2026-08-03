'use client';
/**
 * app/dashboard/page.tsx
 * Main dashboard: quick-index input, repo grid, empty state.
 */
import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { motion } from 'framer-motion';
import { Plus, Loader2, GitBranch, ArrowRight, Activity, Layers, FileCode2, CircleAlert, CircleCheck, Clock3 } from 'lucide-react';
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
    staleTime: 20_000,
    placeholderData: (prev) => prev,
    initialData: () => queryClient.getQueryData<Repo[]>(['repos']),
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
  const totalFiles = repos.reduce((sum, repo) => sum + (repo.file_count ?? 0), 0);
  const totalChunks = repos.reduce((sum, repo) => sum + (repo.node_count ?? 0), 0);
  const recentRepos = [...repos].sort((a, b) => (b.created_at || '').localeCompare(a.created_at || '')).slice(0, 6);
  const activityItems = [
    { label: 'Repositories ready', value: readyRepos.length, icon: CircleCheck, tone: 'text-brand' },
    { label: 'Currently indexing', value: indexingRepos.length, icon: Activity, tone: 'text-amber-400' },
    { label: 'Failed runs', value: failedRepos.length, icon: CircleAlert, tone: 'text-destructive' },
    { label: 'Files observed', value: totalFiles.toLocaleString(), icon: FileCode2, tone: 'text-blue-400' },
  ];

  return (
    <div className="space-y-6">
      <motion.section
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.25 }}
        className="grid gap-4 xl:grid-cols-[1.25fr_0.75fr]"
      >
        <div className="widget-elevated rounded-[1.5rem] border border-border bg-card/80 p-6 shadow-lg shadow-black/5 backdrop-blur-sm">
          <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
            <div className="space-y-3">
              <div className="inline-flex items-center gap-2 rounded-full border border-border bg-muted/70 px-3 py-1 text-xs text-muted-foreground">
                <Activity size={12} className="text-brand" />
                Workspace overview
              </div>
              <div>
                <h1 className="font-heading text-3xl font-bold tracking-tight">Dashboard</h1>
                <p className="mt-2 max-w-2xl text-sm text-muted-foreground">
                  Index repositories, track pipeline health, and jump directly into grounded chat or evaluation flows.
                </p>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:min-w-[28rem]">
              {activityItems.map((item) => (
                <div key={item.label} className="rounded-2xl border border-border bg-background/70 px-3 py-3">
                  <div className="flex items-center gap-2 text-xs text-muted-foreground">
                    <item.icon size={12} className={item.tone} />
                    {item.label}
                  </div>
                  <div className="mt-2 font-heading text-xl font-semibold tracking-tight">{item.value}</div>
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="widget-elevated rounded-[1.5rem] border border-border bg-card/80 p-6 shadow-lg shadow-black/5 backdrop-blur-sm">
          <div className="mb-4 flex items-center gap-2">
            <Layers size={15} className="text-brand" />
            <h2 className="font-heading text-sm font-semibold uppercase tracking-[0.18em] text-muted-foreground">Activity timeline</h2>
          </div>
          <div className="space-y-3">
            {recentRepos.length === 0 ? (
              <p className="rounded-2xl border border-dashed border-border px-4 py-6 text-sm text-muted-foreground">
                Index a repository to populate live activity here.
              </p>
            ) : (
              recentRepos.map((repo) => (
                <div key={repo.id} className="flex items-start gap-3 rounded-2xl border border-border/70 bg-background/70 px-4 py-3">
                  <div className="mt-0.5 flex h-8 w-8 items-center justify-center rounded-full bg-brand/10 text-brand">
                    <Clock3 size={14} />
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center justify-between gap-2">
                      <p className="truncate text-sm font-medium">{repo.name}</p>
                      <span className="rounded-full border border-border px-2 py-0.5 text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
                        {repo.status}
                      </span>
                    </div>
                    <p className="mt-1 text-xs text-muted-foreground">
                      {repo.status === 'ready'
                        ? 'Ready for grounded chat and exploration.'
                        : repo.status === 'indexing'
                        ? 'Pipeline is processing files and embeddings.'
                        : 'Indexing needs attention before chat can start.'}
                    </p>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </motion.section>

      <motion.form
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.05, duration: 0.25 }}
        onSubmit={handleIndex}
        className="widget-elevated rounded-[1.5rem] border border-border bg-card/80 p-5 shadow-lg shadow-black/5 backdrop-blur-sm"
      >
        <div className="mb-4 flex items-center gap-2">
          <GitBranch size={15} className="text-brand" />
          <div>
            <h2 className="font-heading text-sm font-semibold uppercase tracking-[0.18em] text-muted-foreground">Quick index</h2>
            <p className="text-xs text-muted-foreground">Paste a GitHub repository URL to launch the ingestion pipeline.</p>
          </div>
        </div>
        <div className="flex flex-col gap-3 md:flex-row">
          <div className="relative flex-1">
            <GitBranch
              size={15}
              className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground pointer-events-none"
            />
            <Input
              type="url"
              placeholder="https://github.com/owner/repository"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              className="pl-9 bg-background/70 border-border/80 focus-visible:ring-brand"
              disabled={indexMutation.isPending}
            />
          </div>
          <Button
            type="submit"
            className="bg-brand hover:bg-green-400 text-green-950 font-semibold cursor-pointer transition-colors duration-200 md:min-w-48"
            disabled={indexMutation.isPending || !url.trim()}
          >
            {indexMutation.isPending ? (
              <Loader2 size={15} className="animate-spin mr-2" />
            ) : (
              <Plus size={15} className="mr-2" />
            )}
            {indexMutation.isPending ? 'Starting…' : 'Index repository'}
          </Button>
        </div>
      </motion.form>

      {indexingRepos.length > 0 && (
        <section className="space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="font-heading text-sm font-semibold uppercase tracking-[0.18em] text-muted-foreground">Currently indexing</h2>
            <span className="text-xs text-muted-foreground">{indexingRepos.length} active</span>
          </div>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
            {indexingRepos.map((repo, i) => (
              <RepoCard key={repo.id} repo={repo} index={i} />
            ))}
          </div>
        </section>
      )}

      {isLoading ? (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
          {[0, 1, 2].map((i) => (
            <div key={i} className="h-40 rounded-[1.25rem] border border-border bg-card/60 animate-pulse" />
          ))}
        </div>
      ) : readyRepos.length > 0 ? (
        <section className="space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="font-heading text-sm font-semibold uppercase tracking-[0.18em] text-muted-foreground">Ready to chat</h2>
            <span className="text-xs text-muted-foreground">{readyRepos.length} ready · {totalChunks.toLocaleString()} chunks</span>
          </div>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
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
            className="rounded-[1.5rem] border border-dashed border-border bg-card/60 px-6 py-16 text-center"
          >
            <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-2xl border border-border bg-background/70">
              <GitBranch size={24} className="text-muted-foreground" />
            </div>
            <h3 className="font-heading text-lg font-semibold">No repositories yet</h3>
            <p className="mx-auto mt-2 max-w-md text-sm text-muted-foreground">
              Paste a GitHub URL above to index your first repository and unlock grounded chat, evaluation, and activity telemetry.
            </p>
            <div className="mt-5 inline-flex items-center gap-2 rounded-full border border-border bg-background/70 px-3 py-1.5 text-xs text-brand">
              <span>Try: github.com/openai/whisper</span>
              <ArrowRight size={12} />
            </div>
          </motion.div>
        )
      )}

      {failedRepos.length > 0 && (
        <section className="space-y-3">
          <h2 className="font-heading text-sm font-semibold uppercase tracking-[0.18em] text-muted-foreground">Failed</h2>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
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
