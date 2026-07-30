'use client';
/**
 * app/repo/[id]/indexing/page.tsx
 * Centerpiece indexing screen — real-time SSE pipeline with animated steps,
 * live stats bar, progress indicator. No spinners.
 */
import { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { motion, AnimatePresence } from 'framer-motion';
import { CheckCircle2, AlertCircle, MessageSquare, RotateCcw, ArrowLeft } from 'lucide-react';
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

  return (
    <div className="min-h-screen bg-background flex flex-col">
      {/* Back link */}
      <div className="px-8 pt-6">
        <Link
          href="/dashboard"
          className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors cursor-pointer"
        >
          <ArrowLeft size={14} />
          Dashboard
        </Link>
      </div>

      <div className="flex-1 flex items-start justify-center px-4 py-12">
        <div className="w-full max-w-2xl">
          {/* Title */}
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            className="mb-8 text-center"
          >
            <h1 className="font-heading text-xl font-bold mb-1">
              {isComplete ? 'Indexing complete' : hasError ? 'Indexing failed' : 'Indexing repository'}
            </h1>
            <p className="text-muted-foreground text-sm">
              {isComplete && indexName
                ? `"${indexName}" is ready to chat`
                : hasError
                ? 'An error occurred. See details below.'
                : 'Processing your repository through the RAG pipeline…'}
            </p>
          </motion.div>

          {/* Progress bar */}
          <div className="mb-8">
            <div className="flex items-center justify-between text-xs text-muted-foreground mb-2">
              <span>{hasError ? 'Failed' : `${progress}%`}</span>
              <span>{formatElapsed(elapsedMs)}</span>
            </div>
            <Progress
              value={progress}
              className={`h-1.5 ${hasError ? '[&>div]:bg-destructive' : '[&>div]:bg-brand'}`}
            />
          </div>

          {/* Pipeline steps */}
          <div className="bg-card border border-border rounded-xl p-6 mb-6">
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

          {/* Live stats bar */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.3 }}
            className="grid grid-cols-3 gap-4 mb-6"
          >
            {[
              { label: 'Files found', value: fileCount },
              { label: 'Chunks indexed', value: nodeCount },
              { label: 'Elapsed', value: null, custom: formatElapsed(elapsedMs) },
            ].map((stat) => (
              <div
                key={stat.label}
                className="bg-card border border-border rounded-lg p-4 text-center"
              >
                <div className="text-lg font-heading font-bold mb-1">
                  {stat.custom ? (
                    <span className="text-foreground font-semibold font-mono text-base">
                      {stat.custom}
                    </span>
                  ) : (
                    <AnimatedCounter value={stat.value ?? null} />
                  )}
                </div>
                <div className="text-xs text-muted-foreground">{stat.label}</div>
              </div>
            ))}
          </motion.div>

          {/* Error block */}
          <AnimatePresence>
            {hasError && errorMessage && (
              <motion.div
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                className="bg-destructive/5 border border-destructive/20 rounded-xl p-5 mb-6"
              >
                <div className="flex items-start gap-3">
                  <AlertCircle size={18} className="text-destructive flex-shrink-0 mt-0.5" />
                  <div>
                    <p className="text-sm font-medium text-destructive mb-1">
                      Indexing failed
                    </p>
                    <pre className="text-xs text-muted-foreground font-code whitespace-pre-wrap">
                      {errorMessage}
                    </pre>
                  </div>
                </div>
                <div className="flex gap-2 mt-4">
                  <Button
                    size="sm"
                    variant="outline"
                    className="border-border cursor-pointer"
                    onClick={() => router.push('/repo/new')}
                  >
                    <RotateCcw size={13} className="mr-1.5" />
                    Retry with new URL
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

          {/* Success CTA */}
          <AnimatePresence>
            {isComplete && (
              <motion.div
                initial={{ opacity: 0, scale: 0.96 }}
                animate={{ opacity: 1, scale: 1 }}
                className="bg-brand/5 border border-brand/20 rounded-xl p-5 text-center"
              >
                <CheckCircle2 size={32} className="text-brand mx-auto mb-3" />
                <p className="font-heading font-semibold mb-1">Ready to chat!</p>
                <p className="text-sm text-muted-foreground mb-4">
                  {fileCount} files · {nodeCount} chunks indexed
                </p>
                <Button
                  onClick={() => router.push(`/repo/${repoId}/chat`)}
                  className="bg-brand hover:bg-green-400 text-green-950 font-semibold cursor-pointer"
                >
                  <MessageSquare size={15} className="mr-2" />
                  Start chatting
                </Button>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
    </div>
  );
}
