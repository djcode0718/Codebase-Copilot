'use client';

import { CheckCircle2, Clock3, FlaskConical, Loader2, XCircle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import type {
  ExplorerTestDiscoveryResult,
  HealthRecommendation,
  RecommendationLifecycleStatus,
} from '@/lib/types';

export type EngineeringActionEvent = {
  id: string;
  at: string;
  action: string;
  status: 'started' | 'succeeded' | 'failed' | 'skipped';
  detail?: string;
};

type EngineeringActionRunTimelineProps = {
  scopeLabel: string;
  events: EngineeringActionEvent[];
  recommendations: HealthRecommendation[];
  selectedRecommendationId: string;
  onSelectRecommendation: (id: string) => void;
  onSetLifecycleStatus: (status: RecommendationLifecycleStatus, reason?: string) => Promise<void>;
  statusUpdating: boolean;
  testSelection: ExplorerTestDiscoveryResult | null;
};

const STATUS_FLOW: RecommendationLifecycleStatus[] = [
  'ACCEPTED',
  'FIX_GENERATED',
  'DIFF_REVIEW',
  'TESTING',
  'VERIFIED',
  'RESOLVED',
];

function eventTone(status: EngineeringActionEvent['status']): string {
  if (status === 'succeeded') return 'text-emerald-400';
  if (status === 'failed') return 'text-red-400';
  if (status === 'skipped') return 'text-amber-400';
  return 'text-blue-400';
}

function formatLifecycle(status: RecommendationLifecycleStatus): string {
  return status.replace(/_/g, ' ').toLowerCase();
}

function recommendationOptionKey(rec: HealthRecommendation, index: number): string {
  return rec.recommendation_id || rec.fingerprint || `${rec.category}:${rec.title}:${index}`;
}

export default function EngineeringActionRunTimeline({
  scopeLabel,
  events,
  recommendations,
  selectedRecommendationId,
  onSelectRecommendation,
  onSetLifecycleStatus,
  statusUpdating,
  testSelection,
}: EngineeringActionRunTimelineProps) {
  const selectedRecommendation = recommendations.find((rec) => rec.recommendation_id === selectedRecommendationId) ?? null;
  const orderedEvents = [...events].sort((a, b) => new Date(b.at).getTime() - new Date(a.at).getTime()).slice(0, 12);
  const testReasons = testSelection?.rationale ?? [];

  return (
    <section className="rounded-[1.25rem] border border-border bg-card/80 p-4 shadow-sm shadow-black/5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <p className="text-sm font-semibold">Engineering Action Run Timeline</p>
          <p className="text-xs text-muted-foreground">{scopeLabel}</p>
        </div>
        <span className="inline-flex items-center gap-1 rounded-full border border-border bg-background px-2 py-1 text-[11px] text-muted-foreground">
          <Clock3 size={12} />
          {orderedEvents.length} latest events
        </span>
      </div>

      <div className="mt-3 grid gap-3 xl:grid-cols-[1fr_1.05fr]">
        <div className="rounded-xl border border-border bg-background/60 p-3">
          <p className="text-xs font-medium uppercase tracking-[0.14em] text-muted-foreground">Lifecycle controls</p>
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <select
              className="h-8 rounded-md border border-border bg-background px-2 text-xs"
              value={selectedRecommendationId}
              onChange={(event) => onSelectRecommendation(event.target.value)}
              disabled={recommendations.length === 0}
            >
              <option value="">No linked recommendation</option>
              {recommendations.map((rec, index) => (
                <option key={recommendationOptionKey(rec, index)} value={rec.recommendation_id ?? ''}>
                  {rec.category}: {rec.title}
                </option>
              ))}
            </select>
            {selectedRecommendation && (
              <span className="text-xs text-muted-foreground">
                Current: <span className="font-medium uppercase">{selectedRecommendation.current_status}</span>
              </span>
            )}
          </div>

          <div className="mt-2 flex flex-wrap gap-1.5">
            {STATUS_FLOW.map((status) => (
              <Button
                key={status}
                size="sm"
                variant="outline"
                disabled={!selectedRecommendation || statusUpdating}
                className="h-7 text-[11px]"
                onClick={() => void onSetLifecycleStatus(status)}
              >
                {formatLifecycle(status)}
              </Button>
            ))}
            <Button
              size="sm"
              variant="outline"
              disabled={!selectedRecommendation || statusUpdating}
              className="h-7 text-[11px]"
              onClick={() => {
                const reason = window.prompt('Dismiss reason (optional)')?.trim();
                void onSetLifecycleStatus('DISMISSED', reason || undefined);
              }}
            >
              dismiss
            </Button>
            <Button
              size="sm"
              variant="outline"
              disabled={!selectedRecommendation || statusUpdating}
              className="h-7 text-[11px]"
              onClick={() => void onSetLifecycleStatus('OPEN')}
            >
              reopen
            </Button>
            {statusUpdating && <Loader2 size={13} className="animate-spin text-muted-foreground ml-1" />}
          </div>
        </div>

        <div className="rounded-xl border border-border bg-background/60 p-3">
          <p className="text-xs font-medium uppercase tracking-[0.14em] text-muted-foreground">Targeted test selection rationale</p>
          {!testSelection ? (
            <p className="mt-2 text-xs text-muted-foreground">Run Generate Tests or Run Tests to capture selection rationale.</p>
          ) : (
            <div className="mt-2 space-y-1.5">
              <p className="text-xs text-muted-foreground">
                Strategy: <span className="font-medium">{testSelection.selection_strategy ?? 'heuristic'}</span> •
                {' '}Candidates: {testSelection.count}
              </p>
              {testReasons.length === 0 ? (
                <p className="text-xs text-muted-foreground">No explicit rationale returned for selected tests.</p>
              ) : (
                testReasons.slice(0, 6).map((item) => (
                  <div key={item.test} className="rounded-lg border border-border/70 bg-background px-2 py-1.5 text-xs">
                    <p className="font-medium">{item.test}</p>
                    <p className="text-muted-foreground">{item.reason}</p>
                    <p className="text-muted-foreground">tokens: {item.matched_tokens.slice(0, 5).join(', ') || 'n/a'}</p>
                  </div>
                ))
              )}
            </div>
          )}
        </div>
      </div>

      <div className="mt-3 rounded-xl border border-border bg-background/60 p-3">
        <p className="text-xs font-medium uppercase tracking-[0.14em] text-muted-foreground">Run events</p>
        {orderedEvents.length === 0 ? (
          <p className="mt-2 text-xs text-muted-foreground">No engineering actions yet.</p>
        ) : (
          <div className="mt-2 space-y-1.5">
            {orderedEvents.map((event) => (
              <div key={event.id} className="flex items-start justify-between gap-3 text-xs">
                <div className="min-w-0">
                  <p className="font-medium">{event.action}</p>
                  {event.detail && <p className="text-muted-foreground">{event.detail}</p>}
                </div>
                <div className="flex shrink-0 items-center gap-1 text-muted-foreground">
                  {event.status === 'succeeded' ? <CheckCircle2 size={12} className={eventTone(event.status)} /> : null}
                  {event.status === 'failed' ? <XCircle size={12} className={eventTone(event.status)} /> : null}
                  {event.status === 'started' ? <FlaskConical size={12} className={eventTone(event.status)} /> : null}
                  {event.status === 'skipped' ? <Clock3 size={12} className={eventTone(event.status)} /> : null}
                  <span className={cn('capitalize', eventTone(event.status))}>{event.status}</span>
                  <span>{new Date(event.at).toLocaleTimeString()}</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </section>
  );
}
