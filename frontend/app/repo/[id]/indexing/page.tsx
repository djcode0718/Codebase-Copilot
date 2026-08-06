'use client';
/**
 * app/repo/[id]/indexing/page.tsx
 * Centerpiece indexing screen — real-time SSE pipeline with animated steps,
 * live stats bar, progress indicator. No spinners.
 */
import { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { motion, AnimatePresence } from 'framer-motion';
import { CheckCircle2, AlertCircle, MessageSquare, RotateCcw, ArrowLeft, Activity, Sparkles, Clock3, FileCode2, Layers } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import PipelineStep from '@/components/indexing/PipelineStep';
import { useIndexingStream } from '@/hooks/useIndexingStream';
import { createClient } from '@/lib/supabase/client';
import Link from 'next/link';

function formatElapsed(ms: number): string {
  if (ms < 1000) return `${Math.floor(ms)}ms`;
  const s = Math.floor(ms / 1000);
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60);
  return `${m}m ${s % 60}s`;
}

function AnimatedCounter({ value }: { value: number | null }) {
  if (value === null) return <span className="text-muted-foreground">—</span>;
  return (
    <motion.span
      key={value}
      initial={{ opacity: 0, y: 4 }}
      animate={{ opacity: 1, y: 0 }}
      className="text-foreground font-semibold"
    >
      {value.toLocaleString()}
    </motion.span>
  );
}

export default function IndexingPage() {
  const { id: repoId } = useParams<{ id: string }>();
  const router = useRouter();
  const [token, setToken] = useState('');

  useEffect(() => {
    createClient().auth.getSession().then(({ data }) => {
      setToken(data.session?.access_token ?? '');
    });
  }, []);

  const {
    steps,
    progress,
    fileCount,
    nodeCount,
    elapsedMs,
    isComplete,
    hasError,
    errorMessage,
    indexName,
  } = useIndexingStream(repoId, token, !!token);

  // Auto-navigate to repo page after completion
  useEffect(() => {
    if (isComplete) {
      const t = setTimeout(() => {
        router.refresh();
        router.push(`/repo/${repoId}`);
      }, 2000);
      return () => clearTimeout(t);
    }
  }, [isComplete, repoId, router]);

  function headingText() {
    if (isComplete) return 'Indexing complete';
    if (hasError) return 'Indexing failed';
    return 'Indexing repository';
  }

  function subtitleText() {
    if (isComplete && indexName) return `"${indexName}" is ready to chat.`;
    if (hasError) return 'Review the error details below and retry when ready.';
    return 'Processing files, embeddings, and repository structure in real time.';
  }

  return (
    <div className="space-y-6">
      <Link
        href="/dashboard"
        className="inline-flex items-center gap-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground"
      >
        <ArrowLeft size={14} />
        Dashboard
      </Link>

      <motion.section
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        className="rounded-[1.5rem] border border-border bg-card/80 p-6 shadow-lg shadow-black/5 backdrop-blur-sm"
      >
        <div className="flex flex-col gap-6 lg:flex-row lg:items-start lg:justify-between">
          <div className="space-y-4">
            <div className="inline-flex items-center gap-2 rounded-full border border-border bg-muted/70 px-3 py-1 text-xs text-muted-foreground">
              <Activity size={12} className="text-brand" />
              Indexing pipeline
            </div>
            <div>
              <h1 className="font-heading text-3xl font-bold tracking-tight">
                {headingText()}
              </h1>
              <p className="mt-2 max-w-2xl text-sm text-muted-foreground">
                {subtitleText()}
              </p>
            </div>
          </div>
          <div className="grid grid-cols-3 gap-3 sm:min-w-[20rem]">
            {[
              { label: 'Files found', value: fileCount, icon: FileCode2 },
              { label: 'Chunks indexed', value: nodeCount, icon: Layers },
              { label: 'Elapsed', value: null, custom: formatElapsed(elapsedMs), icon: Clock3 },
            ].map((stat) => (
              <div key={stat.label} className="rounded-2xl border border-border bg-background/70 p-3">
                <div className="flex items-center gap-1.5 text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
                  <stat.icon size={11} className="text-brand" />
                  {stat.label}
                </div>
                <div className="mt-2 font-heading text-lg font-semibold">
                  {stat.custom ? stat.custom : <AnimatedCounter value={stat.value ?? null} />}
                </div>
              </div>
            ))}
          </div>
        </div>
      </motion.section>

      <section className="grid min-w-0 grid-cols-1 gap-6 xl:grid-cols-[minmax(0,1.15fr)_minmax(340px,0.85fr)]">
        <div className="min-w-0 rounded-[1.5rem] border border-border bg-card/80 p-5 shadow-lg shadow-black/5 backdrop-blur-sm">
          <div className="flex items-center justify-between gap-3 mb-4">
            <div>
              <h2 className="font-heading text-sm font-semibold uppercase tracking-[0.18em] text-muted-foreground">Pipeline steps</h2>
              <p className="text-xs text-muted-foreground mt-1">Live status and execution order from the indexing stream.</p>
            </div>
            <div className="inline-flex items-center gap-2 rounded-full border border-border bg-background/70 px-3 py-1 text-xs text-muted-foreground">
              <Sparkles size={11} className="text-brand" />
              {hasError ? 'Attention required' : isComplete ? 'Completed' : `${progress}%`}
            </div>
          </div>
          <Progress
            value={progress}
            className={`h-2 mb-5 ${hasError ? '[&>div]:bg-destructive' : '[&>div]:bg-brand'}`}
          />
          <div className="space-y-0">
            {steps.map((step, i) => (
              <PipelineStep
                key={step.id}
                step={step}
                isLast={i === steps.length - 1}
              />
            ))}
          </div>
        </div>

        <div className="min-w-0 space-y-6">

          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}

            transition={{ delay: 0.15 }}
            className="min-w-0 rounded-[1.5rem] border border-border bg-card/80 p-5 shadow-lg shadow-black/5 backdrop-blur-sm"
          >
            <h2 className="font-heading text-sm font-semibold uppercase tracking-[0.18em] text-muted-foreground mb-3">Live summary</h2>

            <div className="grid grid-cols-1 gap-3 sm:grid-cols-3 xl:grid-cols-1">
              {[
                { label: 'Progress', value: `${progress}%` },
                { label: 'Files', value: String(fileCount ?? 0) },
                { label: 'Chunks', value: String(nodeCount ?? 0) },
              ].map((item) => (
                <div key={item.label} className="rounded-2xl border border-border bg-background/70 px-4 py-3">
                  <div className="text-xs text-muted-foreground">{item.label}</div>
                  <div className="mt-1 font-heading text-lg font-semibold">{item.value}</div>
                </div>
              ))}
            </div>
          </motion.div>

          <AnimatePresence>
            {hasError && errorMessage && (
              <motion.div
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                className="min-w-0 rounded-[1.5rem] border border-destructive/20 bg-destructive/5 p-5 shadow-lg shadow-black/5"
              >
                <div className="flex items-start gap-3">
                  <AlertCircle size={18} className="text-destructive flex-shrink-0 mt-0.5" />
                  <div>
                    <p className="text-sm font-medium text-destructive mb-1">Indexing failed</p>
                    <pre className="overflow-x-auto break-words whitespace-pre-wrap text-xs text-muted-foreground font-code">{errorMessage}</pre>
                  </div>
                </div>
                <div className="flex flex-wrap gap-2 mt-4">
                  <Button
                    size="sm"
                    variant="outline"
                    className="border-border cursor-pointer"
                    onClick={() => router.push('/dashboard')}
                  >
                    <RotateCcw size={13} className="mr-1.5" />
                    Index another repository
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    className="border-border cursor-pointer"
                    onClick={() => router.push('/dashboard')}
                  >
                    Back to dashboard
                  </Button>
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          <AnimatePresence>
            {isComplete && (
              <motion.div
                initial={{ opacity: 0, scale: 0.96 }}
                animate={{ opacity: 1, scale: 1 }}
                className="rounded-[1.5rem] border border-brand/20 bg-brand/5 p-5 text-center shadow-lg shadow-black/5"
              >
                <CheckCircle2 size={32} className="text-brand mx-auto mb-3" />
                <p className="font-heading font-semibold mb-1">Ready for Repository Chat</p>
                <p className="text-sm text-muted-foreground mb-4">
                  {fileCount} files · {nodeCount} chunks indexed
                </p>
                <Button
                  onClick={() => router.push(`/repo/${repoId}/chat`)}
                  className="bg-brand hover:bg-green-400 text-green-950 font-semibold cursor-pointer"
                >
                  <MessageSquare size={15} className="mr-2" />
                  Start Repository Chat
                </Button>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </section>
    </div>
  );
}
