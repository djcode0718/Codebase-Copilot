'use client';
/**
 * hooks/useIndexingStream.ts
 * SSE hook for the indexing pipeline.
 * Opens a fetch stream to GET /api/repo/{repoId}/index-progress
 * and maintains ordered PipelineStep state.
 */
import { useEffect, useState, useRef, useCallback, type Dispatch, type SetStateAction, type MutableRefObject } from 'react';
import { getApiBaseUrl } from '@/lib/api';
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

interface IndexingStateSetters {
  setSteps: Dispatch<SetStateAction<PipelineStep[]>>;
  setProgress: Dispatch<SetStateAction<number>>;
  setFileCount: Dispatch<SetStateAction<number | null>>;
  setNodeCount: Dispatch<SetStateAction<number | null>>;
  setIsComplete: Dispatch<SetStateAction<boolean>>;
  setHasError: Dispatch<SetStateAction<boolean>>;
  setErrorMessage: Dispatch<SetStateAction<string | null>>;
  setIndexName: Dispatch<SetStateAction<string | null>>;
  setElapsedMs: Dispatch<SetStateAction<number>>;
}

function resetIndexingRunState(setters: IndexingStateSetters): void {
  setters.setSteps(PIPELINE_ORDER.map((id) => makeStep(id, 'pending')));
  setters.setProgress(0);
  setters.setFileCount(null);
  setters.setNodeCount(null);
  setters.setIsComplete(false);
  setters.setHasError(false);
  setters.setErrorMessage(null);
  setters.setIndexName(null);
  setters.setElapsedMs(0);
}

function stopTimer(timerRef: MutableRefObject<ReturnType<typeof setInterval> | null>) {
  if (timerRef.current) {
    clearInterval(timerRef.current);
    timerRef.current = null;
  }
}

async function connectToStreamWithRetry(
  url: string,
  token: string,
  isAborted: () => boolean,
  onConnectionError: (message: string) => void,
): Promise<Response | null> {
  const MAX_RETRIES = 4;
  const RETRY_DELAY_MS = 1500;

  for (let attempt = 0; attempt <= MAX_RETRIES; attempt++) {
    if (isAborted()) return null;
    try {
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 200_000);
      try {
        return await fetch(url, {
          headers: { Authorization: `Bearer ${token}` },
          signal: controller.signal,
        });
      } finally {
        clearTimeout(timeout);
      }
    } catch (fetchErr) {
      if (attempt < MAX_RETRIES && !isAborted()) {
        await new Promise((resolve) => setTimeout(resolve, RETRY_DELAY_MS));
        continue;
      }
      if (!isAborted()) {
        const message = fetchErr instanceof Error ? fetchErr.message : '';
        onConnectionError(message || 'Failed to connect to indexing stream');
      }
      return null;
    }
  }

  return null;
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

  const startTimeRef = useRef<number>(0);
  const stepStartRef = useRef<Partial<Record<IndexingStepName, number>>>({});
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const apiBase = getApiBaseUrl();

  const updateStep = useCallback((
    stepId: IndexingStepName,
    update: Partial<PipelineStep>
  ) => {
    setSteps((prev) =>
      prev.map((s) => (s.id === stepId ? { ...s, ...update } : s))
    );
  }, []);

  const handleIndexingEvent = useCallback((
    event: IndexingEvent,
    handlers: {
      onError: (message: string) => void;
      onDone: (event: IndexingEvent) => void;
      onStep: (stepId: IndexingStepName, message: string) => void;
    },
  ) => {
    const { step, message, progress: prog } = event;
    setProgress(typeof prog === 'number' ? prog : step === 'error' ? 100 : 0);

    if (step === 'error') {
      setSteps((prev) => {
        const activeIdx = prev.findIndex((s) => s.status === 'active');
        const targetIdx = activeIdx >= 0 ? activeIdx : prev.findIndex((s) => s.status === 'pending');
        return prev.map((s, i) => {
          if (i === targetIdx) return { ...s, status: 'error', message };
          if (i > targetIdx) return { ...s, status: 'pending' };
          return s;
        });
      });
      handlers.onError(message);
      return 'stop' as const;
    }

    if (step === 'done') {
      const elapsed = Date.now() - (stepStartRef.current['summary'] ?? Date.now());
      updateStep('summary', { status: 'done', elapsedMs: elapsed });
      updateStep('done', { status: 'done', message });
      handlers.onDone(event);
      return 'stop' as const;
    }

    // Regular step transition
    const stepId = step as IndexingStepName;
    const now = Date.now();
    setSteps((prev) => {
      const prevActive = prev.find((s) => s.status === 'active');
      if (prevActive && prevActive.id !== stepId) {
        const elapsed = now - (stepStartRef.current[prevActive.id] ?? now);
        return prev.map((s) =>
          s.id === prevActive.id ? { ...s, status: 'done', elapsedMs: elapsed }
            : s.id === stepId ? { ...s, status: 'active', message }
            : s
        );
      }
      return prev.map((s) => s.id === stepId ? { ...s, status: 'active', message } : s);
    });
    stepStartRef.current[stepId] = now;
    return 'continue' as const;
  }, [updateStep]);

  useEffect(() => {
    if (!enabled || !repoId || !token) return;

    let aborted = false;
    startTimeRef.current = Date.now();

    if (timerRef.current) {
      clearInterval(timerRef.current);
    }
    timerRef.current = setInterval(() => {
      if (startTimeRef.current) {
        setElapsedMs(Date.now() - startTimeRef.current);
      }
    }, 100);

    async function readStream() {
      resetIndexingRunState({
        setSteps,
        setProgress,
        setFileCount,
        setNodeCount,
        setIsComplete,
        setHasError,
        setErrorMessage,
        setIndexName,
        setElapsedMs,
      });

      const res = await connectToStreamWithRetry(
        `${apiBase}/api/repo/${repoId}/index-progress`,
        token,
        () => aborted,
        (message) => {
          setHasError(true);
          setErrorMessage(message);
          stopTimer(timerRef);
        }
      );

      if (!res) return;

      try {
        if (!res.ok || !res.body) {
          setHasError(true);
          setErrorMessage(
            `Indexing server error: ${res.status} ${res.statusText || 'check backend logs'}`
          );
          stopTimer(timerRef);
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

            const action = handleIndexingEvent(event, {
              onError: (msg) => {
                setHasError(true);
                setErrorMessage(msg);
                stopTimer(timerRef);
              },
              onDone: (ev) => {
                setFileCount(ev.file_count ?? null);
                setNodeCount(ev.node_count ?? null);
                setIndexName(ev.index_name ?? null);
                setIsComplete(true);
                stopTimer(timerRef);
              },
              onStep: () => {},
            });
            if (action === 'stop') return;
          }
        }
      } catch (err) {
        if (!aborted) {
          setHasError(true);
          setErrorMessage(err instanceof Error ? err.message : 'Stream error');
          stopTimer(timerRef);
        }
      }
    }

    readStream();
    return () => {
      aborted = true;
      stopTimer(timerRef);
    };
  }, [repoId, token, enabled, apiBase, updateStep, handleIndexingEvent]);

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
