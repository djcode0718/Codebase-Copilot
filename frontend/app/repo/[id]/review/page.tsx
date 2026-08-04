'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { useParams } from 'next/navigation';
import { motion } from 'framer-motion';
import { Bot, FileCode2, GitCommitHorizontal, GitPullRequest, Sparkles, Trash2, Wrench } from 'lucide-react';
import { createClient } from '@/lib/supabase/client';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import {
  deleteReview,
  generateReviewFix,
  getReview,
  listReviews,
  reviewCommit,
  reviewFile,
  reviewFiles,
  reviewPullRequest,
} from '@/lib/api';
import type { ReviewFixResponse, ReviewHistoryItem, ReviewRun } from '@/lib/types';
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

export default function RepositoryReviewPage() {
  const { id: repoId } = useParams<{ id: string }>();
  const [token, setToken] = useState('');
  const [history, setHistory] = useState<ReviewHistoryItem[]>([]);
  const [selectedReview, setSelectedReview] = useState<ReviewRun | null>(null);
  const [loading, setLoading] = useState(false);
  const [filePath, setFilePath] = useState('api/services/chat_service.py');
  const [filesCsv, setFilesCsv] = useState('');
  const [commitHash, setCommitHash] = useState('');
  const [prFilesCsv, setPrFilesCsv] = useState('');
  const [prDiff, setPrDiff] = useState('');
  const [prompt, setPrompt] = useState('');
  const [fixOutput, setFixOutput] = useState<ReviewFixResponse | null>(null);

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
        <p className="mt-2 text-sm text-muted-foreground">Review files, commits, and PR diffs with persisted findings and optional fix generation.</p>
      </motion.section>

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
                files: filesCsv.split(',').map((s) => s.trim()).filter(Boolean),
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
                changed_files: prFilesCsv.split(',').map((s) => s.trim()).filter(Boolean),
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
            <div className="mb-3 text-sm font-medium">Review history</div>
            <div className="space-y-2 max-h-[18rem] overflow-auto">
              {history.length === 0 && <p className="text-sm text-muted-foreground">No reviews yet.</p>}
              {history.map((item) => (
                <button
                  key={item.review_id}
                  className="w-full text-left rounded-xl border border-border bg-background/70 p-3 hover:border-brand/30"
                  onClick={async () => {
                    if (!token) return;
                    const row = await getReview(token, item.review_id);
                    setSelectedReview(row);
                    setFixOutput(null);
                  }}
                >
                  <div className="text-xs text-muted-foreground">{item.target_type.toUpperCase()} • {item.created_at ? new Date(item.created_at).toLocaleString() : 'n/a'}</div>
                  <div className="mt-1 text-sm font-medium truncate">{item.summary}</div>
                </button>
              ))}
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
                    await deleteReview(token, selectedReview.review_id);
                    setSelectedReview(null);
                    setFixOutput(null);
                    await loadHistory(token);
                  }}
                >
                  <Trash2 size={13} className="mr-1" /> Delete
                </Button>
              </div>

              <div className="space-y-2 max-h-[18rem] overflow-auto">
                {findings.map((f) => (
                  <div key={f.id} className="rounded-xl border border-border bg-background/70 p-3 space-y-2">
                    <div className="flex items-center justify-between gap-2">
                      <div className="text-sm font-medium">{f.finding}</div>
                      <SeverityPill severity={f.severity} />
                    </div>
                    <div className="text-xs text-muted-foreground">{f.file} • {f.code_area} • risk: {f.risk_level}</div>
                    <p className="text-sm">{f.recommendation}</p>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={async () => {
                        if (!token) return;
                        const fix = await generateReviewFix(token, { review_id: selectedReview.review_id, finding_id: f.id });
                        setFixOutput(fix);
                      }}
                    >
                      <Wrench size={13} className="mr-1" /> Generate fix
                    </Button>
                  </div>
                ))}
              </div>

              {fixOutput && (
                <div className="rounded-xl border border-border bg-background/70 p-3">
                  <div className="mb-1 text-xs text-muted-foreground">Suggested fix for {fixOutput.target_file ?? 'selected target'}</div>
                  <pre className="whitespace-pre-wrap text-sm">{fixOutput.suggested_fix}</pre>
                </div>
              )}
            </div>
          )}
        </div>
      </section>
    </div>
  );
}

