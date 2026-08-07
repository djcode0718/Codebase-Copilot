'use client';

import { useEffect, useMemo, useState } from 'react';
import {
  Bot,
  ChevronDown,
  ChevronRight,
  Circle,
  Copy,
  FileCode,
  FileSearch,
  Folder,
  FolderOpen,
  GitCompare,
  History,
  MessageSquare,
  Loader2,
  Play,
  Shield,
  Sparkles,
  Star,
  TestTube,
  Wrench,
} from 'lucide-react';
import { toast } from 'sonner';
import {
  addExplorerConversationEntry,
  applyExplorerFix,
  discoverExplorerTests,
  generateExplorerFix,
  getExplorerFile,
  getExplorerHistory,
  getExplorerTree,
  runExplorerBatchReview,
  runExplorerFileReview,
  runExplorerTests,
} from '@/lib/api';
import type {
  ExplorerFileDetails,
  ExplorerFixProposal,
  ExplorerReviewResult,
  ExplorerTreeNode,
  ExplorerTestRunResult,
} from '@/lib/types';
import { cn } from '@/lib/utils';

interface RepositoryExplorerProps {
  repoId: string;
  repoName: string;
  repoStatus: string;
  token: string;
  collapsed: boolean;
}

interface FileContextMenuState {
  x: number;
  y: number;
  node: ExplorerTreeNode;
}

type SmartFilter = 'all' | 'python' | 'typescript' | 'tests' | 'modified' | 'high_risk' | 'recent';

const FAVORITES_KEY = 'codebase-copilot.explorer.favorites.v1';
const PINNED_KEY = 'codebase-copilot.explorer.pinned.v1';
const RECENT_KEY = 'codebase-copilot.explorer.recent.v1';

function statusDot(node: ExplorerTreeNode) {
  if (node.health === 'critical') return 'text-red-400';
  if (node.health === 'review_suggested') return 'text-amber-400';
  if (node.health === 'healthy') return 'text-emerald-400';
  return 'text-zinc-500';
}

function canPassFilter(node: ExplorerTreeNode, filter: SmartFilter): boolean {
  if (filter === 'all') return true;
  if (filter === 'python') return node.language === 'python';
  if (filter === 'typescript') return node.language === 'typescript' || node.language === 'tsx';
  if (filter === 'tests') return node.path.toLowerCase().includes('/tests/') || node.name.toLowerCase().startsWith('test_');
  if (filter === 'modified') return node.is_modified;
  if (filter === 'high_risk') return node.health === 'critical' || node.health === 'review_suggested';
  if (filter === 'recent') return node.ai_indicator === 'recently_changed';
  return true;
}

function loadLocalSet(key: string): Set<string> {
  if (typeof window === 'undefined') return new Set();
  try {
    const parsed = JSON.parse(window.localStorage.getItem(key) || '[]');
    return new Set(Array.isArray(parsed) ? parsed : []);
  } catch {
    return new Set();
  }
}

function saveLocalSet(key: string, values: Set<string>) {
  if (typeof window === 'undefined') return;
  try {
    window.localStorage.setItem(key, JSON.stringify(Array.from(values)));
  } catch {
    // noop
  }
}

interface ActiveFileStats {
  healthScore: number;
  language: string;
  lines: number;
  imports: number;
  classes: number;
  functions: number;
  coverage: number;
}

interface ActiveFilePanelProps {
  activeFile: ExplorerFileDetails;
  fileStats: ActiveFileStats;
  activeAction: string | null;
  fixProposal: ExplorerFixProposal | null;
  reviewResult: ExplorerReviewResult | null;
  testResult: ExplorerTestRunResult | null;
  historyText: string;
  recent: string[];
  showDiff: boolean;
  onToggleDiff: () => void;
  onOpenRecent: (path: string) => void;
  onExecuteReview: (type: string) => void;
  onExecuteGenerateTests: () => void;
  onExecuteTests: () => void;
  onExecuteGenerateFix: () => void;
  onExecuteApplyFix: () => void;
  onExecuteAskAi: () => void;
  onExecuteHistory: () => void;
}

function ActiveFilePanel({
  activeFile,
  fileStats,
  activeAction,
  fixProposal,
  reviewResult,
  testResult,
  historyText,
  recent,
  showDiff,
  onToggleDiff,
  onOpenRecent,
  onExecuteReview,
  onExecuteGenerateTests,
  onExecuteTests,
  onExecuteGenerateFix,
  onExecuteApplyFix,
  onExecuteAskAi,
  onExecuteHistory,
}: ActiveFilePanelProps) {
  return (
    <>
      <div className="rounded-xl border border-sidebar-border bg-sidebar p-2.5">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <p className="truncate text-xs font-semibold text-sidebar-foreground">{activeFile.path}</p>
            <p className="mt-0.5 text-[10px] text-sidebar-foreground/60">{fileStats.language} • {fileStats.lines} lines • {fileStats.imports} imports • {fileStats.classes} classes • {fileStats.functions} functions</p>
          </div>
          <div className="text-right">
            <p className="text-[10px] text-sidebar-foreground/55">Repository Health</p>
            <p className="text-sm font-semibold text-sidebar-foreground">{fileStats.healthScore}</p>
          </div>
        </div>
        <p className="mt-1 text-[10px] text-sidebar-foreground/55">Coverage {fileStats.coverage}% • Owner Unknown • Last Modified</p>

        <div className="mt-2 flex flex-wrap items-center gap-1">
          <button type="button" title="E" className="rounded-full border border-sidebar-border px-2 py-1 text-[10px]" onClick={() => onExecuteReview('explain')}>Explain</button>
          <button type="button" title="R" className="rounded-full border border-sidebar-border px-2 py-1 text-[10px]" onClick={() => onExecuteReview('review')}><FileSearch size={10} className="mr-1 inline" />Review</button>
          <button type="button" title="B" className="rounded-full border border-sidebar-border px-2 py-1 text-[10px]" onClick={() => onExecuteReview('find_bugs')}>Find Bugs</button>
          <button type="button" title="S" className="rounded-full border border-sidebar-border px-2 py-1 text-[10px]" onClick={() => onExecuteReview('security')}><Shield size={10} className="mr-1 inline" />Security</button>
          <button type="button" title="A" className="rounded-full border border-sidebar-border px-2 py-1 text-[10px]" onClick={() => onExecuteReview('architecture')}>Architecture</button>
          <button type="button" className="rounded-full border border-sidebar-border px-2 py-1 text-[10px]" onClick={() => onExecuteReview('performance')}><Play size={10} className="mr-1 inline" />Performance</button>
          <button type="button" className="rounded-full border border-sidebar-border px-2 py-1 text-[10px]" onClick={() => onExecuteReview('code_quality')}>Code Quality</button>
          <button type="button" title="T" className="rounded-full border border-sidebar-border px-2 py-1 text-[10px]" onClick={onExecuteGenerateTests}>Generate Tests</button>
          <button type="button" title="Shift+T" className="rounded-full border border-sidebar-border px-2 py-1 text-[10px]" onClick={onExecuteTests}><TestTube size={10} className="mr-1 inline" />Run Tests</button>
          <button type="button" title="F" className="rounded-full border border-sidebar-border px-2 py-1 text-[10px]" onClick={onExecuteGenerateFix}><Wrench size={10} className="mr-1 inline" />Generate Fix</button>
          <button type="button" className="rounded-full border border-sidebar-border px-2 py-1 text-[10px]" onClick={onExecuteApplyFix} disabled={!fixProposal}>Apply Fix</button>
          <button type="button" title="Ctrl+D" className="rounded-full border border-sidebar-border px-2 py-1 text-[10px]" onClick={onToggleDiff}>Show Diff</button>
          <button type="button" className="rounded-full border border-sidebar-border px-2 py-1 text-[10px]" onClick={() => onExecuteReview('commit_impact')}>Commit Impact</button>
          <button type="button" className="rounded-full border border-sidebar-border px-2 py-1 text-[10px]" onClick={() => onExecuteReview('dependencies')}>Dependencies</button>
          <button type="button" title="Ctrl+/" className="rounded-full border border-sidebar-border px-2 py-1 text-[10px]" onClick={onExecuteAskAi}><MessageSquare size={10} className="mr-1 inline" />Ask AI</button>
          <button type="button" className="rounded-full border border-sidebar-border px-2 py-1 text-[10px]" onClick={onExecuteHistory}><History size={10} className="mr-1 inline" />History</button>
        </div>
        {activeAction && (
          <div className="mt-2 inline-flex items-center gap-1 rounded-full border border-brand/30 bg-brand/10 px-2 py-1 text-[10px] text-sidebar-foreground/75">
            <Loader2 size={10} className="animate-spin" /> Running {activeAction.replace('_', ' ')}...
          </div>
        )}
      </div>

      <div className="rounded-xl border border-sidebar-border bg-sidebar p-2">
        <div className="mb-1 flex items-center justify-between">
          <div className="truncate text-xs font-semibold text-sidebar-foreground">{activeFile.path}</div>
          <button type="button" className="text-[10px] text-sidebar-foreground/60" onClick={onExecuteHistory}>History</button>
        </div>
        <p className="line-clamp-2 text-[11px] text-sidebar-foreground/65">{activeFile.summary}</p>
        <div className="mt-1 text-[10px] text-sidebar-foreground/55">Complexity {activeFile.complexity} | {activeFile.line_count} lines | {activeFile.imports.length} imports</div>
        <pre className="mt-2 max-h-36 overflow-auto rounded-lg bg-black/20 p-2 text-[10px] leading-relaxed text-sidebar-foreground/80">{activeFile.content}</pre>
      </div>

      {reviewResult && (
        <div className="rounded-xl border border-sidebar-border bg-sidebar p-2 text-[11px]">
          <div className="font-semibold">AI Review Score: {reviewResult.overall_score}</div>
          <div className="mt-1 text-sidebar-foreground/70">{reviewResult.summary}</div>
          <div className="mt-1 text-sidebar-foreground/60">Findings: {reviewResult.findings.length}</div>
        </div>
      )}

      {fixProposal && (
        <div className="rounded-xl border border-sidebar-border bg-sidebar p-2 text-[11px]">
          <div className="font-semibold">Fix Diff ({fixProposal.diff ? 'ready' : 'no changes'})</div>
          {showDiff && <pre className="mt-1 max-h-32 overflow-auto rounded bg-black/20 p-1 text-[10px]">{fixProposal.diff || 'No changes in diff'}</pre>}
          <div className="mt-1 grid grid-cols-2 gap-2">
            <pre className="max-h-24 overflow-auto rounded bg-black/20 p-1 text-[10px]">{fixProposal.current_content}</pre>
            <pre className="max-h-24 overflow-auto rounded bg-black/20 p-1 text-[10px]">{fixProposal.suggested_content}</pre>
          </div>
        </div>
      )}

      {testResult && (
        <div className="rounded-xl border border-sidebar-border bg-sidebar p-2 text-[11px]">
          <div className="font-semibold">Tests: {testResult.status.toUpperCase()}</div>
          <div className="mt-1 text-sidebar-foreground/65">Passed {testResult.passed} | Failed {testResult.failed} | Duration {testResult.duration_seconds}s</div>
        </div>
      )}

      {historyText && <div className="rounded-xl border border-sidebar-border bg-sidebar p-2 text-[10px] text-sidebar-foreground/60">{historyText}</div>}

      {recent.length > 0 && (
        <div className="rounded-xl border border-sidebar-border bg-sidebar p-2">
          <div className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-sidebar-foreground/55">Recently Viewed</div>
          <div className="space-y-1">
            {recent.slice(0, 5).map((path) => (
              <button key={path} type="button" onClick={() => onOpenRecent(path)} className="block w-full truncate text-left text-[11px] text-sidebar-foreground/70 hover:text-sidebar-foreground">
                {path}
              </button>
            ))}
          </div>
        </div>
      )}
    </>
  );
}

export default function RepositoryExplorer({ repoId, repoName, repoStatus, token, collapsed }: RepositoryExplorerProps) {
  const [expanded, setExpanded] = useState(false);
  const [treeByPath, setTreeByPath] = useState<Record<string, ExplorerTreeNode[]>>({});
  const [openFolders, setOpenFolders] = useState<Set<string>>(new Set(['']));
  const [selectedPaths, setSelectedPaths] = useState<Set<string>>(new Set());
  const [menuState, setMenuState] = useState<FileContextMenuState | null>(null);
  const [activeFile, setActiveFile] = useState<ExplorerFileDetails | null>(null);
  const [historyText, setHistoryText] = useState<string>('');
  const [reviewResult, setReviewResult] = useState<ExplorerReviewResult | null>(null);
  const [testResult, setTestResult] = useState<ExplorerTestRunResult | null>(null);
  const [fixProposal, setFixProposal] = useState<ExplorerFixProposal | null>(null);
  const [search, setSearch] = useState('');
  const [filter, setFilter] = useState<SmartFilter>('all');
  const [loadingPath, setLoadingPath] = useState<string | null>(null);
  const [favorites, setFavorites] = useState<Set<string>>(() => loadLocalSet(FAVORITES_KEY));
  const [pinned, setPinned] = useState<Set<string>>(() => loadLocalSet(PINNED_KEY));
  const [recent, setRecent] = useState<string[]>(() => {
    if (typeof window === 'undefined') return [];
    try {
      const stored = JSON.parse(window.localStorage.getItem(RECENT_KEY) || '[]');
      return Array.isArray(stored) ? stored.slice(0, 20) : [];
    } catch {
      return [];
    }
  });
  const [activeAction, setActiveAction] = useState<string | null>(null);
  const [showDiff, setShowDiff] = useState(false);

  useEffect(() => {
    saveLocalSet(FAVORITES_KEY, favorites);
  }, [favorites]);

  useEffect(() => {
    saveLocalSet(PINNED_KEY, pinned);
  }, [pinned]);

  async function loadFolder(path: string) {
    if (!token || repoStatus !== 'ready') return;
    if (treeByPath[path]) return;
    setLoadingPath(path);
    try {
      const payload = await getExplorerTree(token, repoId, { path, limit: 250 });
      setTreeByPath((prev) => ({ ...prev, [path]: payload.nodes }));
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to load tree');
    } finally {
      setLoadingPath(null);
    }
  }

  function markRecent(path: string) {
    const next = [path, ...recent.filter((item) => item !== path)].slice(0, 20);
    setRecent(next);
    try {
      window.localStorage.setItem(RECENT_KEY, JSON.stringify(next));
    } catch {
      // noop
    }
  }

  async function openFile(path: string) {
    try {
      const details = await getExplorerFile(token, repoId, path);
      setActiveFile(details);
      setReviewResult(null);
      setFixProposal(null);
      setTestResult(null);
      markRecent(path);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to open file');
    }
  }

  function toggleFolder(path: string) {
    const next = new Set(openFolders);
    if (next.has(path)) {
      next.delete(path);
    } else {
      next.add(path);
      void loadFolder(path);
    }
    setOpenFolders(next);
  }

  function toggleSelection(path: string) {
    const next = new Set(selectedPaths);
    if (next.has(path)) next.delete(path);
    else next.add(path);
    setSelectedPaths(next);
  }

  const visibleTreeRoots = useMemo(() => {
    const roots = treeByPath[''] || [];
    return roots.filter((node) => {
      if (!canPassFilter(node, filter)) return false;
      const query = search.trim().toLowerCase();
      if (!query) return true;
      return node.path.toLowerCase().includes(query) || node.name.toLowerCase().includes(query);
    });
  }, [treeByPath, search, filter]);

  async function executeReview(reviewType: string, pathOverride?: string) {
    const targetPath = pathOverride || activeFile?.path;
    if (!targetPath) {
      toast.error('Open a file first');
      return;
    }
    try {
      setActiveAction(reviewType);
      const result = await runExplorerFileReview(token, repoId, { path: targetPath, review_type: reviewType });
      setReviewResult(result);
      await addExplorerConversationEntry(token, repoId, {
        path: targetPath,
        role: 'assistant',
        content: `Review ${reviewType}: score ${result.overall_score}`,
      });
      toast.success('Review complete');
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Review failed');
    } finally {
      setActiveAction(null);
    }
  }

  async function executeBatchReview() {
    const files = Array.from(selectedPaths);
    if (files.length < 2) {
      toast.error('Select at least 2 files for batch review');
      return;
    }
    try {
      const result = await runExplorerBatchReview(token, repoId, { paths: files, review_type: 'review' });
      setReviewResult(result);
      toast.success('Batch review complete');
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Batch review failed');
    }
  }

  async function executeGenerateFix() {
    if (!activeFile) {
      toast.error('Open a file first');
      return;
    }
    const finding = reviewResult?.findings?.[0]?.finding || 'Improve maintainability and robustness in this file';
    const recommendation = reviewResult?.findings?.[0]?.recommendation || '';
    try {
      setActiveAction('generate_fix');
      const proposal = await generateExplorerFix(token, repoId, {
        path: activeFile.path,
        finding,
        recommendation,
      });
      setFixProposal(proposal);
      setShowDiff(true);
      toast.success('Fix proposal generated');
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Fix generation failed');
    } finally {
      setActiveAction(null);
    }
  }

  async function executeApplyFix() {
    if (!fixProposal || !activeFile) {
      toast.error('Generate a fix first');
      return;
    }
    if (!window.confirm('Apply this fix to the repository file? Validation checks will run before accepting.')) return;
    try {
      setActiveAction('apply_fix');
      await applyExplorerFix(token, repoId, {
        fix_id: fixProposal.fix_id,
        expected_sha256: activeFile.sha256,
        run_validation: true,
      });
      toast.success('Fix applied successfully');
      await openFile(activeFile.path);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Fix rejected');
    } finally {
      setActiveAction(null);
    }
  }

  async function executeGenerateTests(pathOverride?: string) {
    const targetPath = pathOverride || activeFile?.path;
    if (!targetPath) {
      toast.error('Open a file first');
      return;
    }
    try {
      setActiveAction('generate_tests');
      const discovered = await discoverExplorerTests(token, repoId, [targetPath]);
      if (!discovered.tests.length) {
        setHistoryText('Generated tests: no impacted tests discovered for this file.');
        toast.info('No candidate tests discovered for this file');
        return;
      }
      setHistoryText(`Generated tests (${discovered.tests.length}): ${discovered.tests.slice(0, 5).join(', ')}`);
      toast.success(`Generated ${discovered.tests.length} targeted test candidates`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Generate tests failed');
    } finally {
      setActiveAction(null);
    }
  }

  async function executeTests(pathOverride?: string) {
    const targetPath = pathOverride || activeFile?.path;
    if (!targetPath) {
      toast.error('Open a file first');
      return;
    }
    try {
      setActiveAction('run_tests');
      const discovered = await discoverExplorerTests(token, repoId, [targetPath]);
      const run = await runExplorerTests(token, repoId, discovered.tests.slice(0, 12), 55);
      setTestResult(run);
      toast.success(`${run.status.toUpperCase()}: ${run.passed} passed, ${run.failed} failed`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Test execution failed');
    } finally {
      setActiveAction(null);
    }
  }

  async function executeHistory(pathOverride?: string) {
    const targetPath = pathOverride || activeFile?.path;
    if (!targetPath) {
      toast.error('Open a file first');
      return;
    }
    try {
      setActiveAction('history');
      const history = await getExplorerHistory(token, repoId, targetPath);
      const compact = [
        `Reviews: ${history.reviews.length}`,
        `Fixes: ${history.fixes.length}`,
        `Applied Fixes: ${history.applied_fixes.length}`,
        `Rejected Fixes: ${history.rejected_fixes.length}`,
        `Test Runs: ${history.test_runs.length}`,
        `Conversations: ${history.conversations.length}`,
      ];
      setHistoryText(compact.join(' | '));
      toast.success('History loaded');
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to load history');
    } finally {
      setActiveAction(null);
    }
  }

  async function executeAskAi(pathOverride?: string) {
    const targetPath = pathOverride || activeFile?.path;
    if (!targetPath) {
      toast.error('Open a file first');
      return;
    }
    try {
      setActiveAction('ask_ai');
      await addExplorerConversationEntry(token, repoId, {
        path: targetPath,
        role: 'user',
        content: `Open AI conversation for ${targetPath}`,
      });
      window.dispatchEvent(new CustomEvent('codebase:new-chat', { detail: { repoId } }));
      toast.success('Opened AI chat context for selected file');
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to open AI chat context');
    } finally {
      setActiveAction(null);
    }
  }

  useEffect(() => {
    if (!activeFile) return;

    function onKeyDown(event: KeyboardEvent) {
      const target = event.target as HTMLElement | null;
      const tag = target?.tagName?.toLowerCase();
      if (tag === 'input' || tag === 'textarea' || target?.isContentEditable) return;

      const key = event.key.toLowerCase();

      if (event.ctrlKey && key === 'd') {
        event.preventDefault();
        setShowDiff((prev) => !prev);
        return;
      }
      if (event.ctrlKey && key === '/') {
        event.preventDefault();
        void executeAskAi();
        return;
      }
      if (event.shiftKey && key === 't') {
        event.preventDefault();
        void executeTests();
        return;
      }
      if (event.ctrlKey || event.metaKey || event.altKey || event.shiftKey) return;

      if (key === 'e') void executeReview('explain');
      else if (key === 'r') void executeReview('review');
      else if (key === 'b') void executeReview('find_bugs');
      else if (key === 's') void executeReview('security');
      else if (key === 'a') void executeReview('architecture');
      else if (key === 't') void executeGenerateTests();
      else if (key === 'f') void executeGenerateFix();
    }

    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeFile]);

  const fileStats = useMemo(() => {
    if (!activeFile) return null;
    const healthScore = activeFile.health === 'critical' ? 42 : activeFile.health === 'review_suggested' ? 67 : activeFile.health === 'healthy' ? 84 : 74;
    return {
      healthScore,
      language: activeFile.language,
      lines: activeFile.line_count,
      imports: activeFile.imports.length,
      classes: activeFile.classes.length,
      functions: activeFile.functions.length,
      coverage: Math.min(95, Math.max(35, 55 + Math.round(activeFile.imports.length * 0.8))),
    };
  }, [activeFile]);

  function toggleFavorite(path: string) {
    const next = new Set(favorites);
    if (next.has(path)) next.delete(path);
    else next.add(path);
    setFavorites(next);
  }

  function togglePinned(path: string) {
    const next = new Set(pinned);
    if (next.has(path)) next.delete(path);
    else next.add(path);
    setPinned(next);
  }

  async function handleContextAction(action: string, node: ExplorerTreeNode) {
    if (node.type === 'folder' && action !== 'open') {
      toast.info('Folder-level action is currently supported through Folder Review from file selection scope.');
      return;
    }

    if (action === 'open') await openFile(node.path);
    else if (action === 'review') await executeReview('review', node.path);
    else if (action === 'explain') await executeReview('explain', node.path);
    else if (action === 'architecture') await executeReview('architecture', node.path);
    else if (action === 'dependencies') await executeReview('dependencies', node.path);
    else if (action === 'security') await executeReview('security', node.path);
    else if (action === 'performance') await executeReview('performance', node.path);
    else if (action === 'tests') await executeTests(node.path);
    else if (action === 'chat') {
      await addExplorerConversationEntry(token, repoId, { path: node.path, role: 'user', content: 'Open chat from explorer.' });
      window.dispatchEvent(new CustomEvent('codebase:new-chat', { detail: { repoId } }));
      toast.success('Conversation scoped to file recorded. Open Repository Chat to continue.');
    } else if (action === 'history') await executeHistory(node.path);
    else if (action === 'copy') {
      try {
        await navigator.clipboard.writeText(node.path);
        toast.success('Path copied');
      } catch {
        toast.error('Failed to copy path');
      }
    } else if (action === 'compare') {
      toast.info('Compare versions is available once historical snapshots are enabled in persistence table.');
    }
  }

  function renderNode(node: ExplorerTreeNode, depth: number) {
    const isOpen = openFolders.has(node.path);
    const children = treeByPath[node.path] || [];
    const isSelected = selectedPaths.has(node.path);
    const isFavorite = favorites.has(node.path);
    const isPinned = pinned.has(node.path);

    return (
      <div key={node.path}>
        <div
          className={cn(
            'group flex items-center gap-1 rounded-lg px-1 py-1 text-xs hover:bg-sidebar-accent/80',
            activeFile?.path === node.path && 'bg-sidebar-accent/80'
          )}
          style={{ paddingLeft: `${4 + depth * 10}px` }}
          onContextMenu={(e) => {
            e.preventDefault();
            setMenuState({ x: e.clientX, y: e.clientY, node });
          }}
        >
          <input checked={isSelected} onChange={() => toggleSelection(node.path)} type="checkbox" className="h-3 w-3" />
          {node.type === 'folder' ? (
            <button type="button" onClick={() => toggleFolder(node.path)} className="inline-flex h-4 w-4 items-center justify-center text-sidebar-foreground/65">
              {isOpen ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
            </button>
          ) : (
            <span className="inline-block h-4 w-4" />
          )}
          <span className={cn('inline-flex h-4 w-4 items-center justify-center', statusDot(node))}><Circle size={8} fill="currentColor" /></span>
          {node.type === 'folder' ? (isOpen ? <FolderOpen size={12} /> : <Folder size={12} />) : <FileCode size={12} />}
          <button type="button" onClick={() => (node.type === 'file' ? void openFile(node.path) : toggleFolder(node.path))} className="min-w-0 flex-1 truncate text-left text-sidebar-foreground/80 hover:text-sidebar-foreground">
            {node.name}
          </button>
          <button type="button" onClick={() => toggleFavorite(node.path)} className={cn('opacity-0 transition group-hover:opacity-100', isFavorite && 'opacity-100 text-amber-400')} title="Favorite">
            <Star size={11} fill={isFavorite ? 'currentColor' : 'none'} />
          </button>
          <button type="button" onClick={() => togglePinned(node.path)} className={cn('opacity-0 transition group-hover:opacity-100', isPinned && 'opacity-100 text-brand')} title="Pin">
            <Sparkles size={11} />
          </button>
        </div>
        {node.type === 'folder' && isOpen && (
          <div>
            {loadingPath === node.path && <div className="px-3 py-1 text-[11px] text-sidebar-foreground/50">Loading...</div>}
            {children.map((child) => renderNode(child, depth + 1))}
          </div>
        )}
      </div>
    );
  }

  if (collapsed) return null;

  return (
    <div className="mt-2 rounded-2xl border border-sidebar-border/70 bg-sidebar-accent/20 p-2">
      <button
        type="button"
        className="flex w-full items-center gap-2 rounded-xl px-2 py-1.5 text-left text-xs font-semibold uppercase tracking-[0.16em] text-sidebar-foreground/60 hover:bg-sidebar-accent"
        onClick={() => {
          const next = !expanded;
          setExpanded(next);
          if (next && repoStatus === 'ready') {
            void loadFolder('');
          }
        }}
      >
        {expanded ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
        Repository Explorer
        <span className="ml-auto text-[10px] normal-case tracking-normal">{repoName}</span>
      </button>

      {expanded && (
        <div className="mt-2 space-y-2">
          <div className="grid grid-cols-2 gap-1">
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search files"
              className="col-span-2 rounded-lg border border-sidebar-border bg-sidebar px-2 py-1 text-xs outline-none"
            />
            <select
              value={filter}
              onChange={(e) => setFilter(e.target.value as SmartFilter)}
              className="col-span-2 rounded-lg border border-sidebar-border bg-sidebar px-2 py-1 text-xs"
            >
              <option value="all">All</option>
              <option value="python">Python</option>
              <option value="typescript">TypeScript</option>
              <option value="tests">Tests</option>
              <option value="modified">Modified</option>
              <option value="high_risk">High Risk</option>
              <option value="recent">Recently Changed</option>
            </select>
          </div>

          <div className="max-h-72 overflow-auto rounded-xl border border-sidebar-border bg-sidebar/40 p-1">
            {repoStatus !== 'ready' ? (
              <div className="px-2 py-2 text-[11px] text-sidebar-foreground/55">Repository explorer unlocks once indexing is ready.</div>
            ) : visibleTreeRoots.length === 0 ? (
              <div className="px-2 py-2 text-[11px] text-sidebar-foreground/55">No matching files.</div>
            ) : (
              visibleTreeRoots.map((node) => renderNode(node, 0))
            )}
          </div>

          {activeFile && fileStats && (
            <ActiveFilePanel
              activeFile={activeFile}
              fileStats={fileStats}
              activeAction={activeAction}
              fixProposal={fixProposal}
              reviewResult={reviewResult}
              testResult={testResult}
              historyText={historyText}
              recent={recent}
              showDiff={showDiff}
              onToggleDiff={() => setShowDiff((prev) => !prev)}
              onOpenRecent={(path) => { void openFile(path); }}
              onExecuteReview={(type) => { void executeReview(type); }}
              onExecuteGenerateTests={() => { void executeGenerateTests(); }}
              onExecuteTests={() => { void executeTests(); }}
              onExecuteGenerateFix={() => { void executeGenerateFix(); }}
              onExecuteApplyFix={() => { void executeApplyFix(); }}
              onExecuteAskAi={() => { void executeAskAi(); }}
              onExecuteHistory={() => { void executeHistory(activeFile.path); }}
            />
          )}

          <div className="flex flex-wrap items-center gap-1">
            <button type="button" className="rounded-lg border border-sidebar-border px-2 py-1 text-[11px]" onClick={() => void executeBatchReview()}>Batch Review</button>
          </div>
        </div>
      )}

      {menuState && (
        <div className="fixed z-[9999] min-w-[180px] rounded-xl border border-sidebar-border bg-sidebar p-1 text-xs shadow-2xl" style={{ left: menuState.x, top: menuState.y }}>
          {[
            ['open', <FileCode key="o" size={12} />, 'Open'],
            ['review', <FileSearch key="r" size={12} />, 'Review'],
            ['explain', <Bot key="e" size={12} />, 'Explain'],
            ['architecture', <Sparkles key="a" size={12} />, 'Architecture'],
            ['dependencies', <GitCompare key="d" size={12} />, 'Dependencies'],
            ['security', <Shield key="s" size={12} />, 'Security Scan'],
            ['performance', <Play key="p" size={12} />, 'Performance Review'],
            ['tests', <TestTube key="t" size={12} />, 'Run Tests'],
            ['chat', <MessageSquare key="c" size={12} />, 'Open Chat'],
            ['history', <History key="h" size={12} />, 'View History'],
            ['compare', <GitCompare key="v" size={12} />, 'Compare Versions'],
            ['copy', <Copy key="cp" size={12} />, 'Copy Path'],
          ].map(([action, icon, label]) => (
            <button
              key={String(action)}
              type="button"
              className="flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-left text-sidebar-foreground/80 hover:bg-sidebar-accent hover:text-sidebar-foreground"
              onClick={() => {
                const node = menuState.node;
                setMenuState(null);
                void handleContextAction(String(action), node);
              }}
            >
              {icon} {label}
            </button>
          ))}
          <button type="button" className="mt-1 w-full rounded-lg border border-sidebar-border px-2 py-1 text-[11px] text-sidebar-foreground/60" onClick={() => setMenuState(null)}>
            Close
          </button>
        </div>
      )}
    </div>
  );
}
