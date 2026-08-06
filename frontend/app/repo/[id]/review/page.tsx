'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { useParams } from 'next/navigation';
import { motion } from 'framer-motion';
import {
  Bot,
  Circle,
  FileCode,
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
import { createClient } from '@/lib/supabase/client';
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
  getExplorerHistory,
  getReview,
  listReviews,
  runExplorerFileReview,
  runExplorerTests,
  reviewCommit,
  reviewFile,
  reviewFiles,
  reviewPullRequest,
} from '@/lib/api';
import type { ExplorerFileDetails, ExplorerFixProposal, ExplorerReviewResult, ExplorerTestRunResult, ReviewFixResponse, ReviewHistoryItem, ReviewRun } from '@/lib/types';
import { toast } from 'sonner';
import { cn } from '@/lib/utils';

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


export default function RepositoryReviewPage() {
  const { id: repoId } = useParams<{ id: string }>();
  const [token, setToken] = useState('');
  const [history, setHistory] = useState<ReviewHistoryItem[]>([]);
  const [selectedReview, setSelectedReview] = useState<ReviewRun | null>(null);
  const [loading, setLoading] = useState(false);
  const [fixLoading, setFixLoading] = useState<string | null>(null); // finding id being fixed
  const [historyLoading, setHistoryLoading] = useState(false);
  const [filePath, setFilePath] = useState('api/services/chat_service.py');
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
  const [ribbonHistory, setRibbonHistory] = useState('');
  const [ribbonAction, setRibbonAction] = useState<string | null>(null);
  const [fileViewerOpen, setFileViewerOpen] = useState(true);
  const [showRibbonDiff, setShowRibbonDiff] = useState(false);

  const loadHistory = useCallback(async (t: string) => {
    const response = await listReviews(t, repoId);
    setHistory(response.items || []);
  }, [repoId]);

  useEffect(() => {
    async function init() {
      const { data } = await createClient().auth.getSession();
      const t = data.session?.access_token ?? '';
      setToken(t);
      if (!t) return;
      try {
        await loadHistory(t);
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
  }, [loadHistory, repoId]);

  const selectedFilePath = filePath.trim();

  useEffect(() => {
    if (!token || !selectedFilePath) return;
    let cancelled = false;
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


  const visibleTreeRoots = useMemo(() => [], []); // Explorer moved to sidebar

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

  function csvToList(csv: string): string[] {
    return csv.split(',').map((s) => s.trim()).filter(Boolean);
  }

  const ribbonHealthScore = useMemo(() => {
    if (!selectedFile) return 74;
    if (selectedFile.health === 'critical') return 42;
    if (selectedFile.health === 'review_suggested') return 67;
    if (selectedFile.health === 'healthy') return 84;
    return 74;
  }, [selectedFile]);

  async function runRibbonAction<T>(actionName: string, fn: () => Promise<T>, successMsg?: string): Promise<T | undefined> {
    if (!token || !selectedFilePath) return undefined;
    try {
      setRibbonAction(actionName);
      const result = await fn();
      if (successMsg) toast.success(successMsg);
      return result;
    } catch (err) {
      toast.error(err instanceof Error ? err.message : `${actionName.replace('_', ' ')} failed`);
      return undefined;
    } finally {
      setRibbonAction(null);
    }
  }

  async function runRibbonReview(type: string) {
    const result = await runRibbonAction(type, () =>
      runExplorerFileReview(token, repoId, { path: selectedFilePath, review_type: type }),
      `${type.replace('_', ' ')} complete`
    );
    if (result) setRibbonReview(result);
  }

  async function runRibbonGenerateTests() {
    await runRibbonAction('generate_tests', async () => {
      const discovered = await discoverExplorerTests(token, repoId, [selectedFilePath]);
      setRibbonHistory(`Generated tests (${discovered.tests.length}): ${discovered.tests.slice(0, 6).join(', ') || 'none'}`);
    }, 'Generated test candidates');
  }

  async function runRibbonTests() {
    await runRibbonAction('run_tests', async () => {
      const discovered = await discoverExplorerTests(token, repoId, [selectedFilePath]);
      const run = await runExplorerTests(token, repoId, discovered.tests.slice(0, 12), 55);
      setRibbonTests(run);
      toast.success(`${run.status.toUpperCase()}: ${run.passed} passed, ${run.failed} failed`);
    });
  }

  async function runRibbonGenerateFix() {
    const finding = ribbonReview?.findings?.[0]?.finding || 'Improve maintainability and robustness in this file';
    const recommendation = ribbonReview?.findings?.[0]?.recommendation || '';
    const fix = await runRibbonAction('generate_fix', () =>
      generateExplorerFix(token, repoId, { path: selectedFilePath, finding, recommendation }),
      'Fix generated'
    );
    if (fix) { setRibbonFix(fix); setShowRibbonDiff(true); }
  }

  async function runRibbonApplyFix() {
    if (!ribbonFix) return;
    if (!window.confirm('Apply this fix? Validation checks will run before acceptance.')) return;
    await runRibbonAction('apply_fix', async () => {
      await applyExplorerFix(token, repoId, { fix_id: ribbonFix.fix_id, expected_sha256: selectedFile?.sha256, run_validation: true });
      const refreshed = await getExplorerFile(token, repoId, selectedFilePath);
      setSelectedFile(refreshed);
    }, 'Fix applied');
  }

  async function runRibbonHistory() {
    await runRibbonAction('history', async () => {
      const h = await getExplorerHistory(token, repoId, selectedFilePath);
      setRibbonHistory(
        [`Reviews: ${h.reviews.length}`, `Fixes: ${h.fixes.length}`, `Applied: ${h.applied_fixes.length}`,
         `Rejected: ${h.rejected_fixes.length}`, `Tests: ${h.test_runs.length}`, `Conversations: ${h.conversations.length}`].join(' | ')
      );
    }, 'History loaded');
  }

  async function runRibbonAskAi() {
    await runRibbonAction('ask_ai', async () => {
      await addExplorerConversationEntry(token, repoId, { path: selectedFilePath, role: 'user', content: `Open AI conversation for ${selectedFilePath}` });
      window.dispatchEvent(new CustomEvent('codebase:new-chat', { detail: { repoId } }));
    }, 'AI chat context queued');
  }

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

      {selectedFilePath && (
        <section className="rounded-[1.25rem] border border-border bg-card/80 p-4 shadow-lg shadow-black/5">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="min-w-0">
              <p className="truncate text-sm font-semibold">{selectedFilePath}</p>
              <p className="mt-1 text-xs text-muted-foreground">
                {selectedFile?.language || 'unknown'} • {selectedFile?.line_count || 'n/a'} lines • {selectedFile?.imports.length || 0} imports • {selectedFile?.classes.length || 0} classes • {selectedFile?.functions.length || 0} functions
              </p>
              <p className="mt-1 text-[11px] text-muted-foreground">Coverage 72% • Owner Unknown • Last Modified</p>
            </div>
            <div className="text-right">
              <p className="text-[11px] text-muted-foreground">Repository Health</p>
              <p className="text-lg font-semibold">{ribbonHealthScore}</p>
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
      )}

      {/* File Viewer removed — use /explorer page for full file browsing */}

      <section className="grid gap-6 xl:grid-cols-[1.1fr_0.9fr]">
        <div className="space-y-4">
          <div className="rounded-2xl border border-border bg-card/80 p-4 space-y-3">
            <div className="flex items-center gap-2 text-sm font-medium"><FileCode2 size={14} className="text-brand" /> Review file</div>
            <Input value={filePath} onChange={(e) => setFilePath(e.target.value)} placeholder="api/services/chat_service.py" />
            <Button disabled={loading || !filePath.trim()} onClick={() => runReview(() => reviewFile(token, { repo_id: repoId, filename: filePath.trim(), prompt: prompt.trim() || undefined }))}>Run file review</Button>
          </div>

          <div className="rounded-2xl border border-border bg-card/80 p-4 space-y-3">
            <div className="flex items-center gap-2 text-sm font-medium"><Bot size={14} className="text-brand" /> Review multiple files</div>
            <Textarea value={filesCsv} onChange={(e) => setFilesCsv(e.target.value)} placeholder="api/services/chat_service.py,api/routers/chat.py" rows={2} />
            <Button
              disabled={loading || !filesCsv.trim()}
              onClick={() => runReview(() => reviewFiles(token, {
                repo_id: repoId,
                files: csvToList(filesCsv),
                prompt: prompt.trim() || undefined,
              }))}
            >
              Run files review
            </Button>
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
                {findings.length === 0 && (
                  <p className="text-sm text-muted-foreground">No findings for this review.</p>
                )}
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
      </section>
    </div>
  );
}
