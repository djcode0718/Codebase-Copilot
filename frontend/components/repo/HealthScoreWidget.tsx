'use client';
/**
 * components/repo/HealthScoreWidget.tsx
 * Computes and displays a repository intelligence health score (0–100)
 * based on indexing completeness, file coverage, and provider readiness.
 */
import { motion } from 'framer-motion';
import { ShieldCheck, TrendingUp, AlertTriangle } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { Repo } from '@/lib/types';

function computeHealthScore(repo: Repo): { score: number; grade: string; factors: { label: string; pass: boolean; points: number }[] } {
  const factors = [
    { label: 'Repository indexed',     pass: repo.status === 'ready',       points: 35 },
    { label: 'Files processed',         pass: (repo.file_count ?? 0) > 0,    points: 20 },
    { label: 'Knowledge chunks built',  pass: (repo.node_count ?? 0) > 50,   points: 20 },
    { label: 'LLM provider configured', pass: Boolean(repo.llm_provider),    points: 15 },
    { label: 'Rich codebase (100+ files)', pass: (repo.file_count ?? 0) >= 100, points: 10 },
  ];
  const score = factors.reduce((sum, f) => sum + (f.pass ? f.points : 0), 0);
  const grade = score >= 90 ? 'A' : score >= 75 ? 'B' : score >= 60 ? 'C' : score >= 40 ? 'D' : 'F';
  return { score, grade, factors };
}

function ScoreRing({ score }: { score: number }) {
  const r = 28;
  const circ = 2 * Math.PI * r;
  const filled = (score / 100) * circ;
  const color = score >= 75 ? '#22c55e' : score >= 50 ? '#f59e0b' : '#ef4444';

  return (
    <svg width="72" height="72" className="rotate-[-90deg]">
      <circle cx="36" cy="36" r={r} strokeWidth="5" fill="none" stroke="currentColor" className="text-border" />
      <motion.circle
        cx="36" cy="36" r={r} strokeWidth="5" fill="none"
        stroke={color}
        strokeDasharray={`${circ}`}
        strokeDashoffset={circ}
        strokeLinecap="round"
        animate={{ strokeDashoffset: circ - filled }}
        transition={{ duration: 1, ease: 'easeOut', delay: 0.2 }}
      />
    </svg>
  );
}

interface HealthScoreWidgetProps {
  repo: Repo;
}

export default function HealthScoreWidget({ repo }: HealthScoreWidgetProps) {
  const { score, grade, factors } = computeHealthScore(repo);
  const color = score >= 75 ? 'text-brand' : score >= 50 ? 'text-amber-400' : 'text-destructive';
  const bgColor = score >= 75 ? 'bg-brand/5 border-brand/20' : score >= 50 ? 'bg-amber-500/5 border-amber-500/20' : 'bg-destructive/5 border-destructive/20';

  return (
    <div className={cn('rounded-[1.5rem] border p-5 shadow-sm shadow-black/5 space-y-4', bgColor)}>
      <div className="flex items-center gap-2">
        <ShieldCheck size={15} className={color} />
        <h2 className="font-heading text-sm font-semibold uppercase tracking-[0.18em] text-muted-foreground">
          Repository Health
        </h2>
      </div>

      <div className="flex items-center gap-5">
        <div className="relative flex-shrink-0">
          <ScoreRing score={score} />
          <div className="absolute inset-0 flex flex-col items-center justify-center">
            <span className={cn('text-xl font-bold font-heading', color)}>{grade}</span>
          </div>
        </div>
        <div className="space-y-1 flex-1 min-w-0">
          <div className="flex items-baseline gap-1.5">
            <span className={cn('text-3xl font-bold font-heading', color)}>{score}</span>
            <span className="text-sm text-muted-foreground">/100</span>
          </div>
          <p className="text-xs text-muted-foreground">
            {score >= 75 ? 'Well-indexed, ready for deep intelligence.' : score >= 50 ? 'Partially indexed — some features limited.' : 'Needs attention before intelligence features activate.'}
          </p>
        </div>
      </div>

      <div className="space-y-1.5">
        {factors.map((f) => (
          <div key={f.label} className="flex items-center gap-2 text-xs">
            <div className={cn('h-1.5 w-1.5 rounded-full flex-shrink-0', f.pass ? 'bg-brand' : 'bg-border')} />
            <span className={f.pass ? 'text-foreground/80' : 'text-muted-foreground'}>{f.label}</span>
            {f.pass && <TrendingUp size={9} className="text-brand ml-auto flex-shrink-0" />}
            {!f.pass && <AlertTriangle size={9} className="text-muted-foreground ml-auto flex-shrink-0" />}
          </div>
        ))}
      </div>
    </div>
  );
}

