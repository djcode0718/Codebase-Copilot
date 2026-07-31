'use client';
/**
 * app/repo/[id]/page.tsx
 * Repository overview: file count, chunk count, extension breakdown,
 * tech stack detection, quick actions.
 */
import { useParams, useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import {
  MessageSquare, BarChart2, Trash2, FileCode2,
  Layers, GitBranch, ExternalLink, Clock, Cpu, Activity, ArrowRight, ShieldCheck, Sparkles,
} from 'lucide-react';
import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { createClient } from '@/lib/supabase/client';
import { getRepo, deleteRepo } from '@/lib/api';
import { cn } from '@/lib/utils';
import { toast } from 'sonner';
import type { Repo } from '@/lib/types';

// Detect tech stack from index_name (simple heuristic for display)
const TECH_CHIPS: Record<string, { label: string; color: string }> = {
  python:    { label: 'Python',     color: 'bg-blue-500/10 text-blue-400 border-blue-500/20' },
  js:        { label: 'JavaScript', color: 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20' },
  ts:        { label: 'TypeScript', color: 'bg-blue-400/10 text-blue-300 border-blue-400/20' },
  react:     { label: 'React',      color: 'bg-cyan-500/10 text-cyan-400 border-cyan-500/20' },
  next:      { label: 'Next.js',    color: 'bg-foreground/10 text-foreground border-foreground/20' },
  fastapi:   { label: 'FastAPI',    color: 'bg-green-500/10 text-green-400 border-green-500/20' },
  flutter:   { label: 'Flutter',    color: 'bg-sky-500/10 text-sky-400 border-sky-500/20' },
  carousel:  { label: 'Media',      color: 'bg-pink-500/10 text-pink-400 border-pink-500/20' },
  splitter:  { label: 'Utilities',  color: 'bg-violet-500/10 text-violet-400 border-violet-500/20' },
};

function detectTechChips(name: string): typeof TECH_CHIPS[string][] {
  const lower = name.toLowerCase();
  return Object.entries(TECH_CHIPS)
    .filter(([key]) => lower.includes(key))
    .map(([, val]) => val)
    .slice(0, 4);
}

export default function RepoOverviewPage() {
  const { id: repoId } = useParams<{ id: string }>();
  const router = useRouter();
  const [repo, setRepo] = useState<Repo | null>(null);
  const [token, setToken] = useState('');

  useEffect(() => {
    async function load() {
      const { data } = await createClient().auth.getSession();
      const t = data.session?.access_token ?? '';
      setToken(t);
      if (!t) return;
      try {
        const r = await getRepo(t, repoId);
        setRepo(r);
      } catch {
        toast.error('Repository not found');
        router.push('/dashboard');
      }
    }
    load();
  }, [repoId, router]);

  async function handleDelete() {
    if (!token || !repo) return;
    if (!confirm(`Delete "${repo.name}"? This cannot be undone.`)) return;
    try {
      await deleteRepo(token, repoId);
      toast.success('Repository deleted');
      router.push('/dashboard');
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to delete');
    }
  }

  if (!repo) {
    return (
      <div className="p-8 space-y-4">
        {[1, 2, 3].map((i) => (
          <div key={i} className="h-16 bg-card border border-border rounded-xl animate-pulse" />
        ))}
      </div>
    );
  }

  const chips = detectTechChips(repo.name);
  const formattedDate = new Date(repo.created_at).toLocaleString('en-US', {
    month: 'short', day: 'numeric', year: 'numeric', hour: '2-digit', minute: '2-digit',
  });
  const kpis = [
    { label: 'Files indexed', value: repo.file_count?.toLocaleString() ?? '—', icon: FileCode2 },
    { label: 'Chunks created', value: repo.node_count?.toLocaleString() ?? '—', icon: Layers },
    { label: 'LLM provider', value: repo.llm_provider ?? 'ollama', icon: Cpu },
    { label: 'Indexed at', value: formattedDate, icon: Clock },
  ];
  const activity = [
    {
      title: repo.status === 'ready' ? 'Repository is ready' : repo.status === 'indexing' ? 'Pipeline is running' : 'Repository needs attention',
      description: repo.status === 'ready'
        ? 'Grounded chat and evaluations are available.'
        : repo.status === 'indexing'
        ? 'The ingestion pipeline is processing files and embeddings.'
        : 'Review indexing logs or delete and re-run the repository.',
      tone: repo.status === 'ready' ? 'text-brand' : repo.status === 'indexing' ? 'text-amber-400' : 'text-destructive',
    },
    {
      title: 'Next best action',
      description: 'Open chat to ask about architecture or run the evaluation suite to benchmark grounding quality.',
      tone: 'text-blue-400',
    },
    {
      title: 'Tech signal',
      description: chips.length > 0 ? chips.map((chip) => chip.label).join(' · ') : 'No stack signal detected yet.',
      tone: 'text-muted-foreground',
    },
  ];

  return (
    <div className="space-y-6">
      <motion.section
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        className="rounded-[1.5rem] border border-border bg-card/80 p-6 shadow-lg shadow-black/5 backdrop-blur-sm"
      >
        <div className="flex flex-col gap-6 lg:flex-row lg:items-start lg:justify-between">
          <div className="space-y-4">
            <div className="inline-flex items-center gap-2 rounded-full border border-border bg-muted/70 px-3 py-1 text-xs text-muted-foreground">
              <Sparkles size={12} className="text-brand" />
              Repository workspace
            </div>
            <div className="flex items-start gap-4">
              <div className="flex h-12 w-12 items-center justify-center rounded-2xl border border-border bg-background/70">
                <GitBranch size={20} className="text-muted-foreground" />
              </div>
              <div className="min-w-0">
                <h1 className="font-heading text-3xl font-bold tracking-tight">{repo.name}</h1>
                <a
                  href={repo.source_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="mt-1 inline-flex items-center gap-1.5 text-sm text-muted-foreground transition-colors hover:text-brand"
                >
                  {repo.source_url}
                  <ExternalLink size={11} />
                </a>
              </div>
            </div>
            <div className="flex flex-wrap gap-2">
              <Badge variant="outline" className={`${repo.status === 'ready' ? 'bg-brand/10 text-brand border-brand/20' : repo.status === 'indexing' ? 'bg-amber-500/10 text-amber-400 border-amber-500/20' : 'bg-destructive/10 text-destructive border-destructive/20'} text-xs`}>
                {repo.status}
              </Badge>
              {chips.map((chip, i) => (
                <Badge key={i} variant="outline" className={`${chip.color} border text-xs`}>
                  {chip.label}
                </Badge>
              ))}
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <Button
              onClick={() => router.push(`/repo/${repoId}/chat`)}
              className="bg-brand hover:bg-green-400 text-green-950 font-semibold cursor-pointer"
            >
              <MessageSquare size={14} className="mr-2" />
              Chat
            </Button>
            <Button
              variant="outline"
              className="border-border cursor-pointer"
              onClick={() => router.push(`/repo/${repoId}/eval`)}
            >
              <BarChart2 size={14} className="mr-2" />
              Evaluate
            </Button>
            <Button
              variant="outline"
              className="border-destructive/30 text-destructive hover:bg-destructive/10 cursor-pointer"
              onClick={handleDelete}
            >
              <Trash2 size={14} />
            </Button>
          </div>
        </div>
      </motion.section>

      <section className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
        {kpis.map((stat, i) => (
          <motion.div
            key={stat.label}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.04 }}
            className="rounded-[1.25rem] border border-border bg-card/80 p-4 shadow-sm shadow-black/5"
          >
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <stat.icon size={13} className="text-brand" />
              {stat.label}
            </div>
            <p className="mt-3 text-sm font-semibold tracking-tight">{stat.value}</p>
          </motion.div>
        ))}
      </section>

      <section className="grid grid-cols-1 gap-6 xl:grid-cols-[1.15fr_0.85fr]">
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.05 }}
          className="rounded-[1.5rem] border border-border bg-card/80 p-5 shadow-lg shadow-black/5 backdrop-blur-sm"
        >
          <div className="mb-4 flex items-center gap-2">
            <Activity size={15} className="text-brand" />
            <h2 className="font-heading text-sm font-semibold uppercase tracking-[0.18em] text-muted-foreground">Repository activity</h2>
          </div>
          <div className="space-y-3">
            {activity.map((item) => (
              <div key={item.title} className="flex gap-3 rounded-2xl border border-border/70 bg-background/70 px-4 py-3">
                <div className={cn('mt-0.5 flex h-8 w-8 items-center justify-center rounded-full bg-brand/10', item.tone)}>
                  <ShieldCheck size={14} />
                </div>
                <div className="min-w-0">
                  <p className="text-sm font-medium">{item.title}</p>
                  <p className="mt-1 text-xs text-muted-foreground">{item.description}</p>
                </div>
              </div>
            ))}
          </div>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          className="rounded-[1.5rem] border border-border bg-card/80 p-5 shadow-lg shadow-black/5 backdrop-blur-sm"
        >
          <div className="mb-4 flex items-center gap-2">
            <Sparkles size={15} className="text-brand" />
            <h2 className="font-heading text-sm font-semibold uppercase tracking-[0.18em] text-muted-foreground">Fast actions</h2>
          </div>
          <div className="space-y-3">
            <Link href={`/repo/${repoId}/chat`} className="group block rounded-2xl border border-border/70 bg-background/70 p-4 transition-colors hover:border-brand/30 hover:bg-brand/5">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="font-medium">Start chatting</p>
                  <p className="mt-1 text-xs text-muted-foreground">Ask architectural or code-level questions.</p>
                </div>
                <ArrowRight size={14} className="text-muted-foreground transition-transform group-hover:translate-x-0.5" />
              </div>
            </Link>
            <Link href={`/repo/${repoId}/eval`} className="group block rounded-2xl border border-border/70 bg-background/70 p-4 transition-colors hover:border-violet-500/30 hover:bg-violet-500/5">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="font-medium">Run evaluation</p>
                  <p className="mt-1 text-xs text-muted-foreground">Benchmark grounding, relevancy, and latency.</p>
                </div>
                <ArrowRight size={14} className="text-muted-foreground transition-transform group-hover:translate-x-0.5" />
              </div>
            </Link>
          </div>
        </motion.div>
      </section>
    </div>
  );
}
