'use client';
/**
 * hooks/useIndexingStream.ts
 * SSE hook for the indexing pipeline.
 * Opens a fetch stream to GET /api/repo/{repoId}/index-progress
 * and maintains ordered PipelineStep state.
 */
import { useEffect, useState, useRef, useCallback } from 'react';
import type { IndexingEvent, IndexingStepName, PipelineStep, StepStatus } from '@/lib/types';

// Maps SSE step → human-readable label + description
const STEP_META: Record<IndexingStepName, { label: string; description: string }> = {
  cloning:   { label: 'Clone repository',     description: 'Cloning from GitHub into local storage' },
  filtering: { label: 'Filter files',          description: 'Identifying valid source code files' },
  parsing:   { label: 'Parse documents',       description: 'Loading and tokenising code files' },
  embedding: { label: 'Build embeddings',      description: 'Embedding chunks into ChromaDB via Ollama' },
  summary:   { label: 'Finalise index',        description: 'Completing architectural context and BM25 index' },
  done:      { label: 'Done',                  description: 'Indexing complete — ready to chat' },
  error:     { label: 'Error',                 description: 'An error occurred during indexing' },
};

// Ordered pipeline steps (error not in order — it interrupts)
const PIPELINE_ORDER: IndexingStepName[] = [
  'cloning', 'filtering', 'parsing', 'embedding', 'summary', 'done',
];

function makeStep(id: IndexingStepName, status: StepStatus = 'pending'): PipelineStep {
  return { id, status, ...STEP_META[id] };
}

interface UseIndexingStreamResult {
  steps: PipelineStep[];
  progress: number;
  fileCount: number | null;
  nodeCount: number | null;
  elapsedMs: number;
  isComplete: boolean;
  hasError: boolean;
  errorMessage: string | null;
  indexName: string | null;
}

export function useIndexingStream(
  repoId: string,
  token: string,
  enabled: boolean = true
): UseIndexingStreamResult {
  const [steps, setSteps] = useState<PipelineStep[]>(
    PIPELINE_ORDER.map((id) => makeStep(id, 'pending'))
  );
  const [progress, setProgress] = useState(0);
  const [fileCount, setFileCount] = useState<number | null>(null);
  const [nodeCount, setNodeCount] = useState<number | null>(null);
  const [isComplete, setIsComplete] = useState(false);
  const [hasError, setHasError] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [indexName, setIndexName] = useState<string | null>(null);
  const [elapsedMs, setElapsedMs] = useState(0);

  const startTimeRef = useRef<number>(Date.now());
  const stepStartRef = useRef<Partial<Record<IndexingStepName, number>>>({});
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL ?? 'http://localhost:8000';

  // Elapsed timer
  useEffect(() => {
    if (!enabled || isComplete || hasError) return;
    timerRef.current = setInterval(() => {
      setElapsedMs(Date.now() - startTimeRef.current);
    }, 100);
    return () => { if (timerRef.current) clearInterval(timerRef.current); };
  }, [enabled, isComplete, hasError]);

  const updateStep = useCallback((
    stepId: IndexingStepName,
    update: Partial<PipelineStep>
  ) => {
    setSteps((prev) =>
      prev.map((s) => (s.id === stepId ? { ...s, ...update } : s))
    );
  }, []);

  useEffect(() => {
    if (!enabled || !repoId || !token) return;

    let aborted = false;
    startTimeRef.current = Date.now();

    async function readStream() {
      try {
        const res = await fetch(
          `${apiBase}/api/repo/${repoId}/index-progress`,
          {
            headers: { Authorization: `Bearer ${token}` },
            signal: AbortSignal.timeout(200_000), // 200s max
          }
        );

        if (!res.ok || !res.body) {
          setHasError(true);
          setErrorMessage('Failed to connect to indexing stream');
          return;
        }

        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
          if (aborted) break;
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n');
          buffer = lines.pop() ?? '';

          for (const line of lines) {
            const trimmed = line.trim();
            if (!trimmed.startsWith('data: ')) continue;

            let event: IndexingEvent;
            try {
              event = JSON.parse(trimmed.slice(6));
            } catch {
              continue;
            }

            const { step, message, progress: prog } = event;
            setProgress(prog);

            if (step === 'error') {
              // Mark active step (or first pending) as error
              setSteps((prev) => {
                const activeIdx = prev.findIndex(
                  (s) => s.status === 'active'
                );
                const targetIdx = activeIdx >= 0
                  ? activeIdx
                  : prev.findIndex((s) => s.status === 'pending');
                return prev.map((s, i) => {
                  if (i === targetIdx) return { ...s, status: 'error', message };
                  if (i > targetIdx) return { ...s, status: 'pending' };
                  return s;
                });
              });
              setHasError(true);
              setErrorMessage(message);
              if (timerRef.current) clearInterval(timerRef.current);
              return;
            }

            if (step === 'done') {
              const elapsed = Date.now() - (stepStartRef.current['summary'] ?? Date.now());
              updateStep('summary', { status: 'done', elapsedMs: elapsed });
              updateStep('done', { status: 'done', message });
              setFileCount(event.file_count ?? null);
              setNodeCount(event.node_count ?? null);
              setIndexName(event.index_name ?? null);
              setIsComplete(true);
              if (timerRef.current) clearInterval(timerRef.current);
              return;
            }

            // Regular step
            const stepId = step as IndexingStepName;
            const now = Date.now();

            // Close previous active step
            setSteps((prev) => {
              const prevActive = prev.find((s) => s.status === 'active');
              if (prevActive && prevActive.id !== stepId) {
                const elapsed = now - (stepStartRef.current[prevActive.id] ?? now);
                return prev.map((s) =>
                  s.id === prevActive.id
                    ? { ...s, status: 'done', elapsedMs: elapsed }
                    : s.id === stepId
                    ? { ...s, status: 'active', message }
                    : s
                );
              }
              return prev.map((s) =>
                s.id === stepId ? { ...s, status: 'active', message } : s
              );
            });
            stepStartRef.current[stepId] = now;
          }
        }
      } catch (err) {
        if (!aborted) {
          setHasError(true);
          setErrorMessage(err instanceof Error ? err.message : 'Stream error');
          if (timerRef.current) clearInterval(timerRef.current);
        }
      }
    }

    readStream();
    return () => { aborted = true; };
  }, [repoId, token, enabled, apiBase, updateStep]);

  return {
    steps,
    progress,
    fileCount,
    nodeCount,
    elapsedMs,
    isComplete,
    hasError,
    errorMessage,
    indexName,
  };
}
