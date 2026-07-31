'use client';
/**
 * components/indexing/PipelineStep.tsx
 * Single step row in the indexing pipeline list.
 */
import { motion, AnimatePresence } from 'framer-motion';
import { Check, X, ChevronDown, ChevronRight, Terminal } from 'lucide-react';
import { useState } from 'react';
import { cn } from '@/lib/utils';
import type { PipelineStep as PipelineStepType } from '@/lib/types';

function formatMs(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

interface Props {
  step: PipelineStepType;
  isLast?: boolean;
}

export default function PipelineStep({ step, isLast }: Props) {
  const [expanded, setExpanded] = useState(false);

  const iconClass = {
    pending: 'bg-secondary text-muted-foreground border-border',
    active:  'bg-brand/10 text-brand border-brand/40',
    done:    'bg-brand/10 text-brand border-brand/40',
    error:   'bg-destructive/10 text-destructive border-destructive/40',
  }[step.status];

  return (
    <motion.div
      initial={{ opacity: 0, x: -8 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.2, ease: [0.4, 0, 0.2, 1] }}
      className="relative"
    >
      {/* Connector line */}
      {!isLast && (
        <div className="absolute left-4 top-9 bottom-0 w-px bg-border/80" />
      )}

      <div className="flex items-start gap-3 rounded-2xl px-1.5 py-3 transition-colors hover:bg-background/60">
        {/* Status icon */}
        <div className={cn(
          'w-8 h-8 rounded-full border flex items-center justify-center flex-shrink-0 mt-0.5 shadow-sm',
          iconClass
        )}>
          {step.status === 'done' && <Check size={13} strokeWidth={2.5} />}
          {step.status === 'error' && <X size={13} strokeWidth={2.5} />}
          {step.status === 'active' && (
            <span className="w-2.5 h-2.5 rounded-full bg-brand step-active-dot" />
          )}
          {step.status === 'pending' && (
            <span className="w-2 h-2 rounded-full bg-border" />
          )}
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 justify-between">
            <div>
              <span
                className={cn('text-sm font-medium', {
                  'text-foreground': step.status === 'active' || step.status === 'done',
                  'text-muted-foreground': step.status === 'pending',
                  'text-destructive': step.status === 'error',
                })}
              >
                {step.label}
              </span>
              {step.status !== 'pending' && (
                <p className="text-xs text-muted-foreground mt-0.5 truncate">
                  {step.message ?? step.description}
                </p>
              )}
              {step.status === 'pending' && (
                <p className="text-xs text-muted-foreground/50 mt-0.5">
                  {step.description}
                </p>
              )}
            </div>

            <div className="flex items-center gap-2 flex-shrink-0">
              {step.status === 'active' && (
                <span className="text-xs text-brand font-mono animate-pulse">
                  running…
                </span>
              )}
              {step.status === 'done' && step.elapsedMs !== undefined && (
                <span className="text-xs text-muted-foreground font-mono">
                  {formatMs(step.elapsedMs)}
                </span>
              )}
              {step.message && step.status !== 'pending' && (
                <button
                  onClick={() => setExpanded(!expanded)}
                  className="text-muted-foreground hover:text-foreground transition-colors cursor-pointer"
                  aria-label="Toggle log"
                >
                  {expanded ? <ChevronDown size={13} /> : <ChevronRight size={13} />}
                </button>
              )}
            </div>
          </div>

          {/* Expandable raw log */}
          <AnimatePresence>
            {expanded && step.message && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                exit={{ opacity: 0, height: 0 }}
                transition={{ duration: 0.2 }}
                className="overflow-hidden"
              >
                <div className="mt-2 mb-1 flex items-center gap-1.5 text-xs text-muted-foreground">
                  <Terminal size={11} />
                  <span>Raw log</span>
                </div>
                <pre className="text-xs font-code bg-background border border-border rounded-xl p-3 text-muted-foreground whitespace-pre-wrap leading-relaxed overflow-x-auto scrollbar-thin">
                  {step.message}
                </pre>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
    </motion.div>
  );
}
