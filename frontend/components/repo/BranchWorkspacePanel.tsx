'use client';

import { useEffect, useMemo, useState, type ReactNode } from 'react';
import { GitBranch, Loader2, RefreshCw, RotateCcw, Search, ArrowUpDown, GitCommit, User, Gauge, ShieldAlert } from 'lucide-react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  checkoutRepoBranch,
  compareRepoBranches,
  getRepo,
  getRepoBranchStatus,
  listRepoBranches,
  pullRepoBranch,
  refreshRepoBranches,
  returnRepoDefaultBranch,
} from '@/lib/api';
import type { BranchComparison, BranchListResponse, BranchStatus, Repo } from '@/lib/types';

interface BranchWorkspacePanelProps {
  token: string;
  repoId: string;
  repo: Repo;
  onRepoUpdated: (nextRepo: Repo) => void;
}

export default function BranchWorkspacePanel({ token, repoId, repo, onRepoUpdated }: BranchWorkspacePanelProps) {
  const [query, setQuery] = useState('');
  const [branches, setBranches] = useState<BranchListResponse | null>(null);
  const [status, setStatus] = useState<BranchStatus | null>(null);
  const [compareBase, setCompareBase] = useState('');
  const [compareTarget, setCompareTarget] = useState('');
  const [comparison, setComparison] = useState<BranchComparison | null>(null);
  const [loading, setLoading] = useState(false);
  const [action, setAction] = useState<string | null>(null);

  const allBranchOptions = useMemo(() => {
    if (!branches) return [];
    return Array.from(new Set([...branches.local_branches, ...branches.remote_branches]));
  }, [branches]);

  async function reloadBranches(search = query) {
    if (!token) return;
    setLoading(true);
    try {
      const [nextBranches, nextStatus] = await Promise.all([
        listRepoBranches(token, repoId, search),
        getRepoBranchStatus(token, repoId),
      ]);
      setBranches(nextBranches);
      setStatus(nextStatus);
      if (!compareBase) setCompareBase(nextBranches.default_branch || 'main');
      if (!compareTarget) setCompareTarget(nextBranches.current_branch || nextBranches.default_branch || 'main');
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to load branch workspace');
    } finally {
      setLoading(false);
    }
  }

  async function refreshRepoContext() {
    if (!token) return;
    try {
      const nextRepo = await getRepo(token, repoId);
      onRepoUpdated(nextRepo);
    } catch {
      // keep existing UI state when metadata refresh fails
    }
  }

  useEffect(() => {
    const timeoutId = window.setTimeout(() => {
      void reloadBranches('');
    }, 0);
    return () => window.clearTimeout(timeoutId);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [repoId, token]);

  async function runBranchAction(name: string, fn: () => Promise<void>) {
    setAction(name);
    try {
      await fn();
      await reloadBranches('');
      await refreshRepoContext();
    } finally {
      setAction(null);
    }
  }

  async function handleCheckout(branch: string) {
    await runBranchAction('checkout', async () => {
      const result = await checkoutRepoBranch(token, repoId, branch, true);
      setStatus(result.status);
      toast.success(result.message);
    });
  }

  async function handlePullLatest() {
    await runBranchAction('pull', async () => {
      const result = await pullRepoBranch(token, repoId, status?.current_branch);
      setStatus(result.status);
      toast.success(result.message);
    });
  }

  async function handleReturnDefault() {
    await runBranchAction('return-default', async () => {
      const result = await returnRepoDefaultBranch(token, repoId);
      setStatus(result.status);
      toast.success(result.message);
    });
  }

  async function handleRefreshBranchList() {
    await runBranchAction('refresh', async () => {
      const refreshed = await refreshRepoBranches(token, repoId);
      setBranches(refreshed);
      toast.success('Branch list refreshed');
    });
  }

  async function handleCompare() {
    if (!compareBase || !compareTarget) {
      toast.error('Select both branches to compare');
      return;
    }
    await runBranchAction('compare', async () => {
      const result = await compareRepoBranches(token, repoId, compareBase, compareTarget);
      setComparison(result);
      toast.success('Branch comparison generated');
    });
  }

  const isBusy = Boolean(action) || loading;

  return (
    <section className="rounded-[1.5rem] border border-border bg-card/80 p-5 shadow-lg shadow-black/5 backdrop-blur-sm">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <GitBranch size={16} className="text-brand" />
          <h2 className="font-heading text-sm font-semibold uppercase tracking-[0.18em] text-muted-foreground">Branch Workspace</h2>
        </div>
        <div className="flex items-center gap-2">
          <Button size="sm" variant="outline" onClick={() => void handleRefreshBranchList()} disabled={!token || isBusy}>
            {action === 'refresh' ? <Loader2 size={13} className="mr-1 animate-spin" /> : <RefreshCw size={13} className="mr-1" />}
            Refresh branch list
          </Button>
          <Button size="sm" variant="outline" onClick={() => void handlePullLatest()} disabled={!token || isBusy}>
            {action === 'pull' ? <Loader2 size={13} className="mr-1 animate-spin" /> : <ArrowUpDown size={13} className="mr-1" />}
            Pull latest
          </Button>
          <Button size="sm" variant="outline" onClick={() => void handleReturnDefault()} disabled={!token || isBusy}>
            {action === 'return-default' ? <Loader2 size={13} className="mr-1 animate-spin" /> : <RotateCcw size={13} className="mr-1" />}
            Return to default
          </Button>
        </div>
      </div>

      <div className="grid gap-4 xl:grid-cols-[1.2fr_0.8fr]">
        <div className="space-y-3 rounded-2xl border border-border bg-background/70 p-4">
          <div className="flex items-center gap-2">
            <Search size={13} className="text-muted-foreground" />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') void reloadBranches(e.currentTarget.value); }}
              placeholder="Search branches (feature, release, hotfix, payment...)"
              className="w-full rounded-lg border border-border bg-card px-2.5 py-1.5 text-sm outline-none focus:border-brand"
            />
            <Button size="sm" variant="outline" onClick={() => void reloadBranches(query)} disabled={!token || isBusy}>Search</Button>
          </div>

          <div className="space-y-2">
            <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Current Branch</p>
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant="outline" className="border-brand/30 bg-brand/10 text-brand">{status?.current_branch || repo.active_branch || 'unknown'}</Badge>
              <Badge variant="outline">Default: {status?.default_branch || repo.default_branch || 'main/master'}</Badge>
              {status?.short_commit_sha && <Badge variant="outline">{status.short_commit_sha}</Badge>}
            </div>
          </div>

          <div className="grid gap-3 md:grid-cols-3">
            <BranchColumn
              title="Recent"
              branches={branches?.recent_branches || []}
              active={status?.current_branch || ''}
              onSelect={handleCheckout}
              disabled={!token || isBusy}
            />
            <BranchColumn
              title="Local"
              branches={branches?.local_branches || []}
              active={status?.current_branch || ''}
              onSelect={handleCheckout}
              disabled={!token || isBusy}
            />
            <BranchColumn
              title="Remote"
              branches={branches?.remote_branches || []}
              active={status?.current_branch || ''}
              onSelect={handleCheckout}
              disabled={!token || isBusy}
            />
          </div>
        </div>

        <div className="space-y-3 rounded-2xl border border-border bg-background/70 p-4">
          <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Branch Status</p>
          <StatusRow icon={<GitCommit size={12} />} label="Last commit" value={status?.last_commit || 'n/a'} />
          <StatusRow icon={<User size={12} />} label="Author" value={status?.author || 'n/a'} />
          <StatusRow icon={<Gauge size={12} />} label="Ahead / Behind" value={`${status?.ahead ?? 0} / ${status?.behind ?? 0}`} />
          <StatusRow icon={<ShieldAlert size={12} />} label="Changed files" value={String(status?.changed_files ?? 0)} />
          <StatusRow icon={<GitBranch size={12} />} label="Added / Modified / Deleted" value={`${status?.files_added ?? 0} / ${status?.files_modified ?? 0} / ${status?.files_deleted ?? 0}`} />
          <StatusRow icon={<GitBranch size={12} />} label="Sync status" value={status?.sync_status || 'unknown'} />
          <StatusRow icon={<GitBranch size={12} />} label="Index status" value={status?.index_status || repo.status} />
          <StatusRow icon={<GitBranch size={12} />} label="Evaluation status" value={status?.evaluation_status || 'unknown'} />
          <StatusRow icon={<GitBranch size={12} />} label="Health score" value={status?.health_score != null ? String(status.health_score) : 'n/a'} />
          <StatusRow icon={<GitBranch size={12} />} label="Last indexed" value={status?.indexed_at ? new Date(status.indexed_at).toLocaleString() : 'n/a'} />
        </div>
      </div>

      <div className="mt-4 rounded-2xl border border-border bg-background/70 p-4">
        <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Branch Comparison</p>
        <div className="mt-2 grid gap-2 md:grid-cols-3">
          <select value={compareBase} onChange={(e) => setCompareBase(e.target.value)} className="rounded-lg border border-border bg-card px-2.5 py-1.5 text-sm">
            {allBranchOptions.map((branch) => <option key={`base-${branch}`} value={branch}>{branch}</option>)}
          </select>
          <select value={compareTarget} onChange={(e) => setCompareTarget(e.target.value)} className="rounded-lg border border-border bg-card px-2.5 py-1.5 text-sm">
            {allBranchOptions.map((branch) => <option key={`target-${branch}`} value={branch}>{branch}</option>)}
          </select>
          <Button size="sm" variant="outline" onClick={() => void handleCompare()} disabled={!token || isBusy || !compareBase || !compareTarget}>
            {action === 'compare' ? <Loader2 size={13} className="mr-1 animate-spin" /> : <ArrowUpDown size={13} className="mr-1" />}
            Compare branches
          </Button>
        </div>

        {comparison && (
          <div className="mt-3 grid gap-3 lg:grid-cols-[1fr_1fr]">
            <div className="rounded-xl border border-border bg-card p-3 text-sm">
              <p className="font-medium">AI Executive Summary</p>
              <p className="mt-1 text-muted-foreground">{comparison.ai_executive_summary}</p>
              <p className="mt-2 text-xs text-muted-foreground">Risk: {comparison.risk_assessment} • Changed files: {comparison.changed_files}</p>
            </div>
            <div className="rounded-xl border border-border bg-card p-3 text-sm">
              <p className="font-medium">Merge Readiness</p>
              <p className="mt-1 text-muted-foreground">Score: {comparison.merge_readiness.overall_score} • Deployment risk: {comparison.merge_readiness.deployment_risk}</p>
              <p className="mt-1 text-muted-foreground">Safe to merge: {comparison.merge_readiness.safe_to_merge ? 'Yes' : 'No'}</p>
              {comparison.merge_readiness.blocking_issues.length > 0 && (
                <ul className="mt-2 list-disc pl-4 text-xs text-destructive">
                  {comparison.merge_readiness.blocking_issues.slice(0, 3).map((issue) => <li key={issue}>{issue}</li>)}
                </ul>
              )}
            </div>
            <div className="rounded-xl border border-border bg-card p-3 text-sm lg:col-span-2">
              <p className="font-medium">Branch vs Base Delta Overlay</p>
              <p className="mt-1 text-muted-foreground">{comparison.impact_summary}</p>
              <div className="mt-2 grid gap-2 md:grid-cols-3">
                <StatusRow icon={<Gauge size={12} />} label="Health delta" value={`${comparison.health_impact_delta >= 0 ? '+' : ''}${comparison.health_impact_delta}`} />
                <StatusRow icon={<ShieldAlert size={12} />} label="Security delta" value={`${comparison.security_impact_delta >= 0 ? '+' : ''}${comparison.security_impact_delta}`} />
                <StatusRow icon={<GitCommit size={12} />} label="Test impact delta" value={`${comparison.test_impact_delta >= 0 ? '+' : ''}${comparison.test_impact_delta}`} />
              </div>
              <p className="mt-2 text-xs text-muted-foreground">
                Testing-related changes: {comparison.testing_changes} • Security-related changes: {comparison.security_changes}
              </p>
            </div>
          </div>
        )}
      </div>
    </section>
  );
}

function BranchColumn({
  title,
  branches,
  active,
  onSelect,
  disabled,
}: {
  title: string;
  branches: string[];
  active: string;
  onSelect: (branch: string) => Promise<void>;
  disabled: boolean;
}) {
  return (
    <div className="rounded-xl border border-border bg-card/60 p-2">
      <p className="mb-1 px-1 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">{title}</p>
      <div className="max-h-44 space-y-1 overflow-auto">
        {branches.length === 0 ? (
          <p className="px-2 py-1 text-xs text-muted-foreground">No branches</p>
        ) : (
          branches.map((branch) => (
            <button
              key={`${title}-${branch}`}
              type="button"
              disabled={disabled}
              className={`w-full truncate rounded-lg px-2 py-1.5 text-left text-xs transition-colors ${active === branch ? 'bg-brand/15 text-brand' : 'hover:bg-muted'}`}
              onClick={() => void onSelect(branch)}
              title={branch}
            >
              {branch}
            </button>
          ))
        )}
      </div>
    </div>
  );
}

function StatusRow({ icon, label, value }: { icon: ReactNode; label: string; value: string }) {
  return (
    <div className="flex items-start justify-between gap-3 rounded-lg border border-border/70 bg-card/60 px-2.5 py-1.5 text-xs">
      <div className="flex items-center gap-1.5 text-muted-foreground">{icon}{label}</div>
      <div className="max-w-[65%] truncate text-right">{value}</div>
    </div>
  );
}
