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
  ResponsiveContainer, Tooltip, LineChart, Line, XAxis, YAxis, CartesianGrid,
} from 'recharts';
import { BarChart2, Zap, Play, Loader2, Target, CheckCircle2, Activity, Sparkles, Clock3 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { createClient } from '@/lib/supabase/client';
import { getLatestEval, evalRunUrl, authHeaders, getEvalHistory, compareEvals, type RunEvalPayload } from '@/lib/api';
import { toast } from 'sonner';
import type { EvalSummary, EvalEvent, EvalHistoryPoint, EvalComparisonResponse, EvalRecommendation } from '@/lib/types';
import { cn } from '@/lib/utils';

function pct(v: number) { return `${(v * 100).toFixed(1)}%`; }
function ms(v: number)  { return `${Math.round(v)}ms`; }
function usd(v: number) { return `$${Number(v || 0).toFixed(4)}`; }

const EVAL_MODES = [
  { key: 'quick', label: 'Quick', desc: 'Cache + static analysis only' },
  { key: 'standard', label: 'Standard', desc: 'Changed files + AI only when needed' },
  { key: 'deep', label: 'Deep', desc: 'Full evaluation' },
  { key: 'benchmark', label: 'Benchmark', desc: 'Compare with previous runs' },
] as const;

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

function EvalRunLog({ runLog }: { runLog: string[] }) {
  if (runLog.length === 0) return null;
  return (
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
  );
}

function EvalLoadingSkeleton() {
  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-5">
      {[...Array(5)].map((_, i) => (
        <div key={i} className="h-24 rounded-[1.25rem] border border-border bg-card/60 animate-pulse" />
      ))}
    </div>
  );
}

function EvalBadges({ evalData }: { evalData: EvalSummary }) {
  return (
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
      <span className="inline-flex items-center gap-1.5 rounded-full border border-border bg-card px-2.5 py-1">
        Mode: {(evalData.mode ?? 'standard').toUpperCase()}
      </span>
      <span className="inline-flex items-center gap-1.5 rounded-full border border-border bg-card px-2.5 py-1">
        Cache: {evalData.cache_hit ? 'hit' : 'miss'}
      </span>
    </div>
  );
}

function EvalModeSelector({
  selected,
  onSelect,
  disabled,
}: {
  selected: 'quick' | 'standard' | 'deep' | 'benchmark';
  onSelect: (mode: 'quick' | 'standard' | 'deep' | 'benchmark') => void;
  disabled: boolean;
}) {
  return (
    <div className="grid grid-cols-1 gap-2 md:grid-cols-2 xl:grid-cols-4">
      {EVAL_MODES.map((mode) => (
        <button
          key={mode.key}
          type="button"
          disabled={disabled}
          onClick={() => onSelect(mode.key)}
          className={cn(
            'rounded-[1rem] border p-3 text-left transition-colors',
            selected === mode.key
              ? 'border-violet-400/70 bg-violet-500/10'
              : 'border-border bg-card/70 hover:border-violet-500/30'
          )}
        >
          <p className="text-sm font-semibold">{mode.label}</p>
          <p className="text-xs text-muted-foreground mt-1">{mode.desc}</p>
        </button>
      ))}
    </div>
  );
}

function EvalSummaryCard({ evalData }: { evalData: EvalSummary }) {
  const aiSummary = evalData.ai_summary;
  if (!aiSummary) return null;
  return (
    <div className="rounded-[1.5rem] border border-border bg-card/80 p-5 shadow-sm shadow-black/5">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="font-heading text-sm font-semibold uppercase tracking-[0.18em] text-muted-foreground">AI Evaluation Summary</h2>
        <span className="font-heading text-2xl font-bold text-brand">{aiSummary.overall_score.toFixed(1)}</span>
      </div>
      <p className="text-xs text-muted-foreground">Estimated score lift after top actions: +{aiSummary.estimated_score_improvement.toFixed(1)}</p>
      <div className="mt-4 grid grid-cols-1 gap-3 lg:grid-cols-3">
        <div>
          <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground mb-2">Strengths</p>
          {(aiSummary.strengths ?? []).slice(0, 3).map((s, i) => <p key={i} className="text-sm mb-1">- {s}</p>)}
        </div>
        <div>
          <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground mb-2">Weaknesses</p>
          {(aiSummary.weaknesses ?? []).slice(0, 3).map((s, i) => <p key={i} className="text-sm mb-1">- {s}</p>)}
        </div>
        <div>
          <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground mb-2">Top priority improvements</p>
          {(aiSummary.top_priority_improvements ?? []).slice(0, 3).map((s, i) => <p key={i} className="text-sm mb-1">- {s}</p>)}
        </div>
      </div>
    </div>
  );
}

function TopRecommendationsPanel({
  recommendations,
  onAction,
}: {
  recommendations: EvalRecommendation[];
  onAction: (rec: EvalRecommendation) => void;
}) {
  const top = [...(recommendations ?? [])].sort((a, b) => b.estimated_impact - a.estimated_impact).slice(0, 5);
  if (top.length === 0) return null;

  return (
    <div className="rounded-[1.5rem] border border-border bg-card/80 p-5 shadow-sm shadow-black/5">
      <h2 className="font-heading text-sm font-semibold uppercase tracking-[0.18em] text-muted-foreground mb-3">Top Recommendations</h2>
      <div className="space-y-3">
        {top.map((rec) => (
          <div key={`${rec.rank}-${rec.title}`} className="rounded-xl border border-border bg-background/40 p-3">
            <div className="flex items-start justify-between gap-2">
              <div>
                <p className="text-sm font-semibold">#{rec.rank} {rec.title}</p>
                <p className="text-xs text-muted-foreground mt-1">{rec.description}</p>
              </div>
              <div className="text-right">
                <p className="text-xs text-muted-foreground">Impact {rec.estimated_impact.toFixed(1)}</p>
                <p className="text-xs text-muted-foreground">Effort {rec.expected_effort}</p>
              </div>
            </div>
            {rec.one_click_action && (
              <Button
                className="mt-2 h-8 text-xs bg-violet-500 hover:bg-violet-400 text-white"
                onClick={() => onAction(rec)}
              >
                Run action
              </Button>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

function EvalEfficiencyPanel({ evalData }: { evalData: EvalSummary }) {
  const ef = evalData.efficiency;
  if (!ef) return null;
  return (
    <div className="rounded-[1.5rem] border border-border bg-card/80 p-5 shadow-sm shadow-black/5">
      <h2 className="font-heading text-sm font-semibold uppercase tracking-[0.18em] text-muted-foreground mb-3">Evaluation Efficiency</h2>
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-3">
        <div className="rounded-xl border border-border bg-background/40 p-3"><p className="text-xs text-muted-foreground">Cache hit rate</p><p className="font-heading text-lg">{pct(ef.cache_hit_rate)}</p></div>
        <div className="rounded-xl border border-border bg-background/40 p-3"><p className="text-xs text-muted-foreground">AI calls</p><p className="font-heading text-lg">{ef.ai_calls}</p></div>
        <div className="rounded-xl border border-border bg-background/40 p-3"><p className="text-xs text-muted-foreground">Static analysis</p><p className="font-heading text-lg">{pct(ef.static_analysis_percentage)}</p></div>
        <div className="rounded-xl border border-border bg-background/40 p-3"><p className="text-xs text-muted-foreground">Estimated tokens</p><p className="font-heading text-lg">{ef.estimated_token_usage.toLocaleString()}</p></div>
        <div className="rounded-xl border border-border bg-background/40 p-3"><p className="text-xs text-muted-foreground">Estimated cost</p><p className="font-heading text-lg">{usd(ef.estimated_cost_usd)}</p></div>
        <div className="rounded-xl border border-border bg-background/40 p-3"><p className="text-xs text-muted-foreground">Estimated savings</p><p className="font-heading text-lg text-brand">{usd(ef.estimated_savings_usd)}</p></div>
      </div>
    </div>
  );
}

function EvalTrendCharts({ points }: { points: EvalHistoryPoint[] }) {
  if (!points || points.length === 0) return null;
  const data = [...points].reverse().map((p) => ({
    t: new Date(p.created_at).toLocaleDateString(),
    overall: p.overall_score,
    hitRate: p.hit_rate * 100,
    faithfulness: p.avg_faithfulness * 100,
    latency: p.avg_latency_total,
    cacheHit: p.cache_hit_rate * 100,
    aiCost: p.estimated_ai_cost_usd,
  }));

  return (
    <div className="rounded-[1.5rem] border border-border bg-card/80 p-5 shadow-sm shadow-black/5">
      <h2 className="font-heading text-sm font-semibold uppercase tracking-[0.18em] text-muted-foreground mb-4">Historical Trends</h2>
      <div className="grid grid-cols-1 gap-5 xl:grid-cols-2">
        <ResponsiveContainer width="100%" height={220}><LineChart data={data}><CartesianGrid strokeDasharray="3 3" /><XAxis dataKey="t" /><YAxis /><Tooltip /><Line type="monotone" dataKey="overall" stroke="#22C55E" dot={false} name="Overall score" /><Line type="monotone" dataKey="hitRate" stroke="#60A5FA" dot={false} name="Hit rate %" /></LineChart></ResponsiveContainer>
        <ResponsiveContainer width="100%" height={220}><LineChart data={data}><CartesianGrid strokeDasharray="3 3" /><XAxis dataKey="t" /><YAxis /><Tooltip /><Line type="monotone" dataKey="faithfulness" stroke="#C084FC" dot={false} name="Faithfulness %" /><Line type="monotone" dataKey="cacheHit" stroke="#F59E0B" dot={false} name="Cache hit %" /></LineChart></ResponsiveContainer>
        <ResponsiveContainer width="100%" height={220}><LineChart data={data}><CartesianGrid strokeDasharray="3 3" /><XAxis dataKey="t" /><YAxis /><Tooltip /><Line type="monotone" dataKey="latency" stroke="#F97316" dot={false} name="Latency ms" /></LineChart></ResponsiveContainer>
        <ResponsiveContainer width="100%" height={220}><LineChart data={data}><CartesianGrid strokeDasharray="3 3" /><XAxis dataKey="t" /><YAxis /><Tooltip /><Line type="monotone" dataKey="aiCost" stroke="#34D399" dot={false} name="Estimated AI cost" /></LineChart></ResponsiveContainer>
      </div>
    </div>
  );
}

function EvalComparisonPanel({
  comparison,
  baselineId,
  onSelectBaseline,
  history,
}: {
  comparison: EvalComparisonResponse | null;
  baselineId: string;
  onSelectBaseline: (id: string) => void;
  history: EvalHistoryPoint[];
}) {
  if (!comparison?.comparison) return null;
  const c = comparison.comparison;
  return (
    <div className="rounded-[1.5rem] border border-border bg-card/80 p-5 shadow-sm shadow-black/5">
      <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between mb-3">
        <h2 className="font-heading text-sm font-semibold uppercase tracking-[0.18em] text-muted-foreground">Run Comparison</h2>
        <select
          className="rounded-lg border border-border bg-background px-3 py-2 text-xs"
          value={baselineId}
          onChange={(e) => onSelectBaseline(e.target.value)}
        >
          <option value="">Auto previous run</option>
          {history.map((h) => (
            <option key={h.id} value={h.id}>{new Date(h.created_at).toLocaleString()} - {h.id.slice(0, 8)}</option>
          ))}
        </select>
      </div>
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
        <div className="rounded-xl border border-border bg-background/40 p-3"><p className="text-xs text-muted-foreground">Overall</p><p className="font-heading text-lg">{c.overall_score_delta.toFixed(2)}</p></div>
        <div className="rounded-xl border border-border bg-background/40 p-3"><p className="text-xs text-muted-foreground">Hit rate</p><p className="font-heading text-lg">{pct(c.hit_rate_delta)}</p></div>
        <div className="rounded-xl border border-border bg-background/40 p-3"><p className="text-xs text-muted-foreground">Faithfulness</p><p className="font-heading text-lg">{pct(c.faithfulness_delta)}</p></div>
        <div className="rounded-xl border border-border bg-background/40 p-3"><p className="text-xs text-muted-foreground">Latency</p><p className="font-heading text-lg">{ms(c.latency_delta_ms)}</p></div>
        <div className="rounded-xl border border-border bg-background/40 p-3"><p className="text-xs text-muted-foreground">Cost delta</p><p className="font-heading text-lg">{usd(c.estimated_cost_delta_usd)}</p></div>
      </div>
    </div>
  );
}

function QualityMetrics({ evalData }: { evalData: EvalSummary }) {
  return (
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
  );
}

function QualityRadar({ radarData }: { radarData: { metric: string; value: number }[] }) {
  return (
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
  );
}

function LatencySection({ evalData }: { evalData: EvalSummary }) {
  return (
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
  );
}

function useEvalData(repoId: string) {
  const [token, setToken] = useState('');
  const [evalData, setEvalData] = useState<EvalSummary | null>(null);
  const [history, setHistory] = useState<EvalHistoryPoint[]>([]);
  const [comparison, setComparison] = useState<EvalComparisonResponse | null>(null);
  const [selectedMode, setSelectedMode] = useState<'quick' | 'standard' | 'deep' | 'benchmark'>('standard');
  const [selectedBaselineId, setSelectedBaselineId] = useState('');
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
        const h = await getEvalHistory(t, repoId, 30);
        setHistory(h.points ?? []);
        const c = await compareEvals(t, repoId);
        setComparison(c);
      } catch { /* no eval yet */ }
      setLoading(false);
    }
    load();
  }, [repoId]);

  async function refreshInsights(activeToken: string, baselineId?: string) {
    try {
      const h = await getEvalHistory(activeToken, repoId, 30);
      setHistory(h.points ?? []);
      const c = await compareEvals(activeToken, repoId, baselineId ? { baselineEvalId: baselineId } : undefined);
      setComparison(c);
    } catch {
      // Keep existing dashboard data visible even if history/compare fails.
    }
  }

  async function runEval(modeOverride?: 'quick' | 'standard' | 'deep' | 'benchmark') {
    if (!token || running) return;
    setRunning(true);
    setRunLog([]);
    const mode = modeOverride ?? selectedMode;
    try {
      const payload: RunEvalPayload = {
        repo_id: repoId,
        index_name: '',
        mode,
      };
      const res = await fetch(evalRunUrl(), {
        method: 'POST',
        headers: authHeaders(token),
        body: JSON.stringify(payload),
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
      await refreshInsights(token, selectedBaselineId || undefined);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Evaluation failed');
    }
    setRunning(false);
    setRunLog([]);
  }

  async function applyRecommendation(rec: EvalRecommendation) {
    const action = rec.one_click_action;
    if (!action) return;
    if (action.type === 'run_mode' && action.mode) {
      setSelectedMode(action.mode);
      await runEval(action.mode);
      return;
    }
    toast.info(`${rec.title}: action '${action.type}' ready.`);
  }

  async function refreshComparisonWithBaseline(baselineId: string) {
    setSelectedBaselineId(baselineId);
    if (!token) return;
    await refreshInsights(token, baselineId || undefined);
  }

  return {
    token,
    evalData,
    history,
    comparison,
    selectedMode,
    selectedBaselineId,
    loading,
    running,
    runLog,
    setSelectedMode,
    runEval,
    applyRecommendation,
    refreshComparisonWithBaseline,
  };
}

function buildRadarData(evalData: EvalSummary | null) {
  if (!evalData) return [];
  return [
    { metric: 'Hit Rate',    value: evalData.hit_rate * 100 },
    { metric: 'MRR',         value: evalData.mrr * 100 },
    { metric: 'Faithfulness',value: evalData.avg_faithfulness * 100 },
    { metric: 'Relevancy',   value: evalData.avg_relevancy * 100 },
    { metric: 'Mode Acc.',   value: evalData.mode_accuracy * 100 },
  ];
}

export default function EvalPage() {
  const { id: repoId } = useParams<{ id: string }>();
  const {
    evalData,
    history,
    comparison,
    selectedMode,
    selectedBaselineId,
    loading,
    running,
    runLog,
    setSelectedMode,
    runEval,
    applyRecommendation,
    refreshComparisonWithBaseline,
  } = useEvalData(repoId);
  const radarData = buildRadarData(evalData);

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
            <EvalModeSelector selected={selectedMode} onSelect={setSelectedMode} disabled={running} />
          </div>
          <Button
            onClick={() => runEval()}
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

      <EvalRunLog runLog={runLog} />

      {loading && <EvalLoadingSkeleton />}

      {!loading && !evalData && (
        <EvalEmptyState onRun={runEval} running={running} />
      )}

      {evalData && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="space-y-6"
        >
          <EvalBadges evalData={evalData} />
          <EvalSummaryCard evalData={evalData} />
          <TopRecommendationsPanel
            recommendations={evalData.top_recommendations ?? []}
            onAction={applyRecommendation}
          />
          <EvalEfficiencyPanel evalData={evalData} />
          <EvalComparisonPanel
            comparison={comparison}
            baselineId={selectedBaselineId}
            onSelectBaseline={refreshComparisonWithBaseline}
            history={history}
          />
          <EvalTrendCharts points={history} />
          <div className="grid grid-cols-1 gap-6 xl:grid-cols-[1fr_0.95fr]">
            <QualityMetrics evalData={evalData} />
            <QualityRadar radarData={radarData} />
          </div>
          <LatencySection evalData={evalData} />
        </motion.div>
      )}
    </div>
  );
}
