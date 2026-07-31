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
  Layers, GitBranch, ExternalLink, Clock, Cpu,
} from 'lucide-react';
import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { createClient } from '@/lib/supabase/client';
import { getRepo, deleteRepo } from '@/lib/api';
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

  return (
    <div className="p-8 max-w-4xl">
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        className="mb-8"
      >
        <div className="flex items-start justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-card border border-border rounded-xl flex items-center justify-center">
              <GitBranch size={18} className="text-muted-foreground" />
            </div>
            <div>
              <h1 className="font-heading text-2xl font-bold">{repo.name}</h1>
              <a
                href={repo.source_url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-sm text-muted-foreground hover:text-brand transition-colors inline-flex items-center gap-1 mt-0.5"
              >
                {repo.source_url}
                <ExternalLink size={11} />
              </a>
            </div>
          </div>
          <div className="flex items-center gap-2">
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
      </motion.div>

      {/* Stats grid */}
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.05 }}
        className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8"
      >
        {[
          { icon: FileCode2, label: 'Files indexed', value: repo.file_count?.toLocaleString() ?? '—' },
          { icon: Layers, label: 'Chunks created', value: repo.node_count?.toLocaleString() ?? '—' },
          { icon: Cpu, label: 'LLM provider', value: repo.llm_provider ?? 'ollama' },
          { icon: Clock, label: 'Indexed at', value: formattedDate },
        ].map((stat, i) => (
          <div key={i} className="bg-card border border-border rounded-xl p-4">
            <div className="flex items-center gap-2 text-muted-foreground mb-2">
              <stat.icon size={13} />
              <span className="text-xs">{stat.label}</span>
            </div>
            <p className="font-heading font-semibold text-sm">{stat.value}</p>
          </div>
        ))}
      </motion.div>

      {/* Tech stack chips */}
      {chips.length > 0 && (
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          className="mb-8"
        >
          <h2 className="font-heading text-sm font-semibold text-muted-foreground uppercase tracking-wider mb-3">
            Detected stack
          </h2>
          <div className="flex flex-wrap gap-2">
            {chips.map((chip, i) => (
              <Badge
                key={i}
                variant="outline"
                className={`${chip.color} border text-xs`}
              >
                {chip.label}
              </Badge>
            ))}
          </div>
        </motion.div>
      )}

      {/* Quick actions */}
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.15 }}
        className="grid grid-cols-1 sm:grid-cols-2 gap-4"
      >
        <Link
          href={`/repo/${repoId}/chat`}
          className="bg-card border border-border hover:border-brand/30 rounded-xl p-5 transition-all duration-200 group cursor-pointer"
        >
          <div className="flex items-center gap-3 mb-2">
            <div className="w-8 h-8 bg-brand/10 border border-brand/20 rounded-lg flex items-center justify-center">
              <MessageSquare size={15} className="text-brand" />
            </div>
            <span className="font-heading font-semibold text-sm">Start chatting</span>
          </div>
          <p className="text-xs text-muted-foreground">
            Ask questions about the codebase with grounded, inspectable answers.
          </p>
        </Link>

        <Link
          href={`/repo/${repoId}/eval`}
          className="bg-card border border-border hover:border-violet-500/30 rounded-xl p-5 transition-all duration-200 group cursor-pointer"
        >
          <div className="flex items-center gap-3 mb-2">
            <div className="w-8 h-8 bg-violet-500/10 border border-violet-500/20 rounded-lg flex items-center justify-center">
              <BarChart2 size={15} className="text-violet-400" />
            </div>
            <span className="font-heading font-semibold text-sm">Run evaluation</span>
          </div>
          <p className="text-xs text-muted-foreground">
            Measure hit rate, MRR, faithfulness, relevancy, and latency.
          </p>
        </Link>
      </motion.div>
    </div>
  );
}
