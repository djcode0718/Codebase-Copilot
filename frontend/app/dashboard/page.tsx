'use client';
/**
 * app/dashboard/page.tsx
 * Main dashboard: quick-index input, repo grid, empty state.
 */
import { useEffect, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { motion } from 'framer-motion';
import { Plus, Loader2, GitBranch, ArrowRight, Activity, Layers, FileCode2, CircleAlert, CircleCheck, Clock3, Sparkles, MessageSquare, FolderGit2, Compass, Lock } from 'lucide-react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import RepoCard from '@/components/repo/RepoCard';
import { indexRepo, listRepos, deleteRepo } from '@/lib/api';
import { createClient } from '@/lib/supabase/client';
import { toast } from 'sonner';
import type { Repo } from '@/lib/types';

type ActivityItem = {
  label: string;
  value: number | string;
  icon: React.ComponentType<{ size?: number; className?: string }>;
  tone: string;
};

function getDashboardStats(repos: Repo[]) {
  const readyRepos = repos.filter((r) => r.status === 'ready');
  const indexingRepos = repos.filter((r) => r.status === 'indexing');
  const failedRepos = repos.filter((r) => r.status === 'failed');
  const totalFiles = repos.reduce((sum, repo) => sum + (repo.file_count ?? 0), 0);
  const totalChunks = repos.reduce((sum, repo) => sum + (repo.node_count ?? 0), 0);
  const recentRepos = [...repos]
    .sort((a, b) => (b.created_at || '').localeCompare(a.created_at || ''))
    .slice(0, 6);
  const activityItems: ActivityItem[] = [
    { label: 'Repositories ready', value: readyRepos.length, icon: CircleCheck, tone: 'text-brand' },
    { label: 'Currently indexing', value: indexingRepos.length, icon: Activity, tone: 'text-amber-400' },
    { label: 'Failed runs', value: failedRepos.length, icon: CircleAlert, tone: 'text-destructive' },
    { label: 'Files observed', value: totalFiles.toLocaleString(), icon: FileCode2, tone: 'text-blue-400' },
  ];

  return {
    readyRepos,
    indexingRepos,
    failedRepos,
    totalFiles,
    totalChunks,
    recentRepos,
    activityItems,
  };
}

function ActivityCard({ item }: { item: ActivityItem }) {
  return (
    <div className="rounded-2xl border border-border bg-background/70 px-3 py-3">
      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        <item.icon size={12} className={item.tone} />
        {item.label}
      </div>
      <div className="mt-2 font-heading text-xl font-semibold tracking-tight">{item.value}</div>
    </div>
  );
}

function ActivityTimelineItem({ repo }: { repo: Repo }) {
  return (
    <div className="flex items-start gap-3 rounded-2xl border border-border/70 bg-background/70 px-4 py-3">
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
  );
}

function RepoSection({
  title,
  subtitle,
  repos,
  onDelete,
}: {
  title: string;
  subtitle?: string;
  repos: Repo[];
  onDelete?: (id: string) => void;
}) {
  return (
    <section className="space-y-3">
      <div className="flex items-center justify-between">
        <h2 className="font-heading text-sm font-semibold uppercase tracking-[0.18em] text-muted-foreground">{title}</h2>
        {subtitle ? <span className="text-xs text-muted-foreground">{subtitle}</span> : null}
      </div>
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
        {repos.map((repo, i) => (
          <RepoCard key={repo.id} repo={repo} index={i} onDelete={onDelete} />
        ))}
      </div>
    </section>
  );
}

function QuickIndexForm({
  url,
  isPending,
  onChange,
  onSubmit,
}: {
  url: string;
  isPending: boolean;
  onChange: (value: string) => void;
  onSubmit: (e: React.FormEvent) => void;
}) {
  return (
    <motion.form
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.05, duration: 0.25 }}
      onSubmit={onSubmit}
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
            onChange={(e) => onChange(e.target.value)}
            className="pl-9 bg-background/70 border-border/80 focus-visible:ring-brand"
            disabled={isPending}
          />
        </div>
        <Button
          type="submit"
          className="bg-brand hover:bg-green-400 text-green-950 font-semibold cursor-pointer transition-colors duration-200 md:min-w-48"
          disabled={isPending || !url.trim()}
        >
          {isPending ? (
            <Loader2 size={15} className="animate-spin mr-2" />
          ) : (
            <Plus size={15} className="mr-2" />
          )}
          {isPending ? 'Starting…' : 'Index repository'}
        </Button>
      </div>
    </motion.form>
  );
}

function EmptyStateCard() {
  return (
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
  );
}

function ProgressiveAuthNotice({
  onSignIn,
}: {
  onSignIn: () => void;
}) {
  return (
    <div className="rounded-2xl border border-brand/25 bg-brand/8 px-4 py-3">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <p className="text-sm text-muted-foreground">
          You are exploring in demo mode. Sign in to persist repository indexing, saved chats, exports, and evaluations.
        </p>
        <Button
          type="button"
          variant="outline"
          className="border-brand/40 text-brand hover:bg-brand/10"
          onClick={onSignIn}
        >
          <Lock size={14} className="mr-2" />
          Sign in to persist workspace data
        </Button>
      </div>
    </div>
  );
}

function InstantWorkspaceCard({
  greetingName,
  fromGitHub,
  onIndex,
  onConnect,
  onExploreDemo,
  onTour,
}: {
  greetingName?: string;
  fromGitHub: boolean;
  onIndex: () => void;
  onConnect: () => void;
  onExploreDemo: () => void;
  onTour: () => void;
}) {
  return (
    <motion.section
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25 }}
      className="rounded-[1.5rem] border border-border bg-card/80 p-5 shadow-lg shadow-black/5 backdrop-blur-sm"
    >
      <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
        <span className="inline-flex items-center gap-1 rounded-full border border-border bg-background/60 px-2.5 py-1">
          <Sparkles size={12} className="text-brand" /> Instant Workspace
        </span>
        {fromGitHub ? <span className="rounded-full border border-brand/35 bg-brand/10 px-2.5 py-1 text-brand">GitHub connected</span> : null}
      </div>
      <h2 className="mt-3 font-heading text-2xl font-semibold tracking-tight">
        Welcome{greetingName ? `, ${greetingName}` : ''}
      </h2>
      <p className="mt-1 text-sm text-muted-foreground">
        Choose your next step to get value in seconds.
      </p>
      <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        <button type="button" onClick={onIndex} className="rounded-2xl border border-border bg-background/70 p-4 text-left transition-colors hover:bg-accent">
          <FolderGit2 size={16} className="text-brand" />
          <p className="mt-2 text-sm font-medium">Index a Repository</p>
          <p className="mt-1 text-xs text-muted-foreground">Paste a GitHub URL and start ingestion.</p>
        </button>
        <button type="button" onClick={onConnect} className="rounded-2xl border border-border bg-background/70 p-4 text-left transition-colors hover:bg-accent">
          <GitBranch size={16} className="text-brand" />
          <p className="mt-2 text-sm font-medium">Import from GitHub</p>
          <p className="mt-1 text-xs text-muted-foreground">Connect public or private repositories (optional).</p>
        </button>
        <button type="button" onClick={onExploreDemo} className="rounded-2xl border border-border bg-background/70 p-4 text-left transition-colors hover:bg-accent">
          <Compass size={16} className="text-brand" />
          <p className="mt-2 text-sm font-medium">Explore Demo Workspace</p>
          <p className="mt-1 text-xs text-muted-foreground">No setup needed. Start exploring instantly.</p>
        </button>
        <button type="button" onClick={onTour} className="rounded-2xl border border-border bg-background/70 p-4 text-left transition-colors hover:bg-accent md:col-span-2 xl:col-span-1">
          <MessageSquare size={16} className="text-brand" />
          <p className="mt-2 text-sm font-medium">View Product Tour</p>
          <p className="mt-1 text-xs text-muted-foreground">See architecture, review, and security workflows.</p>
        </button>
      </div>
    </motion.section>
  );
}

async function getToken(): Promise<string> {
  const supabase = createClient();
  const { data } = await supabase.auth.getSession();
  return data.session?.access_token ?? '';
}

export default function DashboardPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const queryClient = useQueryClient();
  const [url, setUrl] = useState('');
  const [isGuest, setIsGuest] = useState(false);
  const [greetingName, setGreetingName] = useState<string | undefined>(undefined);

  const fromGitHubOAuth = searchParams.get('auth_provider') === 'github';

  async function handleUpgradeSignIn() {
    try {
      const supabase = createClient();
      const {
        data: { user },
      } = await supabase.auth.getUser();
      if (user?.is_anonymous) {
        await supabase.auth.signOut();
      }
    } catch {
      // Keep navigation resilient even if session cleanup fails.
    }
    router.push('/auth/sign-in?next=/dashboard');
  }

  useEffect(() => {
    void (async () => {
      const supabase = createClient();
      const {
        data: { user },
      } = await supabase.auth.getUser();
      setIsGuest(Boolean(user?.is_anonymous));
      const fallbackName = user?.email?.split('@')[0] ?? undefined;
      const metadataName = typeof user?.user_metadata?.full_name === 'string'
        ? user.user_metadata.full_name
        : typeof user?.user_metadata?.name === 'string'
          ? user.user_metadata.name
          : undefined;
      setGreetingName(metadataName ?? fallbackName);
    })();
  }, []);

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
    if (isGuest) {
      const wantsSignIn = window.confirm('Sign in now to persist indexing, chats, and workspace history? Select Cancel to continue in demo mode.');
      if (wantsSignIn) {
        void handleUpgradeSignIn();
        return;
      }
    }
    indexMutation.mutate(trimmed);
  }

  const { readyRepos, indexingRepos, failedRepos, totalChunks, recentRepos, activityItems } = getDashboardStats(repos);

  return (
    <div className="space-y-6">
      {isGuest ? <ProgressiveAuthNotice onSignIn={() => void handleUpgradeSignIn()} /> : null}

      {repos.length === 0 ? (
        <InstantWorkspaceCard
          greetingName={greetingName}
          fromGitHub={fromGitHubOAuth}
          onIndex={() => {
            const input = document.querySelector<HTMLInputElement>('input[type="url"]');
            input?.focus();
          }}
          onConnect={() => toast.info('GitHub repository picker is rolling out soon. You can paste any GitHub URL below right now.')}
          onExploreDemo={() => router.push('/')}
          onTour={() => router.push('/#how-it-works')}
        />
      ) : null}

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
                  <ActivityCard key={item.label} item={item} />
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
                <ActivityTimelineItem key={repo.id} repo={repo} />
              ))
            )}
          </div>
        </div>
      </motion.section>

      <QuickIndexForm
        url={url}
        isPending={indexMutation.isPending}
        onChange={setUrl}
        onSubmit={handleIndex}
      />

      {indexingRepos.length > 0 && (
        <RepoSection title="Currently indexing" subtitle={`${indexingRepos.length} active`} repos={indexingRepos} />
      )}

      {isLoading ? (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
          {[0, 1, 2].map((i) => (
            <div key={i} className="h-40 rounded-[1.25rem] border border-border bg-card/60 animate-pulse" />
          ))}
        </div>
      ) : readyRepos.length > 0 ? (
        <RepoSection
          title="Ready to chat"
          subtitle={`${readyRepos.length} ready · ${totalChunks.toLocaleString()} chunks`}
          repos={readyRepos}
          onDelete={(id) => deleteMutation.mutate(id)}
        />
      ) : (
        !indexingRepos.length && (
          <EmptyStateCard />
        )
      )}

      {failedRepos.length > 0 && (
        <RepoSection title="Failed" repos={failedRepos} onDelete={(id) => deleteMutation.mutate(id)} />
      )}
    </div>
  );
}
