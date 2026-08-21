'use client';

import { useCallback, useEffect, useMemo, useRef, useState, type Dispatch, type SetStateAction } from 'react';
import { useParams } from 'next/navigation';
import { motion } from 'framer-motion';
import {
  Bot,
  FileCode2,
  GitCommitHorizontal,
  GitPullRequest,
  History,
  Loader2,
  MessageSquare,
  Play,
  Shield,
  Sparkles,
  TestTube,
  Trash2,
  Wrench,
} from 'lucide-react';
import { useRepoSessionToken } from '@/hooks/useRepoSessionToken';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import {
  deleteReview,
  generateReviewFix,
  addExplorerConversationEntry,
  applyExplorerFix,
  discoverExplorerTests,
  generateExplorerFix,
  getExplorerFile,
  getExplorerTree,
  getExplorerHistory,
  getLatestRepositoryHealth,
  updateRepositoryHealthRecommendationStatus,
  getReview,
  listReviews,
  runExplorerFileReview,
  runExplorerTests,
  reviewCommit,
  reviewFile,
  reviewFiles,
  reviewPullRequest,
} from '@/lib/api';
import type {
  ExplorerFileDetails,
  ExplorerFixProposal,
  ExplorerReviewResult,
  ExplorerTestDiscoveryResult,
  ExplorerTestRunResult,
  ExplorerTreeNode,
  HealthRecommendation,
  RecommendationLifecycleStatus,
  ReviewFixResponse,
  ReviewHistoryItem,
  ReviewRun,
} from '@/lib/types';
import EngineeringActionRunTimeline, { type EngineeringActionEvent } from '@/components/repo/EngineeringActionRunTimeline';
import { toast } from 'sonner';

function SeverityPill({ severity }: { severity: string }) {
  const cls = severity === 'critical'
    ? 'border-red-400/50 text-red-300'
    : severity === 'high'
    ? 'border-amber-400/50 text-amber-300'
    : severity === 'medium'
    ? 'border-violet-400/50 text-violet-300'
    : 'border-border text-muted-foreground';

  return <span className={`rounded-full border px-2 py-0.5 text-[10px] uppercase tracking-[0.14em] ${cls}`}>{severity}</span>;
}

function csvToList(csv: string): string[] {
  return csv.split(',').map((s) => s.trim()).filter(Boolean);
}

function firstPathFromCsv(csv: string): string {
  const first = csvToList(csv)[0] || '';
  return first ? normalizePath(first) : '';
}

function computeRibbonHealthScore(selectedFile: ExplorerFileDetails | null, repoHealthScore: number | null): number | null {
  void selectedFile;
  if (typeof repoHealthScore === 'number') return repoHealthScore;
  return null;
}

const SOURCE_FILE_EXTENSIONS = [
  '.py', '.ts', '.tsx', '.js', '.jsx', '.java', '.kt', '.go', '.rs', '.rb', '.php', '.cs', '.swift', '.scala', '.c', '.cc', '.cpp', '.h', '.hpp', '.m', '.mm',
];

function normalizePath(value: string): string {
  return value.replace(/\\/g, '/').trim();
}

function coverageCacheKey(path: string): string {
  return normalizePath(path).toLowerCase();
}

function isLikelySourceFile(pathValue: string): boolean {
  const path = normalizePath(pathValue).toLowerCase();
  if (!path || path.endsWith('/')) return false;
  if (path.includes('/.git/') || path.includes('/node_modules/') || path.includes('/dist/') || path.includes('/build/')) return false;
  if (path.endsWith('.min.js') || path.endsWith('.lock') || path.endsWith('.map')) return false;
  return SOURCE_FILE_EXTENSIONS.some((ext) => path.endsWith(ext));
}

function pickFirstReviewableFile(nodes: ExplorerTreeNode[]): string | null {
  for (const node of nodes) {
    if (node.type !== 'file') continue;
    const candidate = node.path || node.name;
    if (!candidate) continue;
    if (isLikelySourceFile(candidate)) return normalizePath(candidate);
  }
  for (const node of nodes) {
    if (node.type !== 'file') continue;
    const candidate = node.path || node.name;
    if (!candidate) continue;
    return normalizePath(candidate);
  }
  return null;
}

function readCachedRepoHealthScore(repoId: string): number | null {
  if (typeof window === 'undefined') return null;
  try {
    const raw = window.localStorage.getItem(`codebase:health-latest:${repoId}`);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as { top_level?: { repository_health?: unknown } };
    const value = parsed?.top_level?.repository_health;
    return typeof value === 'number' ? value : null;
  } catch {
    return null;
  }
}

function formatLastModified(value?: string | null): string {
  if (!value) return 'Unavailable';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return 'Unavailable';
  // Fixed locale + timezone keeps SSR and client render deterministic.
  return new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    hour12: true,
    timeZone: 'UTC',
  }).format(date);
}

function buildActionEvent(action: string, status: EngineeringActionEvent['status'], detail?: string): EngineeringActionEvent {
  return {
    id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    at: new Date().toISOString(),
    action,
    status,
    detail,
  };
}

interface FileActionRibbonProps {
  selectedFilePath: string;
  selectedFile: ExplorerFileDetails | null;
  coverageLabel: string;
  ribbonHealthScore: number | null;
  runRibbonReview: (type: string) => Promise<void>;
  runRibbonGenerateTests: () => Promise<void>;
  runRibbonTests: () => Promise<void>;
  runRibbonGenerateFix: () => Promise<void>;
  runRibbonApplyFix: () => Promise<void>;
  runRibbonAskAi: () => Promise<void>;
  runRibbonHistory: () => Promise<void>;
  ribbonAction: string | null;
  ribbonReview: ExplorerReviewResult | null;
  ribbonFix: ExplorerFixProposal | null;
  showRibbonDiff: boolean;
  setShowRibbonDiff: Dispatch<SetStateAction<boolean>>;
  ribbonTests: ExplorerTestRunResult | null;
  ribbonHistory: string;
}

function FileActionRibbon({
  selectedFilePath,
  selectedFile,
  coverageLabel,
  ribbonHealthScore,
  runRibbonReview,
  runRibbonGenerateTests,
  runRibbonTests,
  runRibbonGenerateFix,
  runRibbonApplyFix,
  runRibbonAskAi,
  runRibbonHistory,
  ribbonAction,
  ribbonReview,
  ribbonFix,
  showRibbonDiff,
  setShowRibbonDiff,
  ribbonTests,
  ribbonHistory,
}: FileActionRibbonProps) {
  const [isMounted, setIsMounted] = useState(false);

  useEffect(() => {
    setIsMounted(true);
  }, []);

  const modifierName = selectedFile?.owner?.trim();
  const modifierLabel = modifierName || (isMounted ? 'Unavailable' : '\u2014');
  const modifiedAtLabel = selectedFile?.last_modified
    ? formatLastModified(selectedFile.last_modified)
    : (isMounted ? 'Unavailable' : '\u2014');

  return (
    <section className="rounded-[1.25rem] border border-border bg-card/80 p-4 shadow-lg shadow-black/5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="truncate text-sm font-semibold">{selectedFilePath}</p>
          <p className="mt-1 text-xs text-muted-foreground">
            {selectedFile?.language || 'unknown'} • {selectedFile?.line_count || 'n/a'} lines • {selectedFile?.imports.length || 0} imports • {selectedFile?.classes.length || 0} classes • {selectedFile?.functions.length || 0} functions
          </p>
          <p className="mt-1 text-[11px] text-muted-foreground" suppressHydrationWarning>
            Coverage {coverageLabel} • Last Modified By {modifierLabel} • Last Modified {modifiedAtLabel}
          </p>
        </div>
        <div className="text-right">
          <p className="text-[11px] text-muted-foreground">Repository Health</p>
          <p className="text-lg font-semibold">{typeof ribbonHealthScore === 'number' ? ribbonHealthScore : '—'}</p>
        </div>
      </div>

      <div className="mt-3 flex flex-wrap gap-1.5">
        <Button size="sm" variant="outline" title="E" onClick={() => void runRibbonReview('explain')}>Explain</Button>
        <Button size="sm" variant="outline" title="R" onClick={() => void runRibbonReview('review')}>Review</Button>
        <Button size="sm" variant="outline" title="B" onClick={() => void runRibbonReview('find_bugs')}>Find Bugs</Button>
        <Button size="sm" variant="outline" title="S" onClick={() => void runRibbonReview('security')}><Shield size={13} className="mr-1" />Security</Button>
        <Button size="sm" variant="outline" title="A" onClick={() => void runRibbonReview('architecture')}>Architecture</Button>
        <Button size="sm" variant="outline" onClick={() => void runRibbonReview('performance')}><Play size={13} className="mr-1" />Performance</Button>
        <Button size="sm" variant="outline" onClick={() => void runRibbonReview('code_quality')}>Code Quality</Button>
        <Button size="sm" variant="outline" title="T" onClick={() => void runRibbonGenerateTests()}>Generate Tests</Button>
        <Button size="sm" variant="outline" title="Shift+T" onClick={() => void runRibbonTests()}><TestTube size={13} className="mr-1" />Run Tests</Button>
        <Button size="sm" variant="outline" title="F" onClick={() => void runRibbonGenerateFix()}><Wrench size={13} className="mr-1" />Generate Fix</Button>
        <Button size="sm" variant="outline" onClick={() => void runRibbonApplyFix()} disabled={!ribbonFix}>Apply Fix</Button>
        <Button size="sm" variant="outline" title="Ctrl+D" onClick={() => setShowRibbonDiff((prev) => !prev)}>Show Diff</Button>
        <Button size="sm" variant="outline" onClick={() => void runRibbonReview('commit_impact')}>Commit Impact</Button>
        <Button size="sm" variant="outline" onClick={() => void runRibbonReview('dependencies')}>Dependencies</Button>
        <Button size="sm" variant="outline" title="Ctrl+/" onClick={() => void runRibbonAskAi()}><MessageSquare size={13} className="mr-1" />Ask AI</Button>
        <Button size="sm" variant="outline" onClick={() => void runRibbonHistory()}><History size={13} className="mr-1" />History</Button>
      </div>

      {ribbonAction && (
        <div className="mt-3 inline-flex items-center gap-2 rounded-full border border-brand/30 bg-brand/10 px-3 py-1 text-xs text-brand">
          <Loader2 size={13} className="animate-spin" /> Running {ribbonAction.replace('_', ' ')}...
        </div>
      )}

      {ribbonReview && (
        <div className="mt-3 rounded-xl border border-border bg-background/60 p-3 text-sm">
          <p className="font-medium">AI Review Score: {ribbonReview.overall_score}</p>
          <p className="mt-1 text-muted-foreground">{ribbonReview.summary}</p>
          <p className="mt-1 text-xs text-muted-foreground">Findings: {ribbonReview.findings.length}</p>
        </div>
      )}

      {ribbonFix && (
        <div className="mt-3 rounded-xl border border-border bg-background/60 p-3 text-sm">
          <p className="font-medium">Fix proposal ready</p>
          {showRibbonDiff && <pre className="mt-2 max-h-32 overflow-auto rounded bg-black/10 p-2 text-xs">{ribbonFix.diff || 'No changes'}</pre>}
          <div className="mt-2 grid gap-2 md:grid-cols-2">
            <pre className="max-h-32 overflow-auto rounded bg-black/10 p-2 text-xs">{ribbonFix.current_content}</pre>
            <pre className="max-h-32 overflow-auto rounded bg-black/10 p-2 text-xs">{ribbonFix.suggested_content}</pre>
          </div>
        </div>
      )}

      {ribbonTests && (
        <div className="mt-3 rounded-xl border border-border bg-background/60 p-3 text-sm">
          <p className="font-medium">Tests: {ribbonTests.status.toUpperCase()}</p>
          <p className="mt-1 text-muted-foreground">Passed {ribbonTests.passed} • Failed {ribbonTests.failed} • Duration {ribbonTests.duration_seconds}s</p>
        </div>
      )}

      {ribbonHistory && (
        <div className="mt-3 rounded-xl border border-border bg-background/60 p-3 text-xs text-muted-foreground">{ribbonHistory}</div>
      )}
    </section>
  );
}

type ReviewRibbonActionsArgs = {
  token: string;
  repoId: string;
  selectedFilePath: string;
  selectedFile: ExplorerFileDetails | null;
  ribbonReview: ExplorerReviewResult | null;
  ribbonFix: ExplorerFixProposal | null;
  setRibbonAction: Dispatch<SetStateAction<string | null>>;
  setRibbonReview: Dispatch<SetStateAction<ExplorerReviewResult | null>>;
  setRibbonFix: Dispatch<SetStateAction<ExplorerFixProposal | null>>;
  setRibbonTests: Dispatch<SetStateAction<ExplorerTestRunResult | null>>;
  setRibbonHistory: Dispatch<SetStateAction<string>>;
  setShowRibbonDiff: Dispatch<SetStateAction<boolean>>;
  setSelectedFile: Dispatch<SetStateAction<ExplorerFileDetails | null>>;
  onCoverageMeasured: (path: string, coverage: number | null) => void;
  onTimelineEvent: (event: EngineeringActionEvent) => void;
  onTestDiscovery: (discovery: ExplorerTestDiscoveryResult | null) => void;
};

function useReviewRibbonActions(args: ReviewRibbonActionsArgs) {
  const {
    token,
    repoId,
    selectedFilePath,
    selectedFile,
    ribbonReview,
    ribbonFix,
    setRibbonAction,
    setRibbonReview,
    setRibbonFix,
    setRibbonTests,
    setRibbonHistory,
    setShowRibbonDiff,
    setSelectedFile,
    onCoverageMeasured,
    onTimelineEvent,
    onTestDiscovery,
  } = args;

  const runRibbonAction = useCallback(async <T,>(actionName: string, fn: () => Promise<T>, successMsg?: string): Promise<T | undefined> => {
    if (!token || !selectedFilePath) return undefined;
    onTimelineEvent(buildActionEvent(actionName, 'started', selectedFilePath));
    try {
      setRibbonAction(actionName);
      const result = await fn();
      if (successMsg) toast.success(successMsg);
      onTimelineEvent(buildActionEvent(actionName, 'succeeded'));
      return result;
    } catch (err) {
      onTimelineEvent(buildActionEvent(actionName, 'failed', err instanceof Error ? err.message : 'Action failed'));
      toast.error(err instanceof Error ? err.message : `${actionName.replace('_', ' ')} failed`);
      return undefined;
    } finally {
      setRibbonAction(null);
    }
  }, [onTimelineEvent, selectedFilePath, setRibbonAction, token]);

  const runRibbonReview = useCallback(async (type: string) => {
    const result = await runRibbonAction(type, () =>
      runExplorerFileReview(token, repoId, { path: selectedFilePath, review_type: type }),
      `${type.replace('_', ' ')} complete`
    );
    if (result) setRibbonReview(result);
  }, [repoId, runRibbonAction, selectedFilePath, setRibbonReview, token]);

  const runRibbonGenerateTests = useCallback(async () => {
    await runRibbonAction('generate_tests', async () => {
      const discovered = await discoverExplorerTests(token, repoId, [selectedFilePath]);
      onTestDiscovery(discovered);
      setRibbonHistory(`Generated tests (${discovered.tests.length}): ${discovered.tests.slice(0, 6).join(', ') || 'none'}`);
    }, 'Generated test candidates');
  }, [onTestDiscovery, repoId, runRibbonAction, selectedFilePath, setRibbonHistory, token]);

  const runRibbonTests = useCallback(async () => {
    await runRibbonAction('run_tests', async () => {
      const discovered = await discoverExplorerTests(token, repoId, [selectedFilePath]);
      onTestDiscovery(discovered);
      const testsToRun = discovered.tests.slice(0, 12);
      if (testsToRun.length === 0) {
        setRibbonTests({
          status: 'skipped',
          tests: [],
          passed: 0,
          failed: 0,
          duration_seconds: 0,
          coverage: null,
          output: 'No impacted tests discovered for this file.',
        });
        return;
      }
      const run = await runExplorerTests(token, repoId, testsToRun, 55);
      setRibbonTests(run);
      onCoverageMeasured(selectedFilePath, run.coverage);
      toast.success(`${run.status.toUpperCase()}: ${run.passed} passed, ${run.failed} failed`);
    });
  }, [onCoverageMeasured, onTestDiscovery, onTimelineEvent, repoId, runRibbonAction, selectedFilePath, setRibbonTests, token]);

  const runRibbonGenerateFix = useCallback(async () => {
    const finding = ribbonReview?.findings?.[0]?.finding || 'Improve maintainability and robustness in this file';
    const recommendation = ribbonReview?.findings?.[0]?.recommendation || '';
    const fix = await runRibbonAction('generate_fix', () =>
      generateExplorerFix(token, repoId, { path: selectedFilePath, finding, recommendation }),
      'Fix generated'
    );
    if (fix) {
      setRibbonFix(fix);
      setShowRibbonDiff(true);
    }
  }, [repoId, ribbonReview, runRibbonAction, selectedFilePath, setRibbonFix, setShowRibbonDiff, token]);

  const runRibbonApplyFix = useCallback(async () => {
    if (!ribbonFix) return;
    if (!window.confirm('Apply this fix? Validation checks will run before acceptance.')) return;
    await runRibbonAction('apply_fix', async () => {
      await applyExplorerFix(token, repoId, { fix_id: ribbonFix.fix_id, expected_sha256: selectedFile?.sha256, run_validation: true });
      const refreshed = await getExplorerFile(token, repoId, selectedFilePath);
      setSelectedFile(refreshed);
    }, 'Fix applied');
  }, [repoId, ribbonFix, runRibbonAction, selectedFile?.sha256, selectedFilePath, setSelectedFile, token]);

  const runRibbonHistory = useCallback(async () => {
    await runRibbonAction('history', async () => {
      const h = await getExplorerHistory(token, repoId, selectedFilePath);
      setRibbonHistory(
        [`Reviews: ${h.reviews.length}`, `Fixes: ${h.fixes.length}`, `Applied: ${h.applied_fixes.length}`,
         `Rejected: ${h.rejected_fixes.length}`, `Tests: ${h.test_runs.length}`, `Conversations: ${h.conversations.length}`].join(' | ')
      );
    }, 'History loaded');
  }, [repoId, runRibbonAction, selectedFilePath, setRibbonHistory, token]);

  const runRibbonAskAi = useCallback(async () => {
    await runRibbonAction('ask_ai', async () => {
      await addExplorerConversationEntry(token, repoId, { path: selectedFilePath, role: 'user', content: `Open AI conversation for ${selectedFilePath}` });
      window.dispatchEvent(new CustomEvent('codebase:new-chat', { detail: { repoId } }));
    }, 'AI chat context queued');
  }, [repoId, runRibbonAction, selectedFilePath, token]);

  return {
    runRibbonReview,
    runRibbonGenerateTests,
    runRibbonTests,
    runRibbonGenerateFix,
    runRibbonApplyFix,
    runRibbonHistory,
    runRibbonAskAi,
  };
}

function ReviewHeaderCard({ repoId }: { repoId: string }) {
  return (
    <motion.section
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className="rounded-[1.5rem] border border-border bg-card/80 p-5 shadow-lg shadow-black/5"
    >
      <div className="flex items-center gap-2">
        <Sparkles size={16} className="text-brand" />
        <h1 className="font-heading text-2xl font-bold tracking-tight">AI Engineering Review</h1>
      </div>
      <p className="mt-2 text-sm text-muted-foreground">Review commits and PR diffs with persisted findings and optional fix generation. Use the <a href={`/repo/${repoId}/explorer`} className="text-brand underline hover:no-underline">File Explorer</a> to browse and review individual files.</p>
    </motion.section>
  );
}

type ReviewRunPanelsProps = {
  loading: boolean;
  activeReviewTarget: 'file' | 'files';
  setActiveReviewTarget: Dispatch<SetStateAction<'file' | 'files'>>;
  filePath: string;
  setFilePath: Dispatch<SetStateAction<string>>;
  filesCsv: string;
  setFilesCsv: Dispatch<SetStateAction<string>>;
  commitHash: string;
  setCommitHash: Dispatch<SetStateAction<string>>;
  prFilesCsv: string;
  setPrFilesCsv: Dispatch<SetStateAction<string>>;
  prDiff: string;
  setPrDiff: Dispatch<SetStateAction<string>>;
  prompt: string;
  setPrompt: Dispatch<SetStateAction<string>>;
  repoId: string;
  token: string;
  runReview: (runner: () => Promise<ReviewRun>) => Promise<void>;
};

function ReviewRunPanels(props: ReviewRunPanelsProps) {
  const {
    loading,
    activeReviewTarget,
    setActiveReviewTarget,
    filePath,
    setFilePath,
    filesCsv,
    setFilesCsv,
    commitHash,
    setCommitHash,
    prFilesCsv,
    setPrFilesCsv,
    prDiff,
    setPrDiff,
    prompt,
    setPrompt,
    repoId,
    token,
    runReview,
  } = props;

  return (
    <div className="space-y-4">
      <div className="rounded-2xl border border-border bg-card/80 p-4 space-y-3">
        <div className="flex items-center gap-2 text-sm font-medium"><FileCode2 size={14} className="text-brand" /> Review file</div>
        <Input
          value={filePath}
          onChange={(e) => {
            setActiveReviewTarget('file');
            setFilePath(e.target.value);
          }}
          placeholder="api/services/chat_service.py"
        />
        <Button
          disabled={loading || !filePath.trim()}
          onClick={() => {
            setActiveReviewTarget('file');
            runReview(() => reviewFile(token, { repo_id: repoId, filename: filePath.trim(), prompt: prompt.trim() || undefined }));
          }}
        >
          Run file review
        </Button>
      </div>

      <div className="rounded-2xl border border-border bg-card/80 p-4 space-y-3">
        <div className="flex items-center gap-2 text-sm font-medium"><Bot size={14} className="text-brand" /> Review multiple files</div>
        <Textarea
          value={filesCsv}
          onChange={(e) => {
            setActiveReviewTarget('files');
            setFilesCsv(e.target.value);
          }}
          placeholder="api/services/chat_service.py,api/routers/chat.py"
          rows={2}
        />
        <Button
          disabled={loading || !filesCsv.trim()}
          onClick={() => {
            setActiveReviewTarget('files');
            runReview(() => reviewFiles(token, { repo_id: repoId, files: csvToList(filesCsv), prompt: prompt.trim() || undefined }));
          }}
        >
          Run files review
        </Button>
        {activeReviewTarget === 'files' && firstPathFromCsv(filesCsv) ? (
          <p className="text-[11px] text-muted-foreground">Active file metadata: {firstPathFromCsv(filesCsv)}</p>
        ) : null}
      </div>

      <div className="rounded-2xl border border-border bg-card/80 p-4 space-y-3">
        <div className="flex items-center gap-2 text-sm font-medium"><GitCommitHorizontal size={14} className="text-brand" /> Review commit</div>
        <Input value={commitHash} onChange={(e) => setCommitHash(e.target.value)} placeholder="commit hash" />
        <Button disabled={loading || !commitHash.trim()} onClick={() => runReview(() => reviewCommit(token, { repo_id: repoId, commit_hash: commitHash.trim(), prompt: prompt.trim() || undefined }))}>Run commit review</Button>
      </div>

      <div className="rounded-2xl border border-border bg-card/80 p-4 space-y-3">
        <div className="flex items-center gap-2 text-sm font-medium"><GitPullRequest size={14} className="text-brand" /> Review pull request</div>
        <Textarea value={prFilesCsv} onChange={(e) => setPrFilesCsv(e.target.value)} placeholder="changed files csv" rows={2} />
        <Textarea value={prDiff} onChange={(e) => setPrDiff(e.target.value)} placeholder="paste PR diff (optional if files are available)" rows={5} />
        <Button
          disabled={loading || (!prFilesCsv.trim() && !prDiff.trim())}
          onClick={() => runReview(() => reviewPullRequest(token, {
            repo_id: repoId,
            changed_files: csvToList(prFilesCsv),
            diff: prDiff,
            prompt: prompt.trim() || undefined,
          }))}
        >
          Run PR review
        </Button>
      </div>

      <div className="rounded-2xl border border-border bg-card/80 p-4 space-y-3">
        <div className="text-sm font-medium">Optional reviewer prompt</div>
        <Textarea value={prompt} onChange={(e) => setPrompt(e.target.value)} placeholder="Focus on security/authentication risks..." rows={3} />
      </div>
    </div>
  );
}

type ReviewHistoryPanelsProps = {
  token: string;
  history: ReviewHistoryItem[];
  historyLoading: boolean;
  setHistoryLoading: Dispatch<SetStateAction<boolean>>;
  selectedReview: ReviewRun | null;
  setSelectedReview: Dispatch<SetStateAction<ReviewRun | null>>;
  findings: ReviewRun['findings'];
  fixOutput: ReviewFixResponse | null;
  setFixOutput: Dispatch<SetStateAction<ReviewFixResponse | null>>;
  fixLoading: string | null;
  setFixLoading: Dispatch<SetStateAction<string | null>>;
  setFilePath: Dispatch<SetStateAction<string>>;
  loadHistory: (t: string) => Promise<void>;
};

function ReviewHistoryPanels(props: ReviewHistoryPanelsProps) {
  const {
    token,
    history,
    historyLoading,
    setHistoryLoading,
    selectedReview,
    setSelectedReview,
    findings,
    fixOutput,
    setFixOutput,
    fixLoading,
    setFixLoading,
    setFilePath,
    loadHistory,
  } = props;

  return (
    <div className="space-y-4">
      <div className="rounded-2xl border border-border bg-card/80 p-4">
        <div className="mb-3 flex items-center justify-between">
          <div className="text-sm font-medium">Review history</div>
          {historyLoading && <Loader2 size={13} className="animate-spin text-muted-foreground" />}
        </div>
        <div className="space-y-2 max-h-[18rem] overflow-auto">
          {history.length === 0 && <p className="text-sm text-muted-foreground">No reviews yet.</p>}

          {history.map((item) => {
            const isActive = selectedReview?.review_id === item.review_id;
            return (
              <button
                key={item.review_id}
                className={`w-full text-left rounded-xl border p-3 transition-colors ${isActive ? 'border-brand/40 bg-brand/5' : 'border-border bg-background/70 hover:border-brand/30'}`}
                onClick={async () => {
                  if (!token || historyLoading) return;
                  setHistoryLoading(true);
                  setFixOutput(null);
                  try {
                    const row = await getReview(token, item.review_id);
                    setSelectedReview(row);
                  } catch (err) {
                    toast.error(err instanceof Error ? err.message : 'Failed to load review');
                  } finally {
                    setHistoryLoading(false);
                  }
                }}
              >
                <div className="text-xs text-muted-foreground">{item.target_type.toUpperCase()} • {item.created_at ? new Date(item.created_at).toLocaleString() : 'n/a'}</div>
                <div className="mt-1 text-sm font-medium truncate">{item.summary}</div>
              </button>
            );
          })}
        </div>
      </div>

      {selectedReview && (
        <div className="rounded-2xl border border-border bg-card/80 p-4 space-y-3">
          <div className="flex items-center justify-between gap-2">
            <div>
              <div className="text-xs text-muted-foreground">Review #{selectedReview.review_id.slice(0, 8)}</div>
              <div className="text-sm font-medium">{selectedReview.summary}</div>
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={async () => {
                if (!token) return;
                try {
                  await deleteReview(token, selectedReview.review_id);
                  setSelectedReview(null);
                  setFixOutput(null);
                  await loadHistory(token);
                  toast.success('Review deleted');
                } catch (err) {
                  toast.error(err instanceof Error ? err.message : 'Failed to delete review');
                }
              }}
            >
              <Trash2 size={13} className="mr-1" /> Delete
            </Button>
          </div>

          <div className="space-y-2 max-h-[18rem] overflow-auto">
            {findings.length === 0 && <p className="text-sm text-muted-foreground">No findings for this review.</p>}
            {findings.map((f) => (
              <div key={f.id} className={`rounded-xl border p-3 space-y-2 transition-colors ${fixOutput && fixLoading === null && (fixOutput as ReviewFixResponse & { _findingId?: string })._findingId === f.id ? 'border-brand/40 bg-brand/5' : 'border-border bg-background/70'}`}>
                <div className="flex items-center justify-between gap-2">
                  <button
                    type="button"
                    className="text-left text-sm font-medium hover:text-brand"
                    onClick={() => {
                      if (f.file && f.file !== 'unknown') {
                        setFilePath(f.file);
                      }
                    }}
                  >
                    {f.finding}
                  </button>
                  <SeverityPill severity={f.severity} />
                </div>
                <div className="text-xs text-muted-foreground">{f.file} • {f.code_area} • risk: {f.risk_level}</div>
                <p className="text-sm">{f.recommendation}</p>
                <Button
                  size="sm"
                  variant="outline"
                  disabled={fixLoading !== null}
                  onClick={async () => {
                    if (!token) return;
                    setFixLoading(f.id);
                    setFixOutput(null);
                    try {
                      const fix = await generateReviewFix(token, {
                        review_id: selectedReview.review_id,
                        repo_id: selectedReview.repo_id,
                        finding_id: f.id,
                        finding: f.finding,
                        file: f.file,
                        code_area: f.code_area,
                        recommendation: f.recommendation,
                      });
                      setFixOutput(fix);
                    } catch (err) {
                      toast.error(err instanceof Error ? err.message : 'Failed to generate fix');
                    } finally {
                      setFixLoading(null);
                    }
                  }}
                >
                  {fixLoading === f.id ? (
                    <><Loader2 size={13} className="mr-1 animate-spin" /> Generating…</>
                  ) : (
                    <><Wrench size={13} className="mr-1" /> Generate fix</>
                  )}
                </Button>
              </div>
            ))}
          </div>

          {fixOutput && (
            <div className="rounded-xl border border-brand/30 bg-brand/5 p-3">
              <div className="mb-2 flex items-center gap-2 text-xs font-medium text-brand">
                <Wrench size={12} />
                Suggested fix{fixOutput.target_file ? ` for ${fixOutput.target_file}` : ''}
              </div>
              <pre className="whitespace-pre-wrap text-sm leading-relaxed">{fixOutput.suggested_fix}</pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}


export default function RepositoryReviewPage() {
  const { id: repoId } = useParams<{ id: string }>();
  const token = useRepoSessionToken();
  const [history, setHistory] = useState<ReviewHistoryItem[]>([]);
  const [selectedReview, setSelectedReview] = useState<ReviewRun | null>(null);
  const [loading, setLoading] = useState(false);
  const [fixLoading, setFixLoading] = useState<string | null>(null); // finding id being fixed
  const [historyLoading, setHistoryLoading] = useState(false);
  const [activeReviewTarget, setActiveReviewTarget] = useState<'file' | 'files'>('file');
  const [filePath, setFilePath] = useState('');
  const [filesCsv, setFilesCsv] = useState('');
  const [commitHash, setCommitHash] = useState('');
  const [prFilesCsv, setPrFilesCsv] = useState('');
  const [prDiff, setPrDiff] = useState('');
  const [prompt, setPrompt] = useState('');
  const [fixOutput, setFixOutput] = useState<ReviewFixResponse | null>(null);
  const [selectedFile, setSelectedFile] = useState<ExplorerFileDetails | null>(null);
  const [ribbonReview, setRibbonReview] = useState<ExplorerReviewResult | null>(null);
  const [ribbonFix, setRibbonFix] = useState<ExplorerFixProposal | null>(null);
  const [ribbonTests, setRibbonTests] = useState<ExplorerTestRunResult | null>(null);
  const [coverageByPath, setCoverageByPath] = useState<Record<string, number>>({});
  const [ribbonHistory, setRibbonHistory] = useState('');
  const [ribbonAction, setRibbonAction] = useState<string | null>(null);
  const [showRibbonDiff, setShowRibbonDiff] = useState(false);
  const [repoHealthScore, setRepoHealthScore] = useState<number | null>(null);
  const [healthRecommendations, setHealthRecommendations] = useState<HealthRecommendation[]>([]);
  const [selectedRecommendationId, setSelectedRecommendationId] = useState('');
  const [statusUpdating, setStatusUpdating] = useState(false);
  const [actionTimeline, setActionTimeline] = useState<EngineeringActionEvent[]>([]);
  const [testDiscovery, setTestDiscovery] = useState<ExplorerTestDiscoveryResult | null>(null);
  const inferredRepoIdsRef = useRef<Set<string>>(new Set());
  const previousRepoIdRef = useRef<string | null>(null);

  useEffect(() => {
    if (previousRepoIdRef.current === null) {
      previousRepoIdRef.current = repoId;
      return;
    }
    if (previousRepoIdRef.current === repoId) return;

    previousRepoIdRef.current = repoId;
    inferredRepoIdsRef.current.clear();

    // Prevent stale file/ribbon context from previous repo carrying over.
    setActiveReviewTarget('file');
    setFilePath('');
    setFilesCsv('');
    setCommitHash('');
    setPrFilesCsv('');
    setPrDiff('');
    setSelectedFile(null);
    setSelectedReview(null);
    setFixOutput(null);
    setRibbonReview(null);
    setRibbonFix(null);
    setRibbonTests(null);
    setCoverageByPath({});
    setRibbonHistory('');
    setRibbonAction(null);
    setShowRibbonDiff(false);
    setRepoHealthScore(null);
    setHealthRecommendations([]);
    setSelectedRecommendationId('');
    setStatusUpdating(false);
    setActionTimeline([]);
    setTestDiscovery(null);
  }, [repoId]);

  const setFilePathAndActivate: Dispatch<SetStateAction<string>> = useCallback((next) => {
    setActiveReviewTarget('file');
    setFilePath(next);
  }, []);

  const setFilesCsvAndActivate: Dispatch<SetStateAction<string>> = useCallback((next) => {
    setActiveReviewTarget('files');
    setFilesCsv(next);
  }, []);

  const loadHistory = useCallback(async (t: string) => {
    const response = await listReviews(t, repoId);
    setHistory(response.items || []);
  }, [repoId]);

  useEffect(() => {
    async function init() {
      if (!token) return;
      try {
        await loadHistory(token);
      } catch (err) {
        toast.error(err instanceof Error ? err.message : 'Failed to load review history');
      }

      try {
        const prefillKey = `codebase:review-prefill:${repoId}`;
        const rawPrefill = sessionStorage.getItem(prefillKey);
        if (rawPrefill) {
          sessionStorage.removeItem(prefillKey);
          const parsed = JSON.parse(rawPrefill) as { files?: string[]; prompt?: string };
          const files = (parsed.files || []).filter((f) => typeof f === 'string' && f.trim().length > 0);
          if (files.length > 0) {
            setFilePath(files[0]);
            setFilesCsv(files.join(','));
            setPrFilesCsv(files.join(','));
            inferredRepoIdsRef.current.add(repoId);
          }
          if (parsed.prompt && parsed.prompt.trim()) {
            setPrompt(parsed.prompt.trim());
          }
        }
      } catch {
        // Ignore invalid prefill payloads.
      }
    }
    void init();
  }, [loadHistory, repoId, token]);

  useEffect(() => {
    if (!token || filePath.trim() || inferredRepoIdsRef.current.has(repoId)) return;
    inferredRepoIdsRef.current.add(repoId);
    let cancelled = false;

    async function inferDefaultFile() {
      try {
        const queue: string[] = [''];
        const visited = new Set<string>();
        let attempts = 0;

        while (queue.length > 0 && attempts < 24) {
          const current = queue.shift() ?? '';
          const key = normalizePath(current);
          if (visited.has(key)) continue;
          visited.add(key);
          attempts += 1;

          const tree = await getExplorerTree(token, repoId, { path: current || undefined, limit: 300 });
          const nodes = Array.isArray(tree?.nodes) ? tree.nodes : [];

          const preferredFile = pickFirstReviewableFile(nodes);
          if (preferredFile) {
            if (!cancelled) {
              setFilePath(preferredFile);
            }
            return;
          }

          const childFolders = nodes
            .filter((node) => node.type === 'folder' && node.path)
            .map((node) => normalizePath(node.path))
            .filter((path) => path && !visited.has(path));
          queue.push(...childFolders);
        }
      } catch {
        // Keep the field editable/empty if tree inference is unavailable.
      }

    }

    void inferDefaultFile();
    return () => {
      cancelled = true;
    };
  }, [filePath, repoId, token]);

  const selectedFilePath = useMemo(() => {
    const singlePath = filePath.trim() ? normalizePath(filePath) : '';
    const firstMultiPath = firstPathFromCsv(filesCsv);
    if (activeReviewTarget === 'files') {
      return firstMultiPath || singlePath;
    }
    return singlePath || firstMultiPath;
  }, [activeReviewTarget, filePath, filesCsv]);

  const coverageLabel = useMemo(() => {
    const key = selectedFilePath ? coverageCacheKey(selectedFilePath) : '';
    const cachedCoverage = key ? coverageByPath[key] : undefined;
    const value = typeof cachedCoverage === 'number' ? cachedCoverage : ribbonTests?.coverage;
    if (typeof value !== 'number' || !Number.isFinite(value)) return 'n/a';
    return `${Math.round(value)}%`;
  }, [coverageByPath, ribbonTests, selectedFilePath]);

  const handleCoverageMeasured = useCallback((path: string, coverage: number | null) => {
    const key = coverageCacheKey(path);
    if (!key) return;
    if (typeof coverage !== 'number' || !Number.isFinite(coverage)) return;
    setCoverageByPath((prev) => ({ ...prev, [key]: coverage }));
  }, []);

  useEffect(() => {
    // Keep ribbon context file-scoped; prevents stale coverage/details from previous file.
    setRibbonReview(null);
    setRibbonFix(null);
    setRibbonTests(null);
    setRibbonHistory('');
    setShowRibbonDiff(false);
    setActionTimeline([]);
    setTestDiscovery(null);
  }, [selectedFilePath]);

  useEffect(() => {
    if (!token || !selectedFilePath) {
      setSelectedFile(null);
      return;
    }
    let cancelled = false;
    setSelectedFile(null);
    async function loadSelectedFile() {
      try {
        const details = await getExplorerFile(token, repoId, selectedFilePath);
        if (!cancelled) setSelectedFile(details);
      } catch {
        if (!cancelled) setSelectedFile(null);
      }
    }
    void loadSelectedFile();
    return () => {
      cancelled = true;
    };
  }, [token, repoId, selectedFilePath]);

  useEffect(() => {
    if (!token) return;
    let cancelled = false;

    async function loadRepoHealthScore() {
      try {
        const latest = await getLatestRepositoryHealth(token, repoId);
        if (!cancelled) {
          setRepoHealthScore(latest.latest?.top_level?.repository_health ?? readCachedRepoHealthScore(repoId));
          const recs = latest.latest?.recommendations ?? [];
          setHealthRecommendations(recs);
          setSelectedRecommendationId((prev) => prev || recs[0]?.recommendation_id || '');
        }
      } catch {
        if (!cancelled) {
          setRepoHealthScore(readCachedRepoHealthScore(repoId));
          setHealthRecommendations([]);
          setSelectedRecommendationId('');
        }
      }
    }

    void loadRepoHealthScore();
    return () => {
      cancelled = true;
    };
  }, [repoId, token]);


  const runReview = useCallback(async (runner: () => Promise<ReviewRun>) => {
    if (!token) return;
    setLoading(true);
    setFixOutput(null);
    try {
      const run = await runner();
      setSelectedReview(run);
      await loadHistory(token);
      toast.success('Review generated');
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Review failed');
    } finally {
      setLoading(false);
    }
  }, [loadHistory, token]);

  const findings = useMemo(() => selectedReview?.findings ?? [], [selectedReview]);

  const ribbonHealthScore = useMemo(() => {
    return computeRibbonHealthScore(selectedFile, repoHealthScore);
  }, [selectedFile, repoHealthScore]);

  const appendTimelineEvent = useCallback((event: EngineeringActionEvent) => {
    setActionTimeline((prev) => [event, ...prev].slice(0, 40));
  }, []);

  const scopedRecommendations = useMemo(() => {
    const normalizedPath = normalizePath(selectedFilePath).toLowerCase();
    if (!normalizedPath) return healthRecommendations.slice(0, 10);
    const matched = healthRecommendations.filter((rec) =>
      (rec.affected_files ?? []).some((file) => normalizePath(file).toLowerCase() === normalizedPath)
    );
    return matched.length > 0 ? matched : healthRecommendations.slice(0, 10);
  }, [healthRecommendations, selectedFilePath]);

  useEffect(() => {
    if (!scopedRecommendations.length) {
      setSelectedRecommendationId('');
      return;
    }
    const hasSelected = scopedRecommendations.some((rec) => rec.recommendation_id === selectedRecommendationId);
    if (!hasSelected) {
      setSelectedRecommendationId(scopedRecommendations[0]?.recommendation_id || '');
    }
  }, [scopedRecommendations, selectedRecommendationId]);

  const handleSetLifecycleStatus = useCallback(async (status: RecommendationLifecycleStatus, reason?: string) => {
    const recommendationId = selectedRecommendationId;
    if (!token || !recommendationId) return;
    setStatusUpdating(true);
    try {
      await updateRepositoryHealthRecommendationStatus(token, repoId, recommendationId, status, reason);
      setHealthRecommendations((prev) =>
        prev.map((rec) =>
          rec.recommendation_id === recommendationId
            ? { ...rec, current_status: status, dismissed_reason: reason ?? null, lifecycle_updated_at: new Date().toISOString() }
            : rec
        )
      );
      appendTimelineEvent(buildActionEvent('lifecycle_status', 'succeeded', `${status} for ${recommendationId.slice(0, 8)}`));
      toast.success(`Recommendation marked ${status.replace(/_/g, ' ').toLowerCase()}`);
    } catch (err) {
      appendTimelineEvent(buildActionEvent('lifecycle_status', 'failed', err instanceof Error ? err.message : 'Status update failed'));
      toast.error(err instanceof Error ? err.message : 'Failed to update recommendation status');
    } finally {
      setStatusUpdating(false);
    }
  }, [appendTimelineEvent, repoId, selectedRecommendationId, token]);

  const {
    runRibbonReview,
    runRibbonGenerateTests,
    runRibbonTests,
    runRibbonGenerateFix,
    runRibbonApplyFix,
    runRibbonHistory,
    runRibbonAskAi,
  } = useReviewRibbonActions({
    token,
    repoId,
    selectedFilePath,
    selectedFile,
    ribbonReview,
    ribbonFix,
    setRibbonAction,
    setRibbonReview,
    setRibbonFix,
    setRibbonTests,
    setRibbonHistory,
    setShowRibbonDiff,
    setSelectedFile,
    onCoverageMeasured: handleCoverageMeasured,
    onTimelineEvent: appendTimelineEvent,
    onTestDiscovery: setTestDiscovery,
  });

  useEffect(() => {
    if (!selectedFilePath) return;
    function onKeyDown(event: KeyboardEvent) {
      const target = event.target as HTMLElement | null;
      const tag = target?.tagName?.toLowerCase();
      if (tag === 'input' || tag === 'textarea' || target?.isContentEditable) return;
      const key = event.key.toLowerCase();

      if (event.ctrlKey && key === 'd') {
        event.preventDefault();
        setShowRibbonDiff((prev) => !prev);
        return;
      }
      if (event.ctrlKey && key === '/') {
        event.preventDefault();
        void runRibbonAskAi();
        return;
      }
      if (event.shiftKey && key === 't') {
        event.preventDefault();
        void runRibbonTests();
        return;
      }
      if (event.ctrlKey || event.metaKey || event.altKey || event.shiftKey) return;

      if (key === 'e') void runRibbonReview('explain');
      else if (key === 'r') void runRibbonReview('review');
      else if (key === 'b') void runRibbonReview('find_bugs');
      else if (key === 's') void runRibbonReview('security');
      else if (key === 'a') void runRibbonReview('architecture');
      else if (key === 't') void runRibbonGenerateTests();
      else if (key === 'f') void runRibbonGenerateFix();
    }
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedFilePath, token, repoId, selectedFile, ribbonFix, ribbonReview]);

  return (
    <div className="space-y-6">
      <ReviewHeaderCard repoId={repoId} />

      {selectedFilePath && (
        <FileActionRibbon
          selectedFilePath={selectedFilePath}
          selectedFile={selectedFile}
          coverageLabel={coverageLabel}
          ribbonHealthScore={ribbonHealthScore}
          runRibbonReview={runRibbonReview}
          runRibbonGenerateTests={runRibbonGenerateTests}
          runRibbonTests={runRibbonTests}
          runRibbonGenerateFix={runRibbonGenerateFix}
          runRibbonApplyFix={runRibbonApplyFix}
          runRibbonAskAi={runRibbonAskAi}
          runRibbonHistory={runRibbonHistory}
          ribbonAction={ribbonAction}
          ribbonReview={ribbonReview}
          ribbonFix={ribbonFix}
          showRibbonDiff={showRibbonDiff}
          setShowRibbonDiff={setShowRibbonDiff}
          ribbonTests={ribbonTests}
          ribbonHistory={ribbonHistory}
        />
      )}

      {selectedFilePath && (
        <EngineeringActionRunTimeline
          scopeLabel={selectedFilePath}
          events={actionTimeline}
          recommendations={scopedRecommendations}
          selectedRecommendationId={selectedRecommendationId}
          onSelectRecommendation={setSelectedRecommendationId}
          onSetLifecycleStatus={handleSetLifecycleStatus}
          statusUpdating={statusUpdating}
          testSelection={testDiscovery}
        />
      )}

      <section className="grid gap-6 xl:grid-cols-[1.1fr_0.9fr]">
        <ReviewRunPanels
          loading={loading}
          activeReviewTarget={activeReviewTarget}
          setActiveReviewTarget={setActiveReviewTarget}
          filePath={filePath}
          setFilePath={setFilePathAndActivate}
          filesCsv={filesCsv}
          setFilesCsv={setFilesCsvAndActivate}
          commitHash={commitHash}
          setCommitHash={setCommitHash}
          prFilesCsv={prFilesCsv}
          setPrFilesCsv={setPrFilesCsv}
          prDiff={prDiff}
          setPrDiff={setPrDiff}
          prompt={prompt}
          setPrompt={setPrompt}
          repoId={repoId}
          token={token}
          runReview={runReview}
        />
        <ReviewHistoryPanels
          token={token}
          history={history}
          historyLoading={historyLoading}
          setHistoryLoading={setHistoryLoading}
          selectedReview={selectedReview}
          setSelectedReview={setSelectedReview}
          findings={findings}
          fixOutput={fixOutput}
          setFixOutput={setFixOutput}
          fixLoading={fixLoading}
          setFixLoading={setFixLoading}
          setFilePath={setFilePathAndActivate}
          loadHistory={loadHistory}
        />
      </section>
    </div>
  );
}
