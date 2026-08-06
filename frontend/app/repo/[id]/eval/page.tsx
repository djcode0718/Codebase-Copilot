'use client';
/**
 * app/repo/[id]/eval/page.tsx
 * Evaluation dashboard — radar chart, metric cards, latency breakdown.
 * Uses real EvalSummary fields from supabase_service.py save_evaluation.
 */
import { useParams } from 'next/navigation';
import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import {
  RadarChart, Radar, PolarGrid, PolarAngleAxis,
  ResponsiveContainer, Tooltip,
} from 'recharts';
import { BarChart2, Zap, Play, Loader2, Target, CheckCircle2, Activity, Sparkles, Clock3 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { createClient } from '@/lib/supabase/client';
import { getLatestEval, evalRunUrl, authHeaders } from '@/lib/api';
import { toast } from 'sonner';
import type { EvalSummary, EvalEvent } from '@/lib/types';
import { cn } from '@/lib/utils';

function pct(v: number) { return `${(v * 100).toFixed(1)}%`; }
function ms(v: number)  { return `${Math.round(v)}ms`; }

const METRIC_CARDS = [
  { key: 'hit_rate',        label: 'Hit Rate',      fmt: pct, color: 'text-brand',       desc: 'Retrieved correct chunk in top-k' },
  { key: 'mrr',             label: 'MRR',            fmt: pct, color: 'text-blue-400',    desc: 'Mean Reciprocal Rank' },
  { key: 'avg_faithfulness',label: 'Faithfulness',   fmt: pct, color: 'text-violet-400',  desc: 'Answer grounded in context' },
  { key: 'avg_relevancy',   label: 'Relevancy',      fmt: pct, color: 'text-amber-400',   desc: 'Answer relevant to question' },
  { key: 'mode_accuracy',   label: 'Mode Accuracy',  fmt: pct, color: 'text-pink-400',    desc: 'Query routing correctness' },
] as const;

const LATENCY_CARDS = [
  { key: 'avg_latency_total',     label: 'Total',     color: 'bg-foreground/20' },
  { key: 'avg_latency_retrieval', label: 'Retrieval', color: 'bg-blue-400' },
  { key: 'avg_latency_rerank',    label: 'Rerank',    color: 'bg-violet-400' },
  { key: 'avg_latency_llm',       label: 'LLM',       color: 'bg-amber-400' },
] as const;

function EvalEmptyState({ onRun, running }: { onRun: () => void; running: boolean }) {
  return (
    <div className="rounded-[1.5rem] border border-border bg-card/80 px-6 py-16 text-center shadow-lg shadow-black/5 backdrop-blur-sm">
      <Target size={32} className="text-muted-foreground mx-auto mb-3" />
      <h3 className="font-heading text-lg font-semibold mb-2">No evaluation data yet</h3>
      <p className="mx-auto mb-5 max-w-sm text-sm text-muted-foreground">
        Run an evaluation to see quality metrics, latency breakdown, and a radar chart.
      </p>
      <Button
        onClick={onRun}
        disabled={running}
        className="bg-violet-500 hover:bg-violet-400 text-white cursor-pointer"
      >
        <Play size={14} className="mr-2" />
        Run first evaluation
      </Button>
    </div>
  );
}

export default function EvalPage() {
  const { id: repoId } = useParams<{ id: string }>();
  const [token, setToken] = useState('');
  const [evalData, setEvalData] = useState<EvalSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [runLog, setRunLog] = useState<string[]>([]);

  useEffect(() => {
    async function load() {
      const { data } = await createClient().auth.getSession();
      const t = data.session?.access_token ?? '';
      setToken(t);
      if (!t) return;
      try {
        const e = await getLatestEval(t, repoId);
        setEvalData(e);
      } catch { /* no eval yet */ }
      setLoading(false);
    }
    load();
  }, [repoId]);

  async function runEval() {
    if (!token || running) return;
    setRunning(true);
    setRunLog([]);
    try {
      const res = await fetch(evalRunUrl(), {
        method: 'POST',
        headers: authHeaders(token),
        body: JSON.stringify({ repo_id: repoId, index_name: '' }),
      });
      if (!res.body) throw new Error('No stream');
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() ?? '';
        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          const event: EvalEvent = JSON.parse(line.slice(6));
          if (event.type === 'progress') {
            setRunLog((l) => [...l, event.message]);
          } else if (event.type === 'result') {
            setEvalData(event.summary);
          } else if (event.type === 'error') {
            toast.error('Evaluation error: ' + event.message);
          } else if (event.type === 'done') {
            toast.success('Evaluation complete');
          }
        }
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Evaluation failed');
    }
    setRunning(false);
    setRunLog([]);
  }

  function buildRadarData() {
    if (!evalData) return [];
    return [
      { metric: 'Hit Rate',    value: evalData.hit_rate * 100 },
      { metric: 'MRR',         value: evalData.mrr * 100 },
      { metric: 'Faithfulness',value: evalData.avg_faithfulness * 100 },
      { metric: 'Relevancy',   value: evalData.avg_relevancy * 100 },
      { metric: 'Mode Acc.',   value: evalData.mode_accuracy * 100 },
    ];
  }

  const radarData = buildRadarData();

  return (
    <div className="space-y-6">
      <motion.section
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        className="rounded-[1.5rem] border border-border bg-card/80 p-6 shadow-lg shadow-black/5 backdrop-blur-sm"
      >
        <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
          <div className="space-y-3">
            <div className="inline-flex items-center gap-2 rounded-full border border-border bg-muted/70 px-3 py-1 text-xs text-muted-foreground">
              <Activity size={12} className="text-brand" />
              Evaluation dashboard
            </div>
            <div>
              <h1 className="font-heading text-3xl font-bold tracking-tight flex items-center gap-2">
                <BarChart2 size={20} className="text-violet-400" />
                Evaluation Dashboard
              </h1>
              <p className="mt-2 max-w-2xl text-sm text-muted-foreground">
                Measure retrieval quality, answer fidelity, and latency with a polished enterprise-grade review surface.
              </p>
            </div>
          </div>
          <Button
            onClick={runEval}
            disabled={running}
            className="bg-violet-500 hover:bg-violet-400 text-white cursor-pointer"
          >
            {running ? (
              <><Loader2 size={14} className="animate-spin mr-2" />Running…</>
            ) : (
              <><Play size={14} className="mr-2" />Run evaluation</>
            )}
          </Button>
        </div>
      </motion.section>

      {runLog.length > 0 && (
        <div className="rounded-[1.25rem] border border-border bg-card/80 p-4 shadow-sm shadow-black/5">
          <div className="mb-2 flex items-center gap-2 text-xs uppercase tracking-[0.18em] text-muted-foreground">
            <Sparkles size={11} className="text-brand" />
            Run log
          </div>
          <div className="space-y-1">
            {runLog.map((msg, i) => (
              <p key={i} className="text-xs font-code text-muted-foreground">{msg}</p>
            ))}
          </div>
        </div>
      )}

      {loading && (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-5">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="h-24 rounded-[1.25rem] border border-border bg-card/60 animate-pulse" />
          ))}
        </div>
      )}

      {!loading && !evalData && (
        <EvalEmptyState onRun={runEval} running={running} />
      )}

      {evalData && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="space-y-6"
        >

          <div className="flex flex-wrap items-center gap-3 text-xs text-muted-foreground">

            <span className="inline-flex items-center gap-1.5 rounded-full border border-border bg-card px-2.5 py-1">
              <CheckCircle2 size={12} className="text-brand" />
              {evalData.total_queries ?? '—'} test queries
            </span>
            <span className="inline-flex items-center gap-1.5 rounded-full border border-border bg-card px-2.5 py-1">
              <Zap size={12} className={evalData.colbert_enabled ? 'text-brand' : 'text-muted-foreground'} />
              ColBERT reranking: {evalData.colbert_enabled ? 'enabled' : 'disabled'}
            </span>
            <span className="inline-flex items-center gap-1.5 rounded-full border border-border bg-card px-2.5 py-1">
              <Clock3 size={12} />
              {new Date(evalData.created_at).toLocaleString()}
            </span>
          </div>

          <div className="grid grid-cols-1 gap-6 xl:grid-cols-[1fr_0.95fr]">
            <div className="space-y-3">
              <h2 className="font-heading text-sm font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                Quality metrics
              </h2>
              <div className="grid grid-cols-1 gap-3">
                {METRIC_CARDS.map((m) => {
                  const value = evalData[m.key as keyof EvalSummary] as number;
                  return (
                    <div key={m.key} className="rounded-[1.25rem] border border-border bg-card/80 px-4 py-3 flex items-center justify-between shadow-sm shadow-black/5">
                      <div>
                        <p className="text-xs text-muted-foreground">{m.label}</p>
                        <p className="text-xs text-muted-foreground/60 mt-0.5">{m.desc}</p>
                      </div>
                      <span className={cn('font-heading font-bold text-xl', m.color)}>
                        {m.fmt(value ?? 0)}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>

            <div className="rounded-[1.5rem] border border-border bg-card/80 p-5 shadow-lg shadow-black/5">
              <div className="mb-4 flex items-center gap-2">
                <Sparkles size={15} className="text-brand" />
                <h2 className="font-heading text-sm font-semibold uppercase tracking-[0.18em] text-muted-foreground">Quality radar</h2>
              </div>
              <ResponsiveContainer width="100%" height={320}>
                <RadarChart data={radarData}>
                  <PolarGrid stroke="#334155" />
                  <PolarAngleAxis
                    dataKey="metric"
                    tick={{ fill: 'currentColor', fontSize: 11, fontFamily: 'IBM Plex Sans' }}
                  />
                  <Radar
                    dataKey="value"
                    stroke="#22C55E"
                    fill="#22C55E"
                    fillOpacity={0.16}
                    strokeWidth={2}
                  />
                  <Tooltip
                    contentStyle={{
                      background: 'var(--popover)',
                      border: '1px solid var(--border)',
                      borderRadius: '14px',
                      fontSize: '12px',
                      color: 'var(--popover-foreground)',
                    }}
                    formatter={(value: unknown) => [`${Number(value || 0).toFixed(1)}%`, 'Score']}
                  />
                </RadarChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div>
            <h2 className="font-heading text-sm font-semibold uppercase tracking-[0.18em] text-muted-foreground mb-3">
              Average latency
            </h2>
            <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
              {LATENCY_CARDS.map((lc) => {
                const value = evalData[lc.key as keyof EvalSummary] as number;
                return (
                  <div key={lc.key} className="rounded-[1.25rem] border border-border bg-card/80 p-4 shadow-sm shadow-black/5">
                    <div className="flex items-center gap-2 mb-2">
                      <span className={cn('w-2 h-2 rounded-full', lc.color)} />
                      <span className="text-xs text-muted-foreground">{lc.label}</span>
                    </div>
                    <p className="font-heading font-bold text-lg">{ms(value ?? 0)}</p>
                  </div>
                );
              })}
            </div>
          </div>
        </motion.div>
      )}
    </div>
  );
}
