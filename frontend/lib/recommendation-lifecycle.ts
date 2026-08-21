import type { RecommendationLifecycleStatus } from '@/lib/types';

const LEGACY_TO_CANONICAL: Record<string, RecommendationLifecycleStatus> = {
  OPEN: 'NEW',
  ACCEPTED: 'ACKNOWLEDGED',
  FIX_GENERATED: 'IN_PROGRESS',
  DIFF_REVIEW: 'IN_PROGRESS',
  TESTING: 'IN_PROGRESS',
  VERIFIED: 'RESOLVED',
  DISMISSED: 'IGNORED',
};

export const LIFECYCLE_FLOW: RecommendationLifecycleStatus[] = [
  'NEW',
  'ACKNOWLEDGED',
  'IN_PROGRESS',
  'RESOLVED',
  'REGRESSED',
  'IGNORED',
];

export function canonicalLifecycleStatus(status: string | null | undefined): RecommendationLifecycleStatus {
  const normalized = String(status || '').trim().toUpperCase();
  if (normalized in LEGACY_TO_CANONICAL) {
    return LEGACY_TO_CANONICAL[normalized];
  }
  if (
    normalized === 'NEW' ||
    normalized === 'ACKNOWLEDGED' ||
    normalized === 'IN_PROGRESS' ||
    normalized === 'RESOLVED' ||
    normalized === 'REGRESSED' ||
    normalized === 'IGNORED'
  ) {
    return normalized;
  }
  return 'NEW';
}

export function lifecycleLabel(status: RecommendationLifecycleStatus): string {
  return status.replace(/_/g, ' ').toLowerCase();
}

