'use client';

import { useEffect, useMemo, useState } from 'react';
import {
  AlertTriangle,
  ArrowUpRight,
  CheckCircle2,
  Clock3,
  Loader2,
  RefreshCw,
  TrendingDown,
  TrendingUp,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import {
  getLatestRepositoryHealth,
  getRepositoryHealthHistory,
  runRepositoryHealthAnalysis,
} from '@/lib/api';
import type {
  HealthCategoryName,
  HealthCategoryScore,
  HealthHistoryResponse,
  HealthRun,
} from '@/lib/types';
import { toast } from 'sonner';
import {
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

interface RepositoryHealthDashboardProps {
  repoId: string;
  token: string;
  disabled?: boolean;
  onRunChange?: (run: HealthRun | null) => void;
}

function healthCacheKey(repoId: string): string {
  return `codebase:health-latest:${repoId}`;
}

function readCachedRun(repoId: string): HealthRun | null {
  if (typeof window === 'undefined') return null;
  try {
    const raw = window.localStorage.getItem(healthCacheKey(repoId));
    if (!raw) return null;
    const parsed = JSON.parse(raw) as HealthRun;
    return parsed && typeof parsed === 'object' ? parsed : null;
  } catch {
    return null;
  }
}

function writeCachedRun(repoId: string, run: HealthRun | null): void {
  if (typeof window === 'undefined') return;
  try {
    if (!run) {
      window.localStorage.removeItem(healthCacheKey(repoId));
      return;
    }
    window.localStorage.setItem(healthCacheKey(repoId), JSON.stringify(run));
  } catch {
    // Ignore local storage errors.
  }
}

const CATEGORY_ORDER: HealthCategoryName[] = [
  'Architecture',
  'Security',
  'Testing',
  'Documentation',
  'Performance',
  'Maintainability',
  'Technical Debt',
  'Dependencies',
  'Code Quality',
  'Scalability',
  'Observability',
  'Developer Experience',
];

function trendTone(value: number): string {
  if (value > 0) return 'text-emerald-400';
  if (value < 0) return 'text-rose-400';
  return 'text-muted-foreground';
}

function severityBadge(score: number): string {
  if (score >= 90) return 'bg-emerald-500/10 text-emerald-300 border-emerald-500/30';
  if (score >= 80) return 'bg-blue-500/10 text-blue-300 border-blue-500/30';
  if (score >= 70) return 'bg-amber-500/10 text-amber-300 border-amber-500/30';
  return 'bg-rose-500/10 text-rose-300 border-rose-500/30';
}

export default function RepositoryHealthDashboard({ repoId, token, disabled, onRunChange }: RepositoryHealthDashboardProps) {
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [run, setRun] = useState<HealthRun | null>(null);
  const [history, setHistory] = useState<HealthHistoryResponse | null>(null);
  const [selectedCategory, setSelectedCategory] = useState<HealthCategoryName>('Architecture');

  useEffect(() => {
    if (!token) return;
    let active = true;

    async function load() {
      setLoading(true);
      let nextRun: HealthRun | null = null;
      try {
        const latestRes = await getLatestRepositoryHealth(token, repoId);
        nextRun = latestRes.latest ?? readCachedRun(repoId);
        if (active) {
          setRun(nextRun);
          onRunChange?.(nextRun);
          writeCachedRun(repoId, nextRun);
        }
      } catch (err) {
        nextRun = readCachedRun(repoId);
        if (active) {
          setRun(nextRun);
          onRunChange?.(nextRun);
          if (!nextRun) {
            toast.error(err instanceof Error ? err.message : 'Failed to load repository health intelligence');
          }
        }
      }

      try {
        const historyRes = await getRepositoryHealthHistory(token, repoId, 30, 30);
        if (!active) return;
        setHistory(historyRes);
      } catch (err) {
        if (active) {
          setHistory((prev) => prev ?? null);
          if (!nextRun) {
            toast.error(err instanceof Error ? err.message : 'Failed to load repository health history');
          }
        }
      } finally {
        if (active) setLoading(false);
      }
    }

    load();
    return () => {
      active = false;
    };
  }, [onRunChange, repoId, token]);

  const categories = useMemo(() => {
    if (!run) return [];
    const map = new Map(run.categories.map((c) => [c.category, c]));
    return CATEGORY_ORDER.map((name) => map.get(name)).filter((c): c is HealthCategoryScore => Boolean(c));
  }, [run]);

  const selected = useMemo(() => {
    return categories.find((c) => c.category === selectedCategory) || categories[0] || null;
  }, [categories, selectedCategory]);

  const selectedFindings = useMemo(() => {
    if (!run || !selected) return [];
    return run.findings.filter((f) => f.category === selected.category);
  }, [run, selected]);

  const chartData = useMemo(() => {
    if (!history) return [];
    return [...history.points]
      .reverse()
      .map((point, idx) => ({
        name: idx === 0 ? 'Today' : new Date(point.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
        score: point.repository_health,
      }));
  }, [history]);

  async function handleRunAnalysis() {
    if (!token || disabled || running) return;
    setRunning(true);
    try {
      const nextRun = await runRepositoryHealthAnalysis(token, repoId);
      setRun(nextRun);
      onRunChange?.(nextRun);
      writeCachedRun(repoId, nextRun);
      const historyRes = await getRepositoryHealthHistory(token, repoId, 30, 30);
      setHistory(historyRes);
      toast.success('Repository health analysis completed');
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to run analysis');
    } finally {
      setRunning(false);
    }
  }

  if (loading) {
    return (
      <div className="rounded-[1.5rem] border border-border bg-card/80 p-6 shadow-lg shadow-black/5">
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 size={14} className="animate-spin" />
          Loading Repository Health Intelligence...
        </div>
      </div>
    );
  }

  if (!run) {
    return (
      <div className="rounded-[1.5rem] border border-border bg-card/80 p-6 shadow-lg shadow-black/5 space-y-4">
        <p className="text-sm text-muted-foreground">
          No health scan has been run yet for this repository.
        </p>
        <Button onClick={handleRunAnalysis} disabled={!token || disabled || running} className="cursor-pointer">
          {running ? <Loader2 size={14} className="mr-2 animate-spin" /> : <RefreshCw size={14} className="mr-2" />}
          Run Health Analysis
        </Button>
      </div>
    );
  }

  return (
    <section className="space-y-5">
      <div className="rounded-[1.5rem] border border-border bg-card/80 p-5 shadow-lg shadow-black/5 backdrop-blur-sm">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <h2 className="font-heading text-lg font-semibold tracking-tight">Repository Health Intelligence</h2>
            <p className="text-xs text-muted-foreground mt-1">Dynamic, evidence-backed engineering KPI</p>
          </div>
          <Button onClick={handleRunAnalysis} disabled={!token || disabled || running} className="cursor-pointer">
            {running ? <Loader2 size={14} className="mr-2 animate-spin" /> : <RefreshCw size={14} className="mr-2" />}
            Re-run Analysis
          </Button>
        </div>

        <div className="mt-5 grid grid-cols-1 gap-4 xl:grid-cols-[0.9fr_1.1fr]">
          <div className="rounded-2xl border border-border/70 bg-background/60 p-4">
            <div className="flex items-end gap-2">
              <span className="text-4xl font-bold font-heading">{run.top_level.repository_health}</span>
              <span className="text-sm text-muted-foreground mb-1">/100</span>
              <span className={cn('ml-2 inline-flex rounded-full border px-2 py-0.5 text-xs', severityBadge(run.top_level.repository_health))}>
                {run.top_level.grade}
              </span>
            </div>
            <div className="mt-2 flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
              <span className="inline-flex items-center gap-1"><Clock3 size={12} /> {run.top_level.status}</span>
              <span className={cn('inline-flex items-center gap-1', trendTone(run.top_level.trend))}>
                {run.top_level.trend >= 0 ? <TrendingUp size={12} /> : <TrendingDown size={12} />}
                {run.top_level.trend >= 0 ? '+' : ''}{run.top_level.trend}
              </span>
              <span>Size: {run.top_level.repository_size}</span>
              <span>Lang: {run.top_level.language_detection.join(', ') || 'Auto'}</span>
            </div>
            <div className="mt-3 space-y-2">
              <div>
                <p className="text-[11px] uppercase tracking-[0.15em] text-muted-foreground">Strongest areas</p>
                <div className="mt-1 flex flex-wrap gap-1.5">
                  {run.strengths.slice(0, 3).map((item) => (
                    <span key={item} className="inline-flex rounded-full border border-emerald-400/30 bg-emerald-500/10 px-2 py-0.5 text-[11px] text-emerald-700 dark:text-emerald-300">
                      {item}
                    </span>
                  ))}
                </div>
              </div>
              <div>
                <p className="text-[11px] uppercase tracking-[0.15em] text-muted-foreground">Priority improvements</p>
                <div className="mt-1 flex flex-wrap gap-1.5">
                  {run.weaknesses.slice(0, 3).map((item) => (
                    <span key={item} className="inline-flex rounded-full border border-amber-400/30 bg-amber-500/10 px-2 py-0.5 text-[11px] text-amber-700 dark:text-amber-300">
                      {item}
                    </span>
                  ))}
                  {run.weaknesses.length === 0 && <span className="text-[11px] text-muted-foreground">No critical weak areas detected.</span>}
                </div>
              </div>
            </div>
          </div>

          <div className="rounded-2xl border border-border/70 bg-background/60 p-4 h-[190px]">
            <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground mb-3">Health Trend (30 days)</p>
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={chartData} margin={{ top: 5, right: 10, left: -18, bottom: 0 }}>
                <XAxis dataKey="name" tick={{ fontSize: 11 }} stroke="hsl(var(--muted-foreground))" />
                <YAxis domain={[0, 100]} tick={{ fontSize: 11 }} stroke="hsl(var(--muted-foreground))" />
                <Tooltip />
                <Line type="monotone" dataKey="score" stroke="hsl(var(--primary))" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-[1.25fr_0.95fr]">
        <div className="rounded-[1.5rem] border border-border bg-card/80 p-5 shadow-lg shadow-black/5 space-y-4">
          <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground">Category Breakdown</p>
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
            {categories.map((cat) => (
              <button
                key={cat.category}
                type="button"
                onClick={() => setSelectedCategory(cat.category)}
                className={cn(
                  'rounded-2xl border p-3 text-left transition-colors cursor-pointer',
                  selected?.category === cat.category ? 'border-brand/40 bg-brand/5' : 'border-border/70 bg-background/60 hover:border-brand/20'
                )}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="text-sm font-medium">{cat.category}</span>
                  <span className={cn('rounded-full border px-2 py-0.5 text-xs', severityBadge(cat.score))}>{cat.score}</span>
                </div>
                <p className="text-xs text-muted-foreground mt-2 line-clamp-2">{cat.explanation}</p>
                <div className={cn('mt-2 text-xs inline-flex items-center gap-1', trendTone(cat.trend))}>
                  {cat.trend >= 0 ? <TrendingUp size={11} /> : <TrendingDown size={11} />}
                  {cat.trend >= 0 ? '+' : ''}{cat.trend}
                </div>
              </button>
            ))}
          </div>
        </div>

        <div className="rounded-[1.5rem] border border-border bg-card/80 p-5 shadow-lg shadow-black/5 space-y-4">
          <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground">Category Details</p>
          {!selected ? (
            <p className="text-sm text-muted-foreground">Select a category to inspect findings.</p>
          ) : (
            <>
              <div>
                <div className="flex items-center justify-between">
                  <h3 className="font-semibold">{selected.category}</h3>
                  <span className={cn('rounded-full border px-2 py-0.5 text-xs', severityBadge(selected.score))}>
                    {selected.score} · {selected.grade}
                  </span>
                </div>
                <p className="mt-2 text-xs text-muted-foreground">{selected.explanation}</p>
              </div>

              <div className="space-y-2">
                {selectedFindings.slice(0, 6).map((finding) => (
                  <div key={finding.id} className="rounded-xl border border-border/70 bg-background/60 px-3 py-2">
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <p className="text-sm font-medium">{finding.title}</p>
                        <p className="text-xs text-muted-foreground mt-1">{finding.details}</p>
                      </div>
                      <span className={cn('text-xs', finding.finding_type === 'problem' ? 'text-rose-300' : 'text-emerald-300')}>
                        {finding.finding_type === 'problem' ? <AlertTriangle size={12} /> : <CheckCircle2 size={12} />}
                      </span>
                    </div>
                    {finding.recommendation && (
                      <p className="text-xs mt-2 text-brand">Action: {finding.recommendation}</p>
                    )}
                    {finding.affected_files.length > 0 && (
                      <p className="text-[11px] mt-2 text-muted-foreground">
                        Files: {finding.affected_files.slice(0, 3).join(', ')}
                      </p>
                    )}
                  </div>
                ))}
              </div>
            </>
          )}
        </div>
      </div>

      <div className="rounded-[1.5rem] border border-border bg-card/80 p-5 shadow-lg shadow-black/5 space-y-4">
        <div className="flex items-center justify-between">
          <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground">Top 10 AI Recommendations</p>
          <span className="text-xs text-muted-foreground inline-flex items-center gap-1">
            Prioritized by impact <ArrowUpRight size={12} />
          </span>
        </div>
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          {[run.recommendations.slice(0, 5), run.recommendations.slice(5, 10)].map((column, colIndex) => (
            <div key={colIndex} className="space-y-3">
              {column.map((rec) => (
                <div key={`${rec.rank}-${rec.title}`} className="rounded-2xl border border-border/70 bg-background/60 px-4 py-3">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="text-sm font-medium">{rec.rank}. {rec.title}</p>
                      <p className="text-xs text-muted-foreground mt-1">{rec.description}</p>
                      <p className="text-[11px] mt-2 text-muted-foreground">Category: {rec.category} · Effort: {rec.estimated_effort}</p>
                    </div>
                    <div className="text-right">
                      <p className="text-sm font-semibold text-brand">+{rec.expected_score_gain}</p>
                      <p className="text-[11px] text-muted-foreground">impact {rec.impact_score}</p>
                    </div>
                  </div>
                  {rec.affected_files.length > 0 && (
                    <p className="text-[11px] mt-2 text-muted-foreground">Affected: {rec.affected_files.slice(0, 4).join(', ')}</p>
                  )}
                </div>
              ))}
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

